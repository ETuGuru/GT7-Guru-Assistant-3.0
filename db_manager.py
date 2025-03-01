# db_manager.py

import sqlite3

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 50+ campi in telemetria
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

        car_speed REAL,        -- km/h
        tyre_speed_fl REAL,    -- m/s
        tyre_speed_fr REAL,
        tyre_speed_rl REAL,
        tyre_speed_rr REAL,

        position_x REAL,
        position_y REAL,
        position_z REAL,

        velocity_x REAL,       -- m/s
        velocity_y REAL,
        velocity_z REAL,

        rotation_pitch REAL,   -- gradi
        rotation_yaw REAL,
        rotation_roll REAL,

        angular_velocity_x REAL, -- gradi/s
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

        throttle REAL,       -- [0..100]%
        rpm REAL,
        rpm_rev_warning REAL,
        brake REAL,          -- [0..100]%
        boost REAL,
        rpm_rev_limiter REAL,
        estimated_top_speed REAL, -- m/s
        clutch REAL,         -- [0..100]%
        clutch_engaged REAL, -- [0..100]%
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
    c = conn.cursor()
    c.execute("""
    INSERT INTO telemetry (
        timestamp,
        package_id, car_id,
        best_lap, last_lap, current_lap, total_laps,
        current_gear, suggested_gear, gear_1, gear_2, gear_3, gear_4, gear_5, gear_6, gear_7, gear_8,
        fuel_capacity, current_fuel,
        car_speed,
        tyre_speed_fl, tyre_speed_fr, tyre_speed_rl, tyre_speed_rr,
        position_x, position_y, position_z,
        velocity_x, velocity_y, velocity_z,
        rotation_pitch, rotation_yaw, rotation_roll,
        angular_velocity_x, angular_velocity_y, angular_velocity_z,
        oil_temp, water_temp, tyre_temp_fl, tyre_temp_fr, tyre_temp_rl, tyre_temp_rr,
        oil_pressure, ride_height,
        suspension_fl, suspension_fr, suspension_rl, suspension_rr,
        current_position, total_positions,
        throttle, rpm, rpm_rev_warning, brake, boost, rpm_rev_limiter,
        estimated_top_speed, clutch, clutch_engaged, rpm_after_clutch,
        is_paused, in_race,
        car_model, tyre_type, circuit_name
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data_dict["timestamp"],
        data_dict["package_id"], data_dict["car_id"],
        data_dict["best_lap"], data_dict["last_lap"], data_dict["current_lap"], data_dict["total_laps"],
        data_dict["current_gear"], data_dict["suggested_gear"],
        data_dict["gear_1"], data_dict["gear_2"], data_dict["gear_3"], data_dict["gear_4"],
        data_dict["gear_5"], data_dict["gear_6"], data_dict["gear_7"], data_dict["gear_8"],

        data_dict["fuel_capacity"], data_dict["current_fuel"],

        data_dict["car_speed"],     
        data_dict["tyre_speed_fl"],
        data_dict["tyre_speed_fr"],
        data_dict["tyre_speed_rl"],
        data_dict["tyre_speed_rr"],

        data_dict["position_x"], data_dict["position_y"], data_dict["position_z"],
        data_dict["velocity_x"], data_dict["velocity_y"], data_dict["velocity_z"],
        data_dict["rotation_pitch"], data_dict["rotation_yaw"], data_dict["rotation_roll"],
        data_dict["angular_velocity_x"], data_dict["angular_velocity_y"], data_dict["angular_velocity_z"],

        data_dict["oil_temp"], data_dict["water_temp"],
        data_dict["tyre_temp_fl"], data_dict["tyre_temp_fr"], data_dict["tyre_temp_rl"], data_dict["tyre_temp_rr"],
        data_dict["oil_pressure"], data_dict["ride_height"],
        data_dict["suspension_fl"], data_dict["suspension_fr"], data_dict["suspension_rl"], data_dict["suspension_rr"],
        data_dict["current_position"], data_dict["total_positions"],

        data_dict["throttle"], data_dict["rpm"], data_dict["rpm_rev_warning"],
        data_dict["brake"], data_dict["boost"], data_dict["rpm_rev_limiter"],
        data_dict["estimated_top_speed"], data_dict["clutch"], data_dict["clutch_engaged"], data_dict["rpm_after_clutch"],

        1 if data_dict["is_paused"] else 0,
        1 if data_dict["in_race"] else 0,

        data_dict.get("car_model","Sconosciuta"),
        data_dict.get("tyre_type","Sconosciute"),
        data_dict.get("circuit_name","Sconosciuto")
    ))
    conn.commit()

def load_all_telemetry(conn):
    c = conn.cursor()
    c.execute("SELECT * FROM telemetry ORDER BY id ASC")
    return c.fetchall()

def load_recent_telemetry(conn, limit=50):
    c = conn.cursor()
    c.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()
