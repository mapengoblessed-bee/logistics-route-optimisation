"""
database.py
-----------
SQLite database management for the Logistics Route Optimization DSS.
Stores locations, distance matrix, and default configuration parameters.
Allows reading, updating distances, and resetting to factory defaults.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'logistics_dss.db')

# Predefined realistic sample locations in Zimbabwe
DEFAULT_LOCATIONS = [
    {"name": "Depot (Starting Point)", "is_default_depot": 1, "display_order": 0},
    {"name": "Harare", "is_default_depot": 0, "display_order": 1},
    {"name": "Bulawayo", "is_default_depot": 0, "display_order": 2},
    {"name": "Gweru", "is_default_depot": 0, "display_order": 3},
    {"name": "Mutare", "is_default_depot": 0, "display_order": 4},
    {"name": "Masvingo", "is_default_depot": 0, "display_order": 5},
]

# Realistic illustrative road distances (in km) between Zimbabwean logistics hubs
# Depot is located at the primary logistics park near Harare
DEFAULT_DISTANCES = {
    ("Depot (Starting Point)", "Depot (Starting Point)"): 0.0,
    ("Depot (Starting Point)", "Harare"): 15.0,
    ("Depot (Starting Point)", "Bulawayo"): 445.0,
    ("Depot (Starting Point)", "Gweru"): 285.0,
    ("Depot (Starting Point)", "Mutare"): 270.0,
    ("Depot (Starting Point)", "Masvingo"): 300.0,

    ("Harare", "Depot (Starting Point)"): 15.0,
    ("Harare", "Harare"): 0.0,
    ("Harare", "Bulawayo"): 439.0,
    ("Harare", "Gweru"): 277.0,
    ("Harare", "Mutare"): 263.0,
    ("Harare", "Masvingo"): 293.0,

    ("Bulawayo", "Depot (Starting Point)"): 445.0,
    ("Bulawayo", "Harare"): 439.0,
    ("Bulawayo", "Bulawayo"): 0.0,
    ("Bulawayo", "Gweru"): 164.0,
    ("Bulawayo", "Mutare"): 697.0,
    ("Bulawayo", "Masvingo"): 280.0,

    ("Gweru", "Depot (Starting Point)"): 285.0,
    ("Gweru", "Harare"): 277.0,
    ("Gweru", "Bulawayo"): 164.0,
    ("Gweru", "Gweru"): 0.0,
    ("Gweru", "Mutare"): 538.0,
    ("Gweru", "Masvingo"): 168.0,

    ("Mutare", "Depot (Starting Point)"): 270.0,
    ("Mutare", "Harare"): 263.0,
    ("Mutare", "Bulawayo"): 697.0,
    ("Mutare", "Gweru"): 538.0,
    ("Mutare", "Mutare"): 0.0,
    ("Mutare", "Masvingo"): 297.0,

    ("Masvingo", "Depot (Starting Point)"): 300.0,
    ("Masvingo", "Harare"): 293.0,
    ("Masvingo", "Bulawayo"): 280.0,
    ("Masvingo", "Gweru"): 168.0,
    ("Masvingo", "Mutare"): 297.0,
    ("Masvingo", "Masvingo"): 0.0,
}

DEFAULT_SETTINGS = {
    "fuel_price": "1.65",         # USD per litre
    "fuel_consumption": "28.0",   # Litres per 100 km (typical medium-duty delivery truck)
}

def get_db_connection():
    """Create and return a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(reset=False):
    """
    Initialize SQLite database schema and seed default data if not already present
    or if reset is requested.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if reset:
        cursor.execute("DROP TABLE IF EXISTS distances")
        cursor.execute("DROP TABLE IF EXISTS locations")
        cursor.execute("DROP TABLE IF EXISTS settings")

    # Table: locations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_default_depot INTEGER NOT NULL DEFAULT 0,
            display_order INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Table: distances between locations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS distances (
            origin_id INTEGER NOT NULL,
            destination_id INTEGER NOT NULL,
            distance_km REAL NOT NULL,
            PRIMARY KEY (origin_id, destination_id),
            FOREIGN KEY (origin_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (destination_id) REFERENCES locations(id) ON DELETE CASCADE
        )
    """)

    # Table: settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()

    # Seed locations if empty
    cursor.execute("SELECT COUNT(*) as count FROM locations")
    if cursor.fetchone()["count"] == 0:
        for loc in DEFAULT_LOCATIONS:
            cursor.execute(
                "INSERT INTO locations (name, is_default_depot, display_order) VALUES (?, ?, ?)",
                (loc["name"], loc["is_default_depot"], loc["display_order"])
            )
        conn.commit()

    # Seed distances if empty
    cursor.execute("SELECT COUNT(*) as count FROM distances")
    if cursor.fetchone()["count"] == 0:
        # Build mapping of name -> id
        cursor.execute("SELECT id, name FROM locations")
        loc_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        for (from_name, to_name), dist in DEFAULT_DISTANCES.items():
            if from_name in loc_map and to_name in loc_map:
                cursor.execute(
                    "INSERT OR REPLACE INTO distances (origin_id, destination_id, distance_km) VALUES (?, ?, ?)",
                    (loc_map[from_name], loc_map[to_name], float(dist))
                )
        conn.commit()

    # Seed default settings if empty
    for key, val in DEFAULT_SETTINGS.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, val)
        )
    conn.commit()
    conn.close()

def get_all_locations():
    """Retrieve all locations sorted by display order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, is_default_depot, display_order FROM locations ORDER BY display_order ASC")
    locations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return locations

def get_distance_matrix_dict():
    """
    Returns:
      locations: list of location dicts
      matrix: dict keyed by (origin_id, destination_id) -> distance_km
    """
    locations = get_all_locations()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT origin_id, destination_id, distance_km FROM distances")
    rows = cursor.fetchall()
    conn.close()

    matrix = {}
    for r in rows:
        matrix[(r["origin_id"], r["destination_id"])] = float(r["distance_km"])

    # Ensure self-distances are 0.0
    for loc in locations:
        matrix[(loc["id"], loc["id"])] = 0.0

    return locations, matrix

def update_distance(origin_id, destination_id, distance_km, symmetric=True):
    """
    Update the distance between two locations in the database.
    If symmetric is True, also updates destination_id -> origin_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO distances (origin_id, destination_id, distance_km) VALUES (?, ?, ?)",
        (origin_id, destination_id, float(distance_km))
    )
    if symmetric and origin_id != destination_id:
        cursor.execute(
            "INSERT OR REPLACE INTO distances (origin_id, destination_id, distance_km) VALUES (?, ?, ?)",
            (destination_id, origin_id, float(distance_km))
        )
    conn.commit()
    conn.close()

def update_distance_matrix(matrix_data):
    """
    Batch update distances from a dictionary keyed by (origin_id, destination_id) -> distance_km.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    for (orig_id, dest_id), dist in matrix_data.items():
        cursor.execute(
            "INSERT OR REPLACE INTO distances (origin_id, destination_id, distance_km) VALUES (?, ?, ?)",
            (int(orig_id), int(dest_id), float(dist))
        )
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    """Retrieve a setting value by key."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def update_setting(key, value):
    """Save or update a setting value."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def reset_to_defaults():
    """Reset all tables and reload original sample data."""
    init_db(reset=True)
