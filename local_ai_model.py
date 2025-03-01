# local_ai_model.py

import os
import sqlite3
import numpy as np
import tensorflow as tf
from tensorflow import keras

from config import DB_PATH, LOCAL_TF_MODEL_PATH, EPOCHS, BATCH_SIZE, LEARNING_RATE
from db_manager import load_all_telemetry
from mechanics import extract_features

try:
    tf.config.set_visible_devices([], 'GPU')
except:
    pass

def row_to_dict(row):
    return {
        # Indici come in db_manager
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

        x_vec = [
            feats["car_speed_kmh"],
            feats["avg_slip_ratio"],
            feats["throttle_pct"],
            feats["brake_pct"],
            feats["rpm"],
            feats["gear"]
        ]
        best_lap_s = td["best_lap"] if td["best_lap"] else 0.0
        X_list.append(x_vec)
        Y_list.append(best_lap_s)

    X = np.array(X_list, dtype=np.float32)
    Y = np.array(Y_list, dtype=np.float32)
    return X, Y

def build_model(input_dim):
    model = keras.Sequential([
        keras.layers.Dense(64, activation='relu', input_shape=(input_dim,)),
        keras.layers.Dense(64, activation='relu'),
        keras.layers.Dense(1)
    ])
    opt = keras.optimizers.Adam(learning_rate=LEARNING_RATE)
    model.compile(optimizer=opt, loss='mse')
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
    model.fit(X, Y, epochs=5, batch_size=64, validation_split=0.1)
    os.makedirs(LOCAL_TF_MODEL_PATH, exist_ok=True)
    model.save(os.path.join(LOCAL_TF_MODEL_PATH, "model.h5"))
    print("[local_ai_model] Modello salvato.")
    return model

def load_model():
    path = os.path.join(LOCAL_TF_MODEL_PATH, "model.h5")
    if not os.path.exists(path):
        return None
    return keras.models.load_model(path)

def infer_advice_on_batch(telemetry_batch):
    model = load_model()
    if model is None:
        return "Modello inesistente. Fai training prima."
    X_list = []
    for td in telemetry_batch:
        feats = extract_features(td)
        x_vec = [
            feats["car_speed_kmh"],
            feats["avg_slip_ratio"],
            feats["throttle_pct"],
            feats["brake_pct"],
            feats["rpm"],
            feats["gear"]
        ]
        X_list.append(x_vec)
    if not X_list:
        return "Nessun dato nel batch."
    X = np.array(X_list, dtype=np.float32)
    preds = model.predict(X)
    avg_pred = float(np.mean(preds))
    return f"Stima best_lap medio: {avg_pred:.2f} s. Riduci slip ratio e ottimizza l'assetto!"
