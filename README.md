# GT7 Guru Assistant 3.0

## Italiano

Questa applicazione consente di:
1. **Intercettare** la telemetria di Gran Turismo 7 da un IP configurabile (PlayStation).
2. **Decrittare** i pacchetti con **Salsa20** (vedi `gt7communication.py`), controllando il magic number `0x47375330`.
3. **Decodificare** i 296 byte con la classe `GTData` (in `gtdata.py`), convertendo:
   - Velocità auto da m/s a km/h
   - Velocità ruote in m/s
   - Tempi (best_lap, last_lap) da ms a s
   - Throttle/Brake da [0..255] a [0..100]%, ecc.
4. **Salvare** i dati in un database SQLite (db_manager).
5. **Addestrare** un modello ML (TensorFlow su CPU) per fornire consigli numerici (es. best_lap).
6. **Usare** un LLM locale (GPT-2) per suggerimenti testuali.
7. **GUI** (Tkinter) con campi:
   - IP Playstation
   - Auto (nome+anno)
   - Gomme
   - Circuito
   + Pulsanti "Start", "Stop", "Analyze" e un'area di feedback con l’LLM.

### Avvio
1. `pip install -r requirements.txt`
2. `python main.py`
3. Inserire IP della PS (es. "192.168.1.10"), Auto/Gomme/Circuito, cliccare **Start**.
4. Dopo alcuni giri, **Stop**, poi **Analyze** per allenare il ML e ottenere un consiglio. L’LLM fornirà anche un testo discorsivo.  
5. La sezione "Feedback" consente di interagire con l’LLM.

### Potenziali violazioni dei ToS
L’intercettazione e la decrittazione di pacchetti GT7 può violare i Termini di Servizio di Sony/Polyphony Digital, in particolare:
- Divieto di reverse-engineering e protocolli non documentati
- Uso di dati di gioco non autorizzato
Usare a proprio rischio e consultare i TOS.

---

## English

This application allows:
1. **Intercepting** Gran Turismo 7 telemetry from a user-specified IP (PlayStation).
2. **Decrypting** packets via **Salsa20** (see `gt7communication.py`), checking magic number `0x47375330`.
3. **Decoding** the 296-byte data with `GTData` (`gtdata.py`), converting:
   - Car speed m/s -> km/h
   - Wheel speeds in m/s
   - Lap times ms -> s
   - Throttle/Brake [0..255] -> [0..100]%, etc.
4. **Saving** into an SQLite database.
5. **Training** a local ML model (TensorFlow CPU) for numeric advice (e.g. best_lap).
6. **Using** a local LLM (GPT-2) for textual suggestions.
7. **Tkinter GUI**: 
   - IP address of PS
   - Car name/year
   - Tyre type
   - Circuit variant
   + "Start", "Stop", "Analyze", and a feedback chat area for the LLM.

### How to run
1. `pip install -r requirements.txt`
2. `python main.py`
3. Enter the PlayStation IP (e.g. "192.168.1.10"), car name, tyres, circuit, then **Start** capturing at ~10Hz.
4. **Stop** after some laps, then **Analyze** to train the ML model and get numeric advice. The LLM will provide textual commentary.
5. Use "Feedback" to ask the LLM additional questions.

### Potential TOS Violations
**Warning**: Intercepting and decrypting GT7 packets may violate Sony/Polyphony Digital Terms of Service:
- Reverse engineering or undocumented protocols
- Unauthorized usage of in-game data
Use at your own risk after reviewing the TOS.
