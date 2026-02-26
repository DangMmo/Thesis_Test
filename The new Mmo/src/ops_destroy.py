# ops_destroy.py
import random
from typing import List, Set

import config
from logic_core import _recalculate_fe_route_and_check_feasibility
from model_solution import Solution, ChangeContext
from model_problem import Customer

# ==============================================================================
# BASE REMOVAL FUNCTION
# ==============================================================================

def _perform_removal(solution: Solution, context: ChangeContext, to_remove_ids: Set[int]) -> List[Customer]:
    removed_objs = []
    affected_fes = set()
    cust_map_snapshot = solution.customer_to_se_route_map
    
    # 1. Identify affected FE routes
    for cust_id in to_remove_ids:
        if cust_id in cust_map_snapshot:
            affected_fes.update(cust_map_snapshot[cust_id].serving_fe_routes)
            
    # 2. Backup Routes
    for fe_route in affected_fes:
        context.backup_route(fe_route)
        for se_route in fe_route.serviced_se_routes:
            context.backup_route(se_route)
            
    # 3. Remove Customers from SE Routes
    for cust_id in to_remove_ids:
        if cust_id in cust_map_snapshot:
            se_route = cust_map_snapshot[cust_id]
            customer_obj = solution.problem.node_objects[cust_id]
            removed_objs.append(customer_obj)
            se_route.remove_customer(customer_obj)
            
    solution.update_customer_map()
    
    # 4. Clean up empty routes and Recalculate FE
    for fe_route in affected_fes:
        # Remove empty SE routes
        for se_route_in_fe in list(fe_route.serviced_se_routes):
            if not se_route_in_fe.get_customers():
                solution.unlink_routes(fe_route, se_route_in_fe)
                solution.remove_se_route(se_route_in_fe)
                context.track_removed_route(se_route_in_fe)
        
        # Remove empty FE routes or Recalculate
        if not fe_route.serviced_se_routes:
             solution.remove_fe_route(fe_route)
             context.track_removed_route(fe_route)
        else:
             _recalculate_fe_route_and_check_feasibility(fe_route, solution.problem)
             
    return removed_objs

# ==============================================================================
# DESTROY OPERATORS
# ==============================================================================

def random_removal(solution: Solution, context: ChangeContext, q: int) -> List[Customer]:
    served_ids = list(solution.customer_to_se_route_map.keys())
    if not served_ids: return []
    q = min(q, len(served_ids))
    to_remove_ids = set(random.sample(served_ids, q))
    return _perform_removal(solution, context, to_remove_ids)

# SHAW PARAMETERS
W_DIST = 9; W_TIME = 3; W_DEMAND = 2; W_ROUTE = 5

def _calculate_relatedness(cust1: Customer, cust2: Customer, solution: Solution) -> float:
    problem = solution.problem
    dist = problem.get_distance(cust1.id, cust2.id)
    norm_dist = dist / problem._max_dist if problem._max_dist > 0 else 0
    
    se_route1 = solution.customer_to_se_route_map.get(cust1.id)
    se_route2 = solution.customer_to_se_route_map.get(cust2.id)
    if not se_route1 or not se_route2: return float('inf')
    
    start_time1 = se_route1.service_start_times.get(cust1.id, 0.0)
    start_time2 = se_route2.service_start_times.get(cust2.id, 0.0)
    time_diff = abs(start_time1 - start_time2)
    norm_time = time_diff / problem._max_due_time if problem._max_due_time > 0 else 0
    
    demand_diff = abs(cust1.demand - cust2.demand)
    norm_demand = demand_diff / problem._max_demand if problem._max_demand > 0 else 0
    
    same_route_flag = 0 if se_route1 is se_route2 else 1
    
    return (W_DIST * norm_dist + W_TIME * norm_time + W_DEMAND * norm_demand + W_ROUTE * same_route_flag)

def shaw_removal(solution: Solution, context: ChangeContext, q: int, p: int = 6) -> List[Customer]:
    all_served_cust_ids = list(solution.customer_to_se_route_map.keys())
    if not all_served_cust_ids: return []
    q = min(q, len(all_served_cust_ids))
    to_remove_ids = set()
    
    seed_id = random.choice(all_served_cust_ids)
    to_remove_ids.add(seed_id)
    
    while len(to_remove_ids) < q:
        bait_id = random.choice(list(to_remove_ids))
        bait_obj = solution.problem.node_objects[bait_id]
        
        unselected_cust_ids = [cid for cid in all_served_cust_ids if cid not in to_remove_ids]
        candidates = sorted([(cid, _calculate_relatedness(bait_obj, solution.problem.node_objects[cid], solution)) 
                             for cid in unselected_cust_ids], key=lambda x: x[1])
        
        index = int(pow(random.random(), p) * len(candidates))
        to_remove_ids.add(candidates[index][0])
        
    return _perform_removal(solution, context, to_remove_ids)

def worst_slack_removal(solution: Solution, context: ChangeContext, q: int, p: int = 3) -> List[Customer]:
    candidates = []
    for cust_id, se_route in solution.customer_to_se_route_map.items():
        candidates.append((cust_id, se_route.forward_time_slacks.get(cust_id, 0.0)))
        
    if not candidates: return []
    candidates.sort(key=lambda x: x[1])
    
    to_remove_ids = set()
    q = min(q, len(candidates))
    while len(to_remove_ids) < q and candidates:
        index = int(pow(random.random(), p) * len(candidates))
        to_remove_ids.add(candidates.pop(index)[0])
        
    return _perform_removal(solution, context, to_remove_ids)

def worst_cost_removal(solution: Solution, context: ChangeContext, q: int, p: int = 3) -> List[Customer]:
    problem = solution.problem
    candidates = []
    
    cost_func = problem.get_distance if config.PRIMARY_OBJECTIVE == "DISTANCE" else problem.get_travel_time

    for cust_id, se_route in solution.customer_to_se_route_map.items():
        if cust_id not in se_route.nodes_id: continue
        pos = se_route.nodes_id.index(cust_id)
        if pos == 0 or pos == len(se_route.nodes_id) - 1: continue
            
        prev_node_id = se_route.nodes_id[pos - 1]
        next_node_id = se_route.nodes_id[pos + 1]
        
        cost_prev_cust = cost_func(prev_node_id % problem.total_nodes, cust_id)
        cost_cust_next = cost_func(cust_id, next_node_id % problem.total_nodes)
        cost_prev_next = cost_func(prev_node_id % problem.total_nodes, next_node_id % problem.total_nodes)
        
        cost_saving = cost_prev_cust + cost_cust_next - cost_prev_next
        candidates.append((cust_id, cost_saving))

    if not candidates: return []

    candidates.sort(key=lambda x: x[1], reverse=True)
    to_remove_ids = set()
    q = min(q, len(candidates))
    while len(to_remove_ids) < q and candidates:
        index = int(pow(random.random(), p) * len(candidates))
        to_remove_ids.add(candidates.pop(index)[0])
            
    return _perform_removal(solution, context, to_remove_ids)

def route_removal(solution: Solution, context: ChangeContext, q: int) -> List[Customer]:
    se_routes = list(solution.se_routes)
    if not se_routes: return []
    to_remove_ids = set()
    while len(to_remove_ids) < q and se_routes:
        route_to_remove = random.choice(se_routes)
        to_remove_ids.update({c.id for c in route_to_remove.get_customers()})
        se_routes.remove(route_to_remove)
    return _perform_removal(solution, context, to_remove_ids)

def satellite_removal(solution: Solution, context: ChangeContext, q: int) -> List[Customer]:
    active_satellites = list({se_route.satellite for se_route in solution.se_routes})
    if not active_satellites: return []
    satellite_to_clear = random.choice(active_satellites)
    to_remove_ids = {c.id for se in solution.se_routes if se.satellite.id == satellite_to_clear.id for c in se.get_customers()}
    return _perform_removal(solution, context, to_remove_ids)

def least_utilized_route_removal(solution: Solution, context: ChangeContext, q: int) -> List[Customer]:
    if not solution.se_routes: return []
    sorted_routes = sorted(solution.se_routes, key=lambda r: len(r.get_customers()))
    pool_size = max(1, int(len(sorted_routes) * 0.25))
    candidate_pool = sorted_routes[:pool_size]
    to_remove_ids = set()
    while len(to_remove_ids) < q and candidate_pool:
        route_to_remove = random.choice(candidate_pool)
        to_remove_ids.update({c.id for c in route_to_remove.get_customers()})
        candidate_pool.remove(route_to_remove)
    return _perform_removal(solution, context, to_remove_ids)