# logic_core.py
import heapq
import itertools
from typing import Dict, Optional, List, Tuple
import functools

import config
from model_solution import SERouteData, FERouteData, SolutionData
from model_problem import ProblemInstance, Customer

# ==============================================================================
# CÁC HÀM TÍNH TOÁN CẤP THẤP (LOW-LEVEL CALCULATION FUNCTIONS)
# ==============================================================================

@functools.lru_cache(maxsize=4096)
def calculate_se_route_properties(
    nodes_id: tuple[int, ...], 
    satellite_id: int, 
    start_time: float,
    problem: ProblemInstance
) -> Tuple[bool, Dict]:
    """
    Hàm thuần túy tính toán tất cả thuộc tính của một SE route từ dữ liệu cơ bản.
    Trả về (is_feasible, properties_dict).
    """
    total_dist = 0.0
    total_travel_time = 0.0
    total_load_delivery = 0.0
    total_load_pickup = 0.0
    
    customers = [problem.node_objects[nid] for nid in nodes_id[1:-1]]
    for cust in customers:
        if cust.type == 'DeliveryCustomer':
            total_load_delivery += cust.demand
        else:
            total_load_pickup += cust.demand

    # --- Check SE Capacity ---
    running_load = total_load_delivery
    if running_load > problem.se_vehicle_capacity + 1e-6:
        return False, {}
    for cust in customers:
        if cust.type == 'DeliveryCustomer': running_load -= cust.demand
        else: running_load += cust.demand
        if running_load < -1e-6 or running_load > problem.se_vehicle_capacity + 1e-6:
            return False, {}

    # --- Tính toán lịch trình & dist/time ---
    service_start_times = {nodes_id[0]: start_time}
    waiting_times = {nodes_id[0]: 0.0}

    for i in range(len(nodes_id) - 1):
        prev_id, curr_id = nodes_id[i], nodes_id[i+1]
        prev_obj = problem.node_objects[prev_id % problem.total_nodes]
        curr_obj = problem.node_objects[curr_id % problem.total_nodes]

        dist = problem.get_distance(prev_obj.id, curr_obj.id)
        tt = problem.get_travel_time(prev_obj.id, curr_obj.id)
        total_dist += dist
        total_travel_time += tt

        st_prev = prev_obj.service_time if prev_obj.type != 'Satellite' else 0.0
        departure_prev = service_start_times[prev_id] + st_prev
        arrival_curr = departure_prev + tt
        
        start_service = max(arrival_curr, getattr(curr_obj, 'ready_time', 0))
        
        # --- Check Time Window ---
        if start_service > getattr(curr_obj, 'due_time', float('inf')) + 1e-6:
            return False, {}
            
        service_start_times[curr_id] = start_service
        waiting_times[curr_id] = start_service - arrival_curr

    # --- Tính toán Forward Time Slacks ---
    forward_time_slacks = {nodes_id[-1]: float('inf')}
    for i in range(len(nodes_id) - 2, -1, -1):
        node_id, succ_id = nodes_id[i], nodes_id[i+1]
        node_obj = problem.node_objects[node_id % problem.total_nodes]
        due_time = getattr(node_obj, 'due_time', float('inf'))
        st_node = node_obj.service_time if node_obj.type != 'Satellite' else 0.0
        
        departure_node = service_start_times[node_id] + st_node
        arrival_succ = service_start_times[succ_id] - waiting_times[succ_id]
        slack_between = arrival_succ - departure_node
        
        slack = min(forward_time_slacks[succ_id] + slack_between, due_time - service_start_times[node_id])
        forward_time_slacks[node_id] = slack

    return True, {
        "total_dist": total_dist, "total_travel_time": total_travel_time,
        "total_load_pickup": total_load_pickup, "total_load_delivery": total_load_delivery,
        "service_start_times": service_start_times, "waiting_times": waiting_times,
        "forward_time_slacks": forward_time_slacks
    }


def check_and_calculate_fe_schedule(
    serviced_se_routes: List[SERouteData], 
    problem: ProblemInstance
) -> Tuple[bool, Optional[Dict]]:
    """
    Hàm thuần túy tính toán lịch trình FE và kiểm tra tất cả ràng buộc.
    Trả về (is_feasible, fe_properties_dict).
    """
    if not serviced_se_routes:
        return True, {"schedule": tuple(), "total_dist": 0.0, "total_time": 0.0, 
                       "total_travel_time": 0.0, "route_deadline": float('inf')}

    depot = problem.depot
    
    initial_delivery_load = sum(se.total_load_delivery for se in serviced_se_routes)
    if initial_delivery_load > problem.fe_vehicle_capacity + 1e-6:
        return False, None

    sats_to_visit = {problem.node_objects[se.satellite_id] for se in serviced_se_routes}
    sats_list = sorted(list(sats_to_visit), key=lambda s: problem.get_distance(depot.id, s.id))
    
    schedule = []
    current_time = 0.0
    current_load = initial_delivery_load
    
    schedule.append({'activity': 'DEPART_DEPOT', 'node_id': depot.id, 'load_change': current_load, 
                     'load_after': current_load, 'arrival_time': 0.0, 'start_svc_time': 0.0, 'departure_time': 0.0})
    
    last_node_id = depot.id
    route_deadlines = set()

    for satellite in sats_list:
        arrival_at_sat = current_time + problem.get_travel_time(last_node_id, satellite.id)
        
        se_routes_at_sat = [r for r in serviced_se_routes if r.satellite_id == satellite.id]
        del_load_at_sat = sum(r.total_load_delivery for r in se_routes_at_sat)
        
        current_load -= del_load_at_sat
        schedule.append({'activity': 'UNLOAD_DELIV', 'node_id': satellite.id, 'load_change': -del_load_at_sat, 
                         'load_after': current_load, 'arrival_time': arrival_at_sat, 
                         'start_svc_time': arrival_at_sat, 'departure_time': arrival_at_sat})
        
        latest_se_finish = 0
        for se_route_data in se_routes_at_sat:
            # DOWNSTREAM SYNC: Tính toán lại SE route với thời gian bắt đầu mới
            is_se_feasible, _ = calculate_se_route_properties(
                se_route_data.nodes_id, se_route_data.satellite_id, arrival_at_sat, problem
            )
            if not is_se_feasible:
                return False, None

            # Tính toán lại lịch trình chi tiết để lấy deadline và thời gian kết thúc
            # (tối ưu: calculate_se_route_properties có thể trả về luôn các giá trị này)
            temp_se_sched_is_ok, temp_se_props = calculate_se_route_properties(
                se_route_data.nodes_id, se_route_data.satellite_id, arrival_at_sat, problem
            )
            
            for cust_id in se_route_data.nodes_id[1:-1]:
                cust = problem.node_objects[cust_id]
                if hasattr(cust, 'deadline'):
                    route_deadlines.add(cust.deadline)
            
            latest_se_finish = max(latest_se_finish, temp_se_props['service_start_times'][se_route_data.nodes_id[-1]])
        
        pickup_load_at_sat = sum(r.total_load_pickup for r in se_routes_at_sat)
        departure_from_sat = latest_se_finish
        
        current_load += pickup_load_at_sat
        if current_load > problem.fe_vehicle_capacity + 1e-6:
             return False, None
             
        schedule.append({'activity': 'LOAD_PICKUP', 'node_id': satellite.id, 'load_change': pickup_load_at_sat, 
                         'load_after': current_load, 'arrival_time': latest_se_finish, 
                         'start_svc_time': latest_se_finish, 'departure_time': departure_from_sat})
        
        current_time = departure_from_sat
        last_node_id = satellite.id

    arrival_at_depot = current_time + problem.get_travel_time(last_node_id, depot.id)
    schedule.append({'activity': 'ARRIVE_DEPOT', 'node_id': depot.id, 'load_change': -current_load, 
                     'load_after': 0, 'arrival_time': arrival_at_depot, 
                     'start_svc_time': arrival_at_depot, 'departure_time': arrival_at_depot})
    
    effective_deadline = min(route_deadlines) if route_deadlines else float('inf')
    if arrival_at_depot > effective_deadline + 1e-6:
        return False, None
    
    # Tính các thuộc tính cuối cùng của FE route
    path_nodes = [schedule[0]['node_id']]
    [path_nodes.append(e['node_id']) for e in schedule[1:] if e['node_id'] != path_nodes[-1]]
    total_dist = sum(problem.get_distance(path_nodes[i], path_nodes[i+1]) for i in range(len(path_nodes) - 1))
    total_travel_time = sum(problem.get_travel_time(path_nodes[i], path_nodes[i+1]) for i in range(len(path_nodes) - 1))
    total_time = schedule[-1]['arrival_time'] - schedule[0]['departure_time']
    
    return True, {
        "schedule": tuple(schedule), "total_dist": total_dist, "total_time": total_time,
        "total_travel_time": total_travel_time, "route_deadline": effective_deadline
    }

# ==============================================================================
# CÁC HÀM THAO TÁC LỜI GIẢI (SOLUTION MANIPULATION FUNCTIONS)
# ==============================================================================

def find_feasible_insertions_for_se(
    current_nodes: tuple[int, ...], 
    customer: Customer,
    problem: ProblemInstance
) -> List[Dict]:
    """ Tìm tất cả các vị trí chèn hợp lệ cho một khách hàng vào một chuỗi node. """
    feasible_options = []
    # Tái sử dụng logic từ InsertionProcessor nhưng ở dạng hàm
    for i in range(len(current_nodes) - 1):
        pos_to_insert = i + 1
        temp_nodes_id = current_nodes[:pos_to_insert] + (customer.id,) + current_nodes[pos_to_insert:]
        
        # Chỉ cần kiểm tra tính khả thi về tải trọng ở đây
        # Các ràng buộc về thời gian sẽ được kiểm tra toàn cục sau
        is_feasible, _ = calculate_se_route_properties(temp_nodes_id, 0, 0.0, problem) # satellite_id, start_time không quan trọng
        if is_feasible:
            prev_node_id = current_nodes[pos_to_insert - 1]
            next_node_id = current_nodes[pos_to_insert]
            prev_obj = problem.node_objects[prev_node_id % problem.total_nodes]
            next_obj = problem.node_objects[next_node_id % problem.total_nodes]
            
            dist_increase = (problem.get_distance(prev_obj.id, customer.id) + 
                             problem.get_distance(customer.id, next_obj.id) - 
                             problem.get_distance(prev_obj.id, next_obj.id))
            
            feasible_options.append({"pos": pos_to_insert, "dist_increase": dist_increase})
            
    return feasible_options


def find_best_insertion_for_customer(
    customer: Customer, 
    solution_data: SolutionData
) -> Dict:
    """
    Hàm DOP thay thế cho find_k_best_global_insertion_options.
    Tìm lựa chọn chèn tốt nhất (re-insert, new SE, expand FE).
    """
    problem = solution_data.problem
    best_option = {'objective_increase': float('inf')}
    
    current_cost = calculate_objective_cost(solution_data)
    
    # --- Lựa chọn 1: Chèn vào SE route hiện có ---
    for se_idx, se_route in enumerate(solution_data.se_routes):
        # Tìm FE route đang phục vụ SE route này
        fe_idx_hosting_se = -1
        for fe_i, fe_r in enumerate(solution_data.fe_routes):
            if se_idx in fe_r.serviced_se_route_indices:
                fe_idx_hosting_se = fe_i
                break
        if fe_idx_hosting_se == -1: continue

        local_insertions = find_feasible_insertions_for_se(se_route.nodes_id, customer, problem)
        
        for local_opt in local_insertions:
            # 1. Tạo SE route mới (thử nghiệm)
            new_nodes = se_route.nodes_id[:local_opt['pos']] + (customer.id,) + se_route.nodes_id[local_opt['pos']:]
            # 2. Tạo danh sách SE routes mới (thử nghiệm)
            temp_se_routes = list(solution_data.se_routes)
            # Chỉ cần cập nhật nodes_id để check_and_calculate_fe_schedule tính lại
            temp_se_routes[se_idx] = SERouteData(se_route.satellite_id, new_nodes, 0,0,0,0,{},{},{})
            
            # 3. Lấy ra các SE route bị ảnh hưởng để kiểm tra FE route
            fe_route_to_check = solution_data.fe_routes[fe_idx_hosting_se]
            ses_for_fe_check = [temp_se_routes[i] for i in fe_route_to_check.serviced_se_route_indices]
            
            is_feasible, _ = check_and_calculate_fe_schedule(ses_for_fe_check, problem)
            
            if is_feasible:
                # Nếu khả thi, tạo một SolutionData đầy đủ để tính chi phí
                # (Đây là phần tốn kém, có thể tối ưu bằng cách chỉ tính delta cost)
                temp_sol = SolutionData(problem, solution_data.fe_routes, tuple(temp_se_routes), solution_data.unserved_customer_ids)
                new_cost = calculate_objective_cost_after_recalc(temp_sol)
                increase = new_cost - current_cost
                
                if increase < best_option['objective_increase']:
                    best_option = {
                        'objective_increase': increase, 'type': 'insert_into_existing_se',
                        'se_route_idx': se_idx, 'se_pos': local_opt['pos']
                    }

    # --- Lựa chọn 2 & 3: Tạo SE route mới ---
    candidate_satellites = problem.satellite_neighbors.get(customer.id, problem.satellites)
    for satellite in candidate_satellites:
        new_se_nodes = (satellite.dist_id, customer.id, satellite.coll_id)
        is_se_feasible, se_props = calculate_se_route_properties(new_se_nodes, satellite.id, 0.0, problem)
        if not is_se_feasible: continue
        
        # 2. Thử tạo FE route mới
        is_fe_feasible, fe_props = check_and_calculate_fe_schedule([SERouteData(satellite.id, new_se_nodes, **se_props)], problem)
        if is_fe_feasible:
            # Tính chi phí tăng thêm
            increase = (config.WEIGHT_PRIMARY * (se_props['total_travel_time'] + fe_props['total_travel_time']))
            if config.OPTIMIZE_VEHICLE_COUNT:
                increase += config.WEIGHT_SE_VEHICLE + config.WEIGHT_FE_VEHICLE
            
            if increase < best_option['objective_increase']:
                best_option = {'objective_increase': increase, 'type': 'create_new_se_new_fe', 'new_satellite_id': satellite.id}
        
        # 3. Thử chèn vào FE route có sẵn
        for fe_idx, fe_route in enumerate(solution_data.fe_routes):
            current_se_routes = [solution_data.se_routes[i] for i in fe_route.serviced_se_route_indices]
            new_se_for_test = SERouteData(satellite.id, new_se_nodes, **se_props)
            
            is_feasible_expand, _ = check_and_calculate_fe_schedule(current_se_routes + [new_se_for_test], problem)
            if is_feasible_expand:
                # Tính delta cost
                temp_sol = _apply_option(solution_data, {'type': 'create_new_se_expand_fe', 'fe_route_idx': fe_idx, 'new_satellite_id': satellite.id}, customer)
                new_cost = calculate_objective_cost_after_recalc(temp_sol)
                increase = new_cost - current_cost

                if increase < best_option['objective_increase']:
                     best_option = {
                        'objective_increase': increase, 'type': 'create_new_se_expand_fe', 
                        'fe_route_idx': fe_idx, 'new_satellite_id': satellite.id
                     }
                     
    return best_option

def calculate_objective_cost_after_recalc(solution_data: SolutionData) -> float:
    """ Tính lại toàn bộ chi phí sau khi đã có thay đổi. """
    problem = solution_data.problem
    
    # Recalculate FE routes and get synced SE start times
    temp_fe_routes = []
    recalc_se_routes = list(solution_data.se_routes)
    
    for fe_idx, fe_route_data in enumerate(solution_data.fe_routes):
        serviced_ses = [solution_data.se_routes[i] for i in fe_route_data.serviced_se_route_indices]
        is_ok, fe_props = check_and_calculate_fe_schedule(serviced_ses, problem)
        if not is_ok: 
            return float('inf')
        
        temp_fe_routes.append(FERouteData(fe_route_data.serviced_se_route_indices, **fe_props))
    
    # For simplified implementation, keep SE costs as is
    # A full implementation would update SE start times based on FE schedule
    new_solution = SolutionData(problem, tuple(temp_fe_routes), tuple(recalc_se_routes), solution_data.unserved_customer_ids)
    return calculate_objective_cost(new_solution)

def _apply_option(solution_data: SolutionData, option: Dict, customer: Customer) -> SolutionData:
    """
    Hàm thuần túy để áp dụng một lựa chọn chèn và trả về SolutionData mới.
    """
    problem = solution_data.problem
    cust_id = customer.id
    
    if option['type'] == 'insert_into_existing_se':
        se_idx, pos = option['se_route_idx'], option['se_pos']
        
        old_se = solution_data.se_routes[se_idx]
        new_nodes = old_se.nodes_id[:pos] + (cust_id,) + old_se.nodes_id[pos:]
        
        # Tạo se route mới (với thuộc tính tạm thời, sẽ được tính lại)
        temp_new_se = SERouteData(old_se.satellite_id, new_nodes, 0, 0, 0, 0, {}, {}, {})
        
        new_se_list = list(solution_data.se_routes)
        new_se_list[se_idx] = temp_new_se
        
        return SolutionData(problem, solution_data.fe_routes, tuple(new_se_list), 
                            tuple(cid for cid in solution_data.unserved_customer_ids if cid != cust_id))
    
    elif option['type'] == 'create_new_se_new_fe':
        sat_id = option['new_satellite_id']
        satellite = problem.node_objects[sat_id]
        new_se_nodes = (satellite.dist_id, cust_id, satellite.coll_id)
        is_se_feasible, se_props = calculate_se_route_properties(new_se_nodes, satellite.id, 0.0, problem)
        
        if not is_se_feasible:
            return solution_data
        
        new_se = SERouteData(satellite.id, new_se_nodes, **se_props)
        is_fe_feasible, fe_props = check_and_calculate_fe_schedule([new_se], problem)
        
        if not is_fe_feasible:
            return solution_data
        
        new_fe = FERouteData((len(solution_data.se_routes),), **fe_props)
        
        return SolutionData(problem, solution_data.fe_routes + (new_fe,), solution_data.se_routes + (new_se,),
                            tuple(cid for cid in solution_data.unserved_customer_ids if cid != cust_id))
    
    elif option['type'] == 'create_new_se_expand_fe':
        fe_idx = option['fe_route_idx']
        sat_id = option['new_satellite_id']
        satellite = problem.node_objects[sat_id]
        new_se_nodes = (satellite.dist_id, cust_id, satellite.coll_id)
        is_se_feasible, se_props = calculate_se_route_properties(new_se_nodes, satellite.id, 0.0, problem)
        
        if not is_se_feasible:
            return solution_data
        
        new_se = SERouteData(satellite.id, new_se_nodes, **se_props)
        new_se_idx = len(solution_data.se_routes)
        new_se_list = list(solution_data.se_routes) + [new_se]
        
        old_fe = solution_data.fe_routes[fe_idx]
        new_fe_serviced = old_fe.serviced_se_route_indices + (new_se_idx,)
        
        current_ses = [solution_data.se_routes[i] for i in old_fe.serviced_se_route_indices] + [new_se]
        is_feasible_expand, fe_props = check_and_calculate_fe_schedule(current_ses, problem)
        
        if not is_feasible_expand:
            return solution_data
        
        new_fe = FERouteData(new_fe_serviced, **fe_props)
        new_fe_list = list(solution_data.fe_routes)
        new_fe_list[fe_idx] = new_fe
        
        return SolutionData(problem, tuple(new_fe_list), tuple(new_se_list),
                            tuple(cid for cid in solution_data.unserved_customer_ids if cid != cust_id))
    
    return solution_data

# ==============================================================================
# DOP-STYLE LOGIC FUNCTIONS (CÁC HÀM LOGIC PHIÊN BẢN MỚI)
# ==============================================================================

def calculate_objective_cost(solution_data: SolutionData) -> float:
    """ Tính toán chi phí mục tiêu từ một SolutionData bất biến. """
    primary_cost = 0.0
    if config.PRIMARY_OBJECTIVE == "DISTANCE":
        primary_cost = sum(r.total_dist for r in solution_data.fe_routes) + sum(r.total_dist for r in solution_data.se_routes)
    elif config.PRIMARY_OBJECTIVE == "TRAVEL_TIME":
        primary_cost = sum(r.total_travel_time for r in solution_data.fe_routes) + sum(r.total_travel_time for r in solution_data.se_routes)
    else:
        raise ValueError(f"Unknown PRIMARY_OBJECTIVE in config: {config.PRIMARY_OBJECTIVE}")
        
    total_cost = config.WEIGHT_PRIMARY * primary_cost
    if config.OPTIMIZE_VEHICLE_COUNT:
        num_fe_vehicles = len(solution_data.fe_routes)
        num_se_vehicles = len(solution_data.se_routes)
        vehicle_cost = (num_fe_vehicles * config.WEIGHT_FE_VEHICLE) + (num_se_vehicles * config.WEIGHT_SE_VEHICLE)
        total_cost += vehicle_cost
    return total_cost