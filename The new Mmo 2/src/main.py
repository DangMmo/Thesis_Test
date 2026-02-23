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
# Sử dụng các hàm báo cáo và vẽ đồ thị phiên bản DOP
from util_report import Logger, print_solution_details_dop, validate_solution_feasibility_dop
from util_plot import plot_solution_visualization_dop, plot_alns_history

# Import các toán tử phá hủy và sửa chữa phiên bản DOP
from ops_destroy import (
    random_removal, 
    shaw_removal, 
    worst_cost_removal
)
from ops_repair import (
    greedy_repair
)

def main():
    # --- SETUP ENVIRONMENT ---
    # Lấy đường dẫn tuyệt đối của thư mục chứa file main.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Dọn dẹp kết quả cũ nếu được cấu hình
    if config.CLEAR_OLD_RESULTS_ON_START:
        results_path = os.path.join(base_dir, config.RESULTS_BASE_DIR)
        if os.path.exists(results_path):
            shutil.rmtree(results_path)
    
    # Tạo thư mục lưu kết quả cho lượt chạy này
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = os.path.join(base_dir, config.RESULTS_BASE_DIR, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Thiết lập Logger để ghi log song song ra màn hình và file
    sys.stdout = Logger(os.path.join(run_dir, "log.txt"), sys.stdout)
    
    # Lưu lại bản sao của config để đối chiếu sau này
    config_src_path = os.path.join(base_dir, 'config.py')
    shutil.copy(config_src_path, os.path.join(run_dir, 'config_snapshot.py'))

    start_time = time.time()
    random.seed(config.RANDOM_SEED)

    print(f"=== VRP 2-ECHELON SOLVER STARTED (DOP ARCHITECTURE) ===")
    print(f"Run ID: {timestamp}")
    print(f"Working Directory: {base_dir}")
    
    # 2. LOAD PROBLEM
    try:
        problem = ProblemInstance(file_path=config.FILE_PATH, vehicle_speed=config.VEHICLE_SPEED)
    except Exception as e:
        print(f"Error loading problem: {e}")
        return

    # 3. DEFINE DOP OPERATORS
    # Chỉ bao gồm các toán tử đã được refactor sang kiến trúc DOP
    destroy_ops = {
        "random": random_removal, 
        "shaw": shaw_removal,
        "worst_cost": worst_cost_removal,
        # Lưu ý: Các toán tử khác (worst_slack, route_removal...) 
        # cần được refactor sang DOP trước khi thêm vào đây.
    }
    repair_ops = {
        "greedy": greedy_repair,
        # Lưu ý: Toán tử regret cần được refactor sang DOP trước khi thêm vào đây.
    }

    # 4. RUN ALGORITHMS
    
    # Giai đoạn 1: Tạo lời giải ban đầu (Kết quả là VRP2E_State chứa SolutionData)
    initial_state = generate_initial_solution(
        problem, 
        lns_iterations=config.LNS_INITIAL_ITERATIONS, 
        q_percentage=config.Q_PERCENTAGE_INITIAL
    )
    
    # Giai đoạn 2: Chạy ALNS chính (Hoạt động trực tiếp trên cấu trúc dữ liệu bất biến)
    best_state, (run_history, op_history) = run_alns_phase(
        initial_state=initial_state,
        iterations=config.ALNS_MAIN_ITERATIONS,
        destroy_operators=destroy_ops,
        repair_operators=repair_ops
    )
    
    # Lấy dữ liệu lời giải tốt nhất
    final_solution_data = best_state.solution_data
    end_time = time.time()

    # 5. REPORT & VISUALIZE
    # Sử dụng các hàm tiện ích hỗ trợ SolutionData (DOP)
    print_solution_details_dop(final_solution_data, execution_time=end_time - start_time)
    validate_solution_feasibility_dop(final_solution_data)
    
    print("\nGenerating plots...")
    plot_solution_visualization_dop(final_solution_data, save_dir=run_dir)
    plot_alns_history(run_history, op_history, save_dir=run_dir)
    
    print(f"\nRun complete. Results saved to: {run_dir}")
    print(f"Final Objective Cost: {best_state.cost:.2f}")

if __name__ == "__main__":
    main()