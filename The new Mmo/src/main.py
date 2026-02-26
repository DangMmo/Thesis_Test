# main.py
import time
import os
import sys
import shutil
import datetime
import random

import config
from model_problem import ProblemInstance
from algo_initial import generate_initial_solution
from algo_alns import run_alns_phase
from util_report import Logger, print_solution_details, validate_solution_feasibility
from util_plot import plot_solution_visualization, plot_alns_history

# Import Operators Maps
from ops_destroy import (
    random_removal, shaw_removal, worst_slack_removal, 
    worst_cost_removal, route_removal, satellite_removal, 
    least_utilized_route_removal
)
from ops_repair import (
    greedy_repair, regret_insertion, earliest_deadline_first_insertion,
    farthest_first_insertion, largest_first_insertion, closest_first_insertion,
    earliest_time_window_insertion, latest_time_window_insertion,
    latest_deadline_first_insertion
)

def main():
    # --- FIX PATH: Lấy đường dẫn tuyệt đối của thư mục chứa file main.py ---
    # Điều này đảm bảo code chạy được dù bạn đứng ở bất kỳ đâu trong terminal
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Setup Environment
    if config.CLEAR_OLD_RESULTS_ON_START:
        # Xây dựng đường dẫn results dựa trên base_dir
        results_path = os.path.join(base_dir, config.RESULTS_BASE_DIR)
        if os.path.exists(results_path):
            shutil.rmtree(results_path)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Tạo thư mục run bên trong thư mục results nằm cạnh file code
    run_dir = os.path.join(base_dir, config.RESULTS_BASE_DIR, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    sys.stdout = Logger(os.path.join(run_dir, "log.txt"), sys.stdout)
    
    # --- FIX ERROR: Copy config dùng đường dẫn tuyệt đối ---
    config_src_path = os.path.join(base_dir, 'config.py')
    shutil.copy(config_src_path, os.path.join(run_dir, 'config_snapshot.py'))

    start_time = time.time()
    random.seed(config.RANDOM_SEED)

    print(f"=== VRP 2-ECHELON SOLVER STARTED ===")
    print(f"Run ID: {timestamp}")
    print(f"Working Directory: {base_dir}")
    
    # 2. Load Problem
    try:
        problem = ProblemInstance(file_path=config.FILE_PATH, vehicle_speed=config.VEHICLE_SPEED)
    except Exception as e:
        print(f"Error loading problem: {e}")
        return

    # 3. Define Operators
    destroy_ops = {
        "random": random_removal, "shaw": shaw_removal,
        "worst_slack": worst_slack_removal, "worst_cost": worst_cost_removal,
        "route": route_removal, "satellite": satellite_removal,
        "least_utilized": least_utilized_route_removal,
    }
    repair_ops = {
        "greedy": greedy_repair, "regret": regret_insertion,
        "earliest_deadline": earliest_deadline_first_insertion, 
        "farthest": farthest_first_insertion,
        "largest": largest_first_insertion, "closest": closest_first_insertion,
        "earliest_tw": earliest_time_window_insertion, 
        "latest_tw": latest_time_window_insertion,
        "latest_deadline": latest_deadline_first_insertion,
    }

    # 4. Run Algorithms
    # Stage 1: Initial Solution
    initial_state = generate_initial_solution(
        problem, 
        lns_iterations=config.LNS_INITIAL_ITERATIONS, 
        q_percentage=config.Q_PERCENTAGE_INITIAL
    )
    
    # Stage 2: ALNS
    best_state, (run_history, op_history) = run_alns_phase(
        initial_state=initial_state,
        iterations=config.ALNS_MAIN_ITERATIONS,
        destroy_operators=destroy_ops,
        repair_operators=repair_ops
    )
    
    final_solution = best_state.solution
    end_time = time.time()

    # 5. Report & Visualize
    print_solution_details(final_solution, execution_time=end_time - start_time)
    validate_solution_feasibility(final_solution)
    
    print("\nGenerating plots...")
    plot_solution_visualization(final_solution, save_dir=run_dir)
    plot_alns_history(run_history, op_history, save_dir=run_dir)
    
    print(f"\nRun complete. Results saved to: {run_dir}")

if __name__ == "__main__":
    main()