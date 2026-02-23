# model_problem.py
import pandas as pd
import math
import config

class Node:
    def __init__(self, node_id, x, y):
        self.id = int(node_id)
        self.x = float(x) 
        self.y = float(y)
        self.service_time = 0.0

class Depot(Node):
    def __init__(self, node_id, x, y):
        super().__init__(node_id, x, y)
        self.type = 'Depot'

class Satellite(Node):
    def __init__(self, node_id, x, y, st):
        super().__init__(node_id, x, y)
        self.type = 'Satellite'
        self.service_time = float(st)
        self.dist_id = self.id

class Customer(Node):
    def __init__(self, node_id, x, y, d, st, et, lt):
        super().__init__(node_id, x, y)
        self.demand = float(d)
        self.service_time = float(st)
        self.ready_time = float(et)
        self.due_time = float(lt)

class DeliveryCustomer(Customer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'DeliveryCustomer'

class PickupCustomer(Customer):
    def __init__(self, node_id, x, y, d, st, et, lt, deadline):
        super().__init__(node_id, x, y, d, st, et, lt)
        self.type = 'PickupCustomer'
        self.deadline = float(deadline)

class ProblemInstance:
    def __init__(self, file_path, vehicle_speed=1.0):
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()
        
        self.depot = None
        self.satellites = []
        self.customers = []
        node_objects = {}
        
        for i, row in df.iterrows():
            node = None
            if row['Type'] == 0:
                node = Depot(i, row['X'], row['Y'])
                self.depot = node
            elif row['Type'] == 1:
                node = Satellite(i, row['X'], row['Y'], row['Service Time'])
                self.satellites.append(node)
            elif row['Type'] == 2:
                node = DeliveryCustomer(i, row['X'], row['Y'], row['Demand'], row['Service Time'], row['Early'], row['Latest'])
                self.customers.append(node)
            elif row['Type'] == 3:
                node = PickupCustomer(i, row['X'], row['Y'], row['Demand'], row['Service Time'], row['Early'], row['Latest'], row['Deadline'])
                self.customers.append(node)
            
            if node:
                node_objects[i] = node
        
        self.node_objects = node_objects
        self.total_nodes = len(node_objects)
        
        for sat in self.satellites:
            sat.coll_id = sat.id + self.total_nodes
        
        self.fe_vehicle_capacity = df.iloc[0]['FE Cap']
        self.se_vehicle_capacity = df.iloc[0]['SE Cap']
        self.vehicle_speed = vehicle_speed
        
        nodes = [self.depot] + self.satellites + self.customers
        self.dist_matrix = {n1.id: {n2.id: math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2) for n2 in nodes} for n1 in nodes}
        
        self._max_dist = 0.0
        for row in self.dist_matrix.values():
            if not row: continue
            max_row = max(row.values())
            if max_row > self._max_dist:
                self._max_dist = max_row
        
        self._max_due_time = 0.0
        self._max_demand = 0.0
        for cust in self.customers:
            if cust.due_time > self._max_due_time:
                self._max_due_time = cust.due_time
            if cust.demand > self._max_demand:
                self._max_demand = cust.demand

        print("\nPre-processing for pruning candidate lists...")
        self._precompute_neighbors()
        print("Pre-processing complete.")

    def get_distance(self, n1, n2):
        return self.dist_matrix.get(n1, {}).get(n2, float('inf'))
    
    def get_travel_time(self, n1, n2):
        return self.get_distance(n1, n2) / self.vehicle_speed if self.vehicle_speed > 0 else float('inf')

    def _precompute_neighbors(self):
        self.customer_neighbors = {}
        k = config.PRUNING_K_CUSTOMER_NEIGHBORS
        if k > 0:
            for cust1 in self.customers:
                neighbors = []
                for cust2 in self.customers:
                    if cust1.id == cust2.id:
                        continue
                    dist = self.get_distance(cust1.id, cust2.id)
                    neighbors.append((cust2, dist))
                neighbors.sort(key=lambda x: x[1])
                self.customer_neighbors[cust1.id] = [neighbor_cust for neighbor_cust, dist in neighbors[:k]]

        self.satellite_neighbors = {}
        m = config.PRUNING_M_SATELLITE_NEIGHBORS
        if m > 0:
            for cust in self.customers:
                neighbors = []
                for sat in self.satellites:
                    dist = self.get_distance(cust.id, sat.id)
                    neighbors.append((sat, dist))
                neighbors.sort(key=lambda x: x[1])
                self.satellite_neighbors[cust.id] = [neighbor_sat for neighbor_sat, dist in neighbors[:m]]