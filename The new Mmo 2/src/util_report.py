# util_report.py
import sys
from typing import List
from model_solution import SolutionData, SERouteData, FERouteData
from model_problem import PickupCustomer, DeliveryCustomer

class Logger(object):
    def __init__(self, filename="log.txt", stream=sys.stdout):
        self.terminal = stream
        self.log = open(filename, 'a', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# ==============================================================================
# DOP HELPERS FOR PRINTING (Hàm hỗ trợ định dạng in ấn)
# ==============================================================================

def _format_se_route_data(se_route: SERouteData, problem, route_idx: int) -> str:
    path_ids = [nid % problem.total_nodes for nid in se_route.nodes_id]
    path_str = " -> ".join(map(str, path_ids))
    
    start_time_val = se_route.service_start_times.get(se_route.nodes_id[0], 0.0)
    end_time_val = se_route.service_start_times.get(se_route.nodes_id[-1], 0.0)
    operating_time = end_time_val - start_time_val if len(se_route.nodes_id) > 1 else 0.0
    
    satellite = problem.node_objects[se_route.satellite_id]
    
    lines = []
    lines.append(f"\n[SE Route #{route_idx}]")
    lines.append(f"--- SERoute for Satellite {se_route.satellite_id} (Cost: {se_route.total_dist:.2f}, Time: {operating_time:.2f}) ---")
    lines.append(f"Path: {path_str}")
    
    tbl_header = (f"  {'Node':<10}| {'Type':<18}| {'Demand':>8}| {'Load After':>12}| {'Arrival':>9}| {'Start Svc':>9}| {'Departure':>11}| {'Deadline':>10}")
    lines.append(tbl_header)
    lines.append("  " + "-" * len(tbl_header))
    
    current_load = se_route.total_load_delivery
    dep_start = start_time_val
    
    # Dòng đầu tiên: Satellite (Dist)
    lines.append(f"  {str(satellite.id) + ' (Dist)':<10}| {'Satellite':<18}| {-se_route.total_load_delivery:>8.2f}| {current_load:>12.2f}| {start_time_val:>9.2f}| {start_time_val:>9.2f}| {dep_start:>11.2f}| {'N/A':>10}")
    
    for node_id in se_route.nodes_id[1:-1]:
        customer = problem.node_objects[node_id % problem.total_nodes]
        demand_str, deadline_str = "", "N/A"
        
        if customer.type == 'DeliveryCustomer': 
            current_load -= customer.demand
            demand_str = f"{-customer.demand:.2f}"
        else: 
            current_load += customer.demand
            demand_str = f"+{customer.demand:.2f}"
            
        if hasattr(customer, 'deadline'): 
            deadline_str = f"{customer.deadline:.2f}"
            
        arrival = se_route.service_start_times.get(node_id, 0.0) - se_route.waiting_times.get(node_id, 0.0)
        start_svc = se_route.service_start_times.get(node_id, 0.0)
        departure = start_svc + customer.service_time
        
        lines.append(f"  {customer.id:<10}| {customer.type:<18}| {demand_str:>8}| {current_load:>12.2f}| {arrival:>9.2f}| {start_svc:>9.2f}| {departure:>11.2f}| {deadline_str:>10}")
        
    # Dòng cuối: Satellite (Coll)
    final_load = current_load
    arrival_end = se_route.service_start_times.get(se_route.nodes_id[-1], 0.0) - se_route.waiting_times.get(se_route.nodes_id[-1], 0.0)
    dep_end = end_time_val
    lines.append(f"  {str(satellite.id) + ' (Coll)':<10}| {'Satellite':<18}| {se_route.total_load_pickup:>+8.2f}| {final_load:>12.2f}| {arrival_end:>9.2f}| {end_time_val:>9.2f}| {dep_end:>11.2f}| {'N/A':>10}")
    
    return "\n".join(lines)

def _format_fe_route_data(fe_route: FERouteData, problem, route_idx: int) -> str:
    lines = []
    lines.append(f"\n[FE Route #{route_idx}]")
    
    if not fe_route.schedule:
        lines.append("--- Empty FERoute ---")
        return "\n".join(lines)
        
    path_nodes = [fe_route.schedule[0]['node_id']]
    for event in fe_route.schedule[1:]:
        if event['node_id'] != path_nodes[-1]: 
            path_nodes.append(event['node_id'])
    path_str = " -> ".join(map(str, path_nodes))
    
    deadline_str = f"Route Deadline: {fe_route.route_deadline:.2f}" if fe_route.route_deadline != float('inf') else "No Deadline"
    lines.append(f"--- FERoute (Cost: {fe_route.total_dist:.2f}, Time: {fe_route.total_time:.2f}) --- {deadline_str}")
    lines.append(f"Path: {path_str}")
    
    tbl_header = (f"  {'Activity':<15}| {'Node':<6}| {'Load After':>12}| {'Arrival':>9}| {'Departure':>11}")
    lines.append(tbl_header)
    lines.append("  " + "-" * len(tbl_header))
    
    for event in fe_route.schedule:
        lines.append(f"  {event['activity']:<15}| {event['node_id']:<6}| {event['load_after']:>12.2f}| "
                     f"{event['arrival_time']:>9.2f}| {event['departure_time']:>11.2f}")
    return "\n".join(lines)

# ==============================================================================
# PUBLIC FUNCTIONS (Được gọi từ main.py)
# ==============================================================================

def print_solution_details_dop(solution_data: SolutionData, execution_time: float):
    # Cần logic tính toán lại cost một chút để hiển thị chính xác
    # Vì logic_core.calculate_objective_cost đã có sẵn, ta dùng nó gián tiếp qua VRP2E_State hoặc tính tay ở đây
    # Để đơn giản và tránh vòng lặp import, ta tính tay một cách đơn giản để hiển thị
    
    # Lưu ý: Cost chính xác đã được in ở dòng cuối của ALNS.
    # Ở đây chúng ta in chi tiết cấu trúc.
    
    print("\n" + "#"*70 + "\n### FINAL OPTIMAL SOLUTION DETAILS ###\n" + "#"*70)
    print(f"Total execution time: {execution_time:.2f} seconds")
    # Cost ở đây là tham khảo tổng dist/time, cost thực sự có trọng số nằm ở best_state.cost
    total_dist = sum(r.total_dist for r in solution_data.fe_routes) + sum(r.total_dist for r in solution_data.se_routes)
    total_travel_time = sum(r.total_travel_time for r in solution_data.fe_routes) + sum(r.total_travel_time for r in solution_data.se_routes)
    
    print(f"Total Distance: {total_dist:.2f}")
    print(f"Total Travel Time: {total_travel_time:.2f}")
    print(f"Number of FE Routes: {len(solution_data.fe_routes)}")
    print(f"Number of SE Routes: {len(solution_data.se_routes)}")
    print(f"Unserved Customers: {len(solution_data.unserved_customer_ids)}")

    print("\n--- SE ROUTES ---")
    for i, se_route in enumerate(solution_data.se_routes):
        print(_format_se_route_data(se_route, solution_data.problem, i+1))

    print("\n--- FE ROUTES ---")
    for i, fe_route in enumerate(solution_data.fe_routes):
        print(_format_fe_route_data(fe_route, solution_data.problem, i+1))

def validate_solution_feasibility_dop(solution_data: SolutionData):
    print("\n[VALIDATING SOLUTION FEASIBILITY (DOP)]")
    errors = []
    problem = solution_data.problem
    
    # 1. Check Customer Coverage
    all_served_count = len(solution_data.customer_to_se_route_idx)
    unserved_count = len(solution_data.unserved_customer_ids)
    total_problem_customers = len(problem.customers)
    
    if all_served_count + unserved_count != total_problem_customers:
        errors.append(f"Mismatch in total customer count: Served {all_served_count} + Unserved {unserved_count} != Total {total_problem_customers}")

    # 2. Validate SE Routes
    for i, se_route in enumerate(solution_data.se_routes):
        current_load = se_route.total_load_delivery
        if current_load > problem.se_vehicle_capacity + 1e-6:
             errors.append(f"SE Route #{i+1}: Initial load exceeds capacity ({current_load:.2f} > {problem.se_vehicle_capacity})")
             
        for cust_id in se_route.nodes_id[1:-1]:
            cust = problem.node_objects[cust_id]
            if cust.type == 'DeliveryCustomer': current_load -= cust.demand
            else: current_load += cust.demand
            
            if current_load < -1e-6 or current_load > problem.se_vehicle_capacity + 1e-6:
                errors.append(f"SE Route #{i+1}: Load violation at customer {cust.id} (Load: {current_load:.2f})")
                
        # Time Window Check
        for cust_id in se_route.nodes_id[1:-1]:
            cust = problem.node_objects[cust_id]
            start = se_route.service_start_times.get(cust_id)
            if start is None:
                errors.append(f"SE #{i+1}: Missing service start time for {cust.id}")
                continue
                
            if start < cust.ready_time - 1e-6: 
                errors.append(f"SE #{i+1}: Early service for {cust.id} (Start: {start:.2f} < Ready: {cust.ready_time})")
            if start > cust.due_time + 1e-6: 
                errors.append(f"SE #{i+1}: Late service for {cust.id} (Start: {start:.2f} > Due: {cust.due_time})")

    # 3. Validate FE Routes
    for i, fe_route in enumerate(solution_data.fe_routes):
        if not fe_route.schedule: continue
        # Load Check
        for event in fe_route.schedule:
            if event['load_after'] > problem.fe_vehicle_capacity + 1e-6:
                errors.append(f"FE Route #{i+1}: Capacity violation at node {event['node_id']} (Load: {event['load_after']:.2f})")
        
        # Deadline Check
        arrival_at_depot = fe_route.schedule[-1]['arrival_time']
        
        # Tìm deadline chặt nhất của các khách hàng được phục vụ bởi FE này
        deadlines = []
        for se_idx in fe_route.serviced_se_route_indices:
            se_route = solution_data.se_routes[se_idx]
            for cust_id in se_route.nodes_id[1:-1]:
                cust = problem.node_objects[cust_id]
                if isinstance(cust, PickupCustomer):
                    deadlines.append(cust.deadline)
        
        min_deadline = min(deadlines) if deadlines else float('inf')
        
        if arrival_at_depot > min_deadline + 1e-6:
            errors.append(f"FE Route #{i+1}: Deadline violation (Arrival: {arrival_at_depot:.2f} > Deadline: {min_deadline:.2f})")

    if not errors: 
        print(">> VALIDATION SUCCESS: Solution is feasible.")
    else:
        print(">> VALIDATION FAILED:")
        for e in errors: print(f"  - {e}")