# algo_alns.py
import math
import random
from typing import Callable, List, Tuple, Dict

import config
from model_solution import VRP2E_State, Solution, ChangeContext
from model_problem import Customer

DestroyOperatorFunc = Callable[[Solution, ChangeContext, int], List[Customer]]
RepairOperatorFunc = Callable[[Solution, ChangeContext, List[Customer]], None]

# ==============================================================================
# ADAPTIVE MECHANISM CLASSES
# ==============================================================================

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

# ==============================================================================
# ALNS ALGORITHMS
# ==============================================================================

def run_local_search_phase(initial_state: VRP2E_State, iterations: int, q_percentage: float, 
                           destroy_op: Callable, repair_op: Callable) -> VRP2E_State:
    current_state = initial_state
    best_state = initial_state.copy()

    print("--- Starting Local Search Refinement ---")
    for i in range(iterations):
        context = ChangeContext(current_state.solution)
        cost_before = current_state.cost

        num_cust = len(current_state.solution.customer_to_se_route_map)
        if num_cust == 0:
            print("No customers to optimize. Stopping."); break
        
        q = max(2, int(num_cust * q_percentage))
        
        removed_customers = destroy_op(current_state.solution, context, q)
        repair_op(current_state.solution, context, removed_customers)

        cost_after = current_state.cost
        best_cost = best_state.cost
        log_str = f"  LNS Iter {i+1:>4}/{iterations} | Current: {cost_before:>10.2f}, New: {cost_after:>10.2f}, Best: {best_cost:>10.2f}"

        if cost_after < cost_before:
            log_str += " -> ACCEPTED"
            if cost_after < best_cost:
                best_state = current_state.copy()
                log_str += " (NEW BEST!)"
        else:
            context.rollback()
            assert abs(current_state.cost - cost_before) < 1e-9

        print(log_str)
        
    print(f"--- Local Search complete. Best cost found: {best_state.cost:.2f} ---")
    return best_state


def run_alns_phase(initial_state: VRP2E_State, iterations: int, 
                   destroy_operators: Dict[str, DestroyOperatorFunc], 
                   repair_operators: Dict[str, RepairOperatorFunc]) -> Tuple[VRP2E_State, Tuple[Dict, Dict]]:
    current_state = initial_state
    best_state = initial_state.copy()
    operator_selector = AdaptiveOperatorSelector(destroy_operators, repair_operators, config.REACTION_FACTOR)
    
    # Temperature Calculation
    T_start = 0
    primary_cost = initial_state.solution.get_primary_objective_cost()
    if config.START_TEMP_ACCEPT_PROB > 0 and primary_cost > 0:
        delta_for_temp_calc = config.START_TEMP_WORSENING_PCT * primary_cost
        T_start = -delta_for_temp_calc / math.log(config.START_TEMP_ACCEPT_PROB)
    
    T = T_start if T_start > 0 else 1.0
    
    history = {
        "iteration": [], "best_cost": [], "current_cost": [], "temperature": [],
        "accepted_move_type": [], "q_removed": [], "is_large_destroy": []
    }
    operator_history = {
        "iteration": [], "destroy_weights": [], "repair_weights": []
    }
    
    print(f"\n--- Starting ALNS Phase ---")
    print(f"  Iterations: {iterations}, Initial Temp: {T:.2f}, Initial Cost: {current_state.cost:.2f}")

    small_destroy_counter = 0
    iterations_without_improvement = 0

    for i in range(1, iterations + 1):
        context = ChangeContext(current_state.solution)
        cost_before_change = current_state.cost

        destroy_op_obj = operator_selector.select_destroy_operator()
        repair_op_obj = operator_selector.select_repair_operator()
        num_cust = len(current_state.solution.customer_to_se_route_map)
        if num_cust == 0: break

        is_large_destroy = (small_destroy_counter >= config.SMALL_DESTROY_SEGMENT_LENGTH)
        
        if is_large_destroy:
            q_percentage = random.uniform(*config.Q_LARGE_RANGE); small_destroy_counter = 0
        else:
            q_percentage = random.uniform(*config.Q_SMALL_RANGE); small_destroy_counter += 1
        
        q = max(2, int(num_cust * q_percentage))

        history["q_removed"].append(q)
        history["is_large_destroy"].append(is_large_destroy)

        removed_customers = destroy_op_obj.function(current_state.solution, context, q)
        repair_op_obj.function(current_state.solution, context, removed_customers)

        cost_after_change = current_state.cost
        sigma_update = 0
        log_msg = ""; accepted = False

        if cost_after_change < cost_before_change:
            accepted = True
            if cost_after_change < best_state.cost:
                sigma_update = config.SIGMA_1_NEW_BEST; log_msg = f"(NEW BEST: {cost_after_change:.2f})"
            else:
                sigma_update = config.SIGMA_2_BETTER; log_msg = f"(Accepted: {cost_after_change:.2f})"
        elif T > 1e-6 and random.random() < math.exp(-(cost_after_change - cost_before_change) / T):
            accepted = True
            sigma_update = config.SIGMA_3_ACCEPTED; log_msg = f"(SA Accepted: {cost_after_change:.2f})"

        if accepted:
            operator_selector.update_scores(destroy_op_obj, repair_op_obj, sigma_update)
            if cost_after_change < best_state.cost: best_state = current_state.copy()
        else:
            context.rollback()

        if sigma_update == config.SIGMA_1_NEW_BEST: iterations_without_improvement = 0
        else: iterations_without_improvement += 1
        
        if iterations_without_improvement >= config.RESTART_THRESHOLD:
            print(f"  >>> Restart triggered at iter {i}. Resetting to best known solution. <<<")
            current_state = best_state.copy(); iterations_without_improvement = 0
        
        T *= config.COOLING_RATE
        
        if i % config.SEGMENT_LENGTH == 0:
            operator_selector.update_weights()
            operator_history["iteration"].append(i)
            d_weights = {op.name: op.weight for op in operator_selector.destroy_ops}
            r_weights = {op.name: op.weight for op in operator_selector.repair_ops}
            operator_history["destroy_weights"].append(d_weights)
            operator_history["repair_weights"].append(r_weights)
            
        if i % 100 == 0 or log_msg:
            print(f"  Iter {i:>5}/{iterations} | Best: {best_state.cost:<10.2f} | Current: {current_state.cost:<10.2f} | Temp: {T:<8.2f} | Ops: {destroy_op_obj.name}/{repair_op_obj.name} | {log_msg}")
    
        history["iteration"].append(i)
        history["best_cost"].append(best_state.cost)
        history["current_cost"].append(current_state.cost)
        history["temperature"].append(T)
        log_move_type = 'rejected'
        if sigma_update == config.SIGMA_1_NEW_BEST: log_move_type = 'new_best'
        elif sigma_update == config.SIGMA_2_BETTER: log_move_type = 'better'
        elif accepted: log_move_type = 'sa_accepted'
        history["accepted_move_type"].append(log_move_type)

    print(f"\n--- ALNS phase complete. Best cost found: {best_state.cost:.2f} ---")
    return best_state, (history, operator_history)