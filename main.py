import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3

from db_manager import init_db, load_recent_telemetry, clear_telemetry, save_config
from gt7communication import GT7TelemetryListener
from local_ai_model import train_model, infer_advice_on_batch
from falcon_llm import FalconLLM
from config import DB_PATH

# Imposta la cache di Hugging Face nella cartella locale
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "huggingface_cache")
CONFIG_FILE = "config.json"

def load_config():
    """Carica la configurazione di default, comprensiva di tutti i parametri di assetto."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # Configurazione di default
    return {
        "auto": "",
        "gomme": "",
        "circuito": "",
        # Sospensioni
        "altezza_ant": "100", "altezza_post": "100",
        "altezza_ant_min": "", "altezza_ant_max": "",
        "altezza_post_min": "", "altezza_post_max": "",
        "barre_ant": "5", "barre_post": "5",
        "barre_ant_min": "", "barre_ant_max": "",
        "barre_post_min": "", "barre_post_max": "",
        "ammort_compressione_ant": "50", "ammort_compressione_post": "50",
        "ammort_compressione_ant_min": "", "ammort_compressione_ant_max": "",
        "ammort_compressione_post_min": "", "ammort_compressione_post_max": "",
        "ammort_estensione_ant": "50", "ammort_estensione_post": "50",
        "ammort_estensione_ant_min": "", "ammort_estensione_ant_max": "",
        "ammort_estensione_post_min": "", "ammort_estensione_post_max": "",
        "frequenza_ant": "10", "frequenza_post": "10",
        "frequenza_ant_min": "", "frequenza_ant_max": "",
        "frequenza_post_min": "", "frequenza_post_max": "",
        # Geometria
        "campanatura_ant": "-2", "campanatura_post": "-2",
        "campanatura_ant_min": "", "campanatura_ant_max": "",
        "campanatura_post_min": "", "campanatura_post_max": "",
        "conv_ant": "0", "conv_post": "0",
        "conv_ant_min": "", "conv_ant_max": "",
        "conv_post_min": "", "conv_post_max": "",
        # Differenziale
        "diff_coppia_ant": "5", "diff_coppia_post": "5",
        "diff_coppia_ant_min": "", "diff_coppia_ant_max": "",
        "diff_coppia_post_min": "", "diff_coppia_post_max": "",
        "diff_acc_ant": "5", "diff_acc_post": "5",
        "diff_acc_ant_min": "", "diff_acc_ant_max": "",
        "diff_acc_post_min": "", "diff_acc_post_max": "",
        "diff_frenata_ant": "5", "diff_frenata_post": "5",
        "diff_frenata_ant_min": "", "diff_frenata_ant_max": "",
        "diff_frenata_post_min": "", "diff_frenata_post_max": "",
        "diff_distrib": "50:50",  # es. "0:100", "5:95", "10:90"...
        # Aerodinamica
        "deportanza_ant": "50", "deportanza_post": "50",
        "deportanza_ant_min": "", "deportanza_ant_max": "",
        "deportanza_post_min": "", "deportanza_post_max": "",
        # Prestazioni
        "ecu_reg_potenza": "100",
        "ecu_reg_potenza_min": "", "ecu_reg_potenza_max": "",
        "zavorra": "0",
        "zavorra_min": "", "zavorra_max": "",
        "pos_zavorra": "0",  # -50 anteriore, +50 posteriore
        "limitatore": "100",
        "limitatore_min": "", "limitatore_max": "",
        "freni": "0",
        "freni_min": "", "freni_max": "",
        # Cambio
        "rapporti": "2.83,2.10,1.70,1.45,1.30,1.20,0.00,0.00",
        "rapporto_finale": "4.00"
    }

def save_config_data(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# --- Database per i default di assetto (Car ID) ---
def init_assetto_defaults_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS assetto_defaults (
        car_id TEXT PRIMARY KEY,
        -- qui puoi definire le stesse colonne per parametri di default (se necessario)
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn

def load_car_defaults(conn, car_id):
    c = conn.cursor()
    # in questo esempio la tabella assetto_defaults è minima, da espandere se vuoi salvare i parametri
    c.execute("SELECT * FROM assetto_defaults WHERE car_id = ?", (car_id,))
    row = c.fetchone()
    if row:
        columns = [col[0] for col in c.description]
        return dict(zip(columns, row))
    else:
        return None

def save_car_defaults(conn, car_id, data):
    c = conn.cursor()
    # in questo esempio salviamo solo car_id, ma potresti aggiungere tutte le colonne
    c.execute("""
    INSERT OR REPLACE INTO assetto_defaults (car_id) VALUES (?)
    """, (car_id,))
    conn.commit()

# --- Classe GUI ---
class GT7GuruGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GT7 Guru Assistant 3.0")
        self.config = load_config()
        self.conn = init_db(DB_PATH)
        self.defaults_conn = init_assetto_defaults_db(DB_PATH)
        self.listener = GT7TelemetryListener(self.conn)
        self.llm = None
        self.llm_loaded = False
        self.create_widgets()
        self.update_carid_status()

    def create_widgets(self):
        # Notebook
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, columnspan=7, sticky="nsew")

        # 1. Tab Dati contestuali
        self.tab_context = ttk.Frame(notebook)
        notebook.add(self.tab_context, text="Dati contestuali")

        # Auto, gomme, circuito
        ttk.Label(self.tab_context, text="Auto (nome+anno):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.entry_car = ttk.Entry(self.tab_context, width=30)
        self.entry_car.insert(0, self.config.get("auto", ""))
        self.entry_car.grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(self.tab_context, text="Gomme:").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.entry_tyre = ttk.Entry(self.tab_context, width=30)
        self.entry_tyre.insert(0, self.config.get("gomme", ""))
        self.entry_tyre.grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(self.tab_context, text="Circuito / Variante:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.entry_circuit = ttk.Entry(self.tab_context, width=30)
        self.entry_circuit.insert(0, self.config.get("circuito", ""))
        self.entry_circuit.grid(row=1, column=1, padx=5, pady=2)

        # Car ID + indicator + pulsanti
        ttk.Label(self.tab_context, text="Car ID:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.entry_car_id = ttk.Entry(self.tab_context, width=20)
        self.entry_car_id.grid(row=2, column=1, padx=5, pady=2)
        self.label_carid_status = ttk.Label(self.tab_context, text="N/D", foreground="red")
        self.label_carid_status.grid(row=2, column=2, padx=5, pady=2)
        self.btn_load_carid = ttk.Button(self.tab_context, text="Load Car_ID", command=self.load_car_defaults)
        self.btn_load_carid.grid(row=2, column=3, padx=5, pady=2)
        self.btn_save_carid = ttk.Button(self.tab_context, text="Save Car_ID", command=self.save_car_defaults)
        self.btn_save_carid.grid(row=2, column=4, padx=5, pady=2)

        # 2. Tab Parametri Assetto
        self.tab_params = ttk.Frame(notebook)
        notebook.add(self.tab_params, text="Parametri Assetto")

        # Header: 7 colonne
        headers = ["Parametro", "Ant.", "Post.", "Ant. min", "Ant. max", "Post. min", "Post. max"]
        for idx, text in enumerate(headers):
            ttk.Label(self.tab_params, text=text, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=idx, padx=5, pady=2)

        row = 1
        # Altezza dal suolo
        ttk.Label(self.tab_params, text="Altezza suolo (mm)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_altezza_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_altezza_ant.insert(0, self.config.get("altezza_ant", "100"))
        self.entry_altezza_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_altezza_post = ttk.Entry(self.tab_params, width=10)
        self.entry_altezza_post.insert(0, self.config.get("altezza_post", "100"))
        self.entry_altezza_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_altezza_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_ant_min.insert(0, self.config.get("altezza_ant_min", ""))
        self.entry_altezza_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_altezza_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_ant_max.insert(0, self.config.get("altezza_ant_max", ""))
        self.entry_altezza_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_altezza_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_post_min.insert(0, self.config.get("altezza_post_min", ""))
        self.entry_altezza_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_altezza_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_post_max.insert(0, self.config.get("altezza_post_max", ""))
        self.entry_altezza_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Barre Antirollio
        ttk.Label(self.tab_params, text="Barre Antirollio").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_barre_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_barre_ant.insert(0, self.config.get("barre_ant", "5"))
        self.entry_barre_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_barre_post = ttk.Entry(self.tab_params, width=10)
        self.entry_barre_post.insert(0, self.config.get("barre_post", "5"))
        self.entry_barre_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_barre_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_ant_min.insert(0, self.config.get("barre_ant_min", ""))
        self.entry_barre_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_barre_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_ant_max.insert(0, self.config.get("barre_ant_max", ""))
        self.entry_barre_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_barre_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_post_min.insert(0, self.config.get("barre_post_min", ""))
        self.entry_barre_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_barre_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_post_max.insert(0, self.config.get("barre_post_max", ""))
        self.entry_barre_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Ammortizzazione Compressione
        ttk.Label(self.tab_params, text="Ammort. Compressione (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_comp_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_comp_ant.insert(0, self.config.get("ammort_compressione_ant", "50"))
        self.entry_comp_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_comp_post = ttk.Entry(self.tab_params, width=10)
        self.entry_comp_post.insert(0, self.config.get("ammort_compressione_post", "50"))
        self.entry_comp_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_comp_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_comp_ant_min.insert(0, self.config.get("ammort_compressione_ant_min", ""))
        self.entry_comp_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_comp_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_comp_ant_max.insert(0, self.config.get("ammort_compressione_ant_max", ""))
        self.entry_comp_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_comp_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_comp_post_min.insert(0, self.config.get("ammort_compressione_post_min", ""))
        self.entry_comp_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_comp_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_comp_post_max.insert(0, self.config.get("ammort_compressione_post_max", ""))
        self.entry_comp_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Ammortizzazione Estensione
        ttk.Label(self.tab_params, text="Ammort. Estensione (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_est_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_est_ant.insert(0, self.config.get("ammort_estensione_ant", "50"))
        self.entry_est_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_est_post = ttk.Entry(self.tab_params, width=10)
        self.entry_est_post.insert(0, self.config.get("ammort_estensione_post", "50"))
        self.entry_est_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_est_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_est_ant_min.insert(0, self.config.get("ammort_estensione_ant_min", ""))
        self.entry_est_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_est_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_est_ant_max.insert(0, self.config.get("ammort_estensione_ant_max", ""))
        self.entry_est_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_est_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_est_post_min.insert(0, self.config.get("ammort_estensione_post_min", ""))
        self.entry_est_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_est_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_est_post_max.insert(0, self.config.get("ammort_estensione_post_max", ""))
        self.entry_est_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Frequenza Naturale
        ttk.Label(self.tab_params, text="Frequenza Nat. (Hz)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_freq_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_freq_ant.insert(0, self.config.get("frequenza_ant", "10"))
        self.entry_freq_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_freq_post = ttk.Entry(self.tab_params, width=10)
        self.entry_freq_post.insert(0, self.config.get("frequenza_post", "10"))
        self.entry_freq_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_freq_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_freq_ant_min.insert(0, self.config.get("frequenza_ant_min", ""))
        self.entry_freq_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_freq_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_freq_ant_max.insert(0, self.config.get("frequenza_ant_max", ""))
        self.entry_freq_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_freq_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_freq_post_min.insert(0, self.config.get("frequenza_post_min", ""))
        self.entry_freq_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_freq_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_freq_post_max.insert(0, self.config.get("frequenza_post_max", ""))
        self.entry_freq_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Campanatura
        ttk.Label(self.tab_params, text="Campanatura (°)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_camp_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_camp_ant.insert(0, self.config.get("campanatura_ant", "-2"))
        self.entry_camp_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_camp_post = ttk.Entry(self.tab_params, width=10)
        self.entry_camp_post.insert(0, self.config.get("campanatura_post", "-2"))
        self.entry_camp_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_camp_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_camp_ant_min.insert(0, self.config.get("campanatura_ant_min", ""))
        self.entry_camp_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_camp_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_camp_ant_max.insert(0, self.config.get("campanatura_ant_max", ""))
        self.entry_camp_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_camp_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_camp_post_min.insert(0, self.config.get("campanatura_post_min", ""))
        self.entry_camp_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_camp_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_camp_post_max.insert(0, self.config.get("campanatura_post_max", ""))
        self.entry_camp_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Angolo Convergenza
        ttk.Label(self.tab_params, text="Angolo Convergenza (°)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_conv_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_conv_ant.insert(0, self.config.get("conv_ant", "0"))
        self.entry_conv_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_conv_post = ttk.Entry(self.tab_params, width=10)
        self.entry_conv_post.insert(0, self.config.get("conv_post", "0"))
        self.entry_conv_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_conv_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_ant_min.insert(0, self.config.get("conv_ant_min", ""))
        self.entry_conv_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_conv_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_ant_max.insert(0, self.config.get("conv_ant_max", ""))
        self.entry_conv_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_conv_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_post_min.insert(0, self.config.get("conv_post_min", ""))
        self.entry_conv_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_conv_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_post_max.insert(0, self.config.get("conv_post_max", ""))
        self.entry_conv_post_max.grid(row=row, column=6, padx=5, pady=2)
        ttk.Label(self.tab_params, text="(Usa '+' convergente, '-' divergente)").grid(row=row, column=7, padx=5, pady=2)
        row += 1

        # Differenziale - Coppia Iniziale
        ttk.Label(self.tab_params, text="Diff. Coppia Iniziale").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_coppia_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_coppia_ant.insert(0, self.config.get("diff_coppia_ant", "5"))
        self.entry_diff_coppia_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_diff_coppia_post = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_coppia_post.insert(0, self.config.get("diff_coppia_post", "5"))
        self.entry_diff_coppia_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_diff_coppia_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_coppia_ant_min.insert(0, self.config.get("diff_coppia_ant_min", ""))
        self.entry_diff_coppia_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_diff_coppia_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_coppia_ant_max.insert(0, self.config.get("diff_coppia_ant_max", ""))
        self.entry_diff_coppia_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_diff_coppia_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_coppia_post_min.insert(0, self.config.get("diff_coppia_post_min", ""))
        self.entry_diff_coppia_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_diff_coppia_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_coppia_post_max.insert(0, self.config.get("diff_coppia_post_max", ""))
        self.entry_diff_coppia_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Differenziale - Sensibilità Accelerazione
        ttk.Label(self.tab_params, text="Diff. Sens. Accelerazione").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_acc_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_acc_ant.insert(0, self.config.get("diff_acc_ant", "5"))
        self.entry_diff_acc_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_diff_acc_post = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_acc_post.insert(0, self.config.get("diff_acc_post", "5"))
        self.entry_diff_acc_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_diff_acc_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_acc_ant_min.insert(0, self.config.get("diff_acc_ant_min", ""))
        self.entry_diff_acc_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_diff_acc_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_acc_ant_max.insert(0, self.config.get("diff_acc_ant_max", ""))
        self.entry_diff_acc_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_diff_acc_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_acc_post_min.insert(0, self.config.get("diff_acc_post_min", ""))
        self.entry_diff_acc_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_diff_acc_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_acc_post_max.insert(0, self.config.get("diff_acc_post_max", ""))
        self.entry_diff_acc_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Differenziale - Sensibilità Frenata
        ttk.Label(self.tab_params, text="Diff. Sens. Frenata").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_frenata_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_frenata_ant.insert(0, self.config.get("diff_frenata_ant", "5"))
        self.entry_diff_frenata_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_diff_frenata_post = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_frenata_post.insert(0, self.config.get("diff_frenata_post", "5"))
        self.entry_diff_frenata_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_diff_frenata_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_frenata_ant_min.insert(0, self.config.get("diff_frenata_ant_min", ""))
        self.entry_diff_frenata_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_diff_frenata_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_frenata_ant_max.insert(0, self.config.get("diff_frenata_ant_max", ""))
        self.entry_diff_frenata_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_diff_frenata_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_frenata_post_min.insert(0, self.config.get("diff_frenata_post_min", ""))
        self.entry_diff_frenata_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_diff_frenata_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_diff_frenata_post_max.insert(0, self.config.get("diff_frenata_post_max", ""))
        self.entry_diff_frenata_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # Distribuzione di Coppia
        ttk.Label(self.tab_params, text="Diff. Distribuzione").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_distrib = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_distrib.insert(0, self.config.get("diff_distrib", "50:50"))
        self.entry_diff_distrib.grid(row=row, column=1, padx=5, pady=2)
        # Lasciamo in bianco le altre colonne
        for col in range(2, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Deportanza
        ttk.Label(self.tab_params, text="Deportanza (livello)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_deportanza_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_deportanza_ant.insert(0, self.config.get("deportanza_ant", "50"))
        self.entry_deportanza_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_deportanza_post = ttk.Entry(self.tab_params, width=10)
        self.entry_deportanza_post.insert(0, self.config.get("deportanza_post", "50"))
        self.entry_deportanza_post.grid(row=row, column=2, padx=5, pady=2)
        self.entry_deportanza_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_deportanza_ant_min.insert(0, self.config.get("deportanza_ant_min", ""))
        self.entry_deportanza_ant_min.grid(row=row, column=3, padx=5, pady=2)
        self.entry_deportanza_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_deportanza_ant_max.insert(0, self.config.get("deportanza_ant_max", ""))
        self.entry_deportanza_ant_max.grid(row=row, column=4, padx=5, pady=2)
        self.entry_deportanza_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_deportanza_post_min.insert(0, self.config.get("deportanza_post_min", ""))
        self.entry_deportanza_post_min.grid(row=row, column=5, padx=5, pady=2)
        self.entry_deportanza_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_deportanza_post_max.insert(0, self.config.get("deportanza_post_max", ""))
        self.entry_deportanza_post_max.grid(row=row, column=6, padx=5, pady=2)
        row += 1

        # ECU Reg. Potenza
        ttk.Label(self.tab_params, text="ECU Reg. Potenza (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_ecu = ttk.Entry(self.tab_params, width=10)
        self.entry_ecu.insert(0, self.config.get("ecu_reg_potenza", "100"))
        self.entry_ecu.grid(row=row, column=1, padx=5, pady=2)
        self.entry_ecu_min = ttk.Entry(self.tab_params, width=5)
        self.entry_ecu_min.insert(0, self.config.get("ecu_reg_potenza_min", ""))
        self.entry_ecu_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_ecu_max = ttk.Entry(self.tab_params, width=5)
        self.entry_ecu_max.insert(0, self.config.get("ecu_reg_potenza_max", ""))
        self.entry_ecu_max.grid(row=row, column=3, padx=5, pady=2)
        for col in range(4, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Zavorra
        ttk.Label(self.tab_params, text="Zavorra (kg)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_zavorra = ttk.Entry(self.tab_params, width=10)
        self.entry_zavorra.insert(0, self.config.get("zavorra", "0"))
        self.entry_zavorra.grid(row=row, column=1, padx=5, pady=2)
        self.entry_zavorra_min = ttk.Entry(self.tab_params, width=5)
        self.entry_zavorra_min.insert(0, self.config.get("zavorra_min", ""))
        self.entry_zavorra_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_zavorra_max = ttk.Entry(self.tab_params, width=5)
        self.entry_zavorra_max.insert(0, self.config.get("zavorra_max", ""))
        self.entry_zavorra_max.grid(row=row, column=3, padx=5, pady=2)
        for col in range(4, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Posizionamento Zavorra
        ttk.Label(self.tab_params, text="Pos. Zavorra").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_pos_zavorra = ttk.Entry(self.tab_params, width=10)
        self.entry_pos_zavorra.insert(0, self.config.get("pos_zavorra", "0"))
        self.entry_pos_zavorra.grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(self.tab_params, text="(-50 anteriore, 0 centro, +50 posteriore)").grid(row=row, column=2, columnspan=3, padx=5, pady=2)
        for col in range(5, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Limitatore di potenza
        ttk.Label(self.tab_params, text="Limitatore (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_limitatore = ttk.Entry(self.tab_params, width=10)
        self.entry_limitatore.insert(0, self.config.get("limitatore", "100"))
        self.entry_limitatore.grid(row=row, column=1, padx=5, pady=2)
        self.entry_limitatore_min = ttk.Entry(self.tab_params, width=5)
        self.entry_limitatore_min.insert(0, self.config.get("limitatore_min", ""))
        self.entry_limitatore_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_limitatore_max = ttk.Entry(self.tab_params, width=5)
        self.entry_limitatore_max.insert(0, self.config.get("limitatore_max", ""))
        self.entry_limitatore_max.grid(row=row, column=3, padx=5, pady=2)
        for col in range(4, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Bilanciamento Freni
        ttk.Label(self.tab_params, text="Bilanc. Freni").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_freni = ttk.Entry(self.tab_params, width=10)
        self.entry_freni.insert(0, self.config.get("freni", "0"))
        self.entry_freni.grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(self.tab_params, text="(-5 ... +5)").grid(row=row, column=2, columnspan=2, padx=5, pady=2)
        for col in range(4, 7):
            ttk.Entry(self.tab_params, width=5).grid(row=row, column=col, padx=5, pady=2)
        row += 1

        # Tab Parametri Cambio
        self.tab_cambio = ttk.Frame(notebook)
        notebook.add(self.tab_cambio, text="Parametri Cambio")
        ttk.Label(self.tab_cambio, text="Marcia", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.tab_cambio, text="Rapporto", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, padx=5, pady=2)
        self.entry_rapporti = []
        default_ratios = self.config.get("rapporti", "2.83,2.10,1.70,1.45,1.30,1.20,0.00,0.00").split(',')
        for i in range(8):
            ttk.Label(self.tab_cambio, text=f"{i+1}ª marcia:").grid(row=i+1, column=0, sticky="e", padx=5, pady=2)
            entry = ttk.Entry(self.tab_cambio, width=10)
            if i < len(default_ratios):
                entry.insert(0, default_ratios[i].strip())
            self.entry_rapporti.append(entry)
            entry.grid(row=i+1, column=1, padx=5, pady=2)
        ttk.Label(self.tab_cambio, text="Rapporto finale:").grid(row=9, column=0, sticky="w", padx=5, pady=5)
        self.entry_rapporto_finale = ttk.Entry(self.tab_cambio, width=10)
        self.entry_rapporto_finale.insert(0, self.config.get("rapporto_finale", "4.00"))
        self.entry_rapporto_finale.grid(row=9, column=1, padx=5, pady=5)

        # Frame Suggerimenti AI
        self.frame_suggest = ttk.LabelFrame(self.root, text="Suggerimenti AI")
        self.frame_suggest.grid(row=3, column=0, columnspan=7, padx=5, pady=5, sticky="w")
        self.txt_suggest = scrolledtext.ScrolledText(self.frame_suggest, width=100, height=8)
        self.txt_suggest.pack(padx=5, pady=5)

        # Pulsanti principali
        self.btn_start = ttk.Button(self.root, text="Start", command=self.on_start)
        self.btn_stop = ttk.Button(self.root, text="Stop", command=self.on_stop)
        self.btn_analyze = ttk.Button(self.root, text="Analyze", command=self.on_analyze)
        self.btn_reset = ttk.Button(self.root, text="Reset DB", command=self.on_reset_db)
        self.btn_save_config = ttk.Button(self.root, text="Salva Config", command=self.on_save_config)
        self.btn_start.grid(row=4, column=0, padx=5, pady=5)
        self.btn_stop.grid(row=4, column=1, padx=5, pady=5)
        self.btn_analyze.grid(row=4, column=2, padx=5, pady=5)
        self.btn_reset.grid(row=4, column=3, padx=5, pady=5)
        self.btn_save_config.grid(row=4, column=4, padx=5, pady=5)

        # Area log/feedback
        self.txt_output = scrolledtext.ScrolledText(self.root, width=100, height=8)
        self.txt_output.grid(row=5, column=0, columnspan=7, padx=5, pady=5)
        self.lbl_feedback = ttk.Label(self.root, text="Feedback / Domanda:")
        self.lbl_feedback.grid(row=6, column=0, sticky="e", padx=5, pady=2)
        self.entry_feedback = ttk.Entry(self.root, width=50)
        self.entry_feedback.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        self.btn_feedback = ttk.Button(self.root, text="Invia", command=self.on_feedback)
        self.btn_feedback.grid(row=6, column=2, padx=5, pady=2)

    def update_carid_status(self):
        """Aggiorna l'indicatore di stato per Car ID (verde se dati trovati, rosso se non esistono)."""
        car_id = self.entry_car_id.get().strip()
        if car_id:
            defaults = load_car_defaults(self.defaults_conn, car_id)
            if defaults:
                self.label_carid_status.config(text="Dati trovati", foreground="green")
                self.btn_load_carid.config(state="normal")
            else:
                self.label_carid_status.config(text="Nessun dato", foreground="red")
                self.btn_load_carid.config(state="disabled")
        else:
            self.label_carid_status.config(text="N/D", foreground="red")
            self.btn_load_carid.config(state="disabled")
        self.root.after(3000, self.update_carid_status)

    def load_car_defaults(self):
        """Carica i parametri di default dal database, associati al Car ID inserito."""
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido.")
            return
        defaults = load_car_defaults(self.defaults_conn, car_id)
        if defaults:
            # In questo esempio salviamo/leggiamo solo car_id, ma potresti aggiungere tutte le colonne
            messagebox.showinfo("Load Car_ID", f"Dati caricati per Car ID {car_id} (se hai memorizzato parametri).")
        else:
            messagebox.showwarning("Load Car_ID", f"Nessun dato trovato per il Car ID {car_id}")

    def save_car_defaults(self):
        """Salva i parametri di default nel database, associati al Car ID."""
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido per salvare i dati.")
            return
        # In questo esempio, salviamo solo il car_id, ma puoi espandere il dict con tutti i parametri
        data = {}
        save_car_defaults(self.defaults_conn, car_id, data)
        messagebox.showinfo("Save Car_ID", f"Dati salvati per il Car ID {car_id}")
        self.update_carid_status()

    def on_analyze(self):
        """Esegue il training del modello ML locale, carica telemetria recente, e genera un consiglio dall'LLM."""
        self.listener.stop_listener()
        self.txt_output.insert(tk.END, "[INFO] Training modello ML...\n")
        model = train_model()
        if model is None:
            self.txt_output.insert(tk.END, "[WARN] Nessun dato per training.\n")
            return
        self.txt_output.insert(tk.END, "[INFO] Modello addestrato con successo.\n")
        rows = load_recent_telemetry(self.conn, limit=50)
        telemetry_batch = []
        for r in rows:
            tdict = {
                "car_speed": r[20],
                "tyre_speed_fl": r[21],
                "tyre_speed_fr": r[22],
                "tyre_speed_rl": r[23],
                "tyre_speed_rr": r[24],
                "throttle": r[51],
                "rpm": r[52],
                "brake": r[54],
                "current_gear": r[8],
                "car_model": r[63],
                "tyre_type": r[64],
                "circuit_name": r[65]
            }
            telemetry_batch.append(tdict)
        numeric_advice = infer_advice_on_batch(telemetry_batch)
        self.txt_output.insert(tk.END, f"[ML] {numeric_advice}\n")
        if not self.llm_loaded:
            self.txt_output.insert(tk.END, "[INFO] Caricamento LLM...\n")
            self.llm = FalconLLM()
            self.llm_loaded = True

        # Esempio di come costruire il contesto da passare all'LLM
        params = f"""(Riassunto parametri dall'interfaccia: Altezza Ant={self.entry_altezza_ant.get()}, 
Barre Ant={self.entry_barre_ant.get()}, ... ecc.)"""
        context = f"{numeric_advice}\n{params}\n" \
                  f"Auto: {telemetry_batch[-1].get('car_model', 'Sconosciuta')}, " \
                  f"Gomme: {telemetry_batch[-1].get('tyre_type', 'Sconosciute')}, " \
                  f"Circuito: {telemetry_batch[-1].get('circuit_name', 'Sconosciuto')}"
        suggestion = self.llm.generate_response(context)
        self.txt_suggest.delete(1.0, tk.END)
        self.txt_suggest.insert(tk.END, suggestion)

    def on_reset_db(self):
        clear_telemetry(self.conn)
        self.txt_output.insert(tk.END, "[INFO] Database resettato.\n")

    def on_save_config(self):
        """Salva i parametri correnti nel file config.json."""
        self.config["auto"] = self.entry_car.get().strip()
        self.config["gomme"] = self.entry_tyre.get().strip()
        self.config["circuito"] = self.entry_circuit.get().strip()
        # Sospensioni
        self.config["altezza_ant"] = self.entry_altezza_ant.get().strip()
        self.config["altezza_post"] = self.entry_altezza_post.get().strip()
        self.config["altezza_ant_min"] = self.entry_altezza_ant_min.get().strip()
        self.config["altezza_ant_max"] = self.entry_altezza_ant_max.get().strip()
        self.config["altezza_post_min"] = self.entry_altezza_post_min.get().strip()
        self.config["altezza_post_max"] = self.entry_altezza_post_max.get().strip()

        self.config["barre_ant"] = self.entry_barre_ant.get().strip()
        self.config["barre_post"] = self.entry_barre_post.get().strip()
        self.config["barre_ant_min"] = self.entry_barre_ant_min.get().strip()
        self.config["barre_ant_max"] = self.entry_barre_ant_max.get().strip()
        self.config["barre_post_min"] = self.entry_barre_post_min.get().strip()
        self.config["barre_post_max"] = self.entry_barre_post_max.get().strip()

        self.config["ammort_compressione_ant"] = self.entry_comp_ant.get().strip()
        self.config["ammort_compressione_post"] = self.entry_comp_post.get().strip()
        self.config["ammort_compressione_ant_min"] = self.entry_comp_ant_min.get().strip()
        self.config["ammort_compressione_ant_max"] = self.entry_comp_ant_max.get().strip()
        self.config["ammort_compressione_post_min"] = self.entry_comp_post_min.get().strip()
        self.config["ammort_compressione_post_max"] = self.entry_comp_post_max.get().strip()

        self.config["ammort_estensione_ant"] = self.entry_est_ant.get().strip()
        self.config["ammort_estensione_post"] = self.entry_est_post.get().strip()
        self.config["ammort_estensione_ant_min"] = self.entry_est_ant_min.get().strip()
        self.config["ammort_estensione_ant_max"] = self.entry_est_ant_max.get().strip()
        self.config["ammort_estensione_post_min"] = self.entry_est_post_min.get().strip()
        self.config["ammort_estensione_post_max"] = self.entry_est_post_max.get().strip()

        self.config["frequenza_ant"] = self.entry_freq_ant.get().strip()
        self.config["frequenza_post"] = self.entry_freq_post.get().strip()
        self.config["frequenza_ant_min"] = self.entry_freq_ant_min.get().strip()
        self.config["frequenza_ant_max"] = self.entry_freq_ant_max.get().strip()
        self.config["frequenza_post_min"] = self.entry_freq_post_min.get().strip()
        self.config["frequenza_post_max"] = self.entry_freq_post_max.get().strip()

        # Geometria
        self.config["campanatura_ant"] = self.entry_camp_ant.get().strip()
        self.config["campanatura_post"] = self.entry_camp_post.get().strip()
        self.config["campanatura_ant_min"] = self.entry_camp_ant_min.get().strip()
        self.config["campanatura_ant_max"] = self.entry_camp_ant_max.get().strip()
        self.config["campanatura_post_min"] = self.entry_camp_post_min.get().strip()
        self.config["campanatura_post_max"] = self.entry_camp_post_max.get().strip()

        self.config["conv_ant"] = self.entry_conv_ant.get().strip()
        self.config["conv_post"] = self.entry_conv_post.get().strip()
        self.config["conv_ant_min"] = self.entry_conv_ant_min.get().strip()
        self.config["conv_ant_max"] = self.entry_conv_ant_max.get().strip()
        self.config["conv_post_min"] = self.entry_conv_post_min.get().strip()
        self.config["conv_post_max"] = self.entry_conv_post_max.get().strip()

        # Differenziale
        self.config["diff_coppia_ant"] = self.entry_diff_coppia_ant.get().strip()
        self.config["diff_coppia_post"] = self.entry_diff_coppia_post.get().strip()
        self.config["diff_coppia_ant_min"] = self.entry_diff_coppia_ant_min.get().strip()
        self.config["diff_coppia_ant_max"] = self.entry_diff_coppia_ant_max.get().strip()
        self.config["diff_coppia_post_min"] = self.entry_diff_coppia_post_min.get().strip()
        self.config["diff_coppia_post_max"] = self.entry_diff_coppia_post_max.get().strip()

        self.config["diff_acc_ant"] = self.entry_diff_acc_ant.get().strip()
        self.config["diff_acc_post"] = self.entry_diff_acc_post.get().strip()
        self.config["diff_acc_ant_min"] = self.entry_diff_acc_ant_min.get().strip()
        self.config["diff_acc_ant_max"] = self.entry_diff_acc_ant_max.get().strip()
        self.config["diff_acc_post_min"] = self.entry_diff_acc_post_min.get().strip()
        self.config["diff_acc_post_max"] = self.entry_diff_acc_post_max.get().strip()

        self.config["diff_frenata_ant"] = self.entry_diff_frenata_ant.get().strip()
        self.config["diff_frenata_post"] = self.entry_diff_frenata_post.get().strip()
        self.config["diff_frenata_ant_min"] = self.entry_diff_frenata_ant_min.get().strip()
        self.config["diff_frenata_ant_max"] = self.entry_diff_frenata_ant_max.get().strip()
        self.config["diff_frenata_post_min"] = self.entry_diff_frenata_post_min.get().strip()
        self.config["diff_frenata_post_max"] = self.entry_diff_frenata_post_max.get().strip()

        self.config["diff_distrib"] = self.entry_diff_distrib.get().strip()

        # Aerodinamica
        self.config["deportanza_ant"] = self.entry_deportanza_ant.get().strip()
        self.config["deportanza_post"] = self.entry_deportanza_post.get().strip()
        self.config["deportanza_ant_min"] = self.entry_deportanza_ant_min.get().strip()
        self.config["deportanza_ant_max"] = self.entry_deportanza_ant_max.get().strip()
        self.config["deportanza_post_min"] = self.entry_deportanza_post_min.get().strip()
        self.config["deportanza_post_max"] = self.entry_deportanza_post_max.get().strip()

        # Prestazioni
        self.config["ecu_reg_potenza"] = self.entry_ecu.get().strip()
        self.config["ecu_reg_potenza_min"] = self.entry_ecu_min.get().strip()
        self.config["ecu_reg_potenza_max"] = self.entry_ecu_max.get().strip()
        self.config["zavorra"] = self.entry_zavorra.get().strip()
        self.config["zavorra_min"] = self.entry_zavorra_min.get().strip()
        self.config["zavorra_max"] = self.entry_zavorra_max.get().strip()
        self.config["pos_zavorra"] = self.entry_pos_zavorra.get().strip()
        self.config["limitatore"] = self.entry_limitatore.get().strip()
        self.config["limitatore_min"] = self.entry_limitatore_min.get().strip()
        self.config["limitatore_max"] = self.entry_limitatore_max.get().strip()
        self.config["freni"] = self.entry_freni.get().strip()

        # Cambio
        ratio_list = []
        for entry in self.entry_rapporti:
            ratio_list.append(entry.get().strip())
        self.config["rapporti"] = ",".join(ratio_list)
        self.config["rapporto_finale"] = self.entry_rapporto_finale.get().strip()

        save_config_data(self.config)
        self.txt_output.insert(tk.END, "[INFO] Configurazione salvata.\n")

    def on_feedback(self):
        fb = self.entry_feedback.get().strip()
        if not fb:
            return
        self.txt_output.insert(tk.END, f"[User] {fb}\n")
        if not self.llm_loaded or not self.llm:
            self.txt_output.insert(tk.END, "[WARN] LLM non caricato.\n")
            return
        resp = self.llm.generate_response(fb)
        self.txt_output.insert(tk.END, f"[LLM] {resp}\n")

    def on_start(self):
        car_str = self.entry_car.get().strip() or "Sconosciuta"
        tyre_str = self.entry_tyre.get().strip() or "Sconosciute"
        circuit_str = self.entry_circuit.get().strip() or "Sconosciuto"
        self.listener.car_model = car_str
        self.listener.tyre_type = tyre_str
        self.listener.circuit_name = circuit_str
        self.txt_output.insert(tk.END, f"[INFO] Avvio telemetria: Auto='{car_str}', Gomme='{tyre_str}', Circuito='{circuit_str}'\n")
        self.listener.start_listener()

    def on_stop(self):
        self.txt_output.insert(tk.END, "[INFO] Arresto telemetria.\n")
        self.listener.stop_listener()

def main():
    root = tk.Tk()
    root.geometry("1200x800")
    root.minsize(1200, 800)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    app = GT7GuruGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
