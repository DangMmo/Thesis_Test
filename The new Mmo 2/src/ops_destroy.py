# ops_destroy.py
import random
from typing import List, Set, Tuple

import config
from model_solution import SolutionData, SERouteData, FERouteData
from model_problem import Customer, ProblemInstance
from logic_core import check_and_calculate_fe_schedule, calculate_se_route_properties

# ==============================================================================
# HÀM TRỢ GIÚP (HELPER FUNCTION)
# ==============================================================================

# ops_destroy.py (Sửa lại hàm _rebuild và _perform_removal)

def _rebuild_solution_after_removal(
    problem: ProblemInstance,
    current_se_routes: List[SERouteData],
    current_fe_routes: List[FERouteData],
    unserved_ids: tuple[int, ...] # Thêm tham số này
) -> SolutionData:
    se_routes_to_keep = []
    se_empty_indices = set()
    old_idx_to_new_idx = {}
    
    for i, se in enumerate(current_se_routes):
        if len(se.nodes_id) > 2:
            old_idx_to_new_idx[i] = len(se_routes_to_keep)
            se_routes_to_keep.append(se)
        else:
            se_empty_indices.add(i)

    fe_routes_to_keep = []
    for fe in current_fe_routes:
        new_serviced_indices = [old_idx_to_new_idx[i] for i in fe.serviced_se_route_indices if i not in se_empty_indices]
        if not new_serviced_indices:
            continue

        serviced_ses = [se_routes_to_keep[i] for i in new_serviced_indices]
        is_feasible, fe_props = check_and_calculate_fe_schedule(serviced_ses, problem)
        
        if is_feasible:
            fe_routes_to_keep.append(FERouteData(serviced_se_route_indices=tuple(new_serviced_indices), **fe_props))
    
    return SolutionData(
        problem=problem,
        fe_routes=tuple(fe_routes_to_keep),
        se_routes=tuple(se_routes_to_keep),
        unserved_customer_ids=unserved_ids # Trả lại danh sách unserved đúng
    )

def _perform_removal(solution_data: SolutionData, to_remove_ids: Set[int]) -> Tuple[SolutionData, Tuple[Customer, ...]]:
    problem = solution_data.problem
    removed_objs = [problem.node_objects[cid] for cid in to_remove_ids]
    
    temp_se_routes = list(solution_data.se_routes)
    for cust_id in to_remove_ids:
        se_idx = solution_data.customer_to_se_route_idx.get(cust_id)
        if se_idx is not None:
            old_se = temp_se_routes[se_idx]
            new_nodes = tuple(nid for nid in old_se.nodes_id if nid != cust_id)
            temp_se_routes[se_idx] = SERouteData(
                old_se.satellite_id, new_nodes, 0, 0, 0, 0, {}, {}, {}
            )
            
    # Cập nhật danh sách unserved: cũ + mới xóa
    new_unserved_ids = tuple(set(solution_data.unserved_customer_ids) | to_remove_ids)
    
    partial_solution = _rebuild_solution_after_removal(
        problem, temp_se_routes, list(solution_data.fe_routes), new_unserved_ids
    )
    
    return partial_solution, tuple(removed_objs)
# ==============================================================================
# DESTROY OPERATORS
# ==============================================================================

def random_removal(solution_data: SolutionData, q: int) -> Tuple[SolutionData, Tuple[Customer, ...]]:
    served_ids = list(solution_data.customer_to_se_route_idx.keys())
    if not served_ids: return solution_data, tuple()
    q = min(q, len(served_ids))
    to_remove_ids = set(random.sample(served_ids, q))
    return _perform_removal(solution_data, to_remove_ids)

# --- SHAW REMOVAL PARAMETERS ---
W_DIST = 9; W_TIME = 3; W_DEMAND = 2; W_ROUTE = 5

def _calculate_relatedness(cust1: Customer, cust2: Customer, solution_data: SolutionData) -> float:
    problem = solution_data.problem
    dist = problem.get_distance(cust1.id, cust2.id)
    norm_dist = dist / problem._max_dist if problem._max_dist > 0 else 0
    
    se_idx1 = solution_data.customer_to_se_route_idx.get(cust1.id)
    se_idx2 = solution_data.customer_to_se_route_idx.get(cust2.id)
    if se_idx1 is None or se_idx2 is None: return float('inf')
    
    se_route1 = solution_data.se_routes[se_idx1]
    se_route2 = solution_data.se_routes[se_idx2]
    
    start_time1 = se_route1.service_start_times.get(cust1.id, 0.0)
    start_time2 = se_route2.service_start_times.get(cust2.id, 0.0)
    time_diff = abs(start_time1 - start_time2)
    norm_time = time_diff / problem._max_due_time if problem._max_due_time > 0 else 0
    
    demand_diff = abs(cust1.demand - cust2.demand)
    norm_demand = demand_diff / problem._max_demand if problem._max_demand > 0 else 0
    
    same_route_flag = 0 if se_idx1 == se_idx2 else 1
    
    return (W_DIST * norm_dist + W_TIME * norm_time + W_DEMAND * norm_demand + W_ROUTE * same_route_flag)

def shaw_removal(solution_data: SolutionData, q: int, p: int = 6) -> Tuple[SolutionData, Tuple[Customer, ...]]:
    all_served_cust_ids = list(solution_data.customer_to_se_route_idx.keys())
    if not all_served_cust_ids: return solution_data, tuple()
    q = min(q, len(all_served_cust_ids))
    to_remove_ids = set()
    
    seed_id = random.choice(all_served_cust_ids)
    to_remove_ids.add(seed_id)
    
    while len(to_remove_ids) < q:
        bait_id = random.choice(list(to_remove_ids))
        bait_obj = solution_data.problem.node_objects[bait_id]
        
        unselected_cust_ids = [cid for cid in all_served_cust_ids if cid not in to_remove_ids]
        candidates = sorted([(cid, _calculate_relatedness(bait_obj, solution_data.problem.node_objects[cid], solution_data)) 
                             for cid in unselected_cust_ids], key=lambda x: x[1])
        
        if not candidates: break
        index = int(pow(random.random(), p) * len(candidates))
        to_remove_ids.add(candidates[index][0])
        
    return _perform_removal(solution_data, to_remove_ids)

def worst_cost_removal(solution_data: SolutionData, q: int, p: int = 3) -> Tuple[SolutionData, Tuple[Customer, ...]]:
    problem = solution_data.problem
    candidates = []
    
    cost_func = problem.get_distance if config.PRIMARY_OBJECTIVE == "DISTANCE" else problem.get_travel_time

    for cust_id, se_idx in solution_data.customer_to_se_route_idx.items():
        se_route = solution_data.se_routes[se_idx]
        if cust_id not in se_route.nodes_id: continue
        try:
            pos = se_route.nodes_id.index(cust_id)
        except ValueError:
            continue
        if pos == 0 or pos == len(se_route.nodes_id) - 1: continue
            
        prev_node_id = se_route.nodes_id[pos - 1]
        next_node_id = se_route.nodes_id[pos + 1]
        
        cost_prev_cust = cost_func(prev_node_id % problem.total_nodes, cust_id)
        cost_cust_next = cost_func(cust_id, next_node_id % problem.total_nodes)
        cost_prev_next = cost_func(prev_node_id % problem.total_nodes, next_node_id % problem.total_nodes)
        
        cost_saving = cost_prev_cust + cost_cust_next - cost_prev_next
        candidates.append((cust_id, cost_saving))

    if not candidates: return solution_data, tuple()

    candidates.sort(key=lambda x: x[1], reverse=True)
    to_remove_ids = set()
    q = min(q, len(candidates))
    while len(to_remove_ids) < q and candidates:
        index = int(pow(random.random(), p) * len(candidates))
        to_remove_ids.add(candidates.pop(index)[0])
            
    return _perform_removal(solution_data, to_remove_ids)

# (Các toán tử destroy khác có thể được implement tương tự)
# Để đơn giản, chúng ta sẽ tạm thời comment out chúng
# worst_slack_removal, route_removal, etc.