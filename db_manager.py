# db_manager.py

import sqlite3

def init_db(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        package_id INTEGER,
        car_id INTEGER,
        best_lap REAL,
        last_lap REAL,
        current_lap INTEGER,
        total_laps INTEGER,
        current_gear INTEGER,
        suggested_gear INTEGER,
        gear_1 REAL,
        gear_2 REAL,
        gear_3 REAL,
        gear_4 REAL,
        gear_5 REAL,
        gear_6 REAL,
        gear_7 REAL,
        gear_8 REAL,
        fuel_capacity REAL,
        current_fuel REAL,
        car_speed REAL,
        tyre_speed_fl REAL,
        tyre_speed_fr REAL,
        tyre_speed_rl REAL,
        tyre_speed_rr REAL,
        position_x REAL,
        position_y REAL,
        position_z REAL,
        velocity_x REAL,
        velocity_y REAL,
        velocity_z REAL,
        rotation_pitch REAL,
        rotation_yaw REAL,
        rotation_roll REAL,
        angular_velocity_x REAL,
        angular_velocity_y REAL,
        angular_velocity_z REAL,
        oil_temp REAL,
        water_temp REAL,
        tyre_temp_fl REAL,
        tyre_temp_fr REAL,
        tyre_temp_rl REAL,
        tyre_temp_rr REAL,
        oil_pressure REAL,
        ride_height REAL,
        suspension_fl REAL,
        suspension_fr REAL,
        suspension_rl REAL,
        suspension_rr REAL,
        current_position INTEGER,
        total_positions INTEGER,
        throttle REAL,
        rpm REAL,
        rpm_rev_warning REAL,
        brake REAL,
        boost REAL,
        rpm_rev_limiter REAL,
        estimated_top_speed REAL,
        clutch REAL,
        clutch_engaged REAL,
        rpm_after_clutch REAL,
        is_paused INTEGER,
        in_race INTEGER,
        car_model TEXT,
        tyre_type TEXT,
        circuit_name TEXT
    )
    """)
    conn.commit()
    return conn
    
def save_telemetry(conn, data_dict):
    # Lista dei nomi delle 65 colonne (escludendo l'id autoincrementale)
    keys = [
        "timestamp",
        "package_id",
        "car_id",
        "best_lap",
        "last_lap",
        "current_lap",
        "total_laps",
        "current_gear",
        "suggested_gear",
        "gear_1",
        "gear_2",
        "gear_3",
        "gear_4",
        "gear_5",
        "gear_6",
        "gear_7",
        "gear_8",
        "fuel_capacity",
        "current_fuel",
        "car_speed",
        "tyre_speed_fl",
        "tyre_speed_fr",
        "tyre_speed_rl",
        "tyre_speed_rr",
        "position_x",
        "position_y",
        "position_z",
        "velocity_x",
        "velocity_y",
        "velocity_z",
        "rotation_pitch",
        "rotation_yaw",
        "rotation_roll",
        "angular_velocity_x",
        "angular_velocity_y",
        "angular_velocity_z",
        "oil_temp",
        "water_temp",
        "tyre_temp_fl",
        "tyre_temp_fr",
        "tyre_temp_rl",
        "tyre_temp_rr",
        "oil_pressure",
        "ride_height",
        "suspension_fl",
        "suspension_fr",
        "suspension_rl",
        "suspension_rr",
        "current_position",
        "total_positions",
        "throttle",
        "rpm",
        "rpm_rev_warning",
        "brake",
        "boost",
        "rpm_rev_limiter",
        "estimated_top_speed",
        "clutch",
        "clutch_engaged",
        "rpm_after_clutch",
        "is_paused",
        "in_race",
        "car_model",
        "tyre_type",
        "circuit_name"
    ]

    # Costruiamo la tupla dei valori in base all'ordine definito
    values = tuple(data_dict.get(key, None) for key in keys)
    
    # Debug: stampiamo chiavi, lunghezza e i valori
    print("[db_manager] Chiavi attese:", keys, flush=True)
    print("[db_manager] Numero di valori:", len(values), flush=True)
    print("[db_manager] Valori:", values, flush=True)
    
    # Generiamo dinamicamente i placeholder
    placeholders = ", ".join("?" for _ in keys)
    columns = ", ".join(keys)
    query = f"INSERT INTO telemetry ({columns}) VALUES ({placeholders})"
    
    c = conn.cursor()
    c.execute(query, values)
    conn.commit()

def load_all_telemetry(conn):
    c = conn.cursor()
    c.execute("SELECT * FROM telemetry ORDER BY id ASC")
    return c.fetchall()

def load_recent_telemetry(conn, limit=50):
    c = conn.cursor()
    c.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()
def clear_telemetry(conn):
    c = conn.cursor()
    c.execute("DELETE FROM telemetry")
    conn.commit()