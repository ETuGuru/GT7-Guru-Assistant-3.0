# GT7 Guru Assistant 3.0

## Italiano

Questa applicazione permette di:
1. **Inviare** un byte “ridondante” a `PS_IP:33739` per innescare l'invio di telemetria.  
2. **Ricevere** i pacchetti su porta `33740`.  
3. **Decrittare** con **Salsa20** (key `'Simulator Interface Packet GT7 ver 0.0'`), controllando il magic number `0x47375330`.  
4. **Decodificare** i 296 byte con la classe `GTData` in `gtdata.py` (unità di misura coerenti: car_speed km/h, best_lap s, throttle [0..100]%...).  
5. **Salvare** i dati su SQLite (db_manager).  
6. **Addestrare** un modello ML (TensorFlow CPU) per stime (best_lap, ecc.).  
7. **LLM locale** (GPT-2) per suggerimenti testuali.  
8. **GUI** (Tkinter) con IP, Auto, Gomme, Circuito, pulsanti Start/Stop/Analyze, e “Feedback” con l’LLM.

### Avvio
1. `pip install -r requirements.txt`
2. `python main.py`
3. Inserisci IP della PlayStation, ad es. “192.168.1.10”.
4. Inserisci Auto/Gomme/Circuito, clicca **Start**:  
   - Invia un byte a porta 33739, la PS inizia a mandare telemetria su 33740.  
5. **Stop** quando hai abbastanza dati, poi **Analyze** per allenare il modello ML. L’LLM fornisce consigli testuali.  
6. “Feedback” consente di scrivere domande all’LLM.

### TOS
L’uso di protocolli non documentati e la decrittazione dei pacchetti GT7 può violare i Termini di Servizio di Sony/Polyphony Digital (reverse engineering, uso dati di gioco). Agisci a tuo rischio.

---

## English

This application:
1. **Sends** a “redundant” byte to `PS_IP:33739` to trigger telemetry.  
2. **Receives** packets on port `33740`.  
3. **Decrypts** with **Salsa20** (key `'Simulator Interface Packet GT7 ver 0.0'`), checking magic `0x47375330`.  
4. **Decodes** the 296-byte structure in `gtdata.py` (car speed in km/h, times in s, throttle in [0..100]%...).  
5. **Stores** data in SQLite.  
6. **Trains** a local ML model (TensorFlow CPU) for numeric suggestions.  
7. **Local LLM** (GPT-2) for textual advice.  
8. **GUI** (Tkinter) with fields: IP, Car, Tyres, Circuit, plus “Start/Stop/Analyze” and “Feedback” for LLM Q&A.

### Usage
1. `pip install -r requirements.txt`
2. `python main.py`
3. Provide PlayStation IP, e.g. “192.168.1.10”.  
4. Press **Start**: a byte is sent to port 33739, telemetry arrives on 33740.  
5. **Stop** after enough laps, **Analyze** trains ML. LLM gives textual tips.  
6. “Feedback” can ask the LLM more questions.

### ToS Warning
Intercepting/decrypting GT7 packets may violate Sony/Polyphony Digital’s Terms of Service regarding reverse engineering and unauthorized use of game data. Use at your own risk.
