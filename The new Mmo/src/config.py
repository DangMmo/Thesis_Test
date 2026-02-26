# config.py
import random

# ==============================================================================
# 1. CẤU HÌNH BÀI TOÁN & DỮ LIỆU
# ==============================================================================
FILE_PATH = "C:\\Users\\Dang\\Documents\\Thesis\\The new Mmo\\src\\CS-9C.csv"
VEHICLE_SPEED = 666.0  

# ==============================================================================
# 2. CẤU HÌNH GIAI ĐOẠN TẠO LỜI GIẢI BAN ĐẦU
# ==============================================================================
LNS_INITIAL_ITERATIONS = 10
Q_PERCENTAGE_INITIAL = 0.4

# ==============================================================================
# 3. CẤU HÌNH GIAI ĐOẠN ALNS CHÍNH
# ==============================================================================
ALNS_MAIN_ITERATIONS = 50
START_TEMP_ACCEPT_PROB = 0.5
START_TEMP_WORSENING_PCT = 0.05
COOLING_RATE = 0.9995
REACTION_FACTOR = 0.1
SEGMENT_LENGTH = 100
SIGMA_1_NEW_BEST = 9.0
SIGMA_2_BETTER = 5.0
SIGMA_3_ACCEPTED = 2.0
Q_SMALL_RANGE = (0.04, 0.3)
Q_LARGE_RANGE = (0.55, 0.8)
SMALL_DESTROY_SEGMENT_LENGTH = 500
RESTART_THRESHOLD = 2000

# ==============================================================================
# 4. CẤU HÌNH CHUNG
# ==============================================================================
RANDOM_SEED = 42

# ==============================================================================
# 5. CẤU HÌNH PRUNING (CẮT TỈA)
# ==============================================================================
PRUNING_K_CUSTOMER_NEIGHBORS = 10
PRUNING_M_SATELLITE_NEIGHBORS = 3
PRUNING_N_SE_ROUTE_CANDIDATES = 2

# ==============================================================================
# 6. CẤU HÌNH HÀM MỤC TIÊU
# ==============================================================================
PRIMARY_OBJECTIVE = "TRAVEL_TIME" 
OPTIMIZE_VEHICLE_COUNT = True
WEIGHT_PRIMARY = 1.0
WEIGHT_FE_VEHICLE = 1000.0
WEIGHT_SE_VEHICLE = 200.0

# ==============================================================================
# 7. CẤU HÌNH KHÁC
# ==============================================================================
CLEAR_OLD_RESULTS_ON_START = False
RESULTS_BASE_DIR = "results"