# ops_repair.py
import random
from typing import List, Dict

from model_solution import SolutionData, SERouteData, FERouteData
from model_problem import Customer, ProblemInstance
from logic_core import (
    find_best_insertion_for_customer,
    calculate_se_route_properties,
    check_and_calculate_fe_schedule,
    calculate_objective_cost_after_recalc
)

def _apply_insertion(solution_data: SolutionData, customer: Customer, best_option: Dict) -> SolutionData:
    problem = solution_data.problem
    cust_id = customer.id    
    """
    Hàm thuần túy: nhận lời giải cũ, áp dụng lựa chọn chèn, trả về lời giải mới.
    """
    new_unserved_ids = tuple(cid for cid in solution_data.unserved_customer_ids if cid != cust_id)

    if best_option.get('type') is None:
        # Nếu không chèn được, giữ nguyên danh sách unserved (hoặc thêm vào nếu chưa có)
        if cust_id not in solution_data.unserved_customer_ids:
            new_unserved_ids = solution_data.unserved_customer_ids + (cust_id,)
        else:
            new_unserved_ids = solution_data.unserved_customer_ids
            
        return SolutionData(problem, solution_data.fe_routes, solution_data.se_routes, new_unserved_ids)

    problem = solution_data.problem
    option_type = best_option['type']
    
    temp_se_routes = list(solution_data.se_routes)
    temp_fe_routes = list(solution_data.fe_routes)

    if option_type == 'insert_into_existing_se':
        se_idx, pos = best_option['se_route_idx'], best_option['se_pos']
        old_se = temp_se_routes[se_idx]
        new_nodes = old_se.nodes_id[:pos] + (customer.id,) + old_se.nodes_id[pos:]
        # Ghi đè SE route cũ bằng một cái mới (chỉ với nodes_id, sẽ được tính lại sau)
        temp_se_routes[se_idx] = SERouteData(old_se.satellite_id, new_nodes, 0,0,0,0,{},{},{})
    
    elif option_type == 'create_new_se_new_fe':
        sat_id = best_option['new_satellite_id']
        satellite = problem.node_objects[sat_id]
        new_nodes = (satellite.dist_id, customer.id, satellite.coll_id)
        # Tạo một SE route mới (với thuộc tính tạm) và thêm vào danh sách
        new_se = SERouteData(sat_id, new_nodes, 0,0,0,0,{},{},{})
        temp_se_routes.append(new_se)
        # Tạo FE route mới phục vụ nó
        new_fe = FERouteData(serviced_se_route_indices=(len(temp_se_routes) - 1,), schedule=tuple(), total_dist=0, total_time=0, total_travel_time=0, route_deadline=float('inf'))
        temp_fe_routes.append(new_fe)

    elif option_type == 'create_new_se_expand_fe':
        sat_id, fe_idx = best_option['new_satellite_id'], best_option['fe_route_idx']
        satellite = problem.node_objects[sat_id]
        new_nodes = (satellite.dist_id, customer.id, satellite.coll_id)
        # Tạo SE route mới
        new_se = SERouteData(sat_id, new_nodes, 0,0,0,0,{},{},{})
        temp_se_routes.append(new_se)
        # Cập nhật FE route cũ để phục vụ nó
        old_fe = temp_fe_routes[fe_idx]
        new_serviced = old_fe.serviced_se_route_indices + (len(temp_se_routes) - 1,)
        temp_fe_routes[fe_idx] = FERouteData(new_serviced, old_fe.schedule, old_fe.total_dist, old_fe.total_time, old_fe.total_travel_time, old_fe.route_deadline)

    # --- TÍNH TOÁN LẠI TOÀN BỘ ---
    # Đây là phiên bản đơn giản, có thể tối ưu bằng cách chỉ tính lại các route bị ảnh hưởng
    recalculated_se_routes = []
    for se in temp_se_routes:
        is_ok, props = calculate_se_route_properties(se.nodes_id, se.satellite_id, 0.0, problem)
        if not is_ok or props is None:
            # If SE route becomes infeasible after insertion, return original solution
            return solution_data
        recalculated_se_routes.append(SERouteData(se.satellite_id, se.nodes_id, **props))
    
    recalculated_fe_routes = []
    for fe in temp_fe_routes:
        serviced_ses = [recalculated_se_routes[i] for i in fe.serviced_se_route_indices]
        is_ok, props = check_and_calculate_fe_schedule(serviced_ses, problem)
        if not is_ok or props is None:
            # If FE route becomes infeasible after insertion, return original solution
            return solution_data
        recalculated_fe_routes.append(FERouteData(fe.serviced_se_route_indices, **props))

    return SolutionData(
        problem=problem,
        fe_routes=tuple(recalculated_fe_routes),
        se_routes=tuple(recalculated_se_routes),
        unserved_customer_ids=new_unserved_ids # Cập nhật danh sách đã thu gọn
    )


def greedy_repair(solution_data: SolutionData, customers_to_insert: List[Customer]) -> SolutionData:
    customers = list(customers_to_insert)
    random.shuffle(customers)
    
    current_solution = solution_data

    for customer in customers:
        # Hàm find_best_insertion_for_customer cần được viết lại hoàn toàn theo DOP
        # Tạm thời, chúng ta sẽ dùng một logic đơn giản hóa
        # LƯU Ý: Đây là điểm cần được hoàn thiện. Logic find_best_insertion_for_customer trong logic_core.py
        # là bản phác thảo và cần được làm cho hoàn chỉnh.
        best_option = find_best_insertion_for_customer(customer, current_solution)
        current_solution = _apply_insertion(current_solution, customer, best_option)
                
    return current_solution

# (Các toán tử repair khác có thể được implement tương tự,
# ví dụ regret_insertion sẽ gọi find_k_best... và sau đó là _apply_insertion)