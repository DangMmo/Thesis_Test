# ops_repair.py
import random
from typing import List, Dict

from model_solution import SERoute, FERoute, Solution, ChangeContext
from model_problem import Customer
from logic_core import (
    InsertionProcessor, 
    find_best_global_insertion_option, 
    find_k_best_global_insertion_options, 
    _recalculate_fe_route_and_check_feasibility
)

def _perform_insertion(solution: Solution, context: ChangeContext, customer_to_insert: Customer, best_option: Dict):
    problem = solution.problem
    option_type = best_option.get('type')

    # 1. Backup Phase
    if option_type == 'insert_into_existing_se':
        se_route = best_option['se_route']
        if se_route.serving_fe_routes:
            fe_route = list(se_route.serving_fe_routes)[0]
            context.backup_route(se_route)
            context.backup_route(fe_route)
    elif option_type == 'create_new_se_expand_fe':
        fe_route = best_option['fe_route']
        context.backup_route(fe_route)
    
    # 2. Execution Phase
    if option_type == 'insert_into_existing_se':
        se_route, pos = best_option['se_route'], best_option['se_pos']
        if se_route.serving_fe_routes:
            fe_route = list(se_route.serving_fe_routes)[0]
            se_route.insert_customer_at_pos(customer_to_insert, pos)
            _recalculate_fe_route_and_check_feasibility(fe_route, problem)
        else:
             if customer_to_insert not in solution.unserved_customers:
                solution.unserved_customers.append(customer_to_insert)

    elif option_type == 'create_new_se_new_fe':
        satellite = best_option['new_satellite']
        new_se = SERoute(satellite, problem)
        new_se.insert_customer_at_pos(customer_to_insert, 1)
        solution.add_se_route(new_se)
        context.track_new_route(new_se)
        
        new_fe = FERoute(problem)
        solution.add_fe_route(new_fe)
        context.track_new_route(new_fe)
        
        solution.link_routes(new_fe, new_se)
        _recalculate_fe_route_and_check_feasibility(new_fe, problem)

    elif option_type == 'create_new_se_expand_fe':
        satellite, fe_route = best_option['new_satellite'], best_option['fe_route']
        new_se = SERoute(satellite, problem)
        new_se.insert_customer_at_pos(customer_to_insert, 1)
        solution.add_se_route(new_se)
        context.track_new_route(new_se)
        
        solution.link_routes(fe_route, new_se)
        _recalculate_fe_route_and_check_feasibility(fe_route, problem)
        
    else:
        if customer_to_insert not in solution.unserved_customers:
            solution.unserved_customers.append(customer_to_insert)
    
    solution.update_customer_map()


def greedy_repair(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    customers = list(customers_to_insert)
    random.shuffle(customers)

    for customer in customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)
                
def regret_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer], k: int = 4):
    insertion_processor = InsertionProcessor(solution.problem)
    remaining_customers = list(customers_to_insert)

    while remaining_customers:
        best_customer_to_insert = None
        max_regret = -float('inf')
        best_option_for_max_regret_customer = None

        for customer in remaining_customers:
            best_options = find_k_best_global_insertion_options(customer, solution, insertion_processor, k)
            if not best_options: continue
            
            best_cost = best_options[0]['objective_increase']
            regret = sum(opt['objective_increase'] - best_cost for opt in best_options[1:])
            
            if regret > max_regret:
                max_regret = regret
                best_customer_to_insert = customer
                best_option_for_max_regret_customer = best_options[0]

        if best_customer_to_insert is None:
            solution.unserved_customers.extend(remaining_customers)
            break

        _perform_insertion(solution, context, best_customer_to_insert, best_option_for_max_regret_customer)
        remaining_customers.remove(best_customer_to_insert)

def earliest_deadline_first_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: getattr(c, 'deadline', float('inf')))
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def farthest_first_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    problem = solution.problem
    insertion_processor = InsertionProcessor(problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: problem.get_distance(c.id, problem.depot.id), reverse=True)
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def largest_first_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: c.demand, reverse=True)
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def closest_first_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    problem = solution.problem
    insertion_processor = InsertionProcessor(problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: problem.get_distance(c.id, problem.depot.id))
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def earliest_time_window_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: c.ready_time)
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def latest_time_window_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: c.due_time, reverse=True)
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)

def latest_deadline_first_insertion(solution: Solution, context: ChangeContext, customers_to_insert: List[Customer]):
    insertion_processor = InsertionProcessor(solution.problem)
    sorted_customers = sorted(customers_to_insert, key=lambda c: getattr(c, 'deadline', float('-inf')), reverse=True)
    for customer in sorted_customers:
        best_option = find_best_global_insertion_option(customer, solution, insertion_processor)
        _perform_insertion(solution, context, customer, best_option)