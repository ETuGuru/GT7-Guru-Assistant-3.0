# gt7communication.py

import socket
import time
import threading
import queue
import logging
from Crypto.Cipher import Salsa20
from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData

class GT7TelemetryListener:
    def __init__(self, db_conn, db_lock):
        self.conn = db_conn
        self.db_lock = db_lock
        self.sock = None
        self.running = False
        self.frequency = TELEMETRY_HZ
        self.telemetry_callback = None
        self.BUFFER_SIZE = 4096  # Increased from 2048

        # Non serve più l'IP della PS dalla GUI; utilizziamo il broadcast
        self.ps_port_activate = 33739
        self.ps_port_listen = 33740

        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"
        
        # Buffer per i dati di un giro completo
        self.lap_buffer = []
        self.current_lap = 0
        self.last_known_lap = 0
        
        # Coda per i messaggi tra i thread
        self.data_queue = queue.Queue()
        
        self.byte_sender_thread = None
        self.listen_thread = None
        self.processing_thread = None
        self.is_running = False
        self.first_broadcast = True
    def start_listener(self):
        if self.running:
            logging.info("[gt7communication] Listener già avviato.")
            return

        # Avvia il thread che invia ripetutamente il byte di attivazione in broadcast
        self.running = True
        self.is_running = True
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

        # Il listener si lega a "0.0.0.0" sulla porta 33740
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.ps_port_listen))
        logging.info(f"[gt7communication] Listening on 0.0.0.0:{self.ps_port_listen} @ {self.frequency}Hz")

        # Avvia i thread di ascolto e di elaborazione
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.processing_thread = threading.Thread(target=self._processing_thread, daemon=True)
        
        self.listen_thread.start()
        self.processing_thread.start()

    def stop_listener(self):
        self.running = False
        self.is_running = False
        
        # Ferma i thread attendendo il loro completamento
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(2.0)  # Attende fino a 2 secondi
            
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(2.0)  # Attende fino a 2 secondi
            
        if self.byte_sender_thread and self.byte_sender_thread.is_alive():
            self.byte_sender_thread.join(2.0)  # Attende fino a 2 secondi
            
        # Chiude il socket
        if self.sock:
            self.sock.close()
            self.sock = None
            
        logging.info("[gt7communication] Listener fermato.")

    def _listen_loop(self):
        interval = 0.05  # 50ms, ~20Hz
        while self.running:
            try:
                self.sock.settimeout(0.05)  # riduci il timeout da 0.5 a 0.05
                data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                if data:
                    self.data_queue.put(data)
            except socket.timeout:
                pass
            except Exception as e:
                ...
            time.sleep(interval)
            
    def _processing_thread(self):
        """Thread che processa i dati dalla coda"""
        while self.running:
            try:
                # Attende che ci siano dati nella coda (timeout di 1 secondo)
                data = self.data_queue.get(timeout=0.05)
                
                # Decritta i dati
                dec = self.salsa20_dec(data)
                if not dec:
                    logging.error("[gt7communication] Decrittazione fallita")
                    continue
                
                logging.debug(f"[gt7communication] Decrittazione completata, dimensione dati: {len(dec)} bytes")
                
                # Elabora i dati decriptati
                try:
                    gtdata = GTData(dec)
                    telem_dict = gtdata.to_dict()
                    
                    # Verifica che almeno alcuni valori chiave siano presenti
                    if telem_dict["package_id"] is None or telem_dict["car_id"] is None:
                        logging.warning("[gt7communication] Dati telemetrici incompleti dopo la decodifica")
                        continue
                        
                    # Aggiungiamo informazioni aggiuntive
                    telem_dict["car_model"] = self.car_model
                    telem_dict["tyre_type"] = self.tyre_type
                    telem_dict["circuit_name"] = self.circuit_name
                    
                    # Gestione buffer giro
                    current_lap = telem_dict.get("current_lap", 0)
                    last_lap = telem_dict.get("last_lap", 0)
                    
                    # Se il giro è cambiato, processa il buffer
                    if last_lap > 0 and last_lap != self.last_known_lap:
                        if self.telemetry_callback and self.lap_buffer:
                            # Invia l'intero buffer del giro
                            try:
                                for lap_data in self.lap_buffer:
                                    self.telemetry_callback(lap_data)
                            except Exception as e:
                                print(f"[gt7communication] Errore nel callback: {e}", flush=True)
                        # Resetta il buffer per il nuovo giro
                        self.lap_buffer = []
                        self.last_known_lap = last_lap
                    
                    # Aggiungi i dati al buffer del giro
                    self.lap_buffer.append(telem_dict)
                    
                    # Debug dei dati
                    logging.debug(f"[gt7communication] Dati telemetrici decodificati: id={telem_dict['package_id']}, car={telem_dict['car_id']}")
                    
                    # Salva i dati nel database usando il lock
                    self._save_telemetry(telem_dict)
                    
                    # Invia i dati anche direttamente per l'aggiornamento UI in tempo reale
                    if self.telemetry_callback:
                        try:
                            self.telemetry_callback(telem_dict)
                        except Exception as e:
                            logging.error(f"[gt7communication] Errore nella chiamata del callback di telemetria: {e}")
                except Exception as e:
                    logging.error(f"[gt7communication] Errore generale nell'elaborazione dei dati: {e}")
                    
            except queue.Empty:
                # Timeout della coda, continua il ciclo
                pass
            except Exception as e:
                logging.error(f"[gt7communication] Errore nel thread di elaborazione: {e}")

    def _send_byte_loop(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(("", 0))
                    # Abilita il broadcast
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    # Invia il pacchetto di attivazione ("A") in broadcast
                    if self.first_broadcast:
                        logging.info(f"[gt7communication] Invio byte (broadcast) a: 255.255.255.255:{self.ps_port_activate}")
                        self.first_broadcast = False
                    else:
                        logging.debug(f"[gt7communication] Invio byte (broadcast) a: 255.255.255.255:{self.ps_port_activate}")
                    s.sendto("A".encode('utf-8'), ("255.255.255.255", self.ps_port_activate))
            except Exception as e:
                logging.error(f"[gt7communication] Errore nell'invio del byte: {e}")
            time.sleep(1.0)

    def _save_telemetry(self, telemetry_data):
        """Salva i dati di telemetria nel database usando il lock"""
        try:
            with self.db_lock:
                save_telemetry(self.conn, telemetry_data)
        except Exception as e:
            logging.error(f"[gt7communication] Errore nel salvataggio della telemetria: {e}")
            
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

