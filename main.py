# main.py

import os
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "huggingface_cache")
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from db_manager import init_db, load_recent_telemetry, clear_telemetry, save_config
from gt7communication import GT7TelemetryListener
from local_ai_model import train_model, infer_advice_on_batch
from local_llm import LocalLLM
from config import DB_PATH

# Imposta la cache di Hugging Face nella cartella locale (per il modello LLM)
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "huggingface_cache")

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # Configurazione di default (valori correnti e range per alcuni parametri)
    return {
        "auto": "",
        "gomme": "",
        "circuito": "",
        # Parametri assetto (valore corrente e range)
        "altezza": "100",
        "altezza_min": "",
        "altezza_max": "",
        "barre": "5",
        "barre_min": "",
        "barre_max": "",
        "ammortizzazione_compressione": "50",
        "ammortizzazione_compressione_min": "",
        "ammortizzazione_compressione_max": "",
        "ammortizzazione_estensione": "50",
        "ammortizzazione_estensione_min": "",
        "ammortizzazione_estensione_max": "",
        "frequenza_naturale": "10",
        "frequenza_naturale_min": "",
        "frequenza_naturale_max": "",
        "campanatura": "-2",
        "campanatura_min": "",
        "campanatura_max": "",
        # Angolo di convergenza (anteriore e posteriore)
        "conv_ant": "0",
        "conv_ant_type": "Convergente",
        "conv_ant_min": "",
        "conv_ant_max": "",
        "conv_post": "0",
        "conv_post_type": "Convergente",
        "conv_post_min": "",
        "conv_post_max": "",
        # Differenziale e deportanza (valori correnti)
        "diff_coppia_ant": "5",
        "diff_coppia_post": "5",
        "diff_acc_ant": "5",
        "diff_acc_post": "5",
        "diff_frenata_ant": "5",
        "diff_frenata_post": "5",
        "diff_distrib": "50",
        "deportanza_ant": "50",
        "deportanza_post": "50",
        # Prestazioni
        "zavorra": "0",
        "pos_zavorra": "0",
        "limitatore": "100",
        "freni": "0",
        # Cambio
        "rapporti": "2.83,2.10,1.70,1.45,1.30,1.20,0.00,0.00",
        "rapporto_finale": "4.00"
    }

def save_config_data(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

class GT7GuruGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GT7 Guru Assistant 3.0")
        self.config = load_config()
        self.conn = init_db(DB_PATH)
        self.listener = GT7TelemetryListener(self.conn)
        self.llm = None
        self.llm_loaded = False
        self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, columnspan=5, sticky="nsew")

        # Tab 1: Dati contestuali
        self.tab_context = ttk.Frame(notebook)
        notebook.add(self.tab_context, text="Dati contestuali")
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

        # Tab 2: Parametri Assetto
        self.tab_params = ttk.Frame(notebook)
        notebook.add(self.tab_params, text="Parametri Assetto")
        # Header: Parametro, Valore, Min, Max
        ttk.Label(self.tab_params, text="Parametro", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.tab_params, text="Valore", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(self.tab_params, text="Min", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, padx=5, pady=2)
        ttk.Label(self.tab_params, text="Max", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=3, padx=5, pady=2)

        row = 1
        # Altezza dal suolo
        ttk.Label(self.tab_params, text="Altezza dal suolo (mm)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_altezza = ttk.Entry(self.tab_params, width=10)
        self.entry_altezza.insert(0, self.config.get("altezza", "100"))
        self.entry_altezza.grid(row=row, column=1, padx=5, pady=2)
        self.entry_altezza_min = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_min.insert(0, self.config.get("altezza_min", ""))
        self.entry_altezza_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_altezza_max = ttk.Entry(self.tab_params, width=5)
        self.entry_altezza_max.insert(0, self.config.get("altezza_max", ""))
        self.entry_altezza_max.grid(row=row, column=3, padx=5, pady=2)
        row += 1

        # Barre Antirollio
        ttk.Label(self.tab_params, text="Barre Antirollio (livello)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_barre = ttk.Entry(self.tab_params, width=10)
        self.entry_barre.insert(0, self.config.get("barre", "5"))
        self.entry_barre.grid(row=row, column=1, padx=5, pady=2)
        self.entry_barre_min = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_min.insert(0, self.config.get("barre_min", ""))
        self.entry_barre_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_barre_max = ttk.Entry(self.tab_params, width=5)
        self.entry_barre_max.insert(0, self.config.get("barre_max", ""))
        self.entry_barre_max.grid(row=row, column=3, padx=5, pady=2)
        row += 1

        # [Qui aggiungi altri parametri assetto seguendo la stessa struttura per: Ammort. Compressione, Ammort. Estensione, Frequenza Naturale, Campanatura]
        # ...

        # Angolo di convergenza – Anteriore
        ttk.Label(self.tab_params, text="Angolo convergenza Anteriore (°)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_conv_ant = ttk.Entry(self.tab_params, width=10)
        self.entry_conv_ant.insert(0, self.config.get("conv_ant", "0"))
        self.entry_conv_ant.grid(row=row, column=1, padx=5, pady=2)
        self.entry_conv_ant_min = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_ant_min.insert(0, self.config.get("conv_ant_min", ""))
        self.entry_conv_ant_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_conv_ant_max = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_ant_max.insert(0, self.config.get("conv_ant_max", ""))
        self.entry_conv_ant_max.grid(row=row, column=3, padx=5, pady=2)
        ttk.Label(self.tab_params, text="Tipo").grid(row=row, column=4, sticky="e", padx=5, pady=2)
        self.conv_ant_type = tk.StringVar(value=self.config.get("conv_ant_type", "Convergente"))
        self.radio_conv_ant_conv = ttk.Radiobutton(self.tab_params, text="Convergente", variable=self.conv_ant_type, value="Convergente")
        self.radio_conv_ant_div = ttk.Radiobutton(self.tab_params, text="Divergente", variable=self.conv_ant_type, value="Divergente")
        self.radio_conv_ant_conv.grid(row=row, column=5, padx=5, pady=2, sticky="w")
        self.radio_conv_ant_div.grid(row=row, column=6, padx=5, pady=2, sticky="w")
        row += 1

        # Angolo di convergenza – Posteriore
        ttk.Label(self.tab_params, text="Angolo convergenza Posteriore (°)").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.entry_conv_post = ttk.Entry(self.tab_params, width=10)
        self.entry_conv_post.insert(0, self.config.get("conv_post", "0"))
        self.entry_conv_post.grid(row=row, column=1, padx=5, pady=2)
        self.entry_conv_post_min = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_post_min.insert(0, self.config.get("conv_post_min", ""))
        self.entry_conv_post_min.grid(row=row, column=2, padx=5, pady=2)
        self.entry_conv_post_max = ttk.Entry(self.tab_params, width=5)
        self.entry_conv_post_max.insert(0, self.config.get("conv_post_max", ""))
        self.entry_conv_post_max.grid(row=row, column=3, padx=5, pady=2)
        ttk.Label(self.tab_params, text="Tipo").grid(row=row, column=4, sticky="e", padx=5, pady=2)
        self.conv_post_type = tk.StringVar(value=self.config.get("conv_post_type", "Convergente"))
        self.radio_conv_post_conv = ttk.Radiobutton(self.tab_params, text="Convergente", variable=self.conv_post_type, value="Convergente")
        self.radio_conv_post_div = ttk.Radiobutton(self.tab_params, text="Divergente", variable=self.conv_post_type, value="Divergente")
        self.radio_conv_post_conv.grid(row=row, column=5, padx=5, pady=2, sticky="w")
        self.radio_conv_post_div.grid(row=row, column=6, padx=5, pady=2, sticky="w")
        row += 1

        # (Qui inserisci anche gli altri parametri assetto già implementati, ad es. Differenziale, Deportanza, Zavorra, Posizionamento, Limitatore, Freni)

        # Tab 3: Parametri Cambio
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

        # Frame per i suggerimenti AI
        self.frame_suggest = ttk.LabelFrame(self.root, text="Suggerimenti AI")
        self.frame_suggest.grid(row=3, column=0, columnspan=5, padx=5, pady=5, sticky="w")
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

        # Area di log e feedback
        self.txt_output = scrolledtext.ScrolledText(self.root, width=100, height=8)
        self.txt_output.grid(row=5, column=0, columnspan=5, padx=5, pady=5)
        self.lbl_feedback = ttk.Label(self.root, text="Feedback / Domanda:")
        self.lbl_feedback.grid(row=6, column=0, sticky="e", padx=5, pady=2)
        self.entry_feedback = ttk.Entry(self.root, width=50)
        self.entry_feedback.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        self.btn_feedback = ttk.Button(self.root, text="Invia", command=self.on_feedback)
        self.btn_feedback.grid(row=6, column=2, padx=5, pady=2)

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

    def on_analyze(self):
        self.on_stop()
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
            self.llm = LocalLLM()
            self.llm_loaded = True

        # Calcolo angoli convergenza per Anteriore e Posteriore
        try:
            conv_ant_val = float(self.entry_conv_ant.get())
        except ValueError:
            conv_ant_val = 0.0
        if self.conv_ant_type.get() == "Convergente":
            conv_ant_final = -abs(conv_ant_val)
        else:
            conv_ant_final = abs(conv_ant_val)
        try:
            conv_post_val = float(self.entry_conv_post.get())
        except ValueError:
            conv_post_val = 0.0
        if self.conv_post_type.get() == "Convergente":
            conv_post_final = -abs(conv_post_val)
        else:
            conv_post_final = abs(conv_post_val)

        params = (
            f"Altezza dal suolo: {self.entry_altezza.get()} mm (Min: {self.entry_altezza_min.get()}, Max: {self.entry_altezza_max.get()}); "
            f"Barre Antirollio: {self.entry_barre.get()} (Min: {self.entry_barre_min.get()}, Max: {self.entry_barre_max.get()}); "
            # Aggiungi altri parametri assetto con la stessa logica...
            f"Angolo convergenza: Anteriore {conv_ant_final}° ({self.conv_ant_type.get()}), "
            f"Posteriore {conv_post_final}° ({self.conv_post_type.get()}); "
            f"Rapporti marce: " + ",".join([entry.get().strip() for entry in self.entry_rapporti]) + "; "
            f"Rapporto finale: {self.entry_rapporto_finale.get()}"
        )
        context = f"{numeric_advice}\n{params}\nAuto: {telemetry_batch[-1].get('car_model', 'Sconosciuta')}, " \
                  f"Gomme: {telemetry_batch[-1].get('tyre_type', 'Sconosciute')}, " \
                  f"Circuito: {telemetry_batch[-1].get('circuit_name', 'Sconosciuto')}"
        suggestion = self.llm.generate_response(context)
        self.txt_suggest.delete(1.0, tk.END)
        self.txt_suggest.insert(tk.END, suggestion)

    def on_reset_db(self):
        clear_telemetry(self.conn)
        self.txt_output.insert(tk.END, "[INFO] Database resettato.\n")

    def on_save_config(self):
        self.config["auto"] = self.entry_car.get().strip()
        self.config["gomme"] = self.entry_tyre.get().strip()
        self.config["circuito"] = self.entry_circuit.get().strip()
        # Parametri assetto per Altezza dal suolo
        self.config["altezza"] = self.entry_altezza.get().strip()
        self.config["altezza_min"] = self.entry_altezza_min.get().strip()
        self.config["altezza_max"] = self.entry_altezza_max.get().strip()
        # Barre
        self.config["barre"] = self.entry_barre.get().strip()
        self.config["barre_min"] = self.entry_barre_min.get().strip()
        self.config["barre_max"] = self.entry_barre_max.get().strip()
        # (Salva qui anche gli altri parametri assetto se implementati con range)
        # Angolo convergenza – Anteriore
        self.config["conv_ant"] = self.entry_conv_ant.get().strip()
        self.config["conv_ant_type"] = self.conv_ant_type.get()
        self.config["conv_ant_min"] = self.entry_conv_ant_min.get().strip()
        self.config["conv_ant_max"] = self.entry_conv_ant_max.get().strip()
        # Angolo convergenza – Posteriore
        self.config["conv_post"] = self.entry_conv_post.get().strip()
        self.config["conv_post_type"] = self.conv_post_type.get()
        self.config["conv_post_min"] = self.entry_conv_post_min.get().strip()
        self.config["conv_post_max"] = self.entry_conv_post_max.get().strip()
        # Altri parametri assetto (Differenziale, Deportanza, Zavorra, etc.)
        self.config["diff_coppia_ant"] = self.entry_diff_coppia_ant.get().strip()
        self.config["diff_coppia_post"] = self.entry_diff_coppia_post.get().strip()
        self.config["diff_acc_ant"] = self.entry_diff_acc_ant.get().strip()
        self.config["diff_acc_post"] = self.entry_diff_acc_post.get().strip()
        self.config["diff_frenata_ant"] = self.entry_diff_frenata_ant.get().strip()
        self.config["diff_frenata_post"] = self.entry_diff_frenata_post.get().strip()
        self.config["diff_distrib"] = self.entry_diff_distrib.get().strip()
        self.config["deportanza_ant"] = self.entry_deportanza_ant.get().strip()
        self.config["deportanza_post"] = self.entry_deportanza_post.get().strip()
        self.config["zavorra"] = self.entry_zavorra.get().strip()
        self.config["pos_zavorra"] = self.entry_pos_zavorra.get().strip()
        self.config["limitatore"] = self.entry_limitatore.get().strip()
        self.config["freni"] = self.entry_freni.get().strip()
        # Cambio
        ratios = []
        for entry in self.entry_rapporti:
            ratios.append(entry.get().strip())
        self.config["rapporti"] = ",".join(ratios)
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

def main():
    root = tk.Tk()
    app = GT7GuruGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()