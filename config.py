# config.py

import os

DB_PATH = "gt7_telemetry.db"

# Frequenza (Hz) per la telemetria
TELEMETRY_HZ = 10

# Parametri Training ML
EPOCHS = 5
BATCH_SIZE = 64
LEARNING_RATE = 0.001

LOCAL_TF_MODEL_PATH = "local_tf_model"
LOCAL_LLM_MODEL_NAME = "gpt2"
