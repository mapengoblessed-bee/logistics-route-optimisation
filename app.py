"""
app.py
------
Flask application for the Logistics Route Optimization Decision Support System.
Handles routes for web UI, distance matrix updates, and OR-Tools optimization.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import database
import optimizer

app = Flask(__name__)
app.secret_key = "logistics_dss_secret_key_2026"

# Ensure database is initialized on startup
database.init_db()

@app.route("/", methods=["GET"])
def index():
    """
    Main dashboard view.
    Loads locations, distance matrix, and default parameters.
    Performs initial default optimization for instant demonstration.
    """
    locations, distance_matrix = database.get_distance_matrix_dict()
    loc_dict = {loc["id"]: loc for loc in locations}

    # Retrieve default parameters
    fuel_price = float(database.get_setting("fuel_price", 1.65))
    fuel_consumption = float(database.get_setting("fuel_consumption", 28.0))

    # Identify default depot
    default_depot = next((loc for loc in locations if loc["is_default_depot"]), locations[0])
    depot_id = default_depot["id"]

    # Default delivery locations (all non-depot locations)
    delivery_ids = [loc["id"] for loc in locations if loc["id"] != depot_id]

    # Run initial optimization for instant demonstration
    initial_solution = optimizer.solve_tsp(
        depot_id=depot_id,
        delivery_ids=delivery_ids,
        all_locations_dict=loc_dict,
        full_distance_matrix=distance_matrix,
        fuel_consumption=fuel_consumption,
        fuel_price=fuel_price
    )

    return render_template(
        "index.html",
        locations=locations,
        distance_matrix=distance_matrix,
        selected_depot_id=depot_id,
        selected_delivery_ids=delivery_ids,
        fuel_price=fuel_price,
        fuel_consumption=fuel_consumption,
        solution=initial_solution
    )

@app.route("/optimize", methods=["POST"])
def optimize():
    """
    Process route optimization request.
    Supports both JSON AJAX requests and standard Form submissions.
    """
    locations, distance_matrix = database.get_distance_matrix_dict()
    loc_dict = {loc["id"]: loc for loc in locations}

    # Check if request is JSON
    if request.is_json:
        data = request.get_json()
        try:
            depot_id = int(data.get("depot_id"))
            delivery_ids = [int(i) for i in data.get("delivery_ids", [])]
            fuel_price = float(data.get("fuel_price", 1.65))
            fuel_consumption = float(data.get("fuel_consumption", 28.0))
        except (ValueError, TypeError) as e:
            return jsonify({"success": False, "error": f"Invalid input format: {str(e)}"}), 400
    else:
        try:
            depot_id = int(request.form.get("depot_id"))
            delivery_ids = [int(i) for i in request.form.getlist("delivery_ids")]
            fuel_price = float(request.form.get("fuel_price", 1.65))
            fuel_consumption = float(request.form.get("fuel_consumption", 28.0))
        except (ValueError, TypeError) as e:
            flash(f"Invalid input data: {str(e)}", "error")
            return redirect(url_for("index"))

    # Validate inputs
    if fuel_price <= 0:
        error_msg = "Fuel price must be greater than zero."
        if request.is_json:
            return jsonify({"success": False, "error": error_msg}), 400
        flash(error_msg, "error")
        return redirect(url_for("index"))

    if fuel_consumption <= 0:
        error_msg = "Fuel consumption must be greater than zero."
        if request.is_json:
            return jsonify({"success": False, "error": error_msg}), 400
        flash(error_msg, "error")
        return redirect(url_for("index"))

    # Remove depot from delivery destinations if user checked it
    delivery_ids = [d for d in delivery_ids if d != depot_id]

    if not delivery_ids:
        error_msg = "Please select at least one delivery destination different from the depot."
        if request.is_json:
            return jsonify({"success": False, "error": error_msg}), 400
        flash(error_msg, "error")
        return redirect(url_for("index"))

    # Save settings for convenience
    database.update_setting("fuel_price", fuel_price)
    database.update_setting("fuel_consumption", fuel_consumption)

    # Solve optimization problem
    solution = optimizer.solve_tsp(
        depot_id=depot_id,
        delivery_ids=delivery_ids,
        all_locations_dict=loc_dict,
        full_distance_matrix=distance_matrix,
        fuel_consumption=fuel_consumption,
        fuel_price=fuel_price
    )

    if request.is_json:
        return jsonify(solution)

    return render_template(
        "index.html",
        locations=locations,
        distance_matrix=distance_matrix,
        selected_depot_id=depot_id,
        selected_delivery_ids=delivery_ids,
        fuel_price=fuel_price,
        fuel_consumption=fuel_consumption,
        solution=solution
    )

@app.route("/update_distance", methods=["POST"])
def update_distance():
    """
    Update a single distance value between two locations.
    """
    data = request.get_json() if request.is_json else request.form
    try:
        origin_id = int(data.get("origin_id"))
        destination_id = int(data.get("destination_id"))
        distance_km = float(data.get("distance_km"))
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Invalid distance values: {str(e)}"}), 400

    if distance_km < 0:
        return jsonify({"success": False, "error": "Distance cannot be negative."}), 400

    symmetric = data.get("symmetric", True) in [True, "true", "True", "1", 1]
    database.update_distance(origin_id, destination_id, distance_km, symmetric=symmetric)

    return jsonify({
        "success": True,
        "message": f"Distance updated successfully: {distance_km} km",
        "origin_id": origin_id,
        "destination_id": destination_id,
        "distance_km": distance_km
    })

@app.route("/update_all_distances", methods=["POST"])
def update_all_distances():
    """
    Batch update multiple distances from table edits.
    """
    data = request.get_json()
    if not data or "distances" not in data:
        return jsonify({"success": False, "error": "No distance data provided"}), 400

    batch = {}
    for item in data["distances"]:
        try:
            o_id = int(item["origin_id"])
            d_id = int(item["destination_id"])
            dist = float(item["distance_km"])
            if dist < 0:
                return jsonify({"success": False, "error": "Distances cannot be negative."}), 400
            batch[(o_id, d_id)] = dist
        except (ValueError, KeyError) as e:
            return jsonify({"success": False, "error": f"Malformed distance entry: {str(e)}"}), 400

    database.update_distance_matrix(batch)
    return jsonify({"success": True, "message": "All distances updated successfully."})

@app.route("/reset_distances", methods=["POST"])
def reset_distances():
    """
    Reset all locations, distances, and configuration to default Zimbabwean sample data.
    """
    database.reset_to_defaults()
    if request.is_json:
        return jsonify({"success": True, "message": "Database successfully reset to sample data."})
    flash("Database successfully reset to default sample data.", "info")
    return redirect(url_for("index"))

@app.route("/api/matrix", methods=["GET"])
def api_matrix():
    """
    Return the current locations and distance matrix in JSON format.
    """
    locations, distance_matrix = database.get_distance_matrix_dict()
    matrix_serialized = [
        {"origin_id": k[0], "destination_id": k[1], "distance_km": v}
        for k, v in distance_matrix.items()
    ]
    return jsonify({
        "locations": locations,
        "distances": matrix_serialized
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
