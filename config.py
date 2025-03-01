# config.py

import os

DB_PATH = "gt7_telemetry.db"

# Frequenza di telemetria (10 Hz)
TELEMETRY_HZ = 10

# Parametri di training ML
EPOCHS = 5
BATCH_SIZE = 64
LEARNING_RATE = 0.001

# Path dove salvare e caricare il modello TensorFlow
LOCAL_TF_MODEL_PATH = "local_tf_model"

# Modello LLM locale
LOCAL_LLM_MODEL_NAME = "gpt2"
