# gt7communication.py

import socket
import time
import threading

from Crypto.Cipher import Salsa20
from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData

class GT7TelemetryListener:
    def __init__(self, conn):
        self.conn = conn
        self.sock = None
        self.running = False
        self.frequency = TELEMETRY_HZ

        # IP e porte
        self.playstation_ip = "0.0.0.0"
        self.ps_port_activate = 33739
        self.ps_port_listen = 33740

        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"

        self.byte_sender_thread = None

    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        # Avviamo il listener su 33740
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.playstation_ip, self.ps_port_listen))
        print(f"[gt7communication] Listening on {self.playstation_ip}:{self.ps_port_listen} @ {self.frequency}Hz")

        # Avviamo il thread di ascolto
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

        # Avviamo il thread che invia ripetutamente il byte su 33739
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

    def stop_listener(self):
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        print("[gt7communication] Listener fermato.")

    def _listen_loop(self):
        interval = 1.0 / self.frequency
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                data = None

            if data:
                dec = self.salsa20_dec(data)
                if not dec:
                    time.sleep(interval)
                    continue

                gtdata = GTData(dec)
                telem_dict = gtdata.to_dict()
                # Aggiungiamo contesto (Auto, gomme, circuito)
                telem_dict["car_model"] = self.car_model
                telem_dict["tyre_type"] = self.tyre_type
                telem_dict["circuit_name"] = self.circuit_name

                save_telemetry(self.conn, telem_dict)

            time.sleep(interval)

    def _send_byte_loop(self):
        """
        Thread che ripetutamente invia 1 byte a PS_IP:33739
        finché self.running == True (così la telemetria rimane attiva).
        """
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.sendto(b'\x01', (self.playstation_ip, self.ps_port_activate))
                    # Inviare 1 byte ogni 1s (o altro intervallo)
                time.sleep(1.0)
            except Exception as e:
                print(f"[gt7communication] Errore invio byte: {e}")
                time.sleep(1.0)

    def salsa20_dec(self, dat):
        key = b'Simulator Interface Packet GT7 ver 0.0'
        # oiv = dat[0x40:0x44]
        oiv = dat[0x40:0x44]
        iv1 = int.from_bytes(oiv, 'little')
        iv2 = iv1 ^ 0xDEADBEAF

        iv = bytearray()
        iv.extend(iv2.to_bytes(4, 'little'))
        iv.extend(iv1.to_bytes(4, 'little'))

        cipher = Salsa20.new(key=key[:32], nonce=bytes(iv))
        ddata = cipher.decrypt(dat)

        magic = int.from_bytes(ddata[0:4], 'little')
        if magic != 0x47375330:  # 'G7S0'
            return bytearray()
        return ddata
