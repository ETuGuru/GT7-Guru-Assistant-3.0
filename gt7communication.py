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

        self.playstation_ip = "0.0.0.0"
        # *** PORTA *** su cui RICEVERE i pacchetti => 33740
        self.listener_port = 33740

        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"

    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        # PRIMA: inviamo 1 byte a PS_IP:33739
        # per attivare l'invio telemetria
        self._send_activation_byte()

        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.playstation_ip, self.listener_port))
        print(f"[gt7communication] Listening on {self.playstation_ip}:{self.listener_port} @ {self.frequency}Hz")

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _send_activation_byte(self):
        # Inviamo 1 byte (es. b'\x01') su PORT=33739
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b'\x01', (self.playstation_ip, 33739))
            print(f"[gt7communication] Inviato byte di attivazione a {self.playstation_ip}:33739")

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

                # Aggiungiamo i campi di contesto
                telem_dict["car_model"] = self.car_model
                telem_dict["tyre_type"] = self.tyre_type
                telem_dict["circuit_name"] = self.circuit_name

                save_telemetry(self.conn, telem_dict)

            time.sleep(interval)

    def salsa20_dec(self, dat):
        key = b'Simulator Interface Packet GT7 ver 0.0'
        # 0x40..0x44 per estrarre IV
        oiv = dat[0x40:0x44]
        iv1 = int.from_bytes(oiv, 'little')
        iv2 = iv1 ^ 0xDEADBEAF

        iv = bytearray()
        iv.extend(iv2.to_bytes(4, 'little'))
        iv.extend(iv1.to_bytes(4, 'little'))

        cipher = Salsa20.new(key=key[:32], nonce=bytes(iv))
        ddata = cipher.decrypt(dat)

        magic = int.from_bytes(ddata[0:4], 'little')
        # 0x47375330
        if magic != 0x47375330:
            return bytearray()
        return ddata
