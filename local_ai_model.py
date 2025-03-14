# local_ai_model.py

import os
import sqlite3
import numpy as np
import tensorflow as tf
from tensorflow.keras import Input, Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam

from config import DB_PATH, LOCAL_TF_MODEL_PATH, EPOCHS, BATCH_SIZE, LEARNING_RATE
from db_manager import load_all_telemetry
from mechanics import extract_features

try:
    tf.config.set_visible_devices([], 'GPU')
except Exception as e:
    pass

def row_to_dict(row):
    return {
        "timestamp": row[1],
        "package_id": row[2],
        "car_id": row[3],
        "best_lap": row[4],
        "last_lap": row[5],
        "current_lap": row[6],
        "total_laps": row[7],
        "current_gear": row[8],
        "suggested_gear": row[9],
        "gear_1": row[10],
        "gear_2": row[11],
        "gear_3": row[12],
        "gear_4": row[13],
        "gear_5": row[14],
        "gear_6": row[15],
        "gear_7": row[16],
        "gear_8": row[17],
        "fuel_capacity": row[18],
        "current_fuel": row[19],
        "car_speed": row[20],
        "tyre_speed_fl": row[21],
        "tyre_speed_fr": row[22],
        "tyre_speed_rl": row[23],
        "tyre_speed_rr": row[24],
        "position_x": row[25],
        "position_y": row[26],
        "position_z": row[27],
        "velocity_x": row[28],
        "velocity_y": row[29],
        "velocity_z": row[30],
        "rotation_pitch": row[31],
        "rotation_yaw": row[32],
        "rotation_roll": row[33],
        "angular_velocity_x": row[34],
        "angular_velocity_y": row[35],
        "angular_velocity_z": row[36],
        "oil_temp": row[37],
        "water_temp": row[38],
        "tyre_temp_fl": row[39],
        "tyre_temp_fr": row[40],
        "tyre_temp_rl": row[41],
        "tyre_temp_rr": row[42],
        "oil_pressure": row[43],
        "ride_height": row[44],
        "suspension_fl": row[45],
        "suspension_fr": row[46],
        "suspension_rl": row[47],
        "suspension_rr": row[48],
        "current_position": row[49],
        "total_positions": row[50],
        "throttle": row[51],
        "rpm": row[52],
        "rpm_rev_warning": row[53],
        "brake": row[54],
        "boost": row[55],
        "rpm_rev_limiter": row[56],
        "estimated_top_speed": row[57],
        "clutch": row[58],
        "clutch_engaged": row[59],
        "rpm_after_clutch": row[60],
        "is_paused": bool(row[61]),
        "in_race": bool(row[62]),
        "car_model": row[63],
        "tyre_type": row[64],
        "circuit_name": row[65]
    }

def create_dataset(rows):
    X_list = []
    Y_list = []
    for r in rows:
        td = row_to_dict(r)
        feats = extract_features(td)
        
        # Feature base (dinamica veicolo)
        base_features = [
            feats["car_speed_kmh"],
            feats["avg_slip_ratio"],
            feats["throttle_pct"],
            feats["brake_pct"],
            feats["rpm"],
            feats["gear"]
        ]
        
        # Feature di grip e bilanciamento
        grip_features = [
            # Media slip ratio ant/post per analisi trazione
            (feats["slip_ratios"]["FL"] + feats["slip_ratios"]["FR"]) / 2.0,
            (feats["slip_ratios"]["RL"] + feats["slip_ratios"]["RR"]) / 2.0,
            
            # Differenze temperatura gomme per analisi utilizzo
            max(feats["tyre_temps"].values()) - min(feats["tyre_temps"].values()),
            (feats["tyre_temps"]["FL"] + feats["tyre_temps"]["FR"]) / 2.0 - 
            (feats["tyre_temps"]["RL"] + feats["tyre_temps"]["RR"]) / 2.0,
        ]
        
        # Feature di stabilità
        stability_features = [
            feats.get("suspension_balance", 0.0),
            feats.get("lateral_balance", 0.0),
            feats.get("body_roll", 0.0),
            feats.get("body_pitch", 0.0)
        ]
        
        # Feature di efficienza frenata
        brake_features = [
            feats.get("brake_temp_balance", 0.0),
            feats.get("brake_pressure_balance", 0.0)
        ]
        
        # Feature prestazionali avanzate
        performance_features = [
            feats.get("longitudinal_acceleration", 0.0),
            feats.get("lateral_acceleration", 0.0),
            feats.get("power_delivery", 0.0),
            feats.get("brake_efficiency", 0.0)
        ]

        # Combina tutte le feature
        x_vec = (
            base_features +
            grip_features +
            stability_features +
            brake_features +
            performance_features
        )

        best_lap_s = td["best_lap"] if td["best_lap"] else 0.0
        X_list.append(x_vec)
        Y_list.append(best_lap_s)

    X = np.array(X_list, dtype=np.float32)
    Y = np.array(Y_list, dtype=np.float32)
    return X, Y

def build_model(input_dim):
    """
    Costruisce un modello di rete neurale più sofisticato per l'analisi delle prestazioni
    """
    model = Sequential([
        Input(shape=(input_dim,)),
        Dense(256, activation='relu'),
        Dense(256, activation='relu'),
        Dense(128, activation='relu'),
        Dense(64, activation='relu'),
        Dense(32, activation='relu'),
        Dense(1, activation='linear')
    ])
    
    opt = Adam(learning_rate=LEARNING_RATE)
    model.compile(
        optimizer=opt,
        loss='mse',
        metrics=['mae', 'mse']  # Aggiunti metrics per monitoraggio
    )
    return model

def train_model():
    conn = sqlite3.connect(DB_PATH)
    rows = load_all_telemetry(conn)
    conn.close()
    if not rows:
        print("[local_ai_model] Nessun dato per training.")
        return None
    X, Y = create_dataset(rows)
    model = build_model(X.shape[1])
    print(f"[local_ai_model] Training su X={X.shape}, Y={Y.shape}")
    print(f"[local_ai_model] Dimensione feature vector: {X.shape[1]} (include feature assetto, temperatura e tempo)")
    history = model.fit(X, Y, epochs=EPOCHS, batch_size=BATCH_SIZE, validation_split=0.2, verbose=1)
    
    # Monitora overfitting
    val_loss = history.history['val_loss'][-1]
    train_loss = history.history['loss'][-1]
    print(f"[local_ai_model] Training loss: {train_loss:.4f}, Validation loss: {val_loss:.4f}")
    if val_loss > train_loss * 1.5:
        print("[local_ai_model] ATTENZIONE: Possibile overfitting. Considera riduzione complessità modello.")
    os.makedirs(LOCAL_TF_MODEL_PATH, exist_ok=True)
    model_save_path = os.path.join(LOCAL_TF_MODEL_PATH, "model.keras")
    model.save(model_save_path)
    print("[local_ai_model] Modello salvato nel formato nativo Keras.")
    return model

def load_model():
    path = os.path.join(LOCAL_TF_MODEL_PATH, "model.keras")
    if not os.path.exists(path):
        return None
    return tf.keras.models.load_model(path)

def infer_advice_on_batch(telemetry_batch):
    """
    Analizza un batch di dati telemetrici e fornisce consigli dettagliati
    basati su molteplici aspetti della performance
    """
    model = load_model()
    if model is None:
        return "Modello inesistente. Fai training prima."
        
    X_list = []
    for td in telemetry_batch:
        feats = extract_features(td)
        
        # Estrai e analizza tutte le feature come nel create_dataset
        base_features = [
            feats["car_speed_kmh"],
            feats["avg_slip_ratio"],
            feats["throttle_pct"],
            feats["brake_pct"],
            feats["rpm"],
            feats["gear"]
        ]
        
        grip_features = [
            (feats["slip_ratios"]["FL"] + feats["slip_ratios"]["FR"]) / 2.0,
            (feats["slip_ratios"]["RL"] + feats["slip_ratios"]["RR"]) / 2.0,
            max(feats["tyre_temps"].values()) - min(feats["tyre_temps"].values()),
            (feats["tyre_temps"]["FL"] + feats["tyre_temps"]["FR"]) / 2.0 -
            (feats["tyre_temps"]["RL"] + feats["tyre_temps"]["RR"]) / 2.0,
        ]
        
        stability_features = [
            feats.get("suspension_balance", 0.0),
            feats.get("lateral_balance", 0.0),
            feats.get("body_roll", 0.0),
            feats.get("body_pitch", 0.0)
        ]
        
        brake_features = [
            feats.get("brake_temp_balance", 0.0),
            feats.get("brake_pressure_balance", 0.0)
        ]
        
        performance_features = [
            feats.get("longitudinal_acceleration", 0.0),
            feats.get("lateral_acceleration", 0.0),
            feats.get("power_delivery", 0.0),
            feats.get("brake_efficiency", 0.0)
        ]

        x_vec = (
            base_features +
            grip_features +
            stability_features +
            brake_features +
            performance_features
        )
        X_list.append(x_vec)

    if not X_list:
        return "Nessun dato nel batch."

    X = np.array(X_list, dtype=np.float32)
    predictions = model.predict(X)
    avg_prediction = float(np.mean(predictions))

    # Analisi dettagliata delle performance
    advice = []
    X_mean = np.mean(X, axis=0)

    # Analisi grip e bilanciamento
    front_grip = X_mean[6]  # Media slip ratio anteriore
    rear_grip = X_mean[7]  # Media slip ratio posteriore
    if abs(front_grip - rear_grip) > 0.1:
        advice.append("Sbilanciamento grip ant/post rilevato")

    # Analisi temperature
    temp_spread = X_mean[8]  # Spread temperature gomme
    if temp_spread > 20:
        advice.append("Eccessiva variazione temperature gomme")

    # Analisi stabilità
    suspension_balance = X_mean[10]  # Bilanciamento sospensioni
    if abs(suspension_balance) > 0.15:
        advice.append("Sbilanciamento sospensioni rilevato")

    # Analisi frenata
    brake_balance = X_mean[14]  # Efficienza frenata
    if abs(brake_balance) > 0.2:
        advice.append("Sbilanciamento frenata rilevato")

    # Analisi prestazioni complessive
    power_delivery = X_mean[16]  # Erogazione potenza
    if power_delivery < 0.7:
        advice.append("Erogazione potenza non ottimale")

    if not advice:
        advice.append("Setup generalmente bilanciato")

    detailed_analysis = ". ".join(advice)
    return f"Tempo stimato: {avg_prediction:.2f}s. Analisi: {detailed_analysis}"
