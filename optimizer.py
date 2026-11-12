"""
optimizer.py
------------
Mathematical Modelling and Optimization Engine for Logistics Route Optimization.
Formulates and solves the Travelling Salesperson Problem (TSP) using Google OR-Tools.

Model Formulation:
------------------
Decision-Making Under Conditions of Certainty:
Known distances, fixed fuel prices, and deterministic vehicle fuel consumption.

Objective Function:
    Minimize Z = sum_{i, j} (C_ij * X_ij)
Where:
    C_ij = D_ij * (F / 100) * P
    D_ij = Distance between location i and location j (in km)
    F    = Vehicle fuel consumption rate (litres per 100 km)
    P    = Fuel price per unit volume ($ / litre)
    X_ij = Binary decision variable (1 if route travels from i to j, 0 otherwise)

Constraints:
    1. Vehicle starts at the selected depot.
    2. Every customer/delivery location must be visited exactly once.
    3. Vehicle must return to the starting depot.
    4. Subtour elimination (enforced by OR-Tools RoutingModel).
    5. Minimize total fuel cost.
"""

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def calculate_fuel_and_cost(distance_km, fuel_consumption_per_100km, fuel_price_per_litre):
    """
    Computes estimated fuel used (litres) and fuel cost (currency) for a given distance.
    Formula:
        fuel_litres = distance_km * (fuel_consumption_per_100km / 100.0)
        fuel_cost   = fuel_litres * fuel_price_per_litre
    """
    fuel_litres = float(distance_km) * (float(fuel_consumption_per_100km) / 100.0)
    fuel_cost = fuel_litres * float(fuel_price_per_litre)
    return round(fuel_litres, 2), round(fuel_cost, 2)

def build_route_details(route_indices, ordered_locations, sub_matrix, fuel_consumption, fuel_price):
    """
    Build leg-by-leg breakdown and summary metrics for an ordered route sequence.
    """
    legs = []
    total_distance = 0.0

    for i in range(len(route_indices) - 1):
        u_idx = route_indices[i]
        v_idx = route_indices[i + 1]

        origin_loc = ordered_locations[u_idx]
        dest_loc = ordered_locations[v_idx]
        leg_dist = sub_matrix[u_idx][v_idx]

        leg_fuel, leg_cost = calculate_fuel_and_cost(leg_dist, fuel_consumption, fuel_price)
        total_distance += leg_dist

        legs.append({
            "step": i + 1,
            "origin_id": origin_loc["id"],
            "origin_name": origin_loc["name"],
            "destination_id": dest_loc["id"],
            "destination_name": dest_loc["name"],
            "distance_km": round(leg_dist, 2),
            "fuel_litres": leg_fuel,
            "fuel_cost": leg_cost,
        })

    total_fuel, total_cost = calculate_fuel_and_cost(total_distance, fuel_consumption, fuel_price)
    route_names = [ordered_locations[idx]["name"] for idx in route_indices]

    return {
        "route_indices": route_indices,
        "route_names": route_names,
        "route_display": " → ".join(route_names),
        "legs": legs,
        "total_distance_km": round(total_distance, 2),
        "total_fuel_litres": total_fuel,
        "total_fuel_cost": total_cost,
    }

def solve_tsp(depot_id, delivery_ids, all_locations_dict, full_distance_matrix, fuel_consumption, fuel_price):
    """
    Solves the Travelling Salesperson Problem using Google OR-Tools.

    Parameters:
    -----------
    depot_id : int
        The ID of the starting depot location.
    delivery_ids : list of int
        The IDs of the locations to be visited.
    all_locations_dict : dict of {loc_id: loc_dict}
        Lookup for location information.
    full_distance_matrix : dict of {(orig_id, dest_id): distance_km}
        Full distance lookup.
    fuel_consumption : float
        Litres per 100 km (F).
    fuel_price : float
        Price per litre (P).

    Returns:
    --------
    dict containing:
        - success: bool
        - status: str
        - optimal_route: dict (metrics, legs, display)
        - original_route: dict (metrics, legs, display)
        - comparison: dict (savings, percentage reduction)
        - mathematical_explanation: dict
    """
    # Validation
    if not delivery_ids:
        return {
            "success": False,
            "error": "At least one delivery location must be selected.",
            "status": "No delivery locations selected"
        }

    # Construct ordered sub-nodes: Node 0 is always the Depot
    depot_loc = all_locations_dict.get(depot_id)
    if not depot_loc:
        return {
            "success": False,
            "error": "Specified depot not found.",
            "status": "Invalid depot"
        }

    sub_locations = [depot_loc]
    for d_id in delivery_ids:
        if d_id != depot_id and d_id in all_locations_dict:
            sub_locations.append(all_locations_dict[d_id])

    num_nodes = len(sub_locations)

    # Build sub-matrix of distances and fuel costs
    sub_distance_matrix = []
    sub_cost_matrix = []

    for i in range(num_nodes):
        dist_row = []
        cost_row = []
        u_id = sub_locations[i]["id"]
        for j in range(num_nodes):
            v_id = sub_locations[j]["id"]
            if i == j:
                dist = 0.0
            else:
                dist = full_distance_matrix.get((u_id, v_id), 0.0)
            
            _, cost = calculate_fuel_and_cost(dist, fuel_consumption, fuel_price)
            dist_row.append(dist)
            cost_row.append(cost)
        sub_distance_matrix.append(dist_row)
        sub_cost_matrix.append(cost_row)

    # 1. Determine Default / Original Route:
    # Natural sequential order: Depot -> delivery_1 -> delivery_2 -> ... -> Depot
    original_indices = list(range(num_nodes)) + [0]
    original_route_details = build_route_details(
        original_indices, sub_locations, sub_distance_matrix, fuel_consumption, fuel_price
    )

    # If only 1 delivery location, optimal is trivially identical to original
    if num_nodes == 2:
        optimal_route_details = original_route_details
        comparison = {
            "distance_saved_km": 0.0,
            "fuel_saved_litres": 0.0,
            "cost_saved": 0.0,
            "percentage_reduction": 0.0,
            "explanation": "With only one delivery destination, the outbound and inbound route is unique."
        }
        return {
            "success": True,
            "status": "Optimal Solution Found",
            "optimal_route": optimal_route_details,
            "original_route": original_route_details,
            "comparison": comparison,
            "sub_locations": sub_locations,
            "sub_distance_matrix": sub_distance_matrix,
        }

    # 2. Formulate and Solve with Google OR-Tools
    # Create the routing index manager: num_nodes, 1 vehicle, depot at index 0
    manager = pywrapcp.RoutingIndexManager(num_nodes, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Arc cost evaluator: We optimize the total fuel cost in integer cents
    # Since Cost = Distance * (F/100) * P, minimizing cost in cents (or distance in meters)
    # is mathematically guaranteed to find the minimum fuel cost TSP tour.
    def cost_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Cost in integer cents to maintain high precision
        cost_in_cents = int(round(sub_cost_matrix[from_node][to_node] * 100))
        return cost_in_cents

    transit_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Search parameters: PATH_CHEAPEST_ARC initial heuristic + GUIDED_LOCAL_SEARCH metaheuristic
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 2

    # Solve
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {
            "success": False,
            "error": "Google OR-Tools could not find a valid routing solution.",
            "status": "Infeasible / No Solution"
        }

    # Extract the optimal tour
    optimal_indices = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        optimal_indices.append(node)
        index = solution.Value(routing.NextVar(index))
    optimal_indices.append(manager.IndexToNode(index))  # Return to depot (node 0)

    optimal_route_details = build_route_details(
        optimal_indices, sub_locations, sub_distance_matrix, fuel_consumption, fuel_price
    )

    # 3. Decision Analysis & Comparative Metrics
    dist_saved = round(original_route_details["total_distance_km"] - optimal_route_details["total_distance_km"], 2)
    fuel_saved = round(original_route_details["total_fuel_litres"] - optimal_route_details["total_fuel_litres"], 2)
    cost_saved = round(original_route_details["total_fuel_cost"] - optimal_route_details["total_fuel_cost"], 2)

    if original_route_details["total_fuel_cost"] > 0:
        pct_reduction = round((cost_saved / original_route_details["total_fuel_cost"]) * 100.0, 2)
    else:
        pct_reduction = 0.0

    comparison = {
        "distance_saved_km": max(dist_saved, 0.0),
        "fuel_saved_litres": max(fuel_saved, 0.0),
        "cost_saved": max(cost_saved, 0.0),
        "percentage_reduction": max(pct_reduction, 0.0),
        "explanation": (
            f"The optimized delivery sequence saves {max(dist_saved, 0.0):.1f} km "
            f"and ${max(cost_saved, 0.0):.2f} in fuel costs ({max(pct_reduction, 0.0):.1f}% reduction) "
            f"compared to the unoptimized default order."
        )
    }

    return {
        "success": True,
        "status": "Optimal Solution Found",
        "optimal_route": optimal_route_details,
        "original_route": original_route_details,
        "comparison": comparison,
        "sub_locations": sub_locations,
        "sub_distance_matrix": sub_distance_matrix,
    }
