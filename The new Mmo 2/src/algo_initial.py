# algo_initial.py
import random
from model_solution import VRP2E_State, SolutionData
from model_problem import ProblemInstance
from logic_core import find_best_insertion_for_customer
from ops_repair import _apply_insertion # Import hàm áp dụng chèn
from algo_alns import run_alns_phase # Import ALNS để tinh chỉnh
from ops_destroy import random_removal
from ops_repair import greedy_repair

def create_empty_solution_data(problem: ProblemInstance) -> SolutionData:
    """ Tạo một đối tượng SolutionData rỗng. """
    return SolutionData(
        problem=problem,
        fe_routes=tuple(),
        se_routes=tuple(),
        unserved_customer_ids=tuple()
    )

def generate_initial_solution(problem: ProblemInstance, lns_iterations: int, q_percentage: float) -> VRP2E_State:
    """
    Tạo lời giải ban đầu hoàn toàn bằng logic DOP.
    """
    # Bước 1: Tạo lời giải rất cơ bản bằng chèn tham lam
    print("--- Phase 1a: Greedy Insertion Construction (DOP-style) ---")
    current_solution_data = create_empty_solution_data(problem)
    
    customers_to_serve = list(problem.customers)
    random.shuffle(customers_to_serve)
    
    for i, customer in enumerate(customers_to_serve):
        print(f"  -> Processing customer {i+1}/{len(customers_to_serve)} (ID: {customer.id})...", end='\r')
        
        best_option = find_best_insertion_for_customer(customer, current_solution_data)
        current_solution_data = _apply_insertion(current_solution_data, customer, best_option)

    print("\n\n>>> Greedy construction complete!")
    initial_state = VRP2E_State(current_solution_data)
    print(f"--- Phase 1a Complete. Pre-LNS Cost: {initial_state.cost:.2f} ---")

    # Bước 2: Tinh chỉnh lời giải bằng một pha ALNS hạn chế
    # Lưu ý: run_alns_phase bây giờ phải có khả năng xử lý state DOP
    if lns_iterations > 0:
        print("\n--- Phase 1b: Local Search Refinement (Restrictive LNS) ---")
        
        # Tạo một bộ toán tử đơn giản cho LNS
        lns_destroy_ops = {"random": random_removal}
        lns_repair_ops = {"greedy": greedy_repair}
        
        # Chạy một phiên bản ALNS ngắn với nhiệt độ gần như bằng 0
        final_state, _ = run_alns_phase(
            initial_state=initial_state,
            iterations=lns_iterations,
            destroy_operators=lns_destroy_ops,
            repair_operators=lns_repair_ops,
            is_lns_mode=True # Thêm cờ để tắt SA và các logic phức tạp khác
        )
    else:
        final_state = initial_state
        
    return final_state