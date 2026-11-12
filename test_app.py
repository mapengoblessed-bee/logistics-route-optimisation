"""
test_app.py
-----------
Comprehensive automated test suite for the Logistics Route Optimization DSS.
Verifies database integrity, mathematical model accuracy, OR-Tools TSP solving,
decision comparison logic, and Flask web routes.
"""

import unittest
import json
import database
import optimizer
from app import app

class LogisticsDSSTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        database.init_db(reset=True)
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        # Reset DB before tests to ensure consistent state
        database.init_db(reset=True)

    def test_database_initialization(self):
        """Verify database tables, default locations, and distances are correctly seeded."""
        locations = database.get_all_locations()
        self.assertEqual(len(locations), 6)

        loc_names = [l["name"] for l in locations]
        self.assertIn("Depot (Starting Point)", loc_names)
        self.assertIn("Harare", loc_names)
        self.assertIn("Bulawayo", loc_names)
        self.assertIn("Gweru", loc_names)
        self.assertIn("Mutare", loc_names)
        self.assertIn("Masvingo", loc_names)

        _, matrix = database.get_distance_matrix_dict()
        # Verify self-distances are 0.0
        for loc in locations:
            self.assertEqual(matrix[(loc["id"], loc["id"])], 0.0)

    def test_fuel_and_cost_calculation(self):
        """Test accuracy of fuel and cost formulas: C_ij = D_ij * (F / 100) * P."""
        distance = 100.0  # km
        consumption = 28.0  # L / 100 km
        price = 1.65  # $ / L

        litres, cost = optimizer.calculate_fuel_and_cost(distance, consumption, price)
        self.assertAlmostEqual(litres, 28.0, places=2)
        self.assertAlmostEqual(cost, 28.0 * 1.65, places=2)

        # Distance = 439 km (Harare to Bulawayo)
        dist_h_b = 439.0
        litres_hb, cost_hb = optimizer.calculate_fuel_and_cost(dist_h_b, consumption, price)
        expected_litres = 439.0 * 0.28  # 122.92
        expected_cost = expected_litres * 1.65  # 202.818
        self.assertAlmostEqual(litres_hb, 122.92, places=2)
        self.assertAlmostEqual(cost_hb, round(expected_cost, 2), places=2)

    def test_tsp_optimization_all_locations(self):
        """Test TSP optimization with all 5 delivery destinations from Depot."""
        locations, matrix = database.get_distance_matrix_dict()
        loc_dict = {l["id"]: l for l in locations}

        depot = next(l for l in locations if l["name"] == "Depot (Starting Point)")
        deliveries = [l["id"] for l in locations if l["id"] != depot["id"]]

        fuel_consumption = 28.0
        fuel_price = 1.65

        result = optimizer.solve_tsp(
            depot_id=depot["id"],
            delivery_ids=deliveries,
            all_locations_dict=loc_dict,
            full_distance_matrix=matrix,
            fuel_consumption=fuel_consumption,
            fuel_price=fuel_price
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "Optimal Solution Found")

        optimal_route = result["optimal_route"]
        # Verify closed loop: starts and ends at Depot
        self.assertEqual(optimal_route["route_names"][0], "Depot (Starting Point)")
        self.assertEqual(optimal_route["route_names"][-1], "Depot (Starting Point)")

        # Verify all delivery locations are visited exactly once
        visited_deliveries = optimal_route["route_names"][1:-1]
        self.assertEqual(len(visited_deliveries), len(deliveries))
        self.assertEqual(len(set(visited_deliveries)), len(deliveries))

        # Check Decision Comparison metrics
        comp = result["comparison"]
        self.assertGreater(result["original_route"]["total_distance_km"], 0)
        self.assertGreater(optimal_route["total_distance_km"], 0)
        # Optimal distance should be less than or equal to unoptimized default route
        self.assertLessEqual(optimal_route["total_distance_km"], result["original_route"]["total_distance_km"])
        self.assertGreaterEqual(comp["distance_saved_km"], 0.0)
        self.assertGreaterEqual(comp["cost_saved"], 0.0)
        self.assertGreaterEqual(comp["percentage_reduction"], 0.0)

    def test_tsp_single_delivery(self):
        """Test edge case with only 1 delivery destination."""
        locations, matrix = database.get_distance_matrix_dict()
        loc_dict = {l["id"]: l for l in locations}
        depot = locations[0]
        single_delivery = [locations[1]["id"]]

        result = optimizer.solve_tsp(
            depot_id=depot["id"],
            delivery_ids=single_delivery,
            all_locations_dict=loc_dict,
            full_distance_matrix=matrix,
            fuel_consumption=25.0,
            fuel_price=1.50
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["optimal_route"]["legs"]), 2)
        # Outbound and inbound
        self.assertEqual(result["comparison"]["percentage_reduction"], 0.0)

    def test_flask_index_page(self):
        """Test GET / returns 200 and contains key DSS dashboard elements."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        # Required header and sections
        self.assertIn("Logistics Route Optimization System", html)
        self.assertIn("A Decision Support System for minimizing delivery transportation costs.", html)
        self.assertIn("Find Optimal Route", html)
        self.assertIn("Distance Matrix", html)
        self.assertIn("Decision Analysis: Unoptimized vs. Optimized Route", html)
        self.assertIn("Optimal Delivery Sequence", html)

    def test_flask_optimize_endpoint_json(self):
        """Test POST /optimize with JSON payload."""
        locations = database.get_all_locations()
        payload = {
            "depot_id": locations[0]["id"],
            "delivery_ids": [locations[1]["id"], locations[2]["id"], locations[3]["id"]],
            "fuel_price": 1.70,
            "fuel_consumption": 30.0
        }

        response = self.client.post(
            "/optimize",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Optimal Solution Found")
        self.assertIn("optimal_route", data)
        self.assertIn("comparison", data)
        self.assertIn("percentage_reduction", data["comparison"])

    def test_flask_validation_errors(self):
        """Test validation on negative fuel price and empty deliveries."""
        # Negative fuel price
        payload_neg = {
            "depot_id": 1,
            "delivery_ids": [2, 3],
            "fuel_price": -1.5,
            "fuel_consumption": 28.0
        }
        res = self.client.post("/optimize", data=json.dumps(payload_neg), content_type="application/json")
        self.assertEqual(res.status_code, 400)

        # Empty delivery IDs
        payload_empty = {
            "depot_id": 1,
            "delivery_ids": [],
            "fuel_price": 1.5,
            "fuel_consumption": 28.0
        }
        res2 = self.client.post("/optimize", data=json.dumps(payload_empty), content_type="application/json")
        self.assertEqual(res2.status_code, 400)

    def test_distance_matrix_update_and_reset(self):
        """Test updating distance values and resetting back to defaults."""
        locations, _ = database.get_distance_matrix_dict()
        loc1 = locations[0]["id"]
        loc2 = locations[1]["id"]

        # Update distance
        update_res = self.client.post(
            "/update_distance",
            data=json.dumps({"origin_id": loc1, "destination_id": loc2, "distance_km": 999.0}),
            content_type="application/json"
        )
        self.assertEqual(update_res.status_code, 200)

        _, updated_mat = database.get_distance_matrix_dict()
        self.assertEqual(updated_mat[(loc1, loc2)], 999.0)
        self.assertEqual(updated_mat[(loc2, loc1)], 999.0)

        # Reset to defaults
        reset_res = self.client.post("/reset_distances", content_type="application/json")
        self.assertEqual(reset_res.status_code, 200)

        _, reset_mat = database.get_distance_matrix_dict()
        self.assertEqual(reset_mat[(loc1, loc2)], 15.0)

if __name__ == "__main__":
    unittest.main()
