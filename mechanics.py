# mechanics.py
import logging

# Funzioni per l'estrazione delle feature di assetto, temperatura e tempi
def calc_slip_ratio(tyre_speed_ms, car_speed_ms):
    eps = 1e-3
    if car_speed_ms < eps:
        return 0.0
    return (tyre_speed_ms - car_speed_ms) / car_speed_ms

def extract_setup_features(telemetry_dict):
    """
    Estrae feature relative all'assetto della vettura (sospensioni, rotazioni, ecc.)
    Gestisce valori None restituendo valori di default (0.0 per valori numerici, "" per testi)
    """
    # Valori di sospensione (default 0.0 se None)
    susp_fl = telemetry_dict.get("suspension_FL", 0.0)
    susp_fr = telemetry_dict.get("suspension_FR", 0.0)
    susp_rl = telemetry_dict.get("suspension_RL", 0.0) 
    susp_rr = telemetry_dict.get("suspension_RR", 0.0)
    
    # Gestione esplicita dei valori None per le sospensioni
    susp_fl = 0.0 if susp_fl is None else susp_fl
    susp_fr = 0.0 if susp_fr is None else susp_fr
    susp_rl = 0.0 if susp_rl is None else susp_rl
    susp_rr = 0.0 if susp_rr is None else susp_rr
    
    # Calcolo medie e bilanciamento sospensioni
    front_suspension_avg = (susp_fl + susp_fr) / 2
    rear_suspension_avg = (susp_rl + susp_rr) / 2
    suspension_balance = front_suspension_avg - rear_suspension_avg
    
    # Sbilanciamento sospensioni sinistra-destra
    left_suspension_avg = (susp_fl + susp_rl) / 2
    right_suspension_avg = (susp_fr + susp_rr) / 2
    lateral_balance = left_suspension_avg - right_suspension_avg
    
    # Rotazioni (default 0.0 se None)
    rotation_pitch = telemetry_dict.get("rotation_pitch", 0.0)
    rotation_roll = telemetry_dict.get("rotation_roll", 0.0)
    rotation_yaw = telemetry_dict.get("rotation_yaw", 0.0)
    
    # Gestione esplicita dei valori None per le rotazioni
    rotation_pitch = 0.0 if rotation_pitch is None else rotation_pitch
    rotation_roll = 0.0 if rotation_roll is None else rotation_roll
    rotation_yaw = 0.0 if rotation_yaw is None else rotation_yaw
    
    # Velocità angolari (default 0.0 se None)
    ang_vel_x = telemetry_dict.get("angular_velocity_x", 0.0)
    ang_vel_y = telemetry_dict.get("angular_velocity_y", 0.0)
    ang_vel_z = telemetry_dict.get("angular_velocity_z", 0.0)
    
    # Gestione esplicita dei valori None per le velocità angolari
    ang_vel_x = 0.0 if ang_vel_x is None else ang_vel_x
    ang_vel_y = 0.0 if ang_vel_y is None else ang_vel_y
    ang_vel_z = 0.0 if ang_vel_z is None else ang_vel_z
    
    # Altri parametri di assetto (default 0.0 se None)
    ride_height = telemetry_dict.get("ride_height", 0.0)
    boost = telemetry_dict.get("boost", 0.0)
    
    # Gestione esplicita dei valori None per gli altri parametri
    ride_height = 0.0 if ride_height is None else ride_height
    boost = 0.0 if boost is None else boost
    
    # Gestione di eventuali parametri testuali (esempio)
    car_name = telemetry_dict.get("car_name", "")
    car_name = "" if car_name is None else car_name
    
    return {
        "suspension_fl": susp_fl,
        "suspension_fr": susp_fr,
        "suspension_rl": susp_rl,
        "suspension_rr": susp_rr,
        "front_suspension_avg": front_suspension_avg,
        "rear_suspension_avg": rear_suspension_avg,
        "suspension_balance": suspension_balance,
        "lateral_balance": lateral_balance,
        "rotation_pitch": rotation_pitch,
        "rotation_roll": rotation_roll,
        "rotation_yaw": rotation_yaw,
        "angular_velocity_x": ang_vel_x,
        "angular_velocity_y": ang_vel_y,
        "angular_velocity_z": ang_vel_z,
        "ride_height": ride_height,
        "boost": boost,
        "car_name": car_name  # Aggiunto esempio di parametro testuale
    }

def extract_temperature_features(telemetry_dict):
    """
    Estrae feature relative alle temperature (pneumatici, olio, acqua)
    Gestisce valori None fornendo valori di default (0.0) e calcoli sicuri
    """
    # Temperature pneumatici con gestione valori None
    tyre_temp_fl = telemetry_dict.get("tyre_temp_FL", 0.0)
    tyre_temp_fr = telemetry_dict.get("tyre_temp_FR", 0.0)
    tyre_temp_rl = telemetry_dict.get("tyre_temp_RL", 0.0)
    tyre_temp_rr = telemetry_dict.get("tyre_temp_RR", 0.0)
    
    # Gestione esplicita dei valori None per le temperature degli pneumatici
    tyre_temp_fl = 0.0 if tyre_temp_fl is None else tyre_temp_fl
    tyre_temp_fr = 0.0 if tyre_temp_fr is None else tyre_temp_fr
    tyre_temp_rl = 0.0 if tyre_temp_rl is None else tyre_temp_rl
    tyre_temp_rr = 0.0 if tyre_temp_rr is None else tyre_temp_rr
    
    # Calcolo medie e differenze temperature pneumatici in modo sicuro
    # Usiamo 4 pneumatici per la media totale
    all_tyre_temp_avg = (tyre_temp_fl + tyre_temp_fr + tyre_temp_rl + tyre_temp_rr) / 4
    front_tyre_temp_avg = (tyre_temp_fl + tyre_temp_fr) / 2
    rear_tyre_temp_avg = (tyre_temp_rl + tyre_temp_rr) / 2
    left_tyre_temp_avg = (tyre_temp_fl + tyre_temp_rl) / 2
    right_tyre_temp_avg = (tyre_temp_fr + tyre_temp_rr) / 2
    
    # Bilanciamento temperature pneumatici (fronte-retro e sinistra-destra)
    tyre_temp_fr_balance = front_tyre_temp_avg - rear_tyre_temp_avg
    tyre_temp_lr_balance = left_tyre_temp_avg - right_tyre_temp_avg
    
    # Spread temperature (differenza tra la più alta e la più bassa)
    tyre_temps = [tyre_temp_fl, tyre_temp_fr, tyre_temp_rl, tyre_temp_rr]
    tyre_temp_spread = max(tyre_temps) - min(tyre_temps)
    
    # Temperature motore e freni con gestione valori None
    oil_temp = telemetry_dict.get("oil_temp", 0.0)
    water_temp = telemetry_dict.get("water_temp", 0.0)
    oil_pressure = telemetry_dict.get("oil_pressure", 0.0)
    
    # Gestione esplicita dei valori None per le temperature del motore
    oil_temp = 0.0 if oil_temp is None else oil_temp
    water_temp = 0.0 if water_temp is None else water_temp
    oil_pressure = 0.0 if oil_pressure is None else oil_pressure
    
    # Aggiungiamo gestione per temperature dei freni (se esistono nel dizionario)
    brake_temp_fl = telemetry_dict.get("brake_temp_FL", 0.0)
    brake_temp_fr = telemetry_dict.get("brake_temp_FR", 0.0)
    brake_temp_rl = telemetry_dict.get("brake_temp_RL", 0.0)
    brake_temp_rr = telemetry_dict.get("brake_temp_RR", 0.0)
    
    # Gestione esplicita dei valori None per le temperature dei freni
    brake_temp_fl = 0.0 if brake_temp_fl is None else brake_temp_fl
    brake_temp_fr = 0.0 if brake_temp_fr is None else brake_temp_fr
    brake_temp_rl = 0.0 if brake_temp_rl is None else brake_temp_rl
    brake_temp_rr = 0.0 if brake_temp_rr is None else brake_temp_rr
    
    # Calcolo medie temperature freni
    front_brake_temp_avg = (brake_temp_fl + brake_temp_fr) / 2
    rear_brake_temp_avg = (brake_temp_rl + brake_temp_rr) / 2
    all_brake_temp_avg = (brake_temp_fl + brake_temp_fr + brake_temp_rl + brake_temp_rr) / 4
    
    # Indice di stress termico del motore con gestione sicura
    engine_thermal_stress = (oil_temp / 100.0) + (water_temp / 100.0)
    
    return {
        "tyre_temp_fl": tyre_temp_fl,
        "tyre_temp_fr": tyre_temp_fr,
        "tyre_temp_rl": tyre_temp_rl,
        "tyre_temp_rr": tyre_temp_rr,
        "all_tyre_temp_avg": all_tyre_temp_avg,
        "front_tyre_temp_avg": front_tyre_temp_avg,
        "rear_tyre_temp_avg": rear_tyre_temp_avg,
        "tyre_temp_fr_balance": tyre_temp_fr_balance,
        "tyre_temp_lr_balance": tyre_temp_lr_balance,
        "tyre_temp_spread": tyre_temp_spread,
        "oil_temp": oil_temp,
        "water_temp": water_temp,
        "oil_pressure": oil_pressure,
        "engine_thermal_stress": engine_thermal_stress,
        # Aggiungiamo anche le temperature dei freni al dizionario ritornato
        "brake_temp_fl": brake_temp_fl,
        "brake_temp_fr": brake_temp_fr,
        "brake_temp_rl": brake_temp_rl,
        "brake_temp_rr": brake_temp_rr,
        "front_brake_temp_avg": front_brake_temp_avg,
        "rear_brake_temp_avg": rear_brake_temp_avg,
        "all_brake_temp_avg": all_brake_temp_avg
    }

def extract_timing_features(telemetry_dict):
    """
    Estrae feature relative ai tempi (giri, intertempi)
    Gestisce valori None fornendo valori di default (0.0 per i tempi, 0 per contatori)
    e garantisce calcoli sicuri per i delta temporali
    """
    # Tempi giro con gestione valori None
    current_lap_time = telemetry_dict.get("current_lap", 0)
    best_lap_time = telemetry_dict.get("best_lap", 0)
    last_lap_time = telemetry_dict.get("last_lap", 0)
    
    # Gestione esplicita dei valori None per i tempi
    current_lap_time = 0 if current_lap_time is None else current_lap_time
    best_lap_time = 0 if best_lap_time is None else best_lap_time
    last_lap_time = 0 if last_lap_time is None else last_lap_time
    
    # Progressione con gestione valori None
    total_laps = telemetry_dict.get("total_laps", 0)
    time_on_track = telemetry_dict.get("time_on_track", 0.0)
    
    # Gestione esplicita dei valori None per la progressione
    total_laps = 0 if total_laps is None else total_laps
    time_on_track = 0.0 if time_on_track is None else time_on_track
    
    # Delta con il giro migliore (calcolo sicuro)
    delta_to_best = 0
    if best_lap_time > 0 and current_lap_time > 0:
        delta_to_best = current_lap_time - best_lap_time
    
    # Confronto con l'ultimo giro (calcolo sicuro)
    delta_to_last = 0
    if last_lap_time > 0 and current_lap_time > 0:
        delta_to_last = current_lap_time - last_lap_time
    
    # Posizione e numero di partecipanti con gestione valori None
    current_position = telemetry_dict.get("current_position", 0)
    total_positions = telemetry_dict.get("total_positions", 0)
    
    # Gestione esplicita dei valori None per posizione e totale partecipanti
    current_position = 0 if current_position is None else current_position
    total_positions = 0 if total_positions is None else total_positions
    # Calcolo aggiuntivo: tempo medio per giro (se ci sono giri completati)
    avg_lap_time = 0.0
    if total_laps > 0 and time_on_track > 0:
        avg_lap_time = time_on_track / total_laps
        
    # Calcolo percentuale completamento gara (se i dati sono disponibili)
    race_completion_pct = 0.0
    if total_laps > 0:
        race_completion_pct = (float(total_laps) / 100.0) * 100.0
        
    return {
        "current_lap_time": current_lap_time,
        "best_lap_time": best_lap_time,
        "last_lap_time": last_lap_time,
        "delta_to_best": delta_to_best,
        "delta_to_last": delta_to_last,
        "total_laps": total_laps,
        "time_on_track": time_on_track,
        "current_position": current_position,
        "total_positions": total_positions,
        "avg_lap_time": avg_lap_time,
        "race_completion_pct": race_completion_pct
    }

def extract_features(telemetry_dict, verbose_logging=False):
    """
    Estrae e logga tutte le feature dalla telemetria con metriche avanzate
    Args:
        telemetry_dict: dizionario con i dati telemetrici
        verbose_logging: se True, stampa tutti i dettagli di elaborazione
    """
    logger = logging.getLogger(__name__)
    
    if verbose_logging:
        logger.info("Elaborazione dati telemetrici...")

    # Performance metrics
    car_speed_kmh = telemetry_dict.get("car_speed", 0.0)
    car_speed_ms = (0.0 if car_speed_kmh is None else car_speed_kmh) / 3.6
    
    if verbose_logging:
        logger.info(f"Velocità vettura: {car_speed_kmh:.2f} km/h")

    # Tire metrics with detailed logging
    tire_speeds = {
        "FL": telemetry_dict.get("tyre_speed_fl", 0.0),
        "FR": telemetry_dict.get("tyre_speed_fr", 0.0),
        "RL": telemetry_dict.get("tyre_speed_rl", 0.0),
        "RR": telemetry_dict.get("tyre_speed_rr", 0.0)
    }
    
    tire_temps = {
        "FL": telemetry_dict.get("tyre_temp_fl", 0.0),
        "FR": telemetry_dict.get("tyre_temp_fr", 0.0),
        "RL": telemetry_dict.get("tyre_temp_rl", 0.0),
        "RR": telemetry_dict.get("tyre_temp_rr", 0.0)
    }

    # Safe handling of None values
    tire_speeds = {k: (0.0 if v is None else v) for k, v in tire_speeds.items()}
    tire_temps = {k: (0.0 if v is None else v) for k, v in tire_temps.items()}

    # Calculate and log slip ratios
    slip_ratios = {
        k: calc_slip_ratio(v, car_speed_ms) 
        for k, v in tire_speeds.items()
    }
    
    avg_slip = sum(abs(v) for v in slip_ratios.values()) / 4.0
    
    if verbose_logging:
        logger.info(f"Slip ratio medio: {avg_slip:.3f}")
        logger.info(f"Slip ratios per ruota: {slip_ratios}")
    
    # Performance metrics
    throttle_pct = telemetry_dict.get("throttle", 0.0)
    brake_pct = telemetry_dict.get("brake", 0.0)
    rpm = telemetry_dict.get("rpm", 0.0)
    current_gear = telemetry_dict.get("current_gear", 0)
    
    # Safe value handling
    throttle_pct = 0.0 if throttle_pct is None else throttle_pct
    brake_pct = 0.0 if brake_pct is None else brake_pct
    rpm = 0.0 if rpm is None else rpm
    gear = float(0 if current_gear is None else current_gear)
    
    if verbose_logging:
        logger.info(f"""Performance metrics:
        - Throttle: {throttle_pct:.1f}%
        - Brake: {brake_pct:.1f}%
        - RPM: {rpm:.0f}
        - Gear: {int(gear)}""")

    # Extract additional features with error handling
    try:
        setup_features = extract_setup_features(telemetry_dict)
        if verbose_logging:
            logger.info("Setup features estratte con successo")
    except Exception as e:
        if verbose_logging:
            logger.error(f"Errore nell'estrazione setup features: {e}")
        setup_features = {}

    try:
        temperature_features = extract_temperature_features(telemetry_dict)
        if verbose_logging:
            logger.info("Temperature features estratte con successo")
    except Exception as e:
        if verbose_logging:
            logger.error(f"Errore nell'estrazione temperature features: {e}")
        temperature_features = {}

    try:
        timing_features = extract_timing_features(telemetry_dict)
        if verbose_logging:
            logger.info("Timing features estratte con successo")
    except Exception as e:
        if verbose_logging:
            logger.error(f"Errore nell'estrazione timing features: {e}")
        timing_features = {}

    # Combine all features
    features = {
        "car_speed_kmh": car_speed_kmh,
        "avg_slip_ratio": avg_slip,
        "throttle_pct": throttle_pct,
        "brake_pct": brake_pct,
        "rpm": rpm,
        "gear": gear,
        "tyre_temps": tire_temps,
        "tyre_speeds": tire_speeds,
        "slip_ratios": slip_ratios
    }
    
    # Update with additional features
    features.update(setup_features)
    features.update(temperature_features)
    features.update(timing_features)
    
    if verbose_logging:
        logger.info("Estrazione feature completata")
    return features
