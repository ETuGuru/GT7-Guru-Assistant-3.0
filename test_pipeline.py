import logging
import sqlite3
import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from falcon_llm import FalconLLM

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_pipeline')

def load_data():
    """
    Carica i dati dalla telemetry.db
    """
    logger.info("Caricamento dati dal database telemetry.db")
    try:
        conn = sqlite3.connect('telemetry.db')
        query = "SELECT * FROM telemetry"
        df = pd.read_sql_query(query, conn)
        conn.close()
        logger.info(f"Dati caricati con successo: {len(df)} righe")
        return df
    except Exception as e:
        logger.error(f"Errore durante il caricamento dei dati: {e}")
        raise

def preprocess_data(df):
    """
    Preprocessa i dati usando TensorFlow
    """
    logger.info("Preprocessing dei dati con TensorFlow")
    
    # Rimuove le colonne non numeriche o non utili per la predizione
    numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns
    # Escludiamo best_lap perché sarà il nostro target
    feature_columns = [col for col in numeric_columns if col != 'best_lap']
    
    # Separazione features e target
    X = df[feature_columns].fillna(0)
    y = df['best_lap'].fillna(0)
    
    logger.debug(f"Feature selezionate: {feature_columns}")
    
    # Divisione train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Normalizzazione dei dati
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    logger.info("Dati preprocessati con successo")
    return X_train_scaled, X_test_scaled, y_train, y_test, feature_columns

def build_model(input_shape):
    """
    Costruisce un modello TensorFlow per la predizione
    """
    logger.info("Costruzione del modello TensorFlow")
    
    # Verifica dei dispositivi disponibili
    devices = tf.config.list_physical_devices()
    logger.info(f"Dispositivi TensorFlow disponibili: {devices}")
    
    # Costruzione del modello
    model = tf.keras.Sequential([
        tf.keras.layers.Dense(64, activation='relu', input_shape=(input_shape,)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    logger.info("Modello TensorFlow compilato con successo")
    return model

def train_and_predict(X_train, X_test, y_train, y_test):
    """
    Addestra il modello e fa una predizione
    """
    logger.info("Inizio addestramento del modello")
    
    # Costruzione del modello
    model = build_model(X_train.shape[1])
    
    # Addestramento
    logger.info("Addestramento del modello...")
    model.fit(
        X_train, y_train,
        epochs=50,
        batch_size=32,
        validation_split=0.2,
        verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)
        ]
    )
    
    # Valutazione
    loss, mae = model.evaluate(X_test, y_test, verbose=0)
    logger.info(f"Performance del modello - Loss: {loss:.4f}, MAE: {mae:.4f}")
    
    # Predizione su alcuni esempi
    predictions = model.predict(X_test[:5])
    actual_values = y_test.iloc[:5].values
    
    for i, (pred, actual) in enumerate(zip(predictions, actual_values)):
        logger.info(f"Esempio {i+1} - Predizione: {pred[0]:.4f}, Valore reale: {actual:.4f}")
    
    return predictions, actual_values

def generate_llm_response(predictions, actual_values, feature_importances=None):
    """
    Genera una risposta con FalconLLM basata sui risultati della predizione
    """
    logger.info("Generazione risposta con FalconLLM")
    
    try:
        # Inizializzazione del modello LLM
        llm = FalconLLM()
        
        # Preparazione dei dati telemetrici
        results_text = ""
        for i, (pred, actual) in enumerate(zip(predictions, actual_values)):
            results_text += f"- Esempio {i+1}: Predetto {pred[0]:.4f}, Reale {actual:.4f}, Errore {abs(pred[0] - actual):.4f}\n"
        
        # Creazione del dizionario di configurazione
        config_data = {
            "modello_veicolo": "Modello Test",
            "nome_circuito": "Circuito Simulato",
            "tipo_gomme": "Telemetria simulata"
        }
        
        # Preparazione dei dati telemetrici formattati
        telemetry_data = f"""
        Risultati modello ML per previsione best_lap:
        {results_text}
        
        Metriche di valutazione:
        - Errore medio: {sum([abs(p[0] - a) for p, a in zip(predictions, actual_values)]) / len(predictions):.4f}
        """
        
        # Generazione della risposta usando il metodo corretto
        response = llm.generate_response(config_data, telemetry_data)
        logger.info("Risposta LLM generata con successo")
        return response
        
    except Exception as e:
        logger.error(f"Errore durante la generazione della risposta LLM: {e}")
        return f"Errore nella generazione: {str(e)}"

def main():
    """
    Pipeline principale
    """
    logger.info("Avvio pipeline di test")
    
    try:
        # 1. Caricamento dati
        df = load_data()
        
        # 2. Preprocessing
        X_train, X_test, y_train, y_test, features = preprocess_data(df)
        
        # 3. Addestramento e predizione
        predictions, actual_values = train_and_predict(X_train, X_test, y_train, y_test)
        
        # 4. Generazione risposta LLM
        llm_response = generate_llm_response(predictions, actual_values)
        
        # 5. Output finale
        logger.info("Pipeline completata con successo")
        print("\n" + "="*50)
        print("RISULTATO FINALE DELLA PIPELINE:")
        print("="*50)
        print(llm_response)
        print("="*50)
        
    except Exception as e:
        logger.error(f"Errore nella pipeline: {e}")
        

if __name__ == "__main__":
    main()

