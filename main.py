# main.py

import tkinter as tk
from tkinter import scrolledtext

from db_manager import init_db, load_recent_telemetry
from gt7communication import GT7TelemetryListener
from local_ai_model import train_model, infer_advice_on_batch
from local_llm import LocalLLM
from config import DB_PATH

class GT7GuruGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GT7 Guru Assistant 3.0")

        self.conn = init_db(DB_PATH)
        self.listener = GT7TelemetryListener(self.conn)

        # Campo IP
        self.lbl_ip = tk.Label(root, text="PlayStation IP:")
        self.entry_ip = tk.Entry(root, width=20)
        self.entry_ip.insert(0, "192.168.1.123")
        self.lbl_ip.grid(row=0, column=0, sticky="e")
        self.entry_ip.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # Auto
        self.lbl_car = tk.Label(root, text="Auto (nome+anno):")
        self.entry_car = tk.Entry(root, width=30)
        self.lbl_car.grid(row=1, column=0, sticky="e")
        self.entry_car.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        # Gomme
        self.lbl_tyre = tk.Label(root, text="Gomme:")
        self.entry_tyre = tk.Entry(root, width=30)
        self.lbl_tyre.grid(row=2, column=0, sticky="e")
        self.entry_tyre.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        # Circuito
        self.lbl_circuit = tk.Label(root, text="Circuito / Variante:")
        self.entry_circuit = tk.Entry(root, width=30)
        self.lbl_circuit.grid(row=3, column=0, sticky="e")
        self.entry_circuit.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        # Pulsanti
        self.btn_start = tk.Button(root, text="Start", command=self.on_start)
        self.btn_stop = tk.Button(root, text="Stop", command=self.on_stop)
        self.btn_analyze = tk.Button(root, text="Analyze", command=self.on_analyze)

        self.btn_start.grid(row=4, column=0, padx=5, pady=5)
        self.btn_stop.grid(row=4, column=1, padx=5, pady=5)
        self.btn_analyze.grid(row=4, column=2, padx=5, pady=5)

        self.txt_output = scrolledtext.ScrolledText(root, width=80, height=15)
        self.txt_output.grid(row=5, column=0, columnspan=3, padx=5, pady=5)

        # Feedback
        self.lbl_feedback = tk.Label(root, text="Feedback / Domanda:")
        self.lbl_feedback.grid(row=6, column=0, sticky="e")
        self.entry_feedback = tk.Entry(root, width=50)
        self.entry_feedback.grid(row=6, column=1, sticky="w")
        self.btn_feedback = tk.Button(root, text="Invia", command=self.on_feedback)
        self.btn_feedback.grid(row=6, column=2, padx=5, pady=5)

        self.llm = None
        self.llm_loaded = False

    def on_start(self):
        ip_str = self.entry_ip.get().strip()
        if not ip_str:
            ip_str = "0.0.0.0"

        car_str = self.entry_car.get().strip() or "Sconosciuta"
        tyre_str = self.entry_tyre.get().strip() or "Sconosciute"
        circuit_str = self.entry_circuit.get().strip() or "Sconosciuto"

        self.listener.playstation_ip = ip_str
        self.listener.car_model = car_str
        self.listener.tyre_type = tyre_str
        self.listener.circuit_name = circuit_str

        self.txt_output.insert(tk.END, f"[INFO] Avvio telemetria su IP={ip_str}, Auto='{car_str}', Gomme='{tyre_str}', Circuito='{circuit_str}'\n")
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

        if telemetry_batch:
            cm = telemetry_batch[-1].get("car_model","Sconosciuta")
            tt = telemetry_batch[-1].get("tyre_type","Sconosciute")
            cc = telemetry_batch[-1].get("circuit_name","Sconosciuto")
        else:
            cm, tt, cc = "Sconosciuta", "Sconosciute", "Sconosciuto"

        context = f"{numeric_advice}\nAuto: {cm}\nGomme: {tt}\nCircuito: {cc}"
        final_text = self.llm.generate_response(context)
        self.txt_output.insert(tk.END, f"[LLM] {final_text}\n")

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
