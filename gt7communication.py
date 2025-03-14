import socket
import time
import threading
import queue
from Crypto.Cipher import Salsa20
from datetime import datetime

from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData
from car_setup_manager import CarSetupManager

class GT7TelemetryListener:
    def __init__(self, db_conn, db_lock):
        self.conn = db_conn
        self.db_lock = db_lock
        self.setup_manager = CarSetupManager()
        self.sock = None
        self.running = False
        self.frequency = TELEMETRY_HZ
        self.BUFFER_SIZE = 4096
        self.data_queue = queue.Queue()
        self.last_car_id = None  # Per tracciare cambi auto
        
        # Porte per la comunicazione
        self.ps_port_activate = 33739
        self.ps_port_listen = 33740
        
        # Info contestuali
        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"
        
        # Thread handlers
        self.byte_sender_thread = None
        self.listen_thread = None
        self.processing_thread = None
        self.telemetry_callback = None

    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        self.running = True
        self.last_car_id = None  # Reset car ID tracking

        # Avvia il thread che invia il byte di attivazione
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

        # Inizializza il socket di ascolto
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.ps_port_listen))
        print(f"[gt7communication] Listening on 0.0.0.0:{self.ps_port_listen} @ {self.frequency}Hz", flush=True)

        # Avvia i thread di ascolto e processamento
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.processing_thread = threading.Thread(target=self._processing_thread, daemon=True)
        
        self.listen_thread.start()
        self.processing_thread.start()

    def stop_listener(self):
        if not self.running:
            return

        self.running = False
        
        # Chiude il socket
        if self.sock:
            self.sock.close()
            self.sock = None
        
        # Attende la terminazione dei thread
        for thread in [self.listen_thread, self.processing_thread, self.byte_sender_thread]:
            if thread and thread.is_alive():
                thread.join(2.0)
        
        print("[gt7communication] Listener arrestato.", flush=True)

    def _listen_loop(self):
        interval = 1.0 / self.frequency
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                if data:
                    print(f"[gt7communication] Ricevuti {len(data)} bytes di dati telemetrici", flush=True)
                    self.data_queue.put(data)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"[gt7communication] Errore nel loop di ascolto: {e}", flush=True)
                break
            time.sleep(interval)

    def _processing_thread(self):
        while self.running:
            try:
                data = self.data_queue.get(timeout=1.0)
                
                # Decritta i dati
                dec = self.salsa20_dec(data)
                if not dec:
                    print("[gt7communication] Decrittazione fallita", flush=True)
                    continue
                
                # Elabora i dati decriptati
                gtdata = GTData(dec)
                telem_dict = gtdata.to_dict()
                
                if not self._validate_telemetry(telem_dict):
                    continue
                
                # Arricchisce i dati con informazioni contestuali
                self._enrich_telemetry(telem_dict)
                
                # Gestisce l'aggiornamento del setup se necessario
                self._handle_car_update(telem_dict)
                
                # Salva i dati e notifica
                self._save_telemetry(telem_dict)
                self._notify_callback(telem_dict)
                
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[gt7communication] Errore nel thread di elaborazione: {e}", flush=True)

    def _validate_telemetry(self, telem_dict):
        """Valida i dati telemetrici base"""
        if telem_dict.get("package_id") is None or telem_dict.get("car_id") is None:
            print("[gt7communication] Dati telemetrici incompleti dopo la decodifica", flush=True)
            return False
        return True

    def _enrich_telemetry(self, telem_dict):
        """Arricchisce i dati telemetrici con informazioni contestuali"""
        telem_dict["car_model"] = self.car_model
        telem_dict["tyre_type"] = self.tyre_type
        telem_dict["circuit_name"] = self.circuit_name

    def _handle_car_update(self, telem_dict):
        """Gestisce l'aggiornamento del setup quando cambia l'auto"""
        current_car_id = telem_dict.get("car_id")
        if current_car_id is not None and current_car_id != self.last_car_id:
            print(f"[gt7communication] Rilevata nuova auto: {current_car_id}", flush=True)
            self.setup_manager.update_car(
                car_id=current_car_id,
                model=self.car_model
            )
            self.last_car_id = current_car_id

    def _notify_callback(self, telem_dict):
        """Notifica il callback se presente"""
        if self.telemetry_callback:
            try:
                self.telemetry_callback(telem_dict)
            except Exception as e:
                print(f"[gt7communication] Errore nella chiamata del callback di telemetria: {e}", flush=True)

    def _send_byte_loop(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(("", 0))
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.sendto("A".encode('utf-8'), ("255.255.255.255", self.ps_port_activate))
            except Exception as e:
                print(f"[gt7communication] Errore nell'invio del byte: {e}", flush=True)
            time.sleep(1.0)

    def _save_telemetry(self, telemetry_data):
        """Salva i dati di telemetria nel database usando il lock"""
        try:
            with self.db_lock:
                save_telemetry(self.conn, telemetry_data)
        except Exception as e:
            print(f"[gt7communication] Errore nel salvataggio della telemetria: {e}", flush=True)

    def salsa20_dec(self, dat):
        """Decrittazione dei dati usando Salsa20"""
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

import socket
import time
import threading
import queue
from Crypto.Cipher import Salsa20
from datetime import datetime

from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData
from car_setup_manager import CarSetupManager

class GT7TelemetryListener:
    def __init__(self, db_conn, db_lock):
        self.conn = db_conn
        self.db_lock = db_lock
        self.setup_manager = CarSetupManager()
        self.sock = None
        self.running = False
        self.frequency = TELEMETRY_HZ
        self.BUFFER_SIZE = 4096
        self.data_queue = queue.Queue()
        self.last_car_id = None  # Per tracciare cambi auto
        
        # Porte per la comunicazione
        self.ps_port_activate = 33739
        self.ps_port_listen = 33740
        
        # Info contestuali
        self.car_model = "Sconosciuta"
        self.tyre_type = "Sconosciute"
        self.circuit_name = "Sconosciuto"
        
        # Thread handlers
        self.byte_sender_thread = None
        self.listen_thread = None
        self.processing_thread = None
        self.telemetry_callback = None

    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        self.running = True
        self.last_car_id = None  # Reset car ID tracking

        # Avvia il thread che invia il byte di attivazione
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

        # Inizializza il socket di ascolto
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.ps_port_listen))
        print(f"[gt7communication] Listening on 0.0.0.0:{self.ps_port_listen} @ {self.frequency}Hz", flush=True)

        # Avvia i thread di ascolto e processamento
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.processing_thread = threading.Thread(target=self._processing_thread, daemon=True)
        
        self.listen_thread.start()
        self.processing_thread.start()

    def stop_listener(self):
        if not self.running:
            return

        self.running = False
        
        # Chiude il socket
        if self.sock:
            self.sock.close()
            self.sock = None
        
        # Attende la terminazione dei thread
        for thread in [self.listen_thread, self.processing_thread, self.byte_sender_thread]:
            if thread and thread.is_alive():
                thread.join(2.0)
        
        print("[gt7communication] Listener arrestato.", flush=True)

    def _listen_loop(self):
        interval = 1.0 / self.frequency
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                if data:
                    self.data_queue.put(data)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"[gt7communication] Errore nel loop di ascolto: {e}", flush=True)
                break
            time.sleep(interval)

    def _processing_thread(self):
        while self.running:
            try:
                data = self.data_queue.get(timeout=1.0)
                
                # Decritta i dati
                dec = self.salsa20_dec(data)
                if not dec:
                    print("[gt7communication] Decrittazione fallita", flush=True)
                    continue
                
                # Elabora i dati decriptati
                gtdata = GTData(dec)
                telem_dict = gtdata.to_dict()
                
                if not self._validate_telemetry(telem_dict):
                    continue
                
                # Arricchisce i dati con informazioni contestuali
                self._enrich_telemetry(telem_dict)
                
                # Gestisce l'aggiornamento del setup se necessario
                self._handle_car_update(telem_dict)
                
                # Salva i dati e notifica
                self._save_telemetry(telem_dict)
                self._notify_callback(telem_dict)
                
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[gt7communication] Errore nel thread di elaborazione: {e}", flush=True)

    def _validate_telemetry(self, telem_dict):
        """Valida i dati telemetrici base"""
        if telem_dict.get("package_id") is None or telem_dict.get("car_id") is None:
            print("[gt7communication] Dati telemetrici incompleti dopo la decodifica", flush=True)
            return False
        return True

    def _enrich_telemetry(self, telem_dict):
        """Arricchisce i dati telemetrici con informazioni contestuali"""
        telem_dict["car_model"] = self.car_model
        telem_dict["tyre_type"] = self.tyre_type
        telem_dict["circuit_name"] = self.circuit_name

    def _handle_car_update(self, telem_dict):
        """Gestisce l'aggiornamento del setup quando cambia l'auto"""
        current_car_id = telem_dict.get("car_id")
        if current_car_id is not None and current_car_id != self.last_car_id:
            print(f"[gt7communication] Rilevata nuova auto: {current_car_id}", flush=True)
            self.setup_manager.update_car(
                car_id=current_car_id,
                model=self.car_model
            )
            self.last_car_id = current_car_id

    def _notify_callback(self, telem_dict):
        """Notifica il callback se presente"""
        if self.telemetry_callback:
            try:
                self.telemetry_callback(telem_dict)
            except Exception as e:
                print(f"[gt7communication] Errore nella chiamata del callback di telemetria: {e}", flush=True)

    def _send_byte_loop(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(("", 0))
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.sendto("A".encode('utf-8'), ("255.255.255.255", self.ps_port_activate))
            except Exception as e:
                print(f"[gt7communication] Errore nell'invio del byte: {e}", flush=True)
            time.sleep(1.0)

    def _save_telemetry(self, telemetry_data):
        """Salva i dati di telemetria nel database usando il lock"""
        try:
            with self.db_lock:
                save_telemetry(self.conn, telemetry_data)
        except Exception as e:
            print(f"[gt7communication] Errore nel salvataggio della telemetria: {e}", flush=True)

    def salsa20_dec(self, dat):
        """Decrittazione dei dati usando Salsa20"""
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

import queue
import socket
import threading
import time
import struct
from datetime import datetime

from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData
from car_setup_manager import CarSetupManager

class GT7TelemetryListener:
    def __init__(self, db_conn, db_lock):
        self.conn = db_conn
        self.db_lock = db_lock
        self.setup_manager = CarSetupManager()  # Initialize car setup manager
        self.sock = None
        self.running = False
        self.frequency = TELEMETRY_HZ
        self.input_queue = queue.Queue()
        self.car_model = ""
        self.tyre_type = ""
        self.circuit_name = ""
        self.last_car_id = None  # Track the last car ID to detect changes
        self.telemetry_callback = None

    def _processing_thread(self):
        while self.running:
            try:
                data = self.input_queue.get(timeout=1)
                gtdata = GTData(data)
                telem_dict = gtdata.get_telemetry()
                
                # Debug dei dati
                print(f"[gt7communication] Dati telemetrici decodificati: id={telem_dict['package_id']}, car={telem_dict['car_id']}", flush=True)
                
                current_car_id = telem_dict.get("car_id")
                
                # Check if we've switched to a different car
                if current_car_id is not None and current_car_id != self.last_car_id:
                    print(f"[gt7communication] Rilevata nuova auto: {current_car_id}", flush=True)
                    self.setup_manager.update_car(
                        car_id=current_car_id,
                        model=self.car_model
                    )
                    self.last_car_id = current_car_id
                
                # Salva i dati nel database usando il lock
                self._save_telemetry(telem_dict)
                
                # Chiama il callback di telemetria se esiste
                if self.telemetry_callback:
                    try:
                        self.telemetry_callback(telem_dict)
                    except Exception as e:
                        print(f"[gt7communication] Errore nella chiamata del callback di telemetria: {e}", flush=True)
            except queue.Empty:
                # Timeout della coda, continua il ciclo
                pass
            except Exception as e:
                print(f"[gt7communication] Errore generale nell'elaborazione dei dati: {e}", flush=True)

    def start_listener(self):
        """Starts the telemetry listener"""
        if self.running:
            return

        self.running = True
        self.last_car_id = None  # Reset last car ID when starting

        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 33740))
        self.sock.settimeout(1.0)

        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_thread)
        self.processing_thread.start()

        # Start receiving thread
        self.receiving_thread = threading.Thread(target=self._receiving_thread)
        self.receiving_thread.start()

        print("[gt7communication] Listener avviato", flush=True)

    def stop_listener(self):
        """Stops the telemetry listener"""
        if not self.running:
            return

        self.running = False
        if self.sock:
            self.sock.close()
        
        # Wait for threads to finish
        if hasattr(self, 'processing_thread') and self.processing_thread:
            self.processing_thread.join()
        if hasattr(self, 'receiving_thread') and self.receiving_thread:
            self.receiving_thread.join()

        print("[gt7communication] Listener arrestato", flush=True)

    def _receiving_thread(self):
        """Thread that receives UDP packets"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if data:
                    self.input_queue.put(data)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[gt7communication] Errore nella ricezione dei dati: {e}", flush=True)
                time.sleep(1)

    def _save_telemetry(self, telemetry_dict):
        """Saves telemetry data to database"""
        if not telemetry_dict:
            return
        
        try:
            # Add context data
            telemetry_dict["car_model"] = self.car_model
            telemetry_dict["tyre_type"] = self.tyre_type
            telemetry_dict["circuit_name"] = self.circuit_name
            
            # Save to database
            save_telemetry(self.conn, telemetry_dict, self.db_lock)
        except Exception as e:
            print(f"[gt7communication] Errore nel salvataggio della telemetria: {e}", flush=True)

# gt7communication.py

import socket
import time
import threading
import queue
from Crypto.Cipher import Salsa20
from db_manager import save_telemetry
from config import TELEMETRY_HZ
from gtdata import GTData
from car_setup_manager import CarSetupManager

class GT7TelemetryListener:
    def __init__(self, db_conn, db_lock):
        self.conn = db_conn
        self.db_lock = db_lock
        self.setup_manager = CarSetupManager()  # Add this line
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
        
        # Coda per i messaggi tra i thread
        self.data_queue = queue.Queue()
        
        self.byte_sender_thread = None
        self.listen_thread = None
        self.processing_thread = None
        self.is_running = False
    def start_listener(self):
        if self.running:
            print("[gt7communication] Listener già avviato.")
            return

        # Avvia il thread che invia ripetutamente il byte di attivazione in broadcast
        self.running = True
        self.is_running = True
        self.byte_sender_thread = threading.Thread(target=self._send_byte_loop, daemon=True)
        self.byte_sender_thread.start()

        # Il listener si lega a "0.0.0.0" sulla porta 33740
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.ps_port_listen))
        print(f"[gt7communication] Listening on 0.0.0.0:{self.ps_port_listen} @ {self.frequency}Hz", flush=True)

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
            
        print("[gt7communication] Listener fermato.", flush=True)

    def _listen_loop(self):
        interval = 1.0 / self.frequency
        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                print(f"[gt7communication] Ricevuti {len(data)} bytes di dati telemetrici", flush=True)
                
                # Inserisce i dati grezzi nella coda per l'elaborazione
                if data:
                    self.data_queue.put(data)
                    
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    print(f"[gt7communication] Errore nel loop di ascolto: {e}", flush=True)
                break

            time.sleep(interval)
            
    def _processing_thread(self):
        """Thread che processa i dati dalla coda"""
        while self.running:
            try:
                # Attende che ci siano dati nella coda (timeout di 1 secondo)
                data = self.data_queue.get(timeout=1.0)
                
                # Decritta i dati
                dec = self.salsa20_dec(data)
                if not dec:
                    print("[gt7communication] Decrittazione fallita", flush=True)
                    continue
                
                print(f"[gt7communication] Decrittazione completata, dimensione dati: {len(dec)} bytes", flush=True)
                
                # Elabora i dati decriptati
                try:
                    gtdata = GTData(dec)
                    telem_dict = gtdata.to_dict()
                    
                    # Verifica che almeno alcuni valori chiave siano presenti
                    if telem_dict["package_id"] is None or telem_dict["car_id"] is None:
                        print("[gt7communication] Dati telemetrici incompleti dopo la decodifica", flush=True)
                        continue
                        
                    # Aggiungiamo informazioni aggiuntive
                    telem_dict["car_model"] = self.car_model
                    telem_dict["tyre_type"] = self.tyre_type
                    telem_dict["circuit_name"] = self.circuit_name
                    
                    # Debug dei dati
                    print(f"[gt7communication] Dati telemetrici decodificati: id={telem_dict['package_id']}, car={telem_dict['car_id']}", flush=True)
                    
                    # Update car information in the setup database
                    if telem_dict["car_id"] is not None:
                        # Update car information in the setup database
                        self.setup_manager.update_car(
                            car_id=telem_dict["car_id"],
                            model=self.car_model
                        )
                    
                    # Salva i dati nel database usando il lock
                    self._save_telemetry(telem_dict)
                    
                    # Chiama il callback di telemetria se esiste
                    if self.telemetry_callback:
                        try:
                            self.telemetry_callback(telem_dict)
                        except Exception as e:
                            print(f"[gt7communication] Errore nella chiamata del callback di telemetria: {e}", flush=True)
                except Exception as e:
                    print(f"[gt7communication] Errore generale nell'elaborazione dei dati: {e}", flush=True)
                    
            except queue.Empty:
                # Timeout della coda, continua il ciclo
                pass
            except Exception as e:
                print(f"[gt7communication] Errore nel thread di elaborazione: {e}", flush=True)

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

    def _save_telemetry(self, telemetry_data):
        """Salva i dati di telemetria nel database usando il lock"""
        try:
            with self.db_lock:
                save_telemetry(self.conn, telemetry_data)
        except Exception as e:
            print(f"[gt7communication] Errore nel salvataggio della telemetria: {e}", flush=True)
            
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

