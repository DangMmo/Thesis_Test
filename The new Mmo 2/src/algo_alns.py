# algo_alns.py
import math
import random
from typing import Callable, List, Tuple, Dict

import config
from model_solution import VRP2E_State, SolutionData
from model_problem import Customer

# Thay đổi chữ ký của các toán tử
DestroyOperatorFunc = Callable[[SolutionData, int], Tuple[SolutionData, Tuple[Customer, ...]]]
RepairOperatorFunc = Callable[[SolutionData, Tuple[Customer, ...]], SolutionData]

# =... (Class Operator và AdaptiveOperatorSelector giữ nguyên) ...
class Operator:
    def __init__(self, name: str, function: Callable):
        self.name = name
        self.function = function      
        self.weight = 1.0             
        self.score = 0.0              
        self.times_used = 0           

class AdaptiveOperatorSelector:
    def __init__(self, destroy_operators: Dict[str, Callable], repair_operators: Dict[str, Callable], reaction_factor: float = 0.1):
        self.destroy_ops = [Operator(name, func) for name, func in destroy_operators.items()]
        self.repair_ops = [Operator(name, func) for name, func in repair_operators.items()]
        self.reaction_factor = reaction_factor

    def _select_operator(self, operators: List[Operator]) -> Operator:
        total_weight = sum(op.weight for op in operators)
        pick = random.uniform(0, total_weight)
        current = 0
        for op in operators:
            current += op.weight
            if current > pick:
                op.times_used += 1
                return op
        return operators[-1]

    def select_destroy_operator(self) -> Operator:
        return self._select_operator(self.destroy_ops)

    def select_repair_operator(self) -> Operator:
        return self._select_operator(self.repair_ops)

    def update_scores(self, destroy_op: Operator, repair_op: Operator, sigma: float):
        destroy_op.score += sigma
        repair_op.score += sigma

    def update_weights(self):
        for op_list in [self.destroy_ops, self.repair_ops]:
            for op in op_list:
                if op.times_used > 0:
                    op.weight = (1 - self.reaction_factor) * op.weight + \
                                self.reaction_factor * (op.score / op.times_used)
                op.score = 0
                op.times_used = 0


def run_alns_phase(initial_state: VRP2E_State, iterations: int, 
                   destroy_operators: Dict[str, DestroyOperatorFunc], 
                   repair_operators: Dict[str, RepairOperatorFunc],
                   is_lns_mode: bool = False) -> Tuple[VRP2E_State, Tuple[Dict, Dict]]:
    
    current_state = initial_state
    best_state = initial_state.copy()
    operator_selector = AdaptiveOperatorSelector(destroy_operators, repair_operators, config.REACTION_FACTOR)
    
    # --- Temperature Calculation ---
    T = 0.0
    if not is_lns_mode:
        # (Logic tính nhiệt độ T_start cần được cập nhật để hoạt động với SolutionData nếu cần)
        # Tạm thời đặt một giá trị khởi tạo
        initial_primary_cost = current_state.cost # Giả sử cost ban đầu là primary
        if config.START_TEMP_ACCEPT_PROB > 0 and initial_primary_cost > 0:
            delta = config.START_TEMP_WORSENING_PCT * initial_primary_cost
            T = -delta / math.log(config.START_TEMP_ACCEPT_PROB)
    
    # ... (Khởi tạo history, operator_history giữ nguyên) ...
    history = { "iteration": [], "best_cost": [], "current_cost": [], "temperature": [] }
    operator_history = { "iteration": [], "destroy_weights": [], "repair_weights": [] }
    
    phase_name = "LNS" if is_lns_mode else "ALNS"
    print(f"\n--- Starting {phase_name} Phase (DOP-based) ---")
    print(f"  Iterations: {iterations}, Initial Temp: {T:.2f}, Initial Cost: {current_state.cost:.2f}")

    iterations_without_improvement = 0

    for i in range(1, iterations + 1):
        cost_before_change = current_state.cost

        destroy_op_obj = operator_selector.select_destroy_operator()
        repair_op_obj = operator_selector.select_repair_operator()
        
        num_cust = len(current_state.solution_data.customer_to_se_route_idx)
        if num_cust == 0: break

        q_percentage = config.Q_PERCENTAGE_INITIAL if is_lns_mode else random.uniform(*config.Q_SMALL_RANGE)
        q = max(1, int(num_cust * q_percentage))

        # --- LUỒNG DỮ LIỆU DOP ---
        # 1. Destroy: Trả về lời giải không hoàn chỉnh và danh sách khách hàng
        partial_solution_data, removed_customers = destroy_op_obj.function(current_state.solution_data, q)
        
        # 2. Repair: Nhận lời giải không hoàn chỉnh và chèn lại khách hàng
        new_solution_data = repair_op_obj.function(partial_solution_data, removed_customers)

        new_state = VRP2E_State(new_solution_data)
        cost_after_change = new_state.cost
        
        # --- LOGIC CHẤP NHẬN ---
        log_msg = ""; accepted = False

        if cost_after_change < cost_before_change:
            accepted = True
            operator_selector.update_scores(destroy_op_obj, repair_op_obj, config.SIGMA_2_BETTER)
            log_msg = f"(Accepted: {cost_after_change:.2f})"
            if cost_after_change < best_state.cost:
                operator_selector.update_scores(destroy_op_obj, repair_op_obj, config.SIGMA_1_NEW_BEST)
                log_msg = f"(NEW BEST: {cost_after_change:.2f})"
        elif not is_lns_mode and T > 1e-6 and random.random() < math.exp(-(cost_after_change - cost_before_change) / T):
            accepted = True
            operator_selector.update_scores(destroy_op_obj, repair_op_obj, config.SIGMA_3_ACCEPTED)
            log_msg = f"(SA Accepted: {cost_after_change:.2f})"

        if accepted:
            current_state = new_state
            if current_state.cost < best_state.cost:
                best_state = current_state
        
        if not accepted or cost_after_change >= best_state.cost:
            iterations_without_improvement += 1
        else:
            iterations_without_improvement = 0

        if not is_lns_mode and iterations_without_improvement >= config.RESTART_THRESHOLD:
            print(f"  >>> Restart triggered at iter {i}. Resetting to best known solution. <<<")
            current_state = best_state.copy()
            iterations_without_improvement = 0
        
        if not is_lns_mode:
            T *= config.COOLING_RATE
        
        # ... (Cập nhật weights và history giữ nguyên) ...
        if i % 100 == 0 or log_msg:
             print(f"  Iter {i:>5}/{iterations} | Best: {best_state.cost:<10.2f} | Current: {current_state.cost:<10.2f} | Ops: {destroy_op_obj.name}/{repair_op_obj.name} | {log_msg}")

    print(f"\n--- {phase_name} phase complete. Best cost found: {best_state.cost:.2f} ---")
    return best_state, (history, operator_history)