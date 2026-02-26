# logic_core.py
import copy
import heapq
import itertools
from typing import Dict, Optional, List, Tuple

import config
from model_solution import SERoute, FERoute, Solution
from model_problem import ProblemInstance, Customer

class InsertionProcessor:
    def __init__(self, problem: ProblemInstance):
        self.problem = problem

    def find_all_feasible_insertions_for_se_route(self, route: SERoute, customer: Customer) -> List[Dict]:
        feasible_options = []
        problem = route.problem
        for i in range(len(route.nodes_id) - 1):
            pos_to_insert = i + 1
            temp_nodes_id = route.nodes_id[:pos_to_insert] + [customer.id] + route.nodes_id[pos_to_insert:]
            
            # Check SE Capacity
            new_delivery_load = route.total_load_delivery
            if customer.type == 'DeliveryCustomer': 
                new_delivery_load += customer.demand
            if new_delivery_load > problem.se_vehicle_capacity + 1e-6: 
                break 
            
            running_load = new_delivery_load
            is_load_feasible = True
            for node_id in temp_nodes_id[1:-1]:
                cust_obj = problem.node_objects[node_id]
                if cust_obj.type == 'DeliveryCustomer': 
                    running_load -= cust_obj.demand
                else: 
                    running_load += cust_obj.demand
                
                if running_load < -1e-6 or running_load > problem.se_vehicle_capacity + 1e-6:
                    is_load_feasible = False
                    break
            
            if not is_load_feasible: 
                continue

            prev_node_id = route.nodes_id[pos_to_insert - 1]
            next_node_id = route.nodes_id[pos_to_insert]
            prev_obj = problem.node_objects[prev_node_id % problem.total_nodes]
            next_obj = problem.node_objects[next_node_id % problem.total_nodes]
            
            dist_increase = (problem.get_distance(prev_obj.id, customer.id) + 
                             problem.get_distance(customer.id, next_obj.id) - 
                             problem.get_distance(prev_obj.id, next_obj.id))
            time_increase = (problem.get_travel_time(prev_obj.id, customer.id) + 
                             problem.get_travel_time(customer.id, next_obj.id) - 
                             problem.get_travel_time(prev_obj.id, next_obj.id))
            
            feasible_options.append({
                "pos": pos_to_insert, 
                "dist_increase": dist_increase, 
                "time_increase": time_increase
            })
        return feasible_options

# ==============================================================================
# CORE SYNCHRONIZATION LOGIC (FE-SE HANDSHAKE)
# ==============================================================================

def _recalculate_fe_route_and_check_feasibility(fe_route: FERoute, problem: ProblemInstance) -> Tuple[bool, Optional[float], Optional[float]]:
    """
    Tính toán lại lộ trình FE và kiểm tra tính khả thi.
    Giữ nguyên logic: Static Sorting & Hard Blocking.
    """
    if not fe_route.serviced_se_routes:
        fe_route.total_dist = 0.0
        fe_route.schedule = []
        fe_route.calculate_route_properties()
        return True, 0.0, 0.0
        
    depot = problem.depot
    
    # 1. Tính tải trọng ban đầu
    initial_delivery_load = sum(se.total_load_delivery for se in fe_route.serviced_se_routes)
    
    # 2. Kiểm tra tải trọng ngay lập tức
    if initial_delivery_load > problem.fe_vehicle_capacity + 1e-6:
        return False, None, None

    sats_to_visit = {se.satellite for se in fe_route.serviced_se_routes}
    
    # --- STATIC SORTING: Luôn đi từ vệ tinh gần Depot nhất ---
    sats_list = sorted(list(sats_to_visit), key=lambda s: problem.get_distance(depot.id, s.id))
    
    schedule = []
    current_time = 0.0
    current_load = initial_delivery_load
    
    schedule.append({
        'activity': 'DEPART_DEPOT', 'node_id': depot.id, 'load_change': current_load, 
        'load_after': current_load, 'arrival_time': 0.0, 'start_svc_time': 0.0, 'departure_time': 0.0
    })
    
    last_node_id = depot.id
    route_deadlines = set()

    for satellite in sats_list:
        arrival_at_sat = current_time + problem.get_travel_time(last_node_id, satellite.id)
        
        se_routes_at_sat = [r for r in fe_route.serviced_se_routes if r.satellite == satellite]
        del_load_at_sat = sum(r.total_load_delivery for r in se_routes_at_sat)
        
        # Unload Delivery
        current_load -= del_load_at_sat
        schedule.append({
            'activity': 'UNLOAD_DELIV', 'node_id': satellite.id, 'load_change': -del_load_at_sat, 
            'load_after': current_load, 'arrival_time': arrival_at_sat, 
            'start_svc_time': arrival_at_sat, 'departure_time': arrival_at_sat
        })
        
        latest_se_finish = 0
        for se_route in se_routes_at_sat:
            # --- DOWNSTREAM SYNC: FE đến -> SE được phép chạy ---
            se_route.service_start_times[se_route.nodes_id[0]] = arrival_at_sat
            se_route.calculate_full_schedule_and_slacks()
            
            # Check SE constraints
            for cust in se_route.get_customers():
                if hasattr(cust, 'due_time') and se_route.service_start_times.get(cust.id, float('inf')) > cust.due_time + 1e-6:
                    return False, None, None
                if hasattr(cust, 'deadline'): 
                    route_deadlines.add(cust.deadline)
            
            latest_se_finish = max(latest_se_finish, se_route.service_start_times.get(se_route.nodes_id[-1], 0))
        
        pickup_load_at_sat = sum(r.total_load_pickup for r in se_routes_at_sat)
        
        # --- UPSTREAM SYNC (HARD BLOCKING): FE phải đợi SE chậm nhất ---
        departure_from_sat = latest_se_finish
        
        # Load Pickup
        current_load += pickup_load_at_sat
        schedule.append({
            'activity': 'LOAD_PICKUP', 'node_id': satellite.id, 'load_change': pickup_load_at_sat, 
            'load_after': current_load, 'arrival_time': latest_se_finish, 
            'start_svc_time': latest_se_finish, 'departure_time': departure_from_sat
        })
        
        current_time = departure_from_sat
        last_node_id = satellite.id

    arrival_at_depot = current_time + problem.get_travel_time(last_node_id, depot.id)
    schedule.append({
        'activity': 'ARRIVE_DEPOT', 'node_id': depot.id, 'load_change': -current_load, 
        'load_after': 0, 'arrival_time': arrival_at_depot, 
        'start_svc_time': arrival_at_depot, 'departure_time': arrival_at_depot
    })
    
    fe_route.schedule = schedule
    fe_route.calculate_route_properties()
    
    effective_deadline = min(route_deadlines) if route_deadlines else float('inf')
    if arrival_at_depot > effective_deadline + 1e-6:
        return False, None, None
        
    return True, fe_route.total_dist, fe_route.total_travel_time

def _calculate_route_proximity(customer: Customer, se_route: SERoute, problem: ProblemInstance) -> float:
    if not se_route.get_customers(): return problem.get_distance(customer.id, se_route.satellite.id)
    return min(problem.get_distance(customer.id, c.id) for c in se_route.get_customers())

def find_k_best_global_insertion_options_combined(customer: Customer, solution: Solution, insertion_processor: InsertionProcessor, k: int) -> List[Dict]:
    problem = solution.problem
    best_options_heap = []
    counter = itertools.count()
    
    primary_route_attr = 'total_dist' if config.PRIMARY_OBJECTIVE == "DISTANCE" else 'total_travel_time'
    
    def add_option_to_heap(objective_increase, option_details):
        count = next(counter)
        if len(best_options_heap) < k: 
            heapq.heappush(best_options_heap, (-objective_increase, count, option_details))
        elif objective_increase < -best_options_heap[0][0]: 
            heapq.heapreplace(best_options_heap, (-objective_increase, count, option_details))
            
    # Option 1: Insert into existing SE
    candidate_se_routes = sorted(
        [r for r in solution.se_routes if r.serving_fe_routes], 
        key=lambda r: _calculate_route_proximity(customer, r, problem)
    )
    
    for se_route in candidate_se_routes[:config.PRUNING_N_SE_ROUTE_CANDIDATES]:
        local_insertions = insertion_processor.find_all_feasible_insertions_for_se_route(se_route, customer)
        if not local_insertions: continue
        
        for local_option in local_insertions:
            fe_route = list(se_route.serving_fe_routes)[0]
            fe_memento = fe_route.backup()
            se_mementos = {se: se.backup() for se in fe_route.serviced_se_routes}
            
            try:
                se_route_to_modify = next(se for se in fe_route.serviced_se_routes if se is se_route)
                se_route_to_modify.insert_customer_at_pos(customer, local_option['pos'])
                
                is_feasible, _, _ = _recalculate_fe_route_and_check_feasibility(fe_route, problem)
                
                if is_feasible:
                    primary_increase = (
                        (getattr(se_route_to_modify, primary_route_attr) - getattr(se_mementos[se_route_to_modify], primary_route_attr)) + 
                        (getattr(fe_route, primary_route_attr) - getattr(fe_memento, primary_route_attr))
                    )
                    objective_increase = config.WEIGHT_PRIMARY * primary_increase
                    
                    option = {
                        'objective_increase': objective_increase, 
                        'type': 'insert_into_existing_se', 
                        'se_route': se_route, 
                        'se_pos': local_option['pos']
                    }
                    add_option_to_heap(objective_increase, option)
            finally:
                fe_route.restore(fe_memento)
                for se, memento in se_mementos.items(): se.restore(memento)

    # Option 2 & 3: Create New SE (and New/Expand FE)
    candidate_satellites = problem.satellite_neighbors.get(customer.id, problem.satellites)
    for satellite in candidate_satellites:
        # Temp SE Check
        temp_new_se = SERoute(satellite, problem)
        temp_new_se.insert_customer_at_pos(customer, 1)
        
        if temp_new_se.total_load_delivery <= problem.fe_vehicle_capacity + 1e-6:
            # 2. New SE + New FE
            temp_fe_for_new = FERoute(problem)
            temp_fe_for_new.add_serviced_se_route(temp_new_se)
            is_feasible, new_fe_dist, new_fe_time = _recalculate_fe_route_and_check_feasibility(temp_fe_for_new, problem)
            
            if is_feasible:
                new_fe_primary = new_fe_dist if config.PRIMARY_OBJECTIVE == "DISTANCE" else new_fe_time
                primary_increase = getattr(temp_new_se, primary_route_attr) + new_fe_primary
                objective_increase = config.WEIGHT_PRIMARY * primary_increase
                if config.OPTIMIZE_VEHICLE_COUNT: 
                    objective_increase += config.WEIGHT_SE_VEHICLE + config.WEIGHT_FE_VEHICLE
                
                option = {
                    'objective_increase': objective_increase, 
                    'type': 'create_new_se_new_fe', 
                    'new_satellite': satellite
                }
                add_option_to_heap(objective_increase, option)

        # 3. New SE + Expand FE
        for fe_route in solution.fe_routes:
            if sum(r.total_load_delivery for r in fe_route.serviced_se_routes) + temp_new_se.total_load_delivery > problem.fe_vehicle_capacity + 1e-6: 
                continue
            
            fe_memento_expand = fe_route.backup()
            se_mementos_expand = {se: se.backup() for se in fe_route.serviced_se_routes}
            
            try:
                fe_route.add_serviced_se_route(temp_new_se)
                is_feasible_expand, _, _ = _recalculate_fe_route_and_check_feasibility(fe_route, problem)
                
                if is_feasible_expand:
                    delta_fe_primary = getattr(fe_route, primary_route_attr) - getattr(fe_memento_expand, primary_route_attr)
                    primary_increase = getattr(temp_new_se, primary_route_attr) + delta_fe_primary
                    
                    objective_increase = config.WEIGHT_PRIMARY * primary_increase
                    if config.OPTIMIZE_VEHICLE_COUNT: 
                        objective_increase += config.WEIGHT_SE_VEHICLE
                    
                    option = {
                        'objective_increase': objective_increase, 
                        'type': 'create_new_se_expand_fe', 
                        'new_satellite': satellite, 
                        'fe_route': fe_route
                    }
                    add_option_to_heap(objective_increase, option)
            finally:
                fe_route.restore(fe_memento_expand)
                for se, memento in se_mementos_expand.items(): se.restore(memento)

    sorted_options = sorted([opt for cost, count, opt in best_options_heap], key=lambda x: x['objective_increase'])
    return sorted_options

def find_best_global_insertion_option(customer: Customer, solution: Solution, insertion_processor: InsertionProcessor) -> Dict:
    best_k_options = find_k_best_global_insertion_options_combined(customer, solution, insertion_processor, k=1)
    return best_k_options[0] if best_k_options else {'objective_increase': float('inf')}

def find_k_best_global_insertion_options(customer: Customer, solution: Solution, insertion_processor: InsertionProcessor, k: int) -> List[Dict]:
    return find_k_best_global_insertion_options_combined(customer, solution, insertion_processor, k)