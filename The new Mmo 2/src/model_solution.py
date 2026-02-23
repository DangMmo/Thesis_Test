# model_solution.py
from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass, field # <<< SỬA Ở ĐÂY: THÊM 'field' VÀO IMPORT

if TYPE_CHECKING:
    from model_problem import ProblemInstance

# ==============================================================================
# DOP DATA STRUCTURES (CẤU TRÚC DỮ LIỆU DUY NHẤT)
# ==============================================================================

@dataclass(frozen=True)
class SERouteData:
    """ Dữ liệu thuần túy, bất biến cho một SE Route. """
    satellite_id: int
    nodes_id: tuple[int, ...]
    total_dist: float
    total_travel_time: float
    total_load_pickup: float
    total_load_delivery: float
    # Lịch trình chi tiết, được tính bởi logic bên ngoài
    service_start_times: dict[int, float]
    waiting_times: dict[int, float]
    forward_time_slacks: dict[int, float]

@dataclass(frozen=True)
class FERouteData:
    """ Dữ liệu thuần túy, bất biến cho một FE Route. """
    serviced_se_route_indices: tuple[int, ...]
    schedule: tuple[dict, ...]
    total_dist: float
    total_time: float
    total_travel_time: float
    route_deadline: float

@dataclass(frozen=True)
class SolutionData:
    """ Dữ liệu thuần túy, bất biến cho toàn bộ lời giải. """
    problem: "ProblemInstance"
    fe_routes: tuple[FERouteData, ...]
    se_routes: tuple[SERouteData, ...]
    unserved_customer_ids: tuple[int, ...]
    # Map được tạo động để tăng tốc truy vấn, không phải là một phần của trạng thái cốt lõi
    customer_to_se_route_idx: dict[int, int] = field(init=False, repr=False)

    def __post_init__(self):
        # Tạo map sau khi đối tượng được khởi tạo
        # Dùng object.__setattr__ vì dataclass là frozen=True
        cust_map = {
            cust_id: se_idx
            for se_idx, se_route in enumerate(self.se_routes)
            for cust_id in se_route.nodes_id[1:-1]
        }
        object.__setattr__(self, 'customer_to_se_route_idx', cust_map)

# ==============================================================================
# STATE MANAGEMENT (QUẢN LÝ TRẠNG THÁI)
# ==============================================================================

class VRP2E_State:
    def __init__(self, solution_data: SolutionData): 
        self.solution_data = solution_data
        self._cost = None

    def copy(self):
        # Vì solution_data là bất biến, "copy" nông là đủ và rất nhanh
        return VRP2E_State(self.solution_data)
    
    @property
    def cost(self) -> float:
        if self._cost is None:
            from logic_core import calculate_objective_cost 
            self._cost = calculate_objective_cost(self.solution_data)
        return self._cost

# Các lớp OOP cũ (Solution, SERoute, FERoute, ChangeContext, Memento) đã được XÓA.
# Các hàm convert (convert_data_to_solution, convert_solution_to_data) đã được XÓA.