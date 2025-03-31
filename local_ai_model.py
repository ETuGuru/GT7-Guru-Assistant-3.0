import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model as tf_load_model
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.model_selection import train_test_split
from db_manager import load_telemetry_for_training, create_thread_safe_connection
from mechanics import extract_features

print("Dispositivi disponibili:", tf.config.list_physical_devices())

def train_model():
    """
    Addestra un modello di deep learning sui dati di telemetria.
    Utilizza EarlyStopping e ReduceLROnPlateau per evitare overfitting.
    """
    # Crea connessione al database
    conn, _ = create_thread_safe_connection("telemetry.db")
    
    # Carica dati dal DB
    telemetry_data = load_telemetry_for_training(conn, min_laps=1)
    if not telemetry_data:
        print("[local_ai_model] Nessun dato di training disponibile")
        return None
        
    X_list = []
    y_list = []
    
    for td in telemetry_data:
        try:
            # Estrai feature senza logging verboso
            feats = extract_features(td, verbose_logging=False)
            
            x_vec = [
                feats["car_speed_kmh"],
                feats["avg_slip_ratio"],
                feats["throttle_pct"],
                feats["brake_pct"],
                feats["rpm"],
                feats["gear"]
            ]
            
            # Feature aggiuntive per grip e stabilita
            grip_vec = [
                (feats["slip_ratios"]["FL"] + feats["slip_ratios"]["FR"]) / 2.0,
                (feats["slip_ratios"]["RL"] + feats["slip_ratios"]["RR"]) / 2.0,
                max(feats["tyre_temps"].values()) - min(feats["tyre_temps"].values()),
                (feats["tyre_temps"]["FL"] + feats["tyre_temps"]["FR"]) / 2.0 -
                (feats["tyre_temps"]["RL"] + feats["tyre_temps"]["RR"]) / 2.0
            ]
            
            stability_vec = [
                feats.get("suspension_balance", 0.0),
                feats.get("lateral_balance", 0.0),
                feats.get("body_roll", 0.0),
                feats.get("body_pitch", 0.0)
            ]
            
            # Combina tutti i vettori
            x_vec.extend(grip_vec)
            x_vec.extend(stability_vec)
            
            X_list.append(x_vec)
            y_list.append(td.get("last_lap", 0.0))
            
        except Exception as e:
            print(f"[local_ai_model] Errore estrazione feature: {e}")
            continue
    
    if not X_list:
        print("[local_ai_model] Nessuna feature estratta correttamente")
        conn.close()
        return None
        
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    
    print(f"[local_ai_model] Training su X={X.shape}, Y={y.shape}")
    print(f"[local_ai_model] Dimensione feature vector: {X.shape[1]}")
    
    # Split train/validation
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Costruisci modello piu semplice per evitare overfitting
    model = Sequential([
        Dense(32, activation="relu", input_shape=(X.shape[1],)),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dropout(0.1),
        Dense(1)
    ])
    
    model.compile(optimizer="adam", loss="mse", metrics=["mae", "mse"])
    
    # Callbacks per prevenire overfitting
    early_stopping = EarlyStopping(
        monitor="val_loss",
        patience=3,
        restore_best_weights=True
    )
    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        min_lr=1e-6
    )
    
    # Training con early stopping
    history = model.fit(
        X_train, y_train,
        epochs=20,
        batch_size=64,
        validation_data=(X_val, y_val),
        callbacks=[early_stopping, reduce_lr]
    )
    
    # Valuta il modello
    train_loss = history.history["loss"][-1]
    val_loss = history.history["val_loss"][-1]
    print(f"[local_ai_model] Training loss: {train_loss:.4f}, Validation loss: {val_loss:.4f}")
    
    if val_loss > train_loss * 1.5:
        print("[local_ai_model] ATTENZIONE: Possibile overfitting")
        
    # Salva il modello
    # Verifica che la directory 'models' esista e creala se necessario
    if not os.path.exists("models"):
        os.makedirs("models")
        print("[local_ai_model] Directory 'models' creata")
    model.save("models/lap_time_predictor.keras")
    print("[local_ai_model] Modello salvato nel formato nativo Keras")
    
    conn.close()
    return model


def infer_advice_on_batch(telemetry_batch):
    """
    Analizza un batch di dati telemetrici raccolti in un giro completo.
    Esegue analisi solo se il giro è completato.
    """
    model = load_model()
    if model is None:
        return "⚠️ Modello inesistente. Fai training prima."

    if not telemetry_batch:
        return "⚠️ Nessun dato ricevuto. Impossibile eseguire l’analisi."

    # Controllo dimensione batch minima
    if len(telemetry_batch) < 150:
        return f"⚠️ Solo {len(telemetry_batch)} pacchetti disponibili. Attendere più dati."

    print(f"✅ Analisi di {len(telemetry_batch)} pacchetti di telemetria su un giro completato...")

    X_list = []
    for td in telemetry_batch:
        try:
            feats = extract_features(td, verbose_logging=False)

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
                (feats["tyre_temps"]["RL"] + feats["tyre_temps"]["RR"]) / 2.0
            ]

            stability_features = [
                feats.get("suspension_balance", 0.0),
                feats.get("lateral_balance", 0.0),
                feats.get("body_roll", 0.0),
                feats.get("body_pitch", 0.0)
            ]

            x_vec = base_features + grip_features + stability_features
            X_list.append(x_vec)

        except Exception as e:
            print(f"⚠️ Errore estrazione feature per un pacchetto: {e}")
            continue

    if not X_list:
        return "❌ Errore elaborazione dati telemetrici. Nessun vettore valido estratto."

    X = np.array(X_list, dtype=np.float32)
    predictions = model.predict(X, verbose=0)
    avg_prediction = float(np.mean(predictions))
    avg_prediction /= 1000  # da ms → s

    minuti = int(avg_prediction // 60)
    secondi = avg_prediction % 60
    tempo_formattato = f"{minuti}:{secondi:05.2f}"

    return f"⏱️ Tempo stimato: {tempo_formattato} (≈ {avg_prediction:.2f} s). Analisi completata con successo."
    
def load_model():
    try:
        return tf_load_model("models/lap_time_predictor.keras")
    except:
        print("[local_ai_model] Errore nel caricamento del modello")
        return None
