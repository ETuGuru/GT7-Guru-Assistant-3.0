# main.py

import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3
import sys
import threading

# Aggiungi la cartella lib al path di Python
lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
sys.path.insert(0, lib_path)

# Variabili globali per la gestione dei giri
telemetry_buffer = []  # Buffer per accumulare dati di telemetria
lap_count = 0  # Conta i giri completati
target_laps = 1  # Numero di giri da completare prima dell'analisi

# Moduli del progetto
from db_manager import (
    initialize_database, create_thread_safe_connection,
    load_recent_telemetry, clear_telemetry
)
from gt7communication import GT7TelemetryListener
from local_ai_model import train_model, infer_advice_on_batch
from gemma_llm import GemmaLLM
from config import DB_PATH

# Configurazione logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Nuovi import: gestione parametri auto
from car_setup_manager import (
    init_car_db,
    create_new_car_if_not_exists,
    get_car_parameters,
    update_car_parameter,
    update_car_name,
    load_car_parameters_batch
)

CONFIG_FILE = "config.json"

def load_config():

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Errore nel parsing del file di configurazione: {e}")
            if os.path.exists(CONFIG_FILE):
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{CONFIG_FILE}.{timestamp}.bak"
                try:
                    import shutil
                    shutil.copy2(CONFIG_FILE, backup_file)
                    logging.info(f"Backup del file config creato: {backup_file}")
                except Exception as be:
                    logging.error(f"Impossibile creare il backup: {be}")

    logging.info("Caricamento config di default")
    return {
        "auto": "",
        "gomme": "",
        "circuito": ""
    }

def save_config_data(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except (IOError, json.JSONDecodeError) as e:
        raise Exception(f"Errore nel salvataggio del file di configurazione: {e}")


class GT7GuruGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GT7 Guru Assistant 3.0")
        
        # Setup styles
        style = ttk.Style()
        style.configure('Title.TLabelframe.Label', font=('Segoe UI', 12, 'bold'))
        style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'))
        
        # Set default font for all widgets
        default_font = ('Segoe UI', 10)
        bold_font = ('Segoe UI', 10, 'bold')
        title_font = ('Segoe UI', 12, 'bold')
        self.root.option_add('*Font', default_font)
        self.root.option_add('*TButton*Font', default_font)
        self.root.option_add('*TLabel*Font', default_font)
        self.root.option_add('*TEntry*Font', default_font)
        self.root.option_add('*TCombobox*Font', default_font)
        self.config = load_config()

        # Aggiorna il dizionario config se mancano le nuove chiavi
        if "peso" not in self.config:
            self.config["peso"] = ""
        if "potenza" not in self.config:
            self.config["potenza"] = ""
        if "trazione" not in self.config:
            self.config["trazione"] = ""

        # Inizializza DB telemetria
        try:
            self.db_conn, self.db_lock = create_thread_safe_connection('telemetry.db')
            if not initialize_database(self.db_conn):
                messagebox.showerror("Errore", "Impossibile inizializzare il DB telemetria")
                sys.exit(1)
        except Exception as e:
            messagebox.showerror("Errore DB Telemetria", str(e))
            sys.exit(1)

        # Inizializza DB setup auto
        try:
            init_car_db()
        except Exception as e:
            messagebox.showerror("Errore DB Setup", str(e))
            sys.exit(1)

        # Listener per telemetria
        self.listener = GT7TelemetryListener(self.db_conn, self.db_lock)
        self.listener.telemetry_callback = self.on_telemetry_data

        # Initialize LLM with explicit model path and validation
        self.llm = None
        self.llm_loaded = False
        self.llm_load_error = None
        self.latest_telemetry = {}
        self.model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "gemma-3-4b-it-Q4_K_M.gguf")
        
        # Try to initialize the LLM during startup with validation
        try:
            # Validate the model file exists and is accessible
            if not os.path.exists(self.model_path):
                self.llm_load_error = f"Model file not found at: {self.model_path}"
                logger.warning(self.llm_load_error)
                return
                
            # Validate file size to ensure it's the correct model
            model_size = os.path.getsize(self.model_path) / (1024 * 1024)  # Size in MB
            if model_size < 10:  # Basic size validation
                self.llm_load_error = f"Invalid model file size ({model_size:.2f} MB), expected >10MB"
                logger.warning(self.llm_load_error)
                return
                
            logger.info(f"Initializing LLM with validated model path: {self.model_path}")
            self.llm = GemmaLLM(model_path=self.model_path)
            self.llm_loaded = True
            logger.info("LLM initialized successfully")
        except Exception as e:
            self.llm_load_error = f"Failed to initialize LLM: {str(e)}"
            logger.error(self.llm_load_error)

        self.create_widgets()
        self.update_carid_status()
        self.update_power_to_weight_ratio()
        self.init_parameter_mapping()
    def create_widgets(self):
        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, columnspan=8, sticky="nsew", padx=5, pady=5)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # --- TAB 1: Dati contestuali ---
        self.tab_context = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_context, text="Dati contestuali", padding=5)

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

        # Peso, Potenza, Trazione e rapporto peso/potenza
        self.label_weight = ttk.Label(self.tab_context, text="Peso (kg):")
        self.label_weight.grid(row=1, column=2, sticky="e", padx=5, pady=2)
        self.entry_weight = ttk.Entry(self.tab_context, width=10)
        self.entry_weight.insert(0, self.config.get("peso", ""))
        self.entry_weight.grid(row=1, column=3, padx=5, pady=2)
        self.entry_weight.bind("<KeyRelease>", self.update_power_to_weight_ratio)

        self.label_power = ttk.Label(self.tab_context, text="Potenza (CV):")
        self.label_power.grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.entry_power = ttk.Entry(self.tab_context, width=10)
        self.entry_power.insert(0, self.config.get("potenza", ""))
        self.entry_power.grid(row=2, column=1, padx=5, pady=2)
        self.entry_power.bind("<KeyRelease>", self.update_power_to_weight_ratio)

        self.label_drive_train = ttk.Label(self.tab_context, text="Trazione:")
        self.label_drive_train.grid(row=2, column=2, sticky="e", padx=5, pady=2)
        self.combo_drive_train = ttk.Combobox(self.tab_context, width=8, values=["FF", "FR", "MR", "RR", "4WD"], state="readonly")
        if self.config.get("trazione") in ["FF", "FR", "MR", "RR", "4WD"]:
            self.combo_drive_train.set(self.config["trazione"])
        else:
            self.combo_drive_train.set("")
        self.combo_drive_train.grid(row=2, column=3, padx=5, pady=2)

        self.label_power_weight_ratio = ttk.Label(self.tab_context, text="Rapporto peso/potenza:")
        self.label_power_weight_ratio.grid(row=3, column=0, sticky="e", padx=5, pady=2)
        self.label_power_weight_ratio_value = ttk.Label(self.tab_context, text="2.00 kg/CV")
        self.label_power_weight_ratio_value.grid(row=3, column=1, padx=5, pady=2)

        # Car ID
        self.label_car_id = ttk.Label(self.tab_context, text="Car ID:")
        self.label_car_id.grid(row=4, column=0, sticky="e", padx=5, pady=2)
        self.entry_car_id = ttk.Entry(self.tab_context, width=20)
        self.entry_car_id.grid(row=4, column=1, padx=5, pady=2)

        self.label_carid_status = ttk.Label(self.tab_context, text="N/D", foreground="red")
        self.label_carid_status.grid(row=4, column=2, padx=5, pady=2)

        self.btn_load_carid = ttk.Button(self.tab_context, text="Load Car_ID", command=self.load_car_defaults)
        self.btn_load_carid.grid(row=4, column=3, padx=5, pady=2)

        self.btn_save_carid = ttk.Button(self.tab_context, text="Save Car_ID", command=self.save_car_defaults)
        self.btn_save_carid.grid(row=4, column=4, padx=5, pady=2)

        # --- TAB 2: Parametri Assetto ---
        self.tab_params = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_params, text="Parametri Assetto", padding=5)

        headers = ["Parametro", "Ant.", "Post.", "Ant. min", "Ant. max", "Post. min", "Post. max"]
        for idx, text in enumerate(headers):
            ttk.Label(self.tab_params, text=text, font=('Segoe UI', 10, 'bold')).grid(row=0, column=idx, padx=5, pady=2)

        row = 1
        def make_7entries_row(row, label_text, defaults):
            ttk.Label(self.tab_params, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            e_ant = ttk.Entry(self.tab_params, width=10); e_ant.insert(0, defaults[0]); e_ant.grid(row=row, column=1, padx=5, pady=2)
            e_post = ttk.Entry(self.tab_params, width=10); e_post.insert(0, defaults[1]); e_post.grid(row=row, column=2, padx=5, pady=2)
            e_ant_min = ttk.Entry(self.tab_params, width=5); e_ant_min.insert(0, defaults[2]); e_ant_min.grid(row=row, column=3, padx=5, pady=2)
            e_ant_max = ttk.Entry(self.tab_params, width=5); e_ant_max.insert(0, defaults[3]); e_ant_max.grid(row=row, column=4, padx=5, pady=2)
            e_post_min = ttk.Entry(self.tab_params, width=5); e_post_min.insert(0, defaults[4]); e_post_min.grid(row=row, column=5, padx=5, pady=2)
            e_post_max = ttk.Entry(self.tab_params, width=5); e_post_max.insert(0, defaults[5]); e_post_max.grid(row=row, column=6, padx=5, pady=2)
            return (e_ant, e_post, e_ant_min, e_ant_max, e_post_min, e_post_max)

        # Altezza suolo
        self.entry_altezza_ant, self.entry_altezza_post, \
        self.entry_altezza_ant_min, self.entry_altezza_ant_max, \
        self.entry_altezza_post_min, self.entry_altezza_post_max = make_7entries_row(
            row, "Altezza suolo (mm)", ["52", "57", "40", "60", "40", "60"]
        )
        row += 1

        # Barre
        self.entry_barre_ant, self.entry_barre_post, \
        self.entry_barre_ant_min, self.entry_barre_ant_max, \
        self.entry_barre_post_min, self.entry_barre_post_max = make_7entries_row(
            row, "Barre Antirollio", ["5", "6", "1", "10", "1", "10"]
        )
        row += 1

        # Ammort. Compressione
        self.entry_comp_ant, self.entry_comp_post, \
        self.entry_comp_ant_min, self.entry_comp_ant_max, \
        self.entry_comp_post_min, self.entry_comp_post_max = make_7entries_row(
            row, "Ammort. Compressione (%)", ["25", "25", "20", "40", "20", "40"]
        )
        row += 1

        # Ammort. Estensione
        self.entry_est_ant, self.entry_est_post, \
        self.entry_est_ant_min, self.entry_est_ant_max, \
        self.entry_est_post_min, self.entry_est_post_max = make_7entries_row(
            row, "Ammort. Estensione (%)", ["45", "45", "30", "50", "30", "50"]
        )
        row += 1

        # Frequenza
        self.entry_freq_ant, self.entry_freq_post, \
        self.entry_freq_ant_min, self.entry_freq_ant_max, \
        self.entry_freq_post_min, self.entry_freq_post_max = make_7entries_row(
            row, "Frequenza Nat. (Hz)", ["4.80", "4.90", "4.60", "5.50", "4.60", "5.50"]
        )
        row += 1

        # Campanatura
        self.entry_camp_ant, self.entry_camp_post, \
        self.entry_camp_ant_min, self.entry_camp_ant_max, \
        self.entry_camp_post_min, self.entry_camp_post_max = make_7entries_row(
            row, "Campanatura (Â°)", ["3.5", "2.0", "0.0", "6.0", "0.0", "6.0"]
        )
        row += 1

        # Convergenza
        self.entry_conv_ant, self.entry_conv_post, \
        self.entry_conv_ant_min, self.entry_conv_ant_max, \
        self.entry_conv_post_min, self.entry_conv_post_max = make_7entries_row(
            row, "Angolo Convergenza (Â°)", ["+0.10", "+0.25", "-1.00", "+1.00", "-1.00", "+1.00"]
        )
        ttk.Label(self.tab_params, text="(Usa '+' per convergente, '-' per divergente)").grid(row=row, column=7, padx=5, pady=2)
        row += 1

        # Diff. Coppia Iniziale
        self.entry_diff_coppia_ant, self.entry_diff_coppia_post, \
        self.entry_diff_coppia_ant_min, self.entry_diff_coppia_ant_max, \
        self.entry_diff_coppia_post_min, self.entry_diff_coppia_post_max = make_7entries_row(
            row, "Diff. Coppia Iniziale", ["", "5", "", "", "5", "60"]
        )
        row += 1

        # Diff. Sens. Accelerazione
        self.entry_diff_acc_ant, self.entry_diff_acc_post, \
        self.entry_diff_acc_ant_min, self.entry_diff_acc_ant_max, \
        self.entry_diff_acc_post_min, self.entry_diff_acc_post_max = make_7entries_row(
            row, "Diff. Sens. Accelerazione", ["", "22", "", "", "5", "60"]
        )
        row += 1

        # Diff. Sens. Frenata
        self.entry_diff_frenata_ant, self.entry_diff_frenata_post, \
        self.entry_diff_frenata_ant_min, self.entry_diff_frenata_ant_max, \
        self.entry_diff_frenata_post_min, self.entry_diff_frenata_post_max = make_7entries_row(
            row, "Diff. Sens. Frenata", ["", "5", "", "", "5", "60"]
        )
        row += 1

        # Diff. Distrib
        ttk.Label(self.tab_params, text="Diff. Distribuzione").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_diff_distrib = ttk.Entry(self.tab_params, width=10)
        self.entry_diff_distrib.insert(0, "")
        self.entry_diff_distrib.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # Deportanza
        self.entry_deportanza_ant, self.entry_deportanza_post, \
        self.entry_deportanza_ant_min, self.entry_deportanza_ant_max, \
        self.entry_deportanza_post_min, self.entry_deportanza_post_max = make_7entries_row(
            row, "Deportanza", ["1200", "1650", "900", "1200", "1400", "1800"]
        )
        row += 1

        # ECU Reg. Potenza
        ttk.Label(self.tab_params, text="ECU Reg. Potenza (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_ecu = ttk.Entry(self.tab_params, width=10)
        self.entry_ecu.insert(0, "")
        self.entry_ecu.grid(row=row, column=1, padx=5, pady=2)
        self.entry_ecu_min = ttk.Entry(self.tab_params, width=5)
        self.entry_ecu_min.insert(0, "")
        self.entry_ecu_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_ecu_max = ttk.Entry(self.tab_params, width=5)
        self.entry_ecu_max.insert(0, "")
        self.entry_ecu_max.grid(row=row, column=3, padx=5, pady=2)
        row += 1

        # Zavorra
        ttk.Label(self.tab_params, text="Zavorra (kg)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_zavorra = ttk.Entry(self.tab_params, width=10)
        self.entry_zavorra.insert(0, "")
        self.entry_zavorra.grid(row=row, column=1, padx=5, pady=2)
        self.entry_zavorra_min = ttk.Entry(self.tab_params, width=5)
        self.entry_zavorra_min.insert(0, "")
        self.entry_zavorra_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_zavorra_max = ttk.Entry(self.tab_params, width=5)
        self.entry_zavorra_max.insert(0, "")
        self.entry_zavorra_max.grid(row=row, column=3, padx=5, pady=2)
        row += 1

        # Pos. Zavorra
        ttk.Label(self.tab_params, text="Pos. Zavorra").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_pos_zavorra = ttk.Entry(self.tab_params, width=10)
        self.entry_pos_zavorra.insert(0, "")
        self.entry_pos_zavorra.grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(self.tab_params, text="(-50 ant, 0 centro, +50 post)").grid(row=row, column=2, columnspan=5, padx=5, pady=2)
        row += 1

        # Limitatore
        ttk.Label(self.tab_params, text="Limitatore (%)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_limitatore = ttk.Entry(self.tab_params, width=10)
        self.entry_limitatore.insert(0, "")
        self.entry_limitatore.grid(row=row, column=1, padx=5, pady=2)
        self.entry_limitatore_min = ttk.Entry(self.tab_params, width=5)
        self.entry_limitatore_min.insert(0, "")
        self.entry_limitatore_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_limitatore_max = ttk.Entry(self.tab_params, width=5)
        self.entry_limitatore_max.insert(0, "")
        self.entry_limitatore_max.grid(row=row, column=3, padx=5, pady=2)
        row += 1

        # Freni
        ttk.Label(self.tab_params, text="Bilanc. Freni (-5..+5)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_freni = ttk.Entry(self.tab_params, width=10)
        self.entry_freni.insert(0, "-2")
        self.entry_freni.grid(row=row, column=1, padx=5, pady=2)
        row += 1

        # --- TAB 3: Parametri Cambio ---
        self.tab_cambio = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_cambio, text="Parametri Cambio", padding=5)
        ttk.Label(self.tab_cambio, text="Marcia", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.tab_cambio, text="Rapporto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=2)

        self.entry_rapporti = []
        default_ratios = ["2.826","2.103","1.704","1.450","1.295","1.203","",""]
        for i in range(8):
            ttk.Label(self.tab_cambio, text=f"{i+1}Âª marcia:").grid(row=i+1, column=0, sticky="e", padx=5, pady=2)
            entry = ttk.Entry(self.tab_cambio, width=10)
            entry.insert(0, default_ratios[i])
            self.entry_rapporti.append(entry)
            entry.grid(row=i+1, column=1, padx=5, pady=2)

        ttk.Label(self.tab_cambio, text="Rapporto finale:").grid(row=9, column=0, sticky="w", padx=5, pady=5)
        self.entry_rapporto_finale = ttk.Entry(self.tab_cambio, width=10)
        self.entry_rapporto_finale.insert(0, "4.50")
        self.entry_rapporto_finale.grid(row=9, column=1, padx=5, pady=5)

        # --- TAB 4: Telemetry View ---
        self.tab_telemetry = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_telemetry, text="Telemetry View", padding=5)

        # Creazione frame e label per la telemetria
        # Creazione frame e label per la telemetria
        self.frame_basic_info = ttk.LabelFrame(self.tab_telemetry, text="Informazioni Base", style='TLabelframe')
        self.frame_basic_info.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ttk.Label(self.frame_basic_info, text="VelocitÃ  (km/h):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_speed = ttk.Label(self.frame_basic_info, text="0", font=('Segoe UI', 16, 'bold'))
        self.lbl_speed.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame_basic_info, text="RPM:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.lbl_rpm = ttk.Label(self.frame_basic_info, text="0", font=('Segoe UI', 16, 'bold'))
        self.lbl_rpm.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame_basic_info, text="Marcia:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.lbl_gear = ttk.Label(self.frame_basic_info, text="N", font=('Segoe UI', 16, 'bold'))
        self.lbl_gear.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame_basic_info, text="Carburante:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.lbl_fuel = ttk.Label(self.frame_basic_info, text="0.0 L", font=('Segoe UI', 12))
        self.lbl_fuel.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        self.frame_temperatures = ttk.LabelFrame(self.tab_telemetry, text="Temperature", style='TLabelframe')
        self.frame_temperatures.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ttk.Label(self.frame_temperatures, text="Pneumatici (Â°C):").grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="w")
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

        ttk.Label(self.frame_temperatures, text="Olio (Â°C):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.lbl_oil_temp = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_oil_temp.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.frame_temperatures, text="Acqua (Â°C):").grid(row=3, column=2, padx=5, pady=5, sticky="w")
        self.lbl_water_temp = ttk.Label(self.frame_temperatures, text="0.0")
        self.lbl_water_temp.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        self.frame_performance = ttk.LabelFrame(self.tab_telemetry, text="Performance", style='TLabelframe')
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

        self.frame_timing = ttk.LabelFrame(self.tab_telemetry, text="Tempi e Posizione", style='TLabelframe')
        self.frame_timing.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        ttk.Label(self.frame_timing, text="Best Lap Time:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_best_lap = ttk.Label(self.frame_timing, text="00:00.000", font=('Segoe UI', 12))
        self.lbl_best_lap.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.lbl_last_lap = ttk.Label(self.frame_timing, text="00:00.000", font=('Segoe UI', 12))
        self.lbl_last_lap.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.lbl_current_lap = ttk.Label(self.frame_timing, text="00:00.000", font=('Segoe UI', 12))
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

        # ---- Suggerimenti AI ----
        self.frame_suggest = ttk.LabelFrame(self.root, text="Suggerimenti AI", padding=(10, 5), labelanchor="n", style='Title.TLabelframe')
        self.frame_suggest.grid(row=3, column=0, columnspan=8, padx=5, pady=5, sticky="nsew")
        self.txt_suggest = scrolledtext.ScrolledText(
            self.frame_suggest,
            width=240,
            height=24,
            wrap='word',
            font=('Segoe UI', 12),
            state='normal'
        )
        self.txt_suggest.pack(padx=5, pady=5)
        self.txt_suggest.config(state='disabled')  # Make it read-only while still allowing selection and copying
        
        # Frame per i controlli principali
        self.frame_controls = ttk.Frame(self.root)
        self.frame_controls.grid(row=4, column=0, columnspan=8, sticky="w", padx=5, pady=5)

        # Spinbox per il numero di giri
        ttk.Label(self.frame_controls, text="Numero di giri:").grid(row=0, column=0, padx=5, pady=2)
        self.spin_laps = ttk.Spinbox(self.frame_controls, from_=1, to=100, width=5)
        self.spin_laps.set(10)  # Default a 10 giri
        self.spin_laps.grid(row=0, column=1, padx=5, pady=2)

        # Pulsante Start e Stop
        self.btn_start = ttk.Button(self.frame_controls, text="Start", command=self.on_start)
        self.btn_start.grid(row=0, column=2, padx=5, pady=2)
        self.btn_stop = ttk.Button(self.frame_controls, text="Stop", command=self.on_stop)
        self.btn_stop.grid(row=0, column=3, padx=5, pady=2)

        # Analisi ogni N giri
        self.label_target_laps = ttk.Label(self.frame_controls, text="Analisi ogni")
        self.spin_target_laps = ttk.Spinbox(self.frame_controls, from_=1, to=10, width=5, command=self.update_target_laps)
        self.spin_target_laps.set(1)  # Default: analisi ogni 1 giro
        ttk.Label(self.frame_controls, text="giri").grid(row=0, column=6, padx=2, pady=2)
        
        self.label_target_laps.grid(row=0, column=4, padx=5, pady=2)
        self.spin_target_laps.grid(row=0, column=5, padx=2, pady=2)
        
        # Altri pulsanti
        self.btn_analyze = ttk.Button(self.frame_controls, text="Analyze", command=self.on_analyze)
        self.btn_reset = ttk.Button(self.frame_controls, text="Reset DB", command=self.on_reset_db)
        self.btn_save_config = ttk.Button(self.frame_controls, text="Salva Config", command=self.on_save_config)
        
        self.btn_analyze.grid(row=0, column=7, padx=5, pady=2)
        self.btn_reset.grid(row=0, column=8, padx=5, pady=2)
        self.btn_save_config.grid(row=0, column=9, padx=5, pady=2)
        self.txt_output = scrolledtext.ScrolledText(self.root, width=100, height=8)
        self.txt_output.grid(row=5, column=0, columnspan=8, padx=5, pady=5)

        # Feedback LLM
        self.lbl_feedback = ttk.Label(self.root, text="Feedback / Domanda:")
        self.lbl_feedback.grid(row=6, column=0, sticky="e", padx=5, pady=2)
        self.entry_feedback = ttk.Entry(self.root, width=50)
        self.entry_feedback.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        self.btn_feedback = ttk.Button(self.root, text="Invia", command=self.on_feedback)
        self.btn_feedback.grid(row=6, column=2, padx=5, pady=2)

    def update_carid_status(self):
        car_id = self.entry_car_id.get().strip()
        if car_id:
            car_data = get_car_parameters(car_id)
            if car_data:
                self.label_carid_status.config(text="Dati trovati", foreground="green")
                self.btn_load_carid.config(state="normal")
            else:
                self.label_carid_status.config(text="Nessun dato", foreground="red")
                self.btn_load_carid.config(state="disabled")
        else:
            self.label_carid_status.config(text="N/D", foreground="red")
            self.btn_load_carid.config(state="disabled")

        self.root.after(3000, self.update_carid_status)

    def update_power_to_weight_ratio(self, event=None):
        try:
            peso = self.maybe_float(self.entry_weight.get()) or 0
            potenza = self.maybe_float(self.entry_power.get()) or 0
            
            # Valori di default se mancanti
            if peso <= 0:
                peso = 1200  # Peso default
            if potenza <= 0:
                potenza = 600  # Potenza default
                
            ratio = peso / potenza
            self.label_power_weight_ratio_value.config(text=f"{ratio:.2f} kg/CV")
        except Exception as e:
            self.logger.error(f"Errore nel calcolo del rapporto peso/potenza: {str(e)}")
            self.label_power_weight_ratio_value.config(text="N/D")

    def init_parameter_mapping(self):
        """Inizializza il mapping tra i nomi dei parametri e i widget della GUI"""
        self.PARAMETER_MAPPING = {
            # Parametri Base
            "peso": self.entry_weight,
            "potenza": self.entry_power,
            "trazione": self.combo_drive_train,
            # Altezza
            "altezza_ant": self.entry_altezza_ant,
            "altezza_ant_min": self.entry_altezza_ant_min,
            "altezza_ant_max": self.entry_altezza_ant_max,
            "altezza_post": self.entry_altezza_post,
            "altezza_post_min": self.entry_altezza_post_min,
            "altezza_post_max": self.entry_altezza_post_max,
            # Barre
            "barre_ant": self.entry_barre_ant,
            "barre_ant_min": self.entry_barre_ant_min,
            "barre_ant_max": self.entry_barre_ant_max,
            "barre_post": self.entry_barre_post,
            "barre_post_min": self.entry_barre_post_min,
            "barre_post_max": self.entry_barre_post_max,
            # Ammortizzatori Compressione
            "ammort_compressione_ant": self.entry_comp_ant,
            "ammort_compressione_ant_min": self.entry_comp_ant_min,
            "ammort_compressione_ant_max": self.entry_comp_ant_max,
            "ammort_compressione_post": self.entry_comp_post,
            "ammort_compressione_post_min": self.entry_comp_post_min,
            "ammort_compressione_post_max": self.entry_comp_post_max,
            # Ammortizzatori Estensione
            "ammort_estensione_ant": self.entry_est_ant,
            "ammort_estensione_ant_min": self.entry_est_ant_min,
            "ammort_estensione_ant_max": self.entry_est_ant_max,
            "ammort_estensione_post": self.entry_est_post,
            "ammort_estensione_post_min": self.entry_est_post_min,
            "ammort_estensione_post_max": self.entry_est_post_max,
            # Frequenza
            "frequenza_ant": self.entry_freq_ant,
            "frequenza_ant_min": self.entry_freq_ant_min,
            "frequenza_ant_max": self.entry_freq_ant_max,
            "frequenza_post": self.entry_freq_post,
            "frequenza_post_min": self.entry_freq_post_min,
            "frequenza_post_max": self.entry_freq_post_max,
            # Campanatura
            "campanatura_ant": self.entry_camp_ant,
            "campanatura_ant_min": self.entry_camp_ant_min,
            "campanatura_ant_max": self.entry_camp_ant_max,
            "campanatura_post": self.entry_camp_post,
            "campanatura_post_min": self.entry_camp_post_min,
            "campanatura_post_max": self.entry_camp_post_max,
            # Convergenza
            "conv_ant": self.entry_conv_ant,
            "conv_ant_min": self.entry_conv_ant_min,
            "conv_ant_max": self.entry_conv_ant_max,
            "conv_post": self.entry_conv_post,
            "conv_post_min": self.entry_conv_post_min,
            "conv_post_max": self.entry_conv_post_max,
            # Differenziale Coppia
            "diff_coppia_ant": self.entry_diff_coppia_ant,
            "diff_coppia_ant_min": self.entry_diff_coppia_ant_min,
            "diff_coppia_ant_max": self.entry_diff_coppia_ant_max,
            "diff_coppia_post": self.entry_diff_coppia_post,
            "diff_coppia_post_min": self.entry_diff_coppia_post_min,
            "diff_coppia_post_max": self.entry_diff_coppia_post_max,
            # Differenziale Accelerazione
            "diff_acc_ant": self.entry_diff_acc_ant,
            "diff_acc_ant_min": self.entry_diff_acc_ant_min,
            "diff_acc_ant_max": self.entry_diff_acc_ant_max,
            "diff_acc_post": self.entry_diff_acc_post,
            "diff_acc_post_min": self.entry_diff_acc_post_min,
            "diff_acc_post_max": self.entry_diff_acc_post_max,
            # Differenziale Frenata
            "diff_frenata_ant": self.entry_diff_frenata_ant,
            "diff_frenata_ant_min": self.entry_diff_frenata_ant_min,
            "diff_frenata_ant_max": self.entry_diff_frenata_ant_max,
            "diff_frenata_post": self.entry_diff_frenata_post,
            "diff_frenata_post_min": self.entry_diff_frenata_post_min,
            "diff_frenata_post_max": self.entry_diff_frenata_post_max,
            # Deportanza
            "deportanza_ant": self.entry_deportanza_ant,
            "deportanza_ant_min": self.entry_deportanza_ant_min,
            "deportanza_ant_max": self.entry_deportanza_ant_max,
            "deportanza_post": self.entry_deportanza_post,
            "deportanza_post_min": self.entry_deportanza_post_min,
            "deportanza_post_max": self.entry_deportanza_post_max,
            # Altri parametri
            "diff_distrib": self.entry_diff_distrib,
            "ecu": self.entry_ecu,
            "ecu_min": self.entry_ecu_min,
            "ecu_max": self.entry_ecu_max,
            "zavorra": self.entry_zavorra,
            "zavorra_min": self.entry_zavorra_min,
            "zavorra_max": self.entry_zavorra_max,
            "pos_zavorra": self.entry_pos_zavorra,
            "limitatore": self.entry_limitatore,
            "limitatore_min": self.entry_limitatore_min,
            "limitatore_max": self.entry_limitatore_max,
            "freni": self.entry_freni,
            # Aggiungi i rapporti del cambio
            "rapporto_1": self.entry_rapporti[0],
            "rapporto_2": self.entry_rapporti[1],
            "rapporto_3": self.entry_rapporti[2],
            "rapporto_4": self.entry_rapporti[3],
            "rapporto_5": self.entry_rapporti[4],
            "rapporto_6": self.entry_rapporti[5],
            "rapporto_7": self.entry_rapporti[6],
            "rapporto_8": self.entry_rapporti[7],
            "rapporto_finale": self.entry_rapporto_finale,
        }
    
    def set_value(self, entry_widget, value, formatted_value=None):
        """Imposta il valore di un widget Entry preservando il formato originale se disponibile"""
        entry_widget.delete(0, tk.END)
        if value is not None:  # Solo se il valore non Ã¨ None
            if formatted_value is not None:
                # Usiamo il formato originale se disponibile
                entry_widget.insert(0, formatted_value)
            else:
                # Altrimenti convertiamo in stringa mantenendo gli zeri finali per decimali come 5.10
                if isinstance(value, float):
                    # Se Ã¨ un valore con decimali, preserviamo fino a 2 decimali
                    entry_widget.insert(0, f"{value:.2f}".rstrip('0').rstrip('.') if '.' in f"{value:.2f}" else str(value))
                else:
                    entry_widget.insert(0, str(value))

    def load_car_defaults(self):
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido.")
            return

        logger.debug(f"Caricamento parametri per Car ID: {car_id}")
        
        create_new_car_if_not_exists(car_id, self.entry_car.get().strip() or "Sconosciuta")
        
        # Carica tutti i parametri in batch
        logger.info(f"Caricamento parametri per auto ID: {car_id}")
        param_data = load_car_parameters_batch(car_id, list(self.PARAMETER_MAPPING.keys()))
        if not param_data:
            logger.error(f"Nessun dato trovato per Car ID {car_id}")
            self.txt_output.insert(tk.END, f"[ERRORE] Nessun dato per Car ID {car_id}.\n")
            messagebox.showwarning("Load Car_ID", f"Nessun dato per Car ID {car_id}.")
            return

        # Log dei parametri caricati
        logger.info(f"Parametri caricati: {len(param_data)} trovati")
        
        # Imposta i valori nei widget
        for param_name, entry_widget in self.PARAMETER_MAPPING.items():
            try:
                if param_name in param_data:
                    value = param_data[param_name]["value"]
                    # Ottieni il formato originale se disponibile nel db
                    original_format = param_data[param_name].get("original_format", None)
                    logger.debug(f"Impostazione {param_name} = {value} (formato: {original_format})")
                    if param_name == "trazione":
                        if value in ["FF", "FR", "MR", "RR", "4WD"]:
                            entry_widget.set(value)
                        else:
                            entry_widget.set("")  # Lascia vuoto se non valido
                    else:
                        self.set_value(entry_widget, value, original_format)  # Usa il formato originale se disponibile
            except Exception as e:
                self.txt_output.insert(tk.END, f"[ERRORE] Parametro {param_name}: {str(e)}\n")

        # Aggiorna il rapporto peso/potenza solo se entrambi i valori sono presenti
        peso = self.maybe_float(self.entry_weight.get())
        potenza = self.maybe_float(self.entry_power.get())
        if peso is not None and potenza is not None and potenza > 0:
            self.update_power_to_weight_ratio()

        self.txt_output.insert(tk.END, "[INFO] Caricamento completato.\n")
        messagebox.showinfo("Load Car_ID", f"Dati caricati per Car ID {car_id}.")

    def maybe_float(self, s):
        st = s.strip()
        if not st:
            return None
        try:
            return float(st.replace("+","").replace(",","."))
        except ValueError:
            return None
            
    def maybe_float_preserve_format(self, s):
        """Converte una stringa in float ma preserva il formato originale dei decimali"""
        st = s.strip()
        if not st:
            return None, ""
        try:
            # Salviamo il formato originale
            original_format = st
            # Convertiamo in float per validazione
            float_value = float(st.replace("+","").replace(",","."))
            return float_value, original_format
        except ValueError:
            return None, ""

    def maybe_str(self, s):
        st = s.strip()
        return st if st else None

    def save_car_defaults(self):
        car_id = self.entry_car_id.get().strip()
        if not car_id:
            messagebox.showwarning("Car ID", "Inserisci un Car ID valido.")
            return

        try:
            # Crea o aggiorna l'auto
            create_new_car_if_not_exists(car_id, self.entry_car.get().strip() or "Sconosciuta")
            update_car_name(car_id, self.entry_car.get().strip() or "Sconosciuta")

            # Gestione dei parametri base (peso, potenza, trazione)
            peso_value = self.entry_weight.get().strip()
            potenza_value = self.entry_power.get().strip()
            trazione = self.combo_drive_train.get()

            # Salva solo il valore della trazione se non Ã¨ vuoto
            if trazione:
                update_car_parameter(car_id, "trazione", trazione)
            else:
                update_car_parameter(car_id, "trazione", None)

            # Per peso e potenza, controlla se sono vuoti e salva None se lo sono
            if not peso_value:
                update_car_parameter(car_id, "peso", None)
            else:
                try:
                    peso = float(peso_value.replace("+", "").replace(",", "."))
                    update_car_parameter(car_id, "peso", peso)
                except ValueError:
                    update_car_parameter(car_id, "peso", None)

            if not potenza_value:
                update_car_parameter(car_id, "potenza", None)
            else:
                try:
                    potenza = float(potenza_value.replace("+", "").replace(",", "."))
                    update_car_parameter(car_id, "potenza", potenza)
                except ValueError:
                    update_car_parameter(car_id, "potenza", None)

            # Verifica il salvataggio dei parametri base
            base_params = load_car_parameters_batch(car_id, ["peso", "potenza", "trazione"])
            if not base_params:
                messagebox.showwarning("Errore", "Errore nel salvataggio dei parametri base")
                return

            # Procedi con il salvataggio degli altri parametri
            for param_name, entry_widget in self.PARAMETER_MAPPING.items():
                # Salta i parametri base che sono giÃ  stati gestiti
                if param_name in ["peso", "potenza", "trazione"]:
                    continue
                
                value_str = entry_widget.get().strip()
                
                # Se il campo Ã¨ vuoto, salva None
                if not value_str:
                    update_car_parameter(car_id, param_name, None, None)
                else:
                    # Solo se c'Ã¨ un valore, prova a convertirlo preservando il formato originale
                    try:
                        float_value, original_format = self.maybe_float_preserve_format(value_str)
                        update_car_parameter(car_id, param_name, float_value, original_format)
                    except ValueError:
                        # Se non Ã¨ un numero valido, salva None
                        update_car_parameter(car_id, param_name, None, None)

            messagebox.showinfo("Save Car_ID", f"Dati salvati per Car ID {car_id}.")

        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante il salvataggio: {str(e)}")
    def get_num_laps(self):
        try:
            return int(self.spin_laps.get())
        except ValueError:
            return 10  # Default value if invalid input

    def on_start(self):
        car_str = self.entry_car.get().strip() or "Sconosciuta"
        tyre_str = self.entry_tyre.get().strip() or "Sconosciute"
        circuit_str = self.entry_circuit.get().strip() or "Sconosciuto"
        num_laps = self.get_num_laps()
        
        self.listener.car_model = car_str
        self.listener.tyre_type = tyre_str
        self.listener.circuit_name = circuit_str
        
        self.txt_output.insert(tk.END, f"[INFO] Avvio telemetria: Auto='{car_str}', Gomme='{tyre_str}', Circuito='{circuit_str}', Giri='{num_laps}'\n")
        self.listener.start_listener()
        self.root.after(50, self.update_telemetry_timer)
        
    def on_stop(self):
        self.txt_output.insert(tk.END, "[INFO] Arresto telemetria.\n")
        self.listener.stop_listener()
    def update_target_laps(self):
        """Aggiorna il numero di giri da completare prima di attivare l'analisi."""
        global target_laps
        try:
            target_laps = int(self.spin_target_laps.get())
            print(f"Analisi impostata ogni {target_laps} giri.")
        except ValueError:
            target_laps = 1  # Se l'utente inserisce un valore non valido

    def on_telemetry_data(self, telemetry_data):
        """
        Riceve i dati telemetrici e li accumula fino al completamento del numero di giri scelto.
        Esegue l'analisi solo quando il flag lap_completed == True e abbiamo raggiunto il numero di giri target.
        """
        global telemetry_buffer, lap_count, target_laps
        
        # Elabora i dati telemetrici con logging verboso solo per display real-time
        self.latest_telemetry = telemetry_data
        car_id = telemetry_data.get("car_id")
        if car_id:
            create_new_car_if_not_exists(str(car_id), self.listener.car_model or "Sconosciuta")
            self.entry_car_id.delete(0, tk.END)
            self.entry_car_id.insert(0, str(car_id))
        
        # Verifica se un giro Ã¨ stato completato controllando LAST_LAP
        current_lap = telemetry_data.get("current_lap", 0)
        last_lap = telemetry_data.get("last_lap", 0)
        lap_completed = False
        
        # Un giro Ã¨ completato quando LAST_LAP Ã¨ cambiato rispetto al ciclo precedente
        if last_lap > 0 and telemetry_buffer and last_lap != telemetry_buffer[-1].get("last_lap", 0):
            lap_completed = True
            lap_count += 1  # Incrementiamo il numero di giri completati
            logger.info(f"Giro {lap_count}/{target_laps} completato")
            self.txt_output.insert(tk.END, f"[INFO] Giro {lap_count}/{target_laps} completato\n")
        
        # Accumula dati nel buffer senza logging
        telemetry_buffer.append(telemetry_data)
        
        # Se abbiamo completato il numero target di giri, esegui l'analisi
        if lap_completed and lap_count >= target_laps:
            logger.info(f"Analisi attivata dopo {target_laps} giri")
            self.txt_output.insert(tk.END, f"[INFO] Analisi attivata dopo {target_laps} giri\n")
            self.analyze_lap_data()
            telemetry_buffer.clear()  # Svuota il buffer dopo l'analisi
            lap_count = 0  # Reset del conteggio giri
    def update_telemetry_timer(self):
        if hasattr(self, 'listener') and self.listener and self.listener.is_running:
            try:
                self.update_telemetry()
                self.root.after(250, self.update_telemetry_timer)
            except Exception as e:
                self.txt_output.insert(tk.END, f"[ERRORE] Aggiornamento telemetria: {str(e)}\n")
                self.root.after(1000, self.update_telemetry_timer)

    def format_lap_time(self, ms):
        if not ms or ms<=0:
            return "00:00.000"
        total_s = ms/1000.0
        m = int(total_s//60)
        s = int(total_s%60)
        mil = int((total_s - int(total_s))*1000)
        return f"{m:02d}:{s:02d}.{mil:03d}"

    def update_telemetry(self):
        if not self.latest_telemetry:
            return

        speed = self.latest_telemetry.get("car_speed", 0)
        self.lbl_speed.config(text=f"{speed:.1f}")

        rpm = self.latest_telemetry.get("rpm", 0)
        self.lbl_rpm.config(text=str(int(rpm)))

        gear = self.latest_telemetry.get("current_gear", 0)
        if gear > 0:
            gear_text = str(gear)
        elif gear == 0:
            gear_text = "N"
        else:
            gear_text = "R"
        self.lbl_gear.config(text=gear_text)

        fuel = self.latest_telemetry.get("current_fuel", 0.0)
        fuel_capacity = self.latest_telemetry.get("fuel_capacity", 0.0)
        self.lbl_fuel.config(text=f"{fuel:.1f}/{fuel_capacity:.1f} L")

        self.lbl_tyre_temp_fl.config(text=f"{self.latest_telemetry.get('tyre_temp_FL',0.0):.1f}")
        self.lbl_tyre_temp_fr.config(text=f"{self.latest_telemetry.get('tyre_temp_FR',0.0):.1f}")
        self.lbl_tyre_temp_rl.config(text=f"{self.latest_telemetry.get('tyre_temp_RL',0.0):.1f}")
        self.lbl_tyre_temp_rr.config(text=f"{self.latest_telemetry.get('tyre_temp_RR',0.0):.1f}")

        self.lbl_oil_temp.config(text=f"{self.latest_telemetry.get('oil_temp',0.0):.1f}")
        self.lbl_water_temp.config(text=f"{self.latest_telemetry.get('water_temp',0.0):.1f}")

        throttle = self.latest_telemetry.get("throttle", 0)
        self.lbl_throttle.config(text=f"{throttle:.1f}")

        brake = self.latest_telemetry.get("brake", 0)
        self.lbl_brake.config(text=f"{brake:.1f}")

        lat_g = self.latest_telemetry.get("lateral_g", 0.0)
        long_g = self.latest_telemetry.get("longitudinal_g", 0.0)
        self.lbl_lateral_g.config(text=f"{lat_g:.2f}")
        self.lbl_longitudinal_g.config(text=f"{long_g:.2f}")

        boost = self.latest_telemetry.get("boost", 0.0)
        self.lbl_boost.config(text=f"{boost:.2f}")

        self.lbl_slip_fl.config(text=str(self.latest_telemetry.get("tyre_slip_ratio_FL","0.00")))
        self.lbl_slip_fr.config(text=str(self.latest_telemetry.get("tyre_slip_ratio_FR","0.00")))
        self.lbl_slip_rl.config(text=str(self.latest_telemetry.get("tyre_slip_ratio_RL","0.00")))
        self.lbl_slip_rr.config(text=str(self.latest_telemetry.get("tyre_slip_ratio_RR","0.00")))

        best_lap = self.latest_telemetry.get("best_lap", 0)
        last_lap = self.latest_telemetry.get("last_lap", 0)
        current_lap = self.latest_telemetry.get("current_lap", 0)
        self.lbl_best_lap.config(text=self.format_lap_time(best_lap))
        self.lbl_last_lap.config(text=self.format_lap_time(last_lap))
        self.lbl_current_lap.config(text=self.format_lap_time(current_lap))

        # Sector 1/2/3 se li gestisci, altrimenti rimangono invariati
        # Position
        current_position = self.latest_telemetry.get("current_position", 0)
        total_positions = self.latest_telemetry.get("total_positions", 0)
        self.lbl_track_position.config(text=f"{current_position}/{total_positions}")

        # Track progress se lo calcoli

    def on_analyze(self):
        """
        Analizza i dati e genera suggerimenti usando il modello LLM.
        """
        try:
            # Ferma la telemetria durante l'analisi
            self.listener.stop_listener()
            self.txt_output.insert(tk.END, "[INFO] Training modello ML...\n")
            
            model = train_model()
            if model is None:
                self.txt_output.insert(tk.END, "[WARN] Nessun dato per training.\n")
                return
            
            self.txt_output.insert(tk.END, "[INFO] Modello addestrato.\n")
            rows = load_recent_telemetry(self.db_conn, limit=50)
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
            
            try:
                numeric_advice = infer_advice_on_batch(telemetry_batch)
                logger.info(f"Analisi ML completata: {numeric_advice}")
                self.txt_output.insert(tk.END, f"[ML] {numeric_advice}\n")
            except Exception as e:
                logger.error(f"Errore durante l'analisi ML: {str(e)}")
                self.txt_output.insert(tk.END, f"[ERRORE] Analisi ML: {str(e)}\n")
            
            if not self.llm_loaded:
                logger.info("Caricamento modello LLM in corso...")
                self.txt_output.insert(tk.END, "[INFO] Caricamento LLM...\n")
                try:
                    model_path = os.path.join(os.path.dirname(__file__), "models", "gemma-3-4b-it-Q4_K_M.gguf")
                    if not os.path.exists(model_path):
                        error_msg = f"File modello non trovato: {model_path}"
                        logger.error(error_msg)
                        self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                        messagebox.showerror("Errore LLM", error_msg)
                        return
                    
                    self.llm = GemmaLLM(model_path=model_path)
                    if not self.llm.load_model():
                        error_msg = "Impossibile caricare il modello LLM"
                        logger.error(error_msg)
                        self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                        messagebox.showerror("Errore LLM", error_msg)
                        return
                    
                    self.llm_loaded = True
                    logger.info("Modello LLM caricato con successo")
                    self.txt_output.insert(tk.END, "[INFO] Modello LLM caricato con successo\n")
                except Exception as e:
                    error_msg = f"Errore durante il caricamento del modello LLM: {str(e)}"
                    logger.error(error_msg)
                    self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                    messagebox.showerror("Errore LLM", error_msg)
                    return
            
            # Preparazione dati per il LLM
            car_data = {
                "name": self.entry_car.get().strip(),
                "car_id": self.entry_car_id.get().strip(),
                "setup": {
                    "tipo_gomme": self.entry_tyre.get().strip(),
                    "peso": self.maybe_float(self.entry_weight.get()),
                    "potenza": self.maybe_float(self.entry_power.get()),
                    "trazione": self.combo_drive_train.get()
                }
            }
            
            track_data = {
                "name": self.entry_circuit.get().strip()
            }
            
            feedback_pilota = self.entry_feedback.get().strip()
            
            # Calcola il rapporto peso/potenza
            peso = self.maybe_float(self.entry_weight.get()) or 1200
            potenza = self.maybe_float(self.entry_power.get()) or 600
            car_data["setup"]["rapporto_peso_potenza"] = peso / potenza
            
            # Utilizzo di un mutex o lock per sincronizzare l'accesso al modello LLM
            with threading.Lock():
                suggestion = self.llm.suggest_car_setup(
                    car_data=car_data,
                    track_data=track_data,
                    telemetry_data=telemetry_batch[-1] if telemetry_batch else {},
                    feedback_pilota=feedback_pilota
                )
            
            # Mostra i suggerimenti usando il metodo di utility per gestire in sicurezza lo stato del widget
            self._update_suggestion_widget(suggestion, "Suggerimenti LLM")
            
        except Exception as e:
            error_msg = f"Errore durante l'analisi: {str(e)}"
            logger.error(error_msg)
            self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
            messagebox.showerror("Errore", error_msg)
            
        finally:
            # Assicurati che il listener sia fermato in caso di errore
            if hasattr(self, 'listener'):
                self.listener.stop_listener()
    def on_reset_db(self):
        clear_telemetry(self.db_conn)
        self.txt_output.insert(tk.END, "[INFO] DB telemetria resettato.\n")

    def on_save_config(self):
        car_id = self.entry_car_id.get().strip()
        self.config["car_id"] = car_id
        self.config["auto"] = self.entry_car.get().strip()
        self.config["gomme"] = self.entry_tyre.get().strip()
        self.config["circuito"] = self.entry_circuit.get().strip()
        self.config["peso"] = self.entry_weight.get().strip()
        self.config["potenza"] = self.entry_power.get().strip()
        self.config["trazione"] = self.combo_drive_train.get()

        try:
            save_config_data(self.config)
            self.txt_output.insert(tk.END, "[INFO] Configurazione salvata.\n")
        except Exception as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Salvataggio config: {str(e)}\n")
            messagebox.showerror("Errore", f"Errore durante il salvataggio config: {str(e)}")

    def analyze_lap_data(self):
        """
        Analizza i dati telemetrici dopo il completamento del numero di giri selezionato.
        """
        global telemetry_buffer
        
        if not telemetry_buffer:
            self.txt_output.insert(tk.END, "[INFO] Nessun dato di telemetria da analizzare.\n")
            return
        
        logger.info(f"Analizzando {len(telemetry_buffer)} pacchetti di telemetria accumulati...")
        self.txt_output.insert(tk.END, f"[INFO] Analizzando {len(telemetry_buffer)} pacchetti di telemetria accumulati...\n")
        
        # Prepara l'intero batch di telemetria per l'analisi ma con logging minimo
        telemetry_batch = telemetry_buffer.copy()
        
        # Formatta i dati per il modello LLM
        track_data = {"name": self.entry_circuit.get().strip()}
        feedback_pilota = self.entry_feedback.get().strip()
        
        car_data = {
            "name": self.entry_car.get().strip(),
            "setup": {
                "peso": self.maybe_float(self.entry_weight.get()),
                "potenza": self.maybe_float(self.entry_power.get()),
                "trazione": self.combo_drive_train.get(),
                "tipo_gomme": self.entry_tyre.get().strip(),
                "rapporto_peso_potenza": float(self.label_power_weight_ratio_value.cget("text").split()[0]),
                # Parametri assetto
                "altezza_ant": self.maybe_float(self.entry_altezza_ant.get()),
                "altezza_ant_min": self.maybe_float(self.entry_altezza_ant_min.get()),
                "altezza_ant_max": self.maybe_float(self.entry_altezza_ant_max.get()),
                "altezza_post": self.maybe_float(self.entry_altezza_post.get()),
                "altezza_post_min": self.maybe_float(self.entry_altezza_post_min.get()),
                "altezza_post_max": self.maybe_float(self.entry_altezza_post_max.get()),
                # Barre antirollio
                "barre_ant": self.maybe_float(self.entry_barre_ant.get()),
                "barre_ant_min": self.maybe_float(self.entry_barre_ant_min.get()),
                "barre_ant_max": self.maybe_float(self.entry_barre_ant_max.get()),
                "barre_post": self.maybe_float(self.entry_barre_post.get()),
                "barre_post_min": self.maybe_float(self.entry_barre_post_min.get()),
                "barre_post_max": self.maybe_float(self.entry_barre_post_max.get()),
                # Ammortizzatori
                "ammort_compressione_ant": self.maybe_float(self.entry_comp_ant.get()),
                "ammort_compressione_ant_min": self.maybe_float(self.entry_comp_ant_min.get()),
                "ammort_compressione_ant_max": self.maybe_float(self.entry_comp_ant_max.get()),
                "ammort_compressione_post": self.maybe_float(self.entry_comp_post.get()),
                "ammort_compressione_post_min": self.maybe_float(self.entry_comp_post_min.get()),
                "ammort_compressione_post_max": self.maybe_float(self.entry_comp_post_max.get()),
                "ammort_estensione_ant": self.maybe_float(self.entry_est_ant.get()),
                "ammort_estensione_ant_min": self.maybe_float(self.entry_est_ant_min.get()),
                "ammort_estensione_ant_max": self.maybe_float(self.entry_est_ant_max.get()),
                "ammort_estensione_post": self.maybe_float(self.entry_est_post.get()),
                "ammort_estensione_post_min": self.maybe_float(self.entry_est_post_min.get()),
                "ammort_estensione_post_max": self.maybe_float(self.entry_est_post_max.get()),
                # Frequenza
                "frequenza_ant": self.maybe_float(self.entry_freq_ant.get()),
                "frequenza_ant_min": self.maybe_float(self.entry_freq_ant_min.get()),
                "frequenza_ant_max": self.maybe_float(self.entry_freq_ant_max.get()),
                "frequenza_post": self.maybe_float(self.entry_freq_post.get()),
                "frequenza_post_min": self.maybe_float(self.entry_freq_post_min.get()),
                "frequenza_post_max": self.maybe_float(self.entry_freq_post_max.get()),
                # Campanatura
                "campanatura_ant": self.maybe_float(self.entry_camp_ant.get()),
                "campanatura_ant_min": self.maybe_float(self.entry_camp_ant_min.get()),
                "campanatura_ant_max": self.maybe_float(self.entry_camp_ant_max.get()),
                "campanatura_post": self.maybe_float(self.entry_camp_post.get()),
                "campanatura_post_min": self.maybe_float(self.entry_camp_post_min.get()),
                "campanatura_post_max": self.maybe_float(self.entry_camp_post_max.get()),
                # Convergenza
                "conv_ant": self.maybe_float(self.entry_conv_ant.get()),
                "conv_ant_min": self.maybe_float(self.entry_conv_ant_min.get()),
                "conv_ant_max": self.maybe_float(self.entry_conv_ant_max.get()),
                "conv_post": self.maybe_float(self.entry_conv_post.get()),
                "conv_post_min": self.maybe_float(self.entry_conv_post_min.get()),
                "conv_post_max": self.maybe_float(self.entry_conv_post_max.get()),
                # Differenziali
                "diff_coppia_ant": self.maybe_float(self.entry_diff_coppia_ant.get()),
                "diff_coppia_ant_min": self.maybe_float(self.entry_diff_coppia_ant_min.get()),
                "diff_coppia_ant_max": self.maybe_float(self.entry_diff_coppia_ant_max.get()),
                "diff_coppia_post": self.maybe_float(self.entry_diff_coppia_post.get()),
                "diff_coppia_post_min": self.maybe_float(self.entry_diff_coppia_post_min.get()),
                "diff_coppia_post_max": self.maybe_float(self.entry_diff_coppia_post_max.get()),
                "diff_acc_ant": self.maybe_float(self.entry_diff_acc_ant.get()),
                "diff_acc_ant_min": self.maybe_float(self.entry_diff_acc_ant_min.get()),
                "diff_acc_ant_max": self.maybe_float(self.entry_diff_acc_ant_max.get()),
                "diff_acc_post": self.maybe_float(self.entry_diff_acc_post.get()),
                "diff_acc_post_min": self.maybe_float(self.entry_diff_acc_post_min.get()),
                "diff_acc_post_max": self.maybe_float(self.entry_diff_acc_post_max.get()),
                "diff_frenata_ant": self.maybe_float(self.entry_diff_frenata_ant.get()),
                "diff_frenata_ant_min": self.maybe_float(self.entry_diff_frenata_ant_min.get()),
                "diff_frenata_ant_max": self.maybe_float(self.entry_diff_frenata_ant_max.get()),
                "diff_frenata_post": self.maybe_float(self.entry_diff_frenata_post.get()),
                "diff_frenata_post_min": self.maybe_float(self.entry_diff_frenata_post_min.get()),
                "diff_frenata_post_max": self.maybe_float(self.entry_diff_frenata_post_max.get()),
                "diff_distrib": self.maybe_str(self.entry_diff_distrib.get()),
                # Altri parametri
                "deportanza_ant": self.maybe_float(self.entry_deportanza_ant.get()),
                "deportanza_ant_min": self.maybe_float(self.entry_deportanza_ant_min.get()),
                "deportanza_ant_max": self.maybe_float(self.entry_deportanza_ant_max.get()),
                "deportanza_post": self.maybe_float(self.entry_deportanza_post.get()),
                "deportanza_post_min": self.maybe_float(self.entry_deportanza_post_min.get()),
                "deportanza_post_max": self.maybe_float(self.entry_deportanza_post_max.get()),
                "ecu": self.maybe_float(self.entry_ecu.get()),
                "ecu_min": self.maybe_float(self.entry_ecu_min.get()),
                "ecu_max": self.maybe_float(self.entry_ecu_max.get()),
                "zavorra": self.maybe_float(self.entry_zavorra.get()),
                "zavorra_min": self.maybe_float(self.entry_zavorra_min.get()),
                "zavorra_max": self.maybe_float(self.entry_zavorra_max.get()),
                "pos_zavorra": self.maybe_float(self.entry_pos_zavorra.get()),
                "limitatore": self.maybe_float(self.entry_limitatore.get()),
                "limitatore_min": self.maybe_float(self.entry_limitatore_min.get()),
                "limitatore_max": self.maybe_float(self.entry_limitatore_max.get()),
                "freni": self.maybe_float(self.entry_freni.get()),
                # Rapporti cambio
                "rapporto_1": self.maybe_float(self.entry_rapporti[0].get()),
                "rapporto_2": self.maybe_float(self.entry_rapporti[1].get()),
                "rapporto_3": self.maybe_float(self.entry_rapporti[2].get()),
                "rapporto_4": self.maybe_float(self.entry_rapporti[3].get()),
                "rapporto_5": self.maybe_float(self.entry_rapporti[4].get()),
                "rapporto_6": self.maybe_float(self.entry_rapporti[5].get()),
                "rapporto_7": self.maybe_float(self.entry_rapporti[6].get()),
                "rapporto_8": self.maybe_float(self.entry_rapporti[7].get()),
                "rapporto_finale": self.maybe_float(self.entry_rapporto_finale.get())
            }
        }
        
        # Verifica se il LLM Ã¨ stato caricato
        if not self.llm_loaded:
            logger.info("Caricamento modello LLM in corso...")
            self.txt_output.insert(tk.END, "[INFO] Caricamento LLM...\n")
            try:
                model_path = os.path.join(os.path.dirname(__file__), "models", "gemma-3-4b-it-Q4_K_M.gguf")
                if not os.path.exists(model_path):
                    error_msg = f"File modello non trovato: {model_path}"
                    logger.error(error_msg)
                    self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                    messagebox.showerror("Errore LLM", error_msg)
                    return
                
                self.llm = GemmaLLM(model_path=model_path)
                if not self.llm.load_model():
                    error_msg = "Impossibile caricare il modello LLM"
                    logger.error(error_msg)
                    self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                    messagebox.showerror("Errore LLM", error_msg)
                    return
                
                self.llm_loaded = True
                logger.info("Modello LLM caricato con successo")
                self.txt_output.insert(tk.END, "[INFO] Modello LLM caricato con successo\n")
            except Exception as e:
                error_msg = f"Errore durante il caricamento del modello LLM: {str(e)}"
                logger.error(error_msg)
                self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                messagebox.showerror("Errore LLM", error_msg)
                return
            
        # Prima esegui l'analisi numerica sul batch completo
        try:
            logger.info("Esecuzione analisi ML sui dati di telemetria")
            numeric_advice = infer_advice_on_batch(telemetry_batch)
            logger.info(f"Risultato analisi ML: {numeric_advice}")
            self.txt_output.insert(tk.END, f"[ML] {numeric_advice}\n")
        except Exception as e:
            logger.error(f"Errore nell'analisi ML: {str(e)}")
            self.txt_output.insert(tk.END, f"[ERRORE] Analisi numerica: {str(e)}\n")
        
        # Chiamata al modello LLM per generare suggerimenti
        # Chiamata al modello LLM per generare suggerimenti
        logger.info("Generazione suggerimenti tramite LLM in corso...")
        try:
            if not self.llm or not self.llm_loaded:
                error_msg = "Modello LLM non caricato. Impossibile generare suggerimenti."
                logger.error(error_msg)
                self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                
            logger.debug("Calling LLM suggest_car_setup method")
            self.txt_output.insert(tk.END, "[INFO] Generazione suggerimenti LLM in corso...\n")
            
            # Detailed logging of input data
            logger.debug(f"Car data being sent to LLM: {car_data.get('name')} ({type(car_data)})")
            logger.debug(f"Track data being sent to LLM: {track_data.get('name')} ({type(track_data)})")
            logger.debug(f"Telemetry data available: {bool(telemetry_batch)}")
            logger.debug(f"Feedback pilota length: {len(feedback_pilota) if feedback_pilota else 0}")
            
            # Utilizzo di un mutex o lock per sincronizzare l'accesso al modello LLM
            with threading.Lock():
                suggestion = self.llm.suggest_car_setup(
                    car_data=car_data,
                    track_data=track_data, 
                    telemetry_data=telemetry_batch[-1] if telemetry_batch else {},  # Ultimo pacchetto per i dettagli attuali
                    feedback_pilota=feedback_pilota
                )
                
                # Detailed logging of response
                logger.debug(f"LLM response received, type: {type(suggestion)}")
                if suggestion is not None and isinstance(suggestion, str):
                    logger.debug(f"LLM response length: {len(suggestion)} characters")
                    logger.debug(f"LLM response preview: {suggestion[:100]}...")
                
                if suggestion is None:
                    error_msg = "Nessun suggerimento generato dal modello LLM"
                    logger.warning(error_msg)
                    self.txt_output.insert(tk.END, f"[WARN] {error_msg}\n")
                    suggestion = "Il modello non ha generato alcun suggerimento. Verificare i parametri dell'auto e del circuito."
                logger.info("Suggerimenti LLM generati con successo")
        except Exception as e:
            error_msg = f"Errore durante la generazione dei suggerimenti LLM: {str(e)}"
            logger.error(error_msg)
            self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
            suggestion = f"Errore nella generazione dei suggerimenti: {str(e)}"

        # Mostra il suggerimento nella GUI
        logger.info("Aggiornamento widget suggerimenti con risultati LLM")
        
        # Log the suggestion content for debugging
        logger.debug(f"Contenuto del suggerimento LLM (primi 100 caratteri): {str(suggestion)[:100]}...")
        logger.debug(f"Tipo del contenuto: {type(suggestion)}")
        
        # Provide immediate feedback in output log
        self.txt_output.insert(tk.END, f"[DEBUG] Ricevuta risposta LLM, lunghezza: {len(str(suggestion)) if suggestion else 0} caratteri\n")
        
        # Utilizzo il metodo di utility per aggiornare in sicurezza il widget
        update_success = self._update_suggestion_widget(suggestion, "Suggerimenti LLM")
        
        if not update_success:
            logger.error("Aggiornamento widget suggerimenti fallito")
            self.txt_output.insert(tk.END, "[ERRORE] Impossibile visualizzare il suggerimento nel widget\n")
        # Evidenzia anche i suggerimenti nel log output per migliore visibilitÃ 
        self.txt_output.insert(tk.END, "\n[SUGGERIMENTI LLM] Analisi completata! Controlla il riquadro 'Suggerimenti AI' per i dettagli.\n\n")
        
    def _update_suggestion_widget(self, content, source_label="LLM"):
        """
        Metodo di utilita per aggiornare in sicurezza il widget txt_suggest con contenuto da LLM.
        Gestisce la validazione del contenuto, conversione a stringa, e gestione stati del widget.
        
        Args:
            content: Il contenuto da mostrare (risposta LLM)
            source_label: Etichetta per logging che identifica la fonte del contenuto
        
        Returns:
            bool: True se l'aggiornamento e' riuscito, False altrimenti
        """
        logger.info(f"Aggiornamento widget txt_suggest con {source_label}")
        
        # Verifica debug del contenuto all'ingresso della funzione
        logger.debug(f"_update_suggestion_widget: contenuto ricevuto di tipo {type(content)}")
        if content is None:
            logger.warning(f"_update_suggestion_widget: contenuto ricevuto Ã¨ None")
        elif isinstance(content, str):
            content_preview = content[:100] + "..." if len(content) > 100 else content
            logger.debug(f"_update_suggestion_widget: contenuto preview: {content_preview}")
            logger.debug(f"_update_suggestion_widget: lunghezza contenuto: {len(content)} caratteri")
        else:
            logger.debug(f"_update_suggestion_widget: contenuto non stringa: {str(content)[:100]}...")
        
        # Fornisci feedback immediato nel log output
        self.txt_output.insert(tk.END, f"[DEBUG] Aggiornamento widget con {source_label} in corso...\n")
        
        # Verifica che il widget esista e sia valido
        if not hasattr(self, 'txt_suggest') or self.txt_suggest is None:
            logger.error("Widget txt_suggest non disponibile")
            self.txt_output.insert(tk.END, f"[ERRORE] Widget suggerimenti non disponibile\n")
            return False
            
        try:
            # Verifica che il widget sia ancora valido controllando una proprietÃ 
            current_state = self.txt_suggest.cget('state')
            logger.debug(f"Stato attuale del widget txt_suggest: {current_state}")
        except tk.TclError as e:
            logger.error(f"Widget txt_suggest non valido: {str(e)}")
            self.txt_output.insert(tk.END, f"[ERRORE] Widget suggerimenti non valido: {str(e)}\n")
            return False
            
        # Verifica e prepara il contenuto
        if content is None:
            display_text = f"Nessun contenuto generato dal modello LLM per {source_label}."
            logger.warning(f"Contenuto {source_label} Ã¨ None")
            self.txt_output.insert(tk.END, f"[WARN] Contenuto {source_label} Ã¨ None\n")
        elif isinstance(content, str) and not content.strip():
            display_text = f"Contenuto vuoto ricevuto dal modello LLM per {source_label}."
            logger.warning(f"Contenuto {source_label} Ã¨ una stringa vuota")
            self.txt_output.insert(tk.END, f"[WARN] Contenuto {source_label} Ã¨ una stringa vuota\n")
        else:
            try:
                display_text = str(content)
                logger.info(f"Contenuto {source_label} convertito in stringa, lunghezza: {len(display_text)} caratteri")
            except Exception as e:
                display_text = f"Errore nella formattazione del contenuto {source_label}."
                logger.error(f"Errore nella conversione del contenuto {source_label} in stringa: {str(e)}", exc_info=True)
                self.txt_output.insert(tk.END, f"[ERRORE] Formattazione contenuto {source_label}: {str(e)}\n")
        
        # Aggiorna il widget con gestione sicura degli stati
        try:
            # Salva lo stato corrente per ripristino
            was_disabled = current_state == 'disabled'
            
            # Abilita temporaneamente il widget
            if was_disabled:
                logger.debug(f"Abilitazione temporanea del widget txt_suggest per aggiornamento {source_label}")
                self.txt_suggest.config(state='normal')
            
            self.txt_suggest.delete(1.0, tk.END)
            # Verifica prima dell'inserimento
            logger.debug(f"Inserimento testo nel widget, lunghezza: {len(display_text)} caratteri")
            self.txt_suggest.insert(tk.END, display_text)
            # Verifica dopo l'inserimento
            widget_content = self.txt_suggest.get(1.0, tk.END)
            logger.debug(f"Verifica contenuto widget dopo inserimento: {len(widget_content)} caratteri")
            logger.info(f"Widget suggerimenti aggiornato correttamente con {source_label}")
            
            # Aggiorna log output con la conferma
            self.txt_output.insert(tk.END, f"[INFO] Suggerimento {source_label} visualizzato correttamente\n")
            
            # Ripristina lo stato disabled se necessario
            if was_disabled:
                logger.debug(f"Ripristino stato 'disabled' del widget txt_suggest dopo aggiornamento {source_label}")
                self.txt_suggest.config(state='disabled')
                
            return True
        except tk.TclError as e:
            logger.error(f"Errore Tkinter durante l'aggiornamento del widget suggerimenti con {source_label}: {str(e)}", exc_info=True)
            self.txt_output.insert(tk.END, f"[ERRORE] Impossibile visualizzare {source_label}: {str(e)}\n")
            return False
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'aggiornamento del widget suggerimenti con {source_label}: {str(e)}", exc_info=True)
            self.txt_output.insert(tk.END, f"[ERRORE] Errore durante la visualizzazione di {source_label}: {str(e)}\n")
            return False
            
    def on_feedback(self):
        fb = self.entry_feedback.get().strip()
        if not fb:
            return
        self.txt_output.insert(tk.END, f"[User] {fb}\n")
        if not self.llm_loaded or not self.llm:
            self.txt_output.insert(tk.END, "[WARN] LLM non caricato.\n")
            return
        config_data = {
            "modello_veicolo": self.entry_car.get().strip(),
            "nome_circuito": self.entry_circuit.get().strip(),
            "tipo_gomme": self.entry_tyre.get().strip(),
            "peso_kg": self.maybe_float(self.entry_weight.get()) or 1200,
            "potenza_cv": self.maybe_float(self.entry_power.get()) or 600,
            "tipo_trazione": self.combo_drive_train.get(),
            "rapporto_peso_potenza": float(self.label_power_weight_ratio_value.cget("text").split()[0])
        }

        # Prepara i dati nel formato corretto per GemmaLLM
        car_data = {
            "name": config_data["modello_veicolo"],
            "setup": {
                "peso": config_data["peso_kg"],
                "potenza": config_data["potenza_cv"],
                "trazione": config_data["tipo_trazione"],
                "tipo_gomme": config_data["tipo_gomme"],
                "rapporto_peso_potenza": config_data["rapporto_peso_potenza"]
            }
        }

        track_data = {
            "name": config_data["nome_circuito"]
        }

        # Aggiungi il feedback dell'utente al prompt
        prompt = f"Contesto attuale:\nAuto: {car_data['name']}\nCircuito: {track_data['name']}\nSetup: {car_data['setup']}\n\nDomanda utente: {fb}"
        logger.info(f"Elaborazione domanda utente: {fb}")
        try:
            if not self.llm or not self.llm_loaded:
                error_msg = "Modello LLM non caricato. Impossibile generare risposta."
                logger.error(error_msg)
                self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
                return
            
            logger.info(f"Richiesta risposta LLM, lunghezza prompt: {len(prompt)} caratteri")
            # Utilizzo di un mutex o lock per sincronizzare l'accesso al modello LLM
            with threading.Lock():
                resp = self.llm.generate_response(prompt)
                
            if resp is None:
                error_msg = "Il modello LLM ha restituito una risposta vuota"
                logger.warning(error_msg)
                self.txt_output.insert(tk.END, f"[AVVISO] {error_msg}\n")
                resp = "Nessuna risposta generata. Il modello potrebbe essere sovraccarico o non correttamente inizializzato."
            else:
                logger.info(f"Risposta LLM generata con successo, lunghezza: {len(resp) if isinstance(resp, str) else 'N/A'}")
        except Exception as e:
            error_msg = f"Errore durante la generazione della risposta LLM: {str(e)}"
            logger.error(error_msg)
            self.txt_output.insert(tk.END, f"[ERRORE] {error_msg}\n")
            resp = f"Errore nella generazione della risposta: {str(e)}"
        
        # Visualizza la risposta nel pannello di output con formattazione migliorata
        self.txt_output.insert(tk.END, "\n[RISPOSTA LLM]\n")
        self.txt_output.insert(tk.END, f"{resp}\n")
        self.txt_output.insert(tk.END, "-"*50 + "\n")
        
        # Mostra anche i suggerimenti nel pannello dedicato per maggiore visibilitÃ 
        logger.info("Aggiornamento widget suggerimenti con risposta feedback")
        
        # Utilizzo il metodo di utility per aggiornare in sicurezza il widget
        update_success = self._update_suggestion_widget(resp, "Risposta Feedback")
        if not update_success:
            logger.error("Aggiornamento widget suggerimenti fallito per la risposta feedback")
            self.txt_output.insert(tk.END, "[ERRORE] Impossibile visualizzare la risposta nel widget\n")
    def on_closing(self):
        try:
            if hasattr(self, 'listener') and self.listener and self.listener.is_running:
                self.listener.stop_listener()
                self.txt_output.insert(tk.END, "[INFO] Telemetria arrestata.\n")

            if hasattr(self, 'db_conn') and self.db_conn:
                with self.db_lock:
                    self.db_conn.close()
                self.txt_output.insert(tk.END, "[INFO] DB telemetria chiuso.\n")

            try:
                save_config_data(self.config)
                self.txt_output.insert(tk.END, "[INFO] Config salvata.\n")
            except Exception as e:
                self.txt_output.insert(tk.END, f"[ERRORE] Config: {str(e)}\n")

            self.root.destroy()
        except Exception as e:
            self.txt_output.insert(tk.END, f"[ERRORE] Chiusura: {str(e)}\n")
            self.root.destroy()


def main():
    root = tk.Tk()
    # Set default font for the application
    root.option_add("*Font", "Segoe UI 10")
    root.option_add("*Label.Font", "Segoe UI 10")
    root.option_add("*Button.Font", "Segoe UI 10")
    root.option_add("*Entry.Font", "Segoe UI 10")
    root.geometry("1920x1080")
    root.minsize(1920, 1080)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    app = GT7GuruGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

