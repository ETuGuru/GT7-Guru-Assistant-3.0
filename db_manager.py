def create_thread_safe_connection(db_path):
    """
    Crea una connessione SQLite configurata per essere thread-safe
    
    Args:
        db_path: Percorso al file del database SQLite
        
    Returns:
        tuple: (connessione, lock) per l'accesso thread-safe
    """
    import sqlite3
    import threading
    
    # Crea una connessione con check_same_thread=False per permettere l'uso da thread diversi
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    # Crea un lock per sincronizzare l'accesso
    lock = threading.Lock()
    
    return conn, lock

# db_manager.py

import sqlite3
import json
import logging
CONFIG_FILE = "config.json"
def save_config(config):
    """Salva la configurazione su file JSON."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

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
    logging.debug("[db_manager] Chiavi attese: %s", keys)
    logging.debug("[db_manager] Numero di valori: %d", len(values))
    logging.debug("[db_manager] Valori: %s", values)
    
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

def load_recent_telemetry(conn, limit=None):
    c = conn.cursor()
    if limit is None:
        c.execute("SELECT * FROM telemetry ORDER BY id DESC")
    else:
        c.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()
def clear_telemetry(conn):
    c = conn.cursor()
    c.execute("DELETE FROM telemetry")
    conn.commit()

def initialize_database(conn):
    """
    Crea le tabelle necessarie se non esistono già
    """
    try:
        cursor = conn.cursor()
        # Creazione tabella telemetria principale
        cursor.execute("""
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
                circuit_name TEXT,
                lateral_g REAL,
                longitudinal_g REAL,
                brake_temp_fl REAL,
                brake_temp_fr REAL,
                brake_temp_rl REAL,
                brake_temp_rr REAL,
                brake_pressure_fl REAL,
                brake_pressure_fr REAL,
                brake_pressure_rl REAL,
                brake_pressure_rr REAL
            )
        """)
        
        # Crea indici per migliorare le performance delle query
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_car_id ON telemetry(car_id)")
        
        conn.commit()
        logging.info("[DB] Database inizializzato con successo")
        return True
    except Exception as e:
        logging.error(f"[DB] Errore nell'inizializzazione del database: {e}")
        return False


def load_telemetry_for_training(conn, min_laps=1):
    """
    Carica i dati di telemetria per il training del modello AI.
    Filtra i record per assicurarsi che contengano dati validi e completi.
    
    Args:
        conn: Connessione al database
        min_laps: Numero minimo di giri completati per considerare i dati
        
    Returns:
        list: Lista di dizionari contenenti i dati di telemetria
    """
    cursor = conn.cursor()
    
    # Seleziona solo i record con giri validi e tutti i dati necessari
    query = """
    SELECT *
    FROM telemetry
    WHERE last_lap > 0
    AND car_speed > 0
    AND current_lap >= ?
    AND throttle IS NOT NULL
    AND brake IS NOT NULL
    AND rpm IS NOT NULL
    AND current_gear IS NOT NULL
    ORDER BY timestamp ASC
    """
    
    cursor.execute(query, (min_laps,))
    columns = [description[0] for description in cursor.description]
    results = cursor.fetchall()
    
    # Converti i risultati in una lista di dizionari
    telemetry_data = []
    for row in results:
        data_dict = dict(zip(columns, row))
        telemetry_data.append(data_dict)
        
    logging.debug(f"[db_manager] Caricati {len(telemetry_data)} record validi per il training")
    return telemetry_data
