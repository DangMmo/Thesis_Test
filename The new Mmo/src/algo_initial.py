# algo_initial.py
import random
from model_solution import VRP2E_State, Solution, SERoute, FERoute
from model_problem import ProblemInstance
from logic_core import (
    InsertionProcessor, 
    find_best_global_insertion_option, 
    _recalculate_fe_route_and_check_feasibility
)
from algo_alns import run_local_search_phase
from ops_destroy import random_removal
from ops_repair import greedy_repair

def create_integrated_initial_solution(problem: ProblemInstance, random_customers: bool = True) -> VRP2E_State:
    """
    Tạo lời giải ban đầu bằng cách chèn tham lam tuần tự.
    """
    solution = Solution(problem)
    insertion_processor = InsertionProcessor(problem)
    customers_to_serve = list(problem.customers)
    if random_customers:
        random.shuffle(customers_to_serve)
    
    solution.unserved_customers = []

    print("--- Phase 1a: Greedy Insertion Construction ---")
    for i, customer in enumerate(customers_to_serve):
        print(f"  -> Processing customer {i+1}/{len(customers_to_serve)} (ID: {customer.id})...", end='\r')
        
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        option_type = best_option.get('type')

        if option_type == 'insert_into_existing_se':
            se_route, pos = best_option['se_route'], best_option['se_pos']
            fe_route = list(se_route.serving_fe_routes)[0]
            se_route.insert_customer_at_pos(customer, pos)
            solution.update_customer_map()
            _recalculate_fe_route_and_check_feasibility(fe_route, problem)
        elif option_type == 'create_new_se_new_fe':
            satellite = best_option['new_satellite']
            new_se = SERoute(satellite, solution.problem)
            new_se.insert_customer_at_pos(customer, 1)
            solution.add_se_route(new_se)
            new_fe = FERoute(solution.problem)
            solution.add_fe_route(new_fe)
            solution.link_routes(new_fe, new_se)
            _recalculate_fe_route_and_check_feasibility(new_fe, problem)
        elif option_type == 'create_new_se_expand_fe':
            satellite, fe_route = best_option['new_satellite'], best_option['fe_route']
            new_se = SERoute(satellite, solution.problem)
            new_se.insert_customer_at_pos(customer, 1)
            solution.add_se_route(new_se)
            solution.link_routes(fe_route, new_se)
            _recalculate_fe_route_and_check_feasibility(fe_route, problem)
        else: 
            solution.unserved_customers.append(customer)
            print(f"\nWarning: Could not serve customer {customer.id}")

    print("\n\n>>> Greedy construction complete!")
    return VRP2E_State(solution)

def generate_initial_solution(problem: ProblemInstance, lns_iterations: int, q_percentage: float) -> VRP2E_State:
    # Bước 1: Tạo lời giải rất cơ bản bằng chèn tham lam
    initial_state = create_integrated_initial_solution(problem)
    initial_cost = initial_state.cost
    print(f"--- Phase 1a Complete. Pre-LNS Cost: {initial_cost:.2f} ---")

    # Bước 2: Tinh chỉnh lời giải bằng một pha LNS hạn chế
    if lns_iterations > 0:
        print("\n--- Phase 1b: Local Search Refinement (Restrictive LNS) ---")
        final_state = run_local_search_phase(
            initial_state=initial_state,
            iterations=lns_iterations,
            q_percentage=q_percentage,
            destroy_op=random_removal,
            repair_op=greedy_repair
        )
    else:
        final_state = initial_state
        
    return final_state