# GT7 Guru Assistant 3.0

## Italiano

Questa applicazione:
1. **Invia** ripetutamente un byte (`b'\x01'`) a `PS_IP:33739` per tenere attiva la telemetria.
2. **Riceve** i pacchetti su `porta 33740` in un listener.
3. **Decritta** i dati con Salsa20 (magic number `0x47375330`).
4. **Decodifica** i 296 byte (classe `GTData`), convertendo `car_speed` in km/h, `best_lap`/`last_lap` ms→s, `throttle`/`brake` in [0..100]%, ecc.
5. **Salva** su SQLite (`db_manager`).
6. **Addestra** un modello ML (TensorFlow CPU) per fornire consigli numerici (es. best_lap).
7. **Usa** un LLM locale (GPT-2) per suggerimenti testuali in linguaggio naturale.
8. **GUI** con campi IP, auto, gomme, circuito, pulsanti “Start”, “Stop”, “Analyze”, e feedback con l’LLM.

### Avvio
1. `pip install -r requirements.txt`
2. `python main.py`
3. Inserire l’IP della PlayStation e altre info (auto/gomme/circuito).
4. **Start**: avvia un thread che invia 1 byte/sec su `porta 33739`, e ascolta su `porta 33740`. GT7 invierà telemetria a 33740.
5. **Stop**: ferma listener e invio byte.
6. **Analyze**: addestra il modello ML con i dati raccolti, e l’LLM fornisce un consiglio testuale.
7. Sezione “Feedback” per interagire con l’LLM.

### TOS
L’uso di protocolli non documentati e la decrittazione dei pacchetti GT7 potrebbe violare i Termini di Servizio (reverse engineering, uso non autorizzato di dati di gioco). Usare a proprio rischio.

---

## English

This application:
1. **Repeatedly sends** a byte (`b'\x01'`) to `PS_IP:33739` to keep telemetry active.
2. **Receives** packets on port 33740 in a listener thread.
3. **Decrypts** data via Salsa20 (magic `0x47375330`).
4. **Decodes** 296 bytes (class `GTData`), converting car_speed m/s->km/h, best_lap ms->s, throttle [0..100]%, etc.
5. **Stores** in SQLite.
6. **Trains** a local ML model (TensorFlow CPU) for numeric advice.
7. **Uses** a local LLM (GPT-2) for textual suggestions.
8. **GUI** with IP, car, tyres, circuit, Start/Stop/Analyze, and a feedback field for LLM Q&A.

### Usage
1. `pip install -r requirements.txt`
2. `python main.py`
3. Enter PlayStation IP, etc.
4. **Start**: a thread sends 1 byte/second to `port 33739`, receiving telemetria on `33740`.
5. **Stop**: halts both sending and listening.
6. **Analyze**: trains ML with gathered data, LLM provides textual tips.
7. “Feedback” for LLM queries.

### TOS Warning
Intercepting/decrypting GT7 packets may violate Sony/Polyphony Digital Terms of Service regarding reverse engineering and unauthorized use of game data. Use at your own risk.
