# util_plot.py
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import os
from typing import Dict, List
from model_solution import Solution

def _get_unique_nodes_from_fe_schedule(schedule: List[Dict]) -> List[int]:
    if not schedule: return []
    path_nodes = [schedule[0]['node_id']]
    for event in schedule[1:]:
        if event['node_id'] != path_nodes[-1]:
            path_nodes.append(event['node_id'])
    return path_nodes

def plot_solution_visualization(solution: Solution, save_dir: str):
    if not solution: return

    problem = solution.problem
    fig, ax = plt.subplots(figsize=(20, 16))

    num_fe_routes = len(solution.fe_routes)
    fe_route_colors = plt.cm.get_cmap('tab20', num_fe_routes if num_fe_routes > 0 else 1)

    satellite_to_color_map: Dict[int, any] = {}
    for i, fe_route in enumerate(solution.fe_routes):
        color = fe_route_colors(i)
        for se_route in fe_route.serviced_se_routes:
            satellite_to_color_map[se_route.satellite.id] = color

    ax.scatter([c.x for c in problem.customers], [c.y for c in problem.customers], c='cornflowerblue', marker='o', s=50, label='Customer', zorder=3)
    ax.scatter([s.x for s in problem.satellites], [s.y for s in problem.satellites], c='limegreen', marker='s', s=150, label='Satellite', edgecolors='black', zorder=4)
    ax.scatter(problem.depot.x, problem.depot.y, c='black', marker='*', s=500, label='Depot', edgecolors='white', zorder=5)

    for node in problem.node_objects.values():
        ax.text(node.x, node.y + 1, str(node.id), fontsize=9, ha='center')

    for se_route in solution.se_routes:
        color = satellite_to_color_map.get(se_route.satellite.id, 'gray')
        path_node_ids = [nid % problem.total_nodes for nid in se_route.nodes_id]
        path_coords = [(problem.node_objects[nid].x, problem.node_objects[nid].y) for nid in path_node_ids]
        x_coords, y_coords = zip(*path_coords)
        ax.plot(x_coords, y_coords, color=color, linestyle='-', linewidth=1.2, alpha=0.8, zorder=1)

    for i, fe_route in enumerate(solution.fe_routes):
        color = fe_route_colors(i)
        path_node_ids = _get_unique_nodes_from_fe_schedule(fe_route.schedule)
        if not path_node_ids: continue
        path_coords = [(problem.node_objects[nid].x, problem.node_objects[nid].y) for nid in path_node_ids]
        x_coords, y_coords = zip(*path_coords)
        ax.plot(x_coords, y_coords, color=color, linestyle='--', linewidth=3, alpha=0.9, zorder=2)

    ax.set_title(f"2E-VRP Solution (Total Cost: {solution.get_objective_cost():.2f})", fontsize=18)
    ax.set_aspect('equal')
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "solution_visualization.png"), dpi=300)
    plt.close()

def plot_alns_history(run_history: Dict, op_history: Dict, save_dir: str):
    if not run_history or not run_history['iteration']: return

    # 1. Convergence
    fig, ax1 = plt.subplots(figsize=(15, 7))
    ax1.plot(run_history['iteration'], run_history['best_cost'], label='Best Cost', color='green')
    ax1.plot(run_history['iteration'], run_history['current_cost'], label='Current Cost', color='blue', alpha=0.6)
    ax2 = ax1.twinx()
    ax2.plot(run_history['iteration'], run_history['temperature'], label='Temperature', color='red', linestyle='--')
    plt.title('Algorithm Convergence')
    plt.savefig(os.path.join(save_dir, "convergence.png"), dpi=300)
    plt.close()

    # 2. Operator Weights
    if op_history and op_history['iteration']:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True)
        destroy_df = pd.DataFrame(op_history['destroy_weights'])
        for op in destroy_df.columns: ax1.plot(op_history['iteration'], destroy_df[op], label=op)
        ax1.legend(); ax1.set_title('Destroy Operator Weights')
        
        repair_df = pd.DataFrame(op_history['repair_weights'])
        for op in repair_df.columns: ax2.plot(op_history['iteration'], repair_df[op], label=op)
        ax2.legend(); ax2.set_title('Repair Operator Weights')
        plt.savefig(os.path.join(save_dir, "operator_weights.png"), dpi=300)
        plt.close()