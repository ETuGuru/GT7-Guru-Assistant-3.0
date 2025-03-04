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

        # Non serve più l'IP della PS dalla GUI; utilizziamo il broadcast
        self.ps_port_activate = 33739
        self.ps_port_listen = 33740

        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"

        self.byte_sender_thread = None
        self.listen_thread = None

    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        # Avvia il thread che invia ripetutamente il byte di attivazione in broadcast
        self.running = True
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

        # Il listener si lega a "0.0.0.0" sulla porta 33740
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.ps_port_listen))
        print(f"[gt7communication] Listening on 0.0.0.0:{self.ps_port_listen} @ {self.frequency}Hz", flush=True)

        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def stop_listener(self):
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        print("[gt7communication] Listener fermato.", flush=True)

    def _listen_loop(self):
        interval = 1.0 / self.frequency
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                data = None
            except Exception as e:
                if self.running:
                    print(f"[gt7communication] Errore nel loop di ascolto: {e}", flush=True)
                break

            if data:
                dec = self.salsa20_dec(data)
                if not dec:
                    time.sleep(interval)
                    continue

                gtdata = GTData(dec)
                telem_dict = gtdata.to_dict()
                telem_dict["car_model"] = self.car_model
                telem_dict["tyre_type"] = self.tyre_type
                telem_dict["circuit_name"] = self.circuit_name
                save_telemetry(self.conn, telem_dict)

            time.sleep(interval)

    def _send_byte_loop(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(("", 0))
                    # Abilita il broadcast
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    # Invia il pacchetto di attivazione ("A") in broadcast
                    print(f"[gt7communication] Invio byte (broadcast) a: 255.255.255.255:{self.ps_port_activate}", flush=True)
                    s.sendto("A".encode('utf-8'), ("255.255.255.255", self.ps_port_activate))
            except Exception as e:
                print(f"[gt7communication] Errore nell'invio del byte: {e}", flush=True)
            time.sleep(1.0)

    def salsa20_dec(self, dat):
        key = b'Simulator Interface Packet GT7 ver 0.0'
        oiv = dat[0x40:0x40 + 4]
        iv1 = int.from_bytes(oiv, 'little')
        iv2 = iv1 ^ 0xDEADBEAF

        iv = bytearray()
        iv.extend(iv2.to_bytes(4, 'little'))
        iv.extend(iv1.to_bytes(4, 'little'))

        cipher = Salsa20.new(key=key[:32], nonce=bytes(iv))
        ddata = cipher.decrypt(dat)

        magic = int.from_bytes(ddata[0:4], 'little')
        if magic != 0x47375330:
            return bytearray()
        return ddata

