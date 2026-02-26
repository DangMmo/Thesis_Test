# util_report.py
import sys
from typing import List
from model_solution import Solution
from model_problem import PickupCustomer

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

def print_solution_details(solution: Solution, execution_time: float):
    print("\n" + "#"*70 + "\n### FINAL OPTIMAL SOLUTION ###\n" + "#"*70)
    print(f"Total execution time: {execution_time:.2f} seconds")
    print(f"Objective Cost: {solution.get_objective_cost():.2f}")
    print(f"Number of FE Routes: {len(solution.fe_routes)}")
    print(f"Number of SE Routes: {len(solution.se_routes)}")
    print(f"Unserved Customers: {len(solution.unserved_customers)}")

    print("\n--- SE ROUTES ---")
    for i, se_route in enumerate(solution.se_routes):
        print(f"\n[SE Route #{i+1}]")
        print(se_route)

    print("\n--- FE ROUTES ---")
    for i, fe_route in enumerate(solution.fe_routes):
        print(f"\n[FE Route #{i+1}]")
        print(fe_route)

def validate_solution_feasibility(solution: Solution):
    print("\n[VALIDATING SOLUTION FEASIBILITY]")
    errors = []
    problem = solution.problem
    
    # 1. Check Customer Coverage
    all_served_ids = set(solution.customer_to_se_route_map.keys())
    all_problem_ids = {c.id for c in problem.customers}
    if len(all_served_ids) + len(solution.unserved_customers) != len(all_problem_ids):
        errors.append("Mismatch in total customer count.")

    # 2. Validate SE Routes
    for i, se_route in enumerate(solution.se_routes):
        current_load = se_route.total_load_delivery
        if current_load > problem.se_vehicle_capacity + 1e-6:
             errors.append(f"SE Route #{i}: Initial load exceeds capacity.")
             
        for cust_id in se_route.nodes_id[1:-1]:
            cust = problem.node_objects[cust_id]
            if cust.type == 'DeliveryCustomer': current_load -= cust.demand
            else: current_load += cust.demand
            if current_load < -1e-6 or current_load > problem.se_vehicle_capacity + 1e-6:
                errors.append(f"SE Route #{i}: Load violation at customer {cust.id}")
                
        # Time Window Check
        for cust in se_route.get_customers():
            start = se_route.service_start_times.get(cust.id)
            if start < cust.ready_time - 1e-6: errors.append(f"SE #{i}: Early service for {cust.id}")
            if start > cust.due_time + 1e-6: errors.append(f"SE #{i}: Late service for {cust.id}")

    # 3. Validate FE Routes
    for i, fe_route in enumerate(solution.fe_routes):
        if not fe_route.schedule: continue
        # Load Check
        for event in fe_route.schedule:
            if event['load_after'] > problem.fe_vehicle_capacity + 1e-6:
                errors.append(f"FE Route #{i}: Capacity violation.")
        
        # Deadline Check
        arrival_at_depot = fe_route.schedule[-1]['arrival_time']
        deadlines = {cust.deadline for se in fe_route.serviced_se_routes for cust in se.get_customers() if isinstance(cust, PickupCustomer)}
        if deadlines and arrival_at_depot > min(deadlines) + 1e-6:
            errors.append(f"FE Route #{i}: Deadline violation.")

    if not errors: print(">> VALIDATION SUCCESS: Solution is feasible.")
    else:
        print(">> VALIDATION FAILED:")
        for e in errors: print(f"  - {e}")