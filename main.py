import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3
import sys
import threading

from db_manager import init_db, load_recent_telemetry, clear_telemetry, save_config, initialize_database, create_thread_safe_connection
from gt7communication import GT7TelemetryListener
from local_ai_model import train_model, infer_advice_on_batch
from falcon_llm import FalconLLM
from config import DB_PATH

# Imposta la cache di Hugging Face nella cartella locale
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "huggingface_cache")
CONFIG_FILE = "config.json"

def load_config():
    import logging
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(levelname)s - %(message)s')
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Errore nel parsing del file di configurazione: {e}")
            # In caso di errore, crea un backup del file danneggiato
            if os.path.exists(CONFIG_FILE):
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{CONFIG_FILE}.{timestamp}.bak"
                try:
                    import shutil
                    shutil.copy2(CONFIG_FILE, backup_file)
                    logging.info(f"Backup del file di configurazione creato: {backup_file}")
                except Exception as be:
                    logging.error(f"Impossibile creare il backup del file: {be}")
        except IOError as ioe:
            logging.error(f"Errore di I/O durante la lettura del file di configurazione: {ioe}")
        except Exception as ex:
            logging.error(f"Errore imprevisto durante il caricamento della configurazione: {ex}")
            
    # Configurazione di default con tutti i parametri di assetto
    logging.info("Caricamento della configurazione di default")
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
        "diff_distrib": "50:50",  # Es. "0:100", "5:95", etc.
        # Aerodinamica
        "deportanza_ant": "50", "deportanza_post": "50",
        "deportanza_ant_min": "", "deportanza_ant_max": "",
        "deportanza_post_min": "", "deportanza_post_max": "",
        # Prestazioni
        "ecu_reg_potenza": "100",
        "ecu_reg_potenza_min": "", "ecu_reg_potenza_max": "",
        "zavorra": "0",
        "zavorra_min": "", "zavorra_max": "",
        "pos_zavorra": "0",  # -50 anteriore, +50 posteriore, 0 centro
        "limitatore": "100",
        "limitatore_min": "", "limitatore_max": "",
        "freni": "0",  # Bilanciamento Freni
        "freni_min": "", "freni_max": "",
        # Cambio
        "rapporti": "2.83,2.10,1.70,1.45,1.30,1.20,0.00,0.00",
        "rapporto_finale": "4.00"
    }

def save_config_data(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except (IOError, json.JSONDecodeError) as e:
        raise Exception(f"Errore nel salvataggio del file di configurazione: {e}")

# --- Classe GUI ---
class GT7GuruGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GT7 Guru Assistant 3.0")
        self.config = load_config()
        
        # Inizializza il database nel thread principale
        try:
            self.db_conn, self.db_lock = create_thread_safe_connection('telemetry.db')
            if not initialize_database(self.db_conn):
                messagebox.showerror("Errore", "Impossibile inizializzare il database")
                sys.exit(1)
        except Exception as e:
            messagebox.showerror("Errore Database", f"Errore nell'inizializzazione del database: {str(e)}")
            sys.exit(1)
        
        # Inizializza la connessione per i default delle auto
        try:
            self.defaults_conn = init_db("car_defaults.db")
        except sqlite3.Error as e:
            messagebox.showerror("Errore database", f"Impossibile inizializzare il database dei default: {str(e)}")
            self.defaults_conn = None
        
        # Crea il listener con la connessione al database e il lock
        self.listener = GT7TelemetryListener(self.db_conn, self.db_lock)
        self.listener.telemetry_callback = self.on_telemetry_data
        self.llm = None
        self.llm_loaded = False
        
        # Inizializza l'interfaccia utente
        self.create_widgets()
        self.update_carid_status()
        
    def create_widgets(self):
        """Crea tutti gli elementi dell'interfaccia utente"""
        """Crea tutti gli elementi dell'interfaccia utente"""
        # Creazione del notebook principale come variabile d'istanza
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, columnspan=7, sticky="nsew", padx=5, pady=5)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        # Tab 1: Dati contestuali
        self.tab_context = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_context, text="Dati contestuali")
        self.label_car = ttk.Label(self.tab_context, text="Auto (nome+anno):")
        self.label_car.grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.entry_car = ttk.Entry(self.tab_context, width=30)
        self.entry_car.insert(0, self.config.get("auto", ""))
        self.entry_car.grid(row=0, column=1, padx=5, pady=2)
        self.label_tyres = ttk.Label(self.tab_context, text="Gomme:")
        self.label_tyres.grid(row=0, column=2, sticky="e", padx=5, pady=2)
        self.entry_tyre = ttk.Entry(self.tab_context, width=30)
        self.entry_tyre.insert(0, self.config.get("gomme", ""))
        self.entry_tyre.grid(row=0, column=3, padx=5, pady=2)
        self.label_circuit = ttk.Label(self.tab_context, text="Circuito / Variante:")
        self.label_circuit.grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.entry_circuit = ttk.Entry(self.tab_context, width=30)
        self.entry_circuit.insert(0, self.config.get("circuito", ""))
        self.entry_circuit.grid(row=1, column=1, padx=5, pady=2)
        # Car ID e pulsanti
        self.label_car_id = ttk.Label(self.tab_context, text="Car ID:")
        self.label_car_id.grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.entry_car_id = ttk.Entry(self.tab_context, width=20)
        self.entry_car_id.grid(row=2, column=1, padx=5, pady=2)
        self.label_carid_status = ttk.Label(self.tab_context, text="N/D", foreground="red")
        self.label_carid_status.grid(row=2, column=2, padx=5, pady=2)
        self.btn_load_carid = ttk.Button(self.tab_context, text="Load Car_ID", command=self.load_car_defaults)
        self.btn_load_carid.grid(row=2, column=3, padx=5, pady=2)
        self.btn_save_carid = ttk.Button(self.tab_context, text="Save Car_ID", command=self.save_car_defaults)
        self.btn_save_carid.grid(row=2, column=4, padx=5, pady=2)

        # Tab 2: Parametri Assetto
        self.tab_params = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_params, text="Parametri Assetto")
        headers = ["Parametro", "Ant.", "Post.", "Ant. min", "Ant. max", "Post. min", "Post. max"]
        for idx, text in enumerate(headers):
            ttk.Label(self.tab_params, text=text, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=idx, padx=5, pady=2)
        row = 1
        # Altezza suolo (mm)
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

        # Ammortizzazione Compressione (%)
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

        # Ammortizzazione Estensione (%)
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

        # Frequenza Naturale (Hz)
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

        # Campanatura (°)
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

        # Angolo Convergenza (°) - inserire direttamente il valore con segno
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
        ttk.Label(self.tab_params, text="(Usa '+' per convergente, '-' per divergente)").grid(row=row, column=7, padx=5, pady=2)
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

        # Differenziale - Distribuzione di Coppia
        ttk.Label(self.tab_params, text="Diff. Distribuzione").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_distrib = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_distrib.insert(0, self.config.get("diff_distrib", "50:50"))
        self.entry_diff_distrib.grid(row=row, column=1, padx=5, pady=2)
        # Creazione di entry aggiuntive come variabili d'istanza per futuri riferimenti
        self.entry_diff_distrib_fields = []
        for col in range(2, 7):
            entry = ttk.Entry(self.tab_params, width=5)
            entry.grid(row=row, column=col, padx=5, pady=2)
            self.entry_diff_distrib_fields.append(entry)
        row += 1

        # Deportanza
        ttk.Label(self.tab_params, text="Deportanza").grid(row=row, column=0, sticky="e", padx=5, pady=2)
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

        # ECU Regolazione Potenza
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
        # Entry per altri campi ECU come variabili d'istanza
        self.entry_ecu_fields = []
        for col in range(4, 7):
            entry = ttk.Entry(self.tab_params, width=5)
            entry.grid(row=row, column=col, padx=5, pady=2)
            self.entry_ecu_fields.append(entry)
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
        # Entry per altri campi zavorra come variabili d'istanza
        self.entry_zavorra_fields = []
        for col in range(4, 7):
            entry = ttk.Entry(self.tab_params, width=5)
            entry.grid(row=row, column=col, padx=5, pady=2)
            self.entry_zavorra_fields.append(entry)
        row += 1

        # Posizionamento Zavorra (valore unico + didascalia)
        ttk.Label(self.tab_params, text="Pos. Zavorra").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_pos_zavorra = ttk.Entry(self.tab_params, width=10)
        self.entry_pos_zavorra.insert(0, self.config.get("pos_zavorra", "0"))
        self.entry_pos_zavorra.grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(self.tab_params, text="(-50 anteriore, 0 centro, +50 posteriore)").grid(row=row, column=2, columnspan=5, padx=5, pady=2)
        row += 1

        # Limitatore di Potenza
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
        # Entry per altri campi limitatore come variabili d'istanza
        self.entry_limitatore_fields = []
        for col in range(4, 7):
            entry = ttk.Entry(self.tab_params, width=5)
            entry.grid(row=row, column=col, padx=5, pady=2)
            self.entry_limitatore_fields.append(entry)
        row += 1

        # Bilanciamento Freni (singolo valore)
        ttk.Label(self.tab_params, text="Bilanc. Freni (-5..+5)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_freni = ttk.Entry(self.tab_params, width=10)
        self.entry_freni.insert(0, self.config.get("freni", "0"))
        self.entry_freni.grid(row=row, column=1, padx=5, pady=2)
        # Entry per campi aggiuntivi freni come variabili d'istanza
        self.entry_freni_fields = []
        for col in range(2, 7):
            entry = ttk.Entry(self.tab_params, width=5)
            entry.grid(row=row, column=col, padx=5, pady=2)
            self.entry_freni_fields.append(entry)
        row += 1

        # Tab 3: Parametri Cambio
        self.tab_cambio = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_cambio, text="Parametri Cambio")
        ttk.Label(self.tab_cambio, text="Marcia", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.tab_cambio, text="Rapporto", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, padx=5, pady=2)

        # Tab 4: Telemetry View
        self.tab_telemetry = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_telemetry, text="Telemetry View")
        
        # Divisione della tab in 4 sezioni
        # Sezione superiore sinistra: informazioni base (velocità, RPM, marcia)
        self.frame_basic_info = ttk.LabelFrame(self.tab_telemetry, text="Informazioni Base")
        self.frame_basic_info.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(self.frame_basic_info, text="Velocità (km/h):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_speed = ttk.Label(self.frame_basic_info, text="0", font=("TkDefaultFont", 16, "bold"))
        self.lbl_speed.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_basic_info, text="RPM:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.lbl_rpm = ttk.Label(self.frame_basic_info, text="0", font=("TkDefaultFont", 16, "bold"))
        self.lbl_rpm.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_basic_info, text="Marcia:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.lbl_gear = ttk.Label(self.frame_basic_info, text="N", font=("TkDefaultFont", 16, "bold"))
        self.lbl_gear.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_basic_info, text="Carburante:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.lbl_fuel = ttk.Label(self.frame_basic_info, text="0.0 L", font=("TkDefaultFont", 12))
        self.lbl_fuel.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        # Sezione superiore destra: temperature (gomme, freni, olio, acqua)
        self.frame_temperatures = ttk.LabelFrame(self.tab_telemetry, text="Temperature")
        self.frame_temperatures.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ttk.Label(self.frame_temperatures, text="Pneumatici (°C):").grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_temperatures, text="Ant. SX:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.lbl_tyre_temp_fl = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_tyre_temp_fl.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_temperatures, text="Ant. DX:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.lbl_tyre_temp_fr = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_tyre_temp_fr.grid(row=1, column=3, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_temperatures, text="Post. SX:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.lbl_tyre_temp_rl = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_tyre_temp_rl.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_temperatures, text="Post. DX:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.lbl_tyre_temp_rr = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_tyre_temp_rr.grid(row=2, column=3, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_temperatures, text="Olio (°C):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.lbl_oil_temp = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_oil_temp.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame_temperatures, text="Acqua (°C):").grid(row=3, column=2, padx=5, pady=5, sticky="w")
        self.lbl_water_temp = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_water_temp.grid(row=3, column=3, padx=5, pady=5, sticky="w")
        
        # Sezione inferiore sinistra: indicatori di performance (acceleratore, freno, forze G)
        self.frame_performance = ttk.LabelFrame(self.tab_telemetry, text="Performance")
        self.frame_performance.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(self.frame_performance, text="Acceleratore (%):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_throttle = ttk.Label(self.frame_performance, text="0")
        self.lbl_throttle.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_performance, text="Freno (%):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.lbl_brake = ttk.Label(self.frame_performance, text="0")
        self.lbl_brake.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_performance, text="Forza G Laterale:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.lbl_lateral_g = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_lateral_g.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_performance, text="Forza G Longitudinale:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.lbl_longitudinal_g = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_longitudinal_g.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_performance, text="Pressione Turbo:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.lbl_boost = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_boost.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_performance, text="Slip Ratio (%):").grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        ttk.Label(self.frame_performance, text="Ant. SX:").grid(row=6, column=0, padx=5, pady=2, sticky="w")
        self.lbl_slip_fl = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_slip_fl.grid(row=6, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_performance, text="Ant. DX:").grid(row=6, column=2, padx=5, pady=2, sticky="w")
        self.lbl_slip_fr = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_slip_fr.grid(row=6, column=3, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_performance, text="Post. SX:").grid(row=7, column=0, padx=5, pady=2, sticky="w")
        self.lbl_slip_rl = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_slip_rl.grid(row=7, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_performance, text="Post. DX:").grid(row=7, column=2, padx=5, pady=2, sticky="w")
        self.lbl_slip_rr = ttk.Label(self.frame_performance, text="0.0")
        self.lbl_slip_rr.grid(row=7, column=3, padx=5, pady=2, sticky="w")
        
        # Sezione inferiore destra: tempi e posizione (best lap, last lap, settori)
        self.frame_timing = ttk.LabelFrame(self.tab_telemetry, text="Tempi e Posizione")
        self.frame_timing.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(self.frame_timing, text="Best Lap Time:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_best_lap = ttk.Label(self.frame_timing, text="00:00.000", font=("TkDefaultFont", 12))
        self.lbl_best_lap.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_timing, text="Last Lap Time:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.lbl_last_lap = ttk.Label(self.frame_timing, text="00:00.000", font=("TkDefaultFont", 12))
        self.lbl_last_lap.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_timing, text="Current Lap Time:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.lbl_current_lap = ttk.Label(self.frame_timing, text="00:00.000", font=("TkDefaultFont", 12))
        self.lbl_current_lap.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_timing, text="Sector 1:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.lbl_sector1 = ttk.Label(self.frame_timing, text="00:00.000")
        self.lbl_sector1.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_timing, text="Sector 2:").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.lbl_sector2 = ttk.Label(self.frame_timing, text="00:00.000")
        self.lbl_sector2.grid(row=4, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_timing, text="Sector 3:").grid(row=5, column=0, padx=5, pady=2, sticky="w")
        self.lbl_sector3 = ttk.Label(self.frame_timing, text="00:00.000")
        self.lbl_sector3.grid(row=5, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_timing, text="Track Position:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.lbl_track_position = ttk.Label(self.frame_timing, text="0/0")
        self.lbl_track_position.grid(row=6, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(self.frame_timing, text="Track Progress:").grid(row=7, column=0, padx=5, pady=5, sticky="w")
        self.lbl_track_progress = ttk.Label(self.frame_timing, text="0 %")
        self.lbl_track_progress.grid(row=7, column=1, padx=5, pady=5, sticky="w")
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

        # Tab Suggerimenti AI
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
        car_id = self.entry_car_id.get().strip()
        if car_id:
            try:
                defaults = self.load_car_defaults_from_db(car_id)
                if defaults:
                    self.label_carid_status.config(text="Dati trovati", foreground="green")
                    self.btn_load_carid.config(state="normal")
                else:
                    self.label_carid_status.config(text="Nessun dato", foreground="red")
                    self.btn_load_carid.config(state="disabled")
            except Exception as e:
                self.label_carid_status.config(text="Errore", foreground="red")
                self.btn_load_carid.config(state="disabled")
                self.txt_output.insert(tk.END, f"[ERRORE] Lettura Car ID: {str(e)}\n")
        else:
            self.label_carid_status.config(text="N/D", foreground="red")
            self.btn_load_carid.config(state="disabled")
        self.root.after(3000, self.update_carid_status)

    def load_car_defaults(self):
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido.")
            return
        try:
            defaults = self.load_car_defaults_from_db(car_id)
            if defaults:
                # Aggiorna i campi della GUI se implementi il salvataggio completo
                messagebox.showinfo("Load Car_ID", f"Dati caricati per Car ID {car_id}.")
            else:
                messagebox.showwarning("Load Car_ID", f"Nessun dato trovato per il Car ID {car_id}.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante il caricamento dei dati: {str(e)}")

    def load_car_defaults_from_db(self, car_id):
        """Carica i dati dell'auto dal database"""
        if not self.defaults_conn:
            raise Exception("Connessione al database non disponibile")
        
        try:
            c = self.defaults_conn.cursor()
            # Verifica se la tabella esiste
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='car_defaults'")
            if not c.fetchone():
                return None
                
            c.execute("SELECT data FROM car_defaults WHERE car_id = ?", (car_id,))
            result = c.fetchone()
            if result:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError as je:
                    raise Exception(f"Errore nel parsing dei dati JSON: {je}")
            return None
        except sqlite3.Error as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Database: {str(e)}\n")
            raise Exception(f"Errore nel database: {e}")
        except Exception as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Caricamento dati: {str(e)}\n")
            raise

    def save_car_defaults(self):
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido per salvare i dati.")
            return
        # In questo esempio salviamo solo il Car ID; per un salvataggio completo, raccogli anche i parametri.
        data = {
            "altezza_ant": self.entry_altezza_ant.get().strip(),
            "altezza_post": self.entry_altezza_post.get().strip(),
            "altezza_ant_min": self.entry_altezza_ant_min.get().strip(),
            "altezza_ant_max": self.entry_altezza_ant_max.get().strip(),
            "altezza_post_min": self.entry_altezza_post_min.get().strip(),
            "altezza_post_max": self.entry_altezza_post_max.get().strip(),
            "barre_ant": self.entry_barre_ant.get().strip(),
            "barre_post": self.entry_barre_post.get().strip(),
            "barre_ant_min": self.entry_barre_ant_min.get().strip(),
            "barre_ant_max": self.entry_barre_ant_max.get().strip(),
            "barre_post_min": self.entry_barre_post_min.get().strip(),
            "barre_post_max": self.entry_barre_post_max.get().strip()
            # Aggiungi gli altri parametri se necessario
        }
        try:
            self.save_car_defaults_to_db(car_id, data)
            messagebox.showinfo("Save Car_ID", f"Dati salvati per il Car ID {car_id}.")
            self.update_carid_status()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante il salvataggio dei dati: {str(e)}")

    def save_car_defaults_to_db(self, car_id, data):
        """Salva i dati dell'auto nel database"""
        if not self.defaults_conn:
            raise Exception("Connessione al database non disponibile")
            
        try:
            c = self.defaults_conn.cursor()
            # Crea la tabella se non esiste
            c.execute("""
            CREATE TABLE IF NOT EXISTS car_defaults (
                car_id TEXT PRIMARY KEY,
                data TEXT
            )
            """)
            
            # Converti i dati in JSON
            try:
                json_data = json.dumps(data)
            except Exception as je:
                raise Exception(f"Errore nella conversione dei dati in JSON: {je}")
                
            # Inserisci o aggiorna i dati
            c.execute("""
            INSERT OR REPLACE INTO car_defaults (car_id, data)
            VALUES (?, ?)
            """, (car_id, json_data))
            self.defaults_conn.commit()
            self.txt_output.insert(tk.END, f"[INFO] Dati salvati con successo per l'auto ID: {car_id}\n")
        except sqlite3.Error as e:
            if self.defaults_conn:
                self.defaults_conn.rollback()
            self.txt_output.insert(tk.END, f"[ERRORE] Database: {str(e)}\n")
            raise Exception(f"Errore nel database: {e}")
        except Exception as e:
            if self.defaults_conn:
                self.defaults_conn.rollback()
            self.txt_output.insert(tk.END, f"[ERRORE] Salvataggio dati: {str(e)}\n")
            raise

    def on_analyze(self):
        telemetry_batch = []
        self.listener.stop_listener()
        self.txt_output.insert(tk.END, "[INFO] Training modello ML...\n")
        model = train_model()
        if model is None:
            self.txt_output.insert(tk.END, "[WARN] Nessun dato per training.\n")
            return
        self.txt_output.insert(tk.END, "[INFO] Modello addestrato con successo.\n")
        rows = load_recent_telemetry(self.db_conn, limit=50)
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

        # Costruisco i dati di configurazione e telemetria per il modello LLM
        config_data = {
            "modello_veicolo": self.entry_car.get().strip(),
            "nome_circuito": self.entry_circuit.get().strip(),
            "tipo_gomme": self.entry_tyre.get().strip()
        }
        telemetry_data = telemetry_batch[-1]  # prendo l'ultimo dato raccolto

        suggestion = self.llm.generate_response(config_data, telemetry_data)
        self.txt_suggest.delete(1.0, tk.END)
        self.txt_suggest.insert(tk.END, str(suggestion))

    def on_reset_db(self):
        clear_telemetry(self.db_conn)
        self.txt_output.insert(tk.END, "[INFO] Database resettato.\n")

    def on_save_config(self):
        # Salvataggio del car_id
        car_id = self.entry_car_id.get().strip()
        self.config["car_id"] = car_id
        
        # Altre configurazioni
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
        # Barre Antirollio
        self.config["barre_ant"] = self.entry_barre_ant.get().strip()
        self.config["barre_post"] = self.entry_barre_post.get().strip()
        self.config["barre_ant_min"] = self.entry_barre_ant_min.get().strip()
        self.config["barre_ant_max"] = self.entry_barre_ant_max.get().strip()
        self.config["barre_post_min"] = self.entry_barre_post_min.get().strip()
        self.config["barre_post_max"] = self.entry_barre_post_max.get().strip()
        # Ammortizzazione Compressione
        self.config["ammort_compressione_ant"] = self.entry_comp_ant.get().strip()
        self.config["ammort_compressione_post"] = self.entry_comp_post.get().strip()
        self.config["ammort_compressione_ant_min"] = self.entry_comp_ant_min.get().strip()
        self.config["ammort_compressione_ant_max"] = self.entry_comp_ant_max.get().strip()
        self.config["ammort_compressione_post_min"] = self.entry_comp_post_min.get().strip()
        self.config["ammort_compressione_post_max"] = self.entry_comp_post_max.get().strip()
        # Ammortizzazione Estensione
        self.config["ammort_estensione_ant"] = self.entry_est_ant.get().strip()
        self.config["ammort_estensione_post"] = self.entry_est_post.get().strip()
        self.config["ammort_estensione_ant_min"] = self.entry_est_ant_min.get().strip()
        self.config["ammort_estensione_ant_max"] = self.entry_est_ant_max.get().strip()
        self.config["ammort_estensione_post_min"] = self.entry_est_post_min.get().strip()
        self.config["ammort_estensione_post_max"] = self.entry_est_post_max.get().strip()
        # Frequenza Naturale
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
        self.config["diff_acc_post_max"] = self.entry_diff_acc_post_max.get().strip()
        self.config["diff_frenata_ant"] = self.entry_diff_frenata_ant.get().strip()
        self.config["diff_frenata_post"] = self.entry_diff_frenata_post.get().strip()
        self.config["diff_frenata_ant_min"] = self.entry_diff_frenata_ant_min.get().strip()
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
        self.config["ecu_reg_potenza_min"] = self.entry_ecu_min.get().strip() if hasattr(self, "entry_ecu_min") else ""
        self.config["ecu_reg_potenza_max"] = self.entry_ecu_max.get().strip() if hasattr(self, "entry_ecu_max") else ""
        self.config["zavorra"] = self.entry_zavorra.get().strip()
        self.config["zavorra_min"] = self.entry_zavorra_min.get().strip() if hasattr(self, "entry_zavorra_min") else ""
        self.config["zavorra_max"] = self.entry_zavorra_max.get().strip() if hasattr(self, "entry_zavorra_max") else ""
        self.config["pos_zavorra"] = self.entry_pos_zavorra.get().strip()
        self.config["limitatore"] = self.entry_limitatore.get().strip()
        self.config["limitatore_min"] = self.entry_limitatore_min.get().strip() if hasattr(self, "entry_limitatore_min") else ""
        self.config["limitatore_max"] = self.entry_limitatore_max.get().strip() if hasattr(self, "entry_limitatore_max") else ""
        self.config["freni"] = self.entry_freni.get().strip()
        # Cambio
        ratio_list = []
        for entry in self.entry_rapporti:
            ratio_list.append(entry.get().strip())
        self.config["rapporti"] = ",".join(ratio_list)
        self.config["rapporto_finale"] = self.entry_rapporto_finale.get().strip()

        try:
            save_config_data(self.config)
            self.txt_output.insert(tk.END, "[INFO] Configurazione salvata.\n")
        except json.JSONDecodeError as je:
            self.txt_output.insert(tk.END, f"[ERRORE] Formato JSON non valido: {str(je)}\n")
            messagebox.showerror("Errore JSON", f"Errore nel formato dei dati: {str(je)}")
        except IOError as ioe:
            self.txt_output.insert(tk.END, f"[ERRORE] Accesso al file configurazione: {str(ioe)}\n")
            messagebox.showerror("Errore I/O", f"Impossibile salvare il file di configurazione: {str(ioe)}")
        except Exception as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Salvataggio configurazione fallito: {str(e)}\n")
            messagebox.showerror("Errore", f"Errore durante il salvataggio della configurazione: {str(e)}")

    def on_feedback(self):
        fb = self.entry_feedback.get().strip()
        if not fb:
            return
        self.txt_output.insert(tk.END, f"[User] {fb}\n")
        if not self.llm_loaded or not self.llm:
            self.txt_output.insert(tk.END, "[WARN] LLM non caricato.\n")
            return
        # Costruisci i dati di configurazione anche per il feedback
        config_data = {
            "modello_veicolo": self.entry_car.get().strip(),
            "nome_circuito": self.entry_circuit.get().strip(),
            "tipo_gomme": self.entry_tyre.get().strip()
        }
        # Per il feedback, usiamo il testo inserito come "dati di telemetria"
        telemetry_data = fb
        resp = self.llm.generate_response(config_data, telemetry_data)
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
        # Aggiornamento periodico della telemetria
        self.root.after(250, self.update_telemetry_timer)

    def on_stop(self):
        self.txt_output.insert(tk.END, "[INFO] Arresto telemetria.\n")
        self.listener.stop_listener()

    def on_telemetry_data(self, telemetry_data):
        """Callback che viene chiamato quando arrivano nuovi dati telemetrici"""
        # Salva i dati telemetrici più recenti
        self.latest_telemetry = telemetry_data
    def update_telemetry_timer(self):
        """Timer che aggiorna periodicamente la visualizzazione della telemetria"""
        if hasattr(self, 'listener') and self.listener and self.listener.is_running:
            try:
                self.update_telemetry()
                # Aumentato l'intervallo a 250ms per ridurre il carico
                self.root.after(250, self.update_telemetry_timer)
            except Exception as e:
                self.txt_output.insert(tk.END, f"[ERRORE] Aggiornamento telemetria: {str(e)}\n")
                # In caso di errore, riprova dopo 1 secondo
                self.root.after(1000, self.update_telemetry_timer)
    
    def update_telemetry(self):
        """Aggiorna tutti i valori della telemetria con i dati più recenti"""
        try:
            if not hasattr(self, 'latest_telemetry') or not self.latest_telemetry:
                return
            if not hasattr(self, 'listener') or not self.listener or not self.listener.is_running:
                return
            
            # Debug: stampa i dati ricevuti
            self.txt_output.insert(tk.END, f"[DEBUG] Dati telemetria: {self.latest_telemetry}\n")
        
            # Funzione di utilità per formattare in modo sicuro i valori nulli
            def safe_format(value, format_str="%.1f", default="N/A"):
                try:
                    return format_str % value if value is not None else default
                except (TypeError, ValueError):
                    return default
                    
            # Funzione di utilità per operazioni matematiche sicure
            def safe_calc(value, operation, default="N/A", format_str="%.1f"):
                if value is None:
                    return default
                try:
                    result = operation(value)
                    return format_str % result
                except (TypeError, ValueError, ZeroDivisionError):
                    return default
            
            # Estrai i dati dal dizionario di telemetria
            data = self.latest_telemetry
        
            # Aggiorna informazioni base
            car_speed = data.get('car_speed')
            self.lbl_speed.config(text=safe_format(car_speed, "%.1f", "-"))
            
            rpm = data.get('rpm')
            self.lbl_rpm.config(text=safe_format(rpm, "%.0f", "-"))
            
            gear = data.get('current_gear')
            if gear is not None:
                gear_text = str(gear) if gear > 0 else "N" if gear == 0 else "R"
            else:
                gear_text = "-"
            self.lbl_gear.config(text=gear_text)
            
            fuel_level = data.get('current_fuel')
            fuel_capacity = data.get('fuel_capacity')
            if fuel_level is not None and fuel_capacity is not None:
                self.lbl_fuel.config(text=f"{fuel_level:.1f}/{fuel_capacity:.1f} L")
            else:
                self.lbl_fuel.config(text="-.--/-.-- L")
            
            # Aggiorna temperature dei pneumatici (nomi corretti con maiuscole)
            self.lbl_tyre_temp_fl.config(text=safe_format(data.get('tyre_temp_FL'), "%.1f", "-"))
            self.lbl_tyre_temp_fr.config(text=safe_format(data.get('tyre_temp_FR'), "%.1f", "-"))
            self.lbl_tyre_temp_rl.config(text=safe_format(data.get('tyre_temp_RL'), "%.1f", "-"))
            self.lbl_tyre_temp_rr.config(text=safe_format(data.get('tyre_temp_RR'), "%.1f", "-"))
            
            # Rimuoviamo riferimenti alle temperature dei freni che non sono disponibili
            
            # Aggiorna temperature motore
            self.lbl_oil_temp.config(text=safe_format(data.get('oil_temp'), "%.1f", "-"))
            self.lbl_water_temp.config(text=safe_format(data.get('water_temp'), "%.1f", "-"))
            
            # Aggiorna indicatori di performance
            throttle = data.get('throttle')
            self.lbl_throttle.config(text=safe_calc(throttle, lambda x: x, "-", "%.1f"))
            
            brake = data.get('brake')
            self.lbl_brake.config(text=safe_calc(brake, lambda x: x, "-", "%.1f"))
            
            # Calcola le forze G dai dati di velocità e rotazione
            lat_g = data.get('lateral_g', 0.0)
            self.lbl_lateral_g.config(text=safe_format(lat_g, "%.2f", "-"))
            
            long_g = data.get('longitudinal_g', 0.0)
            self.lbl_longitudinal_g.config(text=safe_format(long_g, "%.2f", "-"))
            
            # Aggiorna boost (pressione turbo)
            boost = data.get('boost')
            self.lbl_boost.config(text=safe_format(boost, "%.2f", "-"))
            
            # Aggiorna slip ratio (usando i dati corretti)
            slip_fl = data.get('tyre_slip_ratio_FL', '0.00')
            slip_fr = data.get('tyre_slip_ratio_FR', '0.00')
            slip_rl = data.get('tyre_slip_ratio_RL', '0.00')
            slip_rr = data.get('tyre_slip_ratio_RR', '0.00')
            
            self.lbl_slip_fl.config(text=slip_fl)
            self.lbl_slip_fr.config(text=slip_fr)
            self.lbl_slip_rl.config(text=slip_rl)
            self.lbl_slip_rr.config(text=slip_rr)
            
            # Aggiorna tempi e posizioni
            best_lap = data.get('best_lap')
            self.lbl_best_lap.config(text=self.format_lap_time(best_lap))
            
            last_lap = data.get('last_lap')
            self.lbl_last_lap.config(text=self.format_lap_time(last_lap))
            
            current_lap = data.get('current_lap')
            self.lbl_current_lap.config(text=self.format_lap_time(current_lap))
            
            # Aggiorna settori (non disponibili nei dati)
            self.lbl_sector1.config(text="--:--.---")
            self.lbl_sector2.config(text="--:--.---")
            self.lbl_sector3.config(text="--:--.---")
        except AttributeError as e:
            # Gestisce errori di attributi mancanti
            self.txt_output.insert(tk.END, f"[ERRORE] Attributo mancante: {str(e)}\n")
        except KeyError as e:
            # Gestisce errori di chiavi mancanti nei dati telemetrici
            self.txt_output.insert(tk.END, f"[ERRORE] Chiave mancante nei dati telemetrici: {str(e)}\n")
        except TypeError as e:
            # Gestisce errori di tipo nei dati o nelle operazioni
            self.txt_output.insert(tk.END, f"[ERRORE] Errore di tipo nei dati: {str(e)}\n")
        except Exception as e:
            # Gestisce ogni altro tipo di errore
            self.txt_output.insert(tk.END, f"[ERRORE] Aggiornamento telemetria: {str(e)}\n")

    @classmethod
    def format_lap_time(cls, milliseconds):
        """Formatta il tempo sul giro in minuti:secondi.millisecondi"""
        if milliseconds is None or milliseconds <= 0:
            return "00:00.000"
        
        try:
            total_seconds = milliseconds / 1000
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            millis = int((total_seconds - int(total_seconds)) * 1000)
            return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
        except (TypeError, ValueError):
            return "00:00.000"

    def on_closing(self):
        """Gestisce la chiusura pulita dell'applicazione"""
        try:
            # Arresta il listener della telemetria se attivo
            if hasattr(self, 'listener') and self.listener and self.listener.is_running:
                self.listener.stop_listener()
                self.txt_output.insert(tk.END, "[INFO] Telemetria arrestata correttamente.\n")
            
            # Chiudi le connessioni al database
            if hasattr(self, 'db_conn') and self.db_conn:
                with self.db_lock:
                    self.db_conn.close()
                self.txt_output.insert(tk.END, "[INFO] Connessione al database chiusa.\n")
                
            if hasattr(self, 'defaults_conn') and self.defaults_conn:
                self.defaults_conn.close()
                self.txt_output.insert(tk.END, "[INFO] Connessione al database defaults chiusa.\n")
                
            # Salva la configurazione
            try:
                save_config_data(self.config)
                self.txt_output.insert(tk.END, "[INFO] Configurazione salvata.\n")
            except Exception as e:
                self.txt_output.insert(tk.END, f"[ERRORE] Impossibile salvare la configurazione: {str(e)}\n")
                
            # Chiudi l'applicazione
            self.root.destroy()
        except Exception as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Errore durante la chiusura: {str(e)}\n")
            # Forza la chiusura in caso di errore
            self.root.destroy()
            

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
