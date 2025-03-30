# GT7 Guru Assistant 3.0
# GT7 Guru Assistant 3.0

## Overview / Panoramica

### 🇬🇧 English
GT7 Guru Assistant is an advanced tool designed to enhance your Gran Turismo 7 racing experience through intelligent car setup recommendations. The application captures comprehensive telemetry data from the game, processes it through TensorFlow-based analysis, and generates optimized setup suggestions via advanced Large Language Models (LLMs).

### 🇮🇹 Italiano
GT7 Guru Assistant è uno strumento avanzato progettato per migliorare la tua esperienza di gioco in Gran Turismo 7 attraverso raccomandazioni intelligenti per la configurazione delle vetture. L'applicazione cattura dati telemetrici completi dal gioco, li elabora tramite analisi basate su TensorFlow e genera suggerimenti ottimizzati per l'assetto tramite avanzati modelli di linguaggio (LLM).

---

## Telemetry Data Flow / Flusso dei Dati Telemetrici

### 🇬🇧 English
The application implements a sophisticated telemetry capture system that extracts and processes a comprehensive set of vehicle data including:

- **Vehicle Dynamics**: Speed, acceleration, position, rotation, angular velocity
- **Powertrain Data**: RPM, gear ratios, clutch engagement
- **Tire Information**: Temperature, pressure, slip ratio, speed, diameter, load
- **Suspension Metrics**: Height, load distribution
- **Temperature Systems**: Oil, water temperature, brake temperature
- **Race Information**: Lap times, position, fuel consumption
- **Track Data**: Track position, sector times, track length

Data packets are captured in real-time via UDP communication with Gran Turismo 7, decoded, and stored for immediate analysis and long-term performance tracking.

### 🇮🇹 Italiano
L'applicazione implementa un sofisticato sistema di acquisizione telemetrica che estrae ed elabora un set completo di dati del veicolo, tra cui:

- **Dinamiche del Veicolo**: Velocità, accelerazione, posizione, rotazione, velocità angolare
- **Dati della Trasmissione**: Giri motore, rapporti del cambio, innesto frizione
- **Informazioni Pneumatici**: Temperatura, pressione, rapporto di slittamento, velocità, diametro, carico
- **Metriche Sospensioni**: Altezza, distribuzione del carico
- **Sistemi di Temperatura**: Temperatura olio, acqua, temperatura freni
- **Informazioni di Gara**: Tempi sul giro, posizione, consumo carburante
- **Dati Tracciato**: Posizione sul tracciato, tempi di settore, lunghezza del tracciato

I pacchetti di dati vengono catturati in tempo reale tramite comunicazione UDP con Gran Turismo 7, decodificati e memorizzati per l'analisi immediata e il monitoraggio delle prestazioni a lungo termine.

---

## TensorFlow Analysis / Analisi TensorFlow

### 🇬🇧 English
The telemetry data undergoes sophisticated analysis through TensorFlow-powered machine learning models:

1. **Performance Pattern Recognition**: Identifies driving patterns and vehicle response characteristics
2. **Handling Analysis**: Evaluates stability, cornering capabilities, and control characteristics
3. **Predictive Modeling**: Projects performance changes based on potential setup modifications
4. **Comparative Assessment**: Benchmarks current setup against optimal parameters for similar track conditions

Our TensorFlow implementation uses both recurrent neural networks (RNNs) for sequential data analysis and convolutional networks for pattern detection, trained on thousands of hours of high-performance driving data.

### 🇮🇹 Italiano
I dati telemetrici vengono sottoposti a un'analisi sofisticata attraverso modelli di machine learning basati su TensorFlow:

1. **Riconoscimento dei Pattern di Prestazione**: Identifica pattern di guida e caratteristiche di risposta del veicolo
2. **Analisi della Maneggevolezza**: Valuta stabilità, capacità in curva e caratteristiche di controllo
3. **Modellazione Predittiva**: Proietta i cambiamenti di prestazione in base a potenziali modifiche dell'assetto
4. **Valutazione Comparativa**: Confronta l'assetto attuale con parametri ottimali per condizioni di pista simili

La nostra implementazione TensorFlow utilizza sia reti neurali ricorrenti (RNN) per l'analisi di dati sequenziali che reti convoluzionali per il rilevamento di pattern, addestrate su migliaia di ore di dati di guida ad alte prestazioni.

---

## LLM-Powered Suggestions / Suggerimenti Basati su LLM

### 🇬🇧 English
The application leverages advanced Large Language Models to transform complex telemetry analysis into actionable setup recommendations:

- **Contextual Understanding**: The LLM interprets TensorFlow analysis within the context of racing dynamics and vehicle-specific characteristics
- **Natural Language Recommendations**: Complex technical insights are translated into clear, actionable setup adjustments
- **Reasoning Transparency**: Each suggestion includes reasoning and expected performance impacts
- **Progressive Learning**: The system refines recommendations based on implementation outcomes and subsequent performance data

The LLM component bridges the gap between raw data analysis and practical application, providing expert-level setup guidance that adapts to your driving style and goals.

### 🇮🇹 Italiano
L'applicazione sfrutta modelli di linguaggio avanzati per trasformare l'analisi complessa della telemetria in raccomandazioni pratiche per l'assetto:

- **Comprensione Contestuale**: L'LLM interpreta l'analisi di TensorFlow nel contesto delle dinamiche di gara e delle caratteristiche specifiche del veicolo
- **Raccomandazioni in Linguaggio Naturale**: Le complesse informazioni tecniche vengono tradotte in regolazioni dell'assetto chiare e attuabili
- **Trasparenza del Ragionamento**: Ogni suggerimento include motivazioni e impatti previsti sulle prestazioni
- **Apprendimento Progressivo**: Il sistema perfeziona le raccomandazioni in base ai risultati dell'implementazione e ai successivi dati di prestazione

Il componente LLM colma il divario tra l'analisi dei dati grezzi e l'applicazione pratica, fornendo una guida per la configurazione a livello di esperti che si adatta al tuo stile di guida e ai tuoi obiettivi.

---

## User Interface / Interfaccia Utente

### 🇬🇧 English
The application features an intuitive interface for:

- **Real-time Telemetry Visualization**: Graphical representation of key vehicle parameters
- **Setup Configuration Panel**: Comprehensive controls for adjusting all vehicle parameters
- **Suggestion Implementation**: One-click application of recommended settings
- **Performance Comparison**: Before/after analysis of setup changes
- **Setup Library**: Save, load, and share optimized configurations for specific tracks and conditions

The interface is designed for both quick adjustments during practice sessions and detailed tuning in the garage, with color-coded indicators highlighting critical areas for improvement.

### 🇮🇹 Italiano
L'applicazione presenta un'interfaccia intuitiva per:

- **Visualizzazione Telemetrica in Tempo Reale**: Rappresentazione grafica dei parametri chiave del veicolo
- **Pannello di Configurazione dell'Assetto**: Controlli completi per la regolazione di tutti i parametri del veicolo
- **Implementazione dei Suggerimenti**: Applicazione con un clic delle impostazioni consigliate
- **Confronto delle Prestazioni**: Analisi prima/dopo delle modifiche all'assetto
- **Libreria di Configurazioni**: Salva, carica e condividi configurazioni ottimizzate per piste e condizioni specifiche

L'interfaccia è progettata sia per regolazioni rapide durante le sessioni di pratica che per la messa a punto dettagliata nel garage, con indicatori codificati a colori che evidenziano le aree critiche da migliorare.

---

## Installation / Installazione

### 🇬🇧 English
1. Ensure you have Python 3.8+ installed
2. Clone this repository: `git clone https://github.com/yourusername/GT7-Guru-Assistant-3.0.git`
3. Install dependencies: `pip install -r requirements.txt`
4. Configure your GT7 game to enable UDP telemetry output (Settings > Network > Telemetry > Enabled)
5. Run the application: `python main.py`

### 🇮🇹 Italiano
1. Assicurati di avere Python 3.8+ installato
2. Clona questo repository: `git clone https://github.com/yourusername/GT7-Guru-Assistant-3.0.git`
3. Installa le dipendenze: `pip install -r requirements.txt`
4. Configura il tuo gioco GT7 per abilitare l'output telemetrico UDP (Impostazioni > Rete > Telemetria > Abilitata)
5. Esegui l'applicazione: `python main.py`

---

## Data Safety / Sicurezza dei Dati

### 🇬🇧 English
The application implements robust data management practices to ensure reliability and data integrity:

- **Null Value Handling**: All telemetry data is validated before processing, with appropriate default values for missing or null data points
- **Automated Backup System**: The application performs regular automatic backups of your configuration and telemetry data to prevent loss
- **Data Validation**: Comprehensive validation checks ensure all input data meets expected formats and ranges before processing
- **Exception Management**: Structured exception handling prevents application crashes when encountering unexpected data
- **Version Control**: All application components are version-controlled to enable rollback to previous stable states if needed

These safeguards ensure consistent application performance even with inconsistent or incomplete telemetry data from the game.

### 🇮🇹 Italiano
L'applicazione implementa robuste pratiche di gestione dei dati per garantire affidabilità e integrità:

- **Gestione Valori Nulli**: Tutti i dati telemetrici vengono validati prima dell'elaborazione, con valori predefiniti appropriati per i dati mancanti o nulli
- **Sistema di Backup Automatico**: L'applicazione esegue regolarmente backup automatici dei dati di configurazione e telemetria per prevenire perdite
- **Validazione Dati**: Controlli di validazione completi garantiscono che tutti i dati di input soddisfino i formati e gli intervalli previsti prima dell'elaborazione
- **Gestione Eccezioni**: Una gestione strutturata delle eccezioni previene arresti dell'applicazione quando si incontrano dati imprevisti
- **Controllo Versione**: Tutti i componenti dell'applicazione sono sotto controllo di versione per consentire il ripristino a stati stabili precedenti se necessario

Queste protezioni garantiscono prestazioni costanti dell'applicazione anche con dati telemetrici inconsistenti o incompleti dal gioco.

---

## Key Components / Componenti Chiave

### 🇬🇧 English
- **gt7communication.py**: Manages UDP communication with the game
- **gtdata.py**: Decodes and processes telemetry data packets
- **mechanics.py**: Performs physical calculations and handling analysis
- **db_manager.py**: Handles database operations for storing and retrieving telemetry data
- **falcon_llm.py**: Interfaces with Falcon LLM to generate natural language setup recommendations
- **local_ai_model.py**: Deep learning analysis of performance data using TensorFlow
- **config.py**: Manages application configuration settings
- **main.py**: Main application entry point and user interface controller
- **backup.py**: Handles automated backup of application data and configurations
- **data_validator.py**: Validates input data and provides safe defaults for null values

### 🇮🇹 Italiano
- **gt7communication.py**: Gestisce la comunicazione UDP con il gioco
- **gtdata.py**: Decodifica ed elabora i pacchetti di dati telemetrici
- **mechanics.py**: Esegue calcoli fisici e analisi della maneggevolezza
- **db_manager.py**: Gestisce le operazioni del database per memorizzare e recuperare i dati telemetrici
- **falcon_llm.py**: Interfaccia con Falcon LLM per generare raccomandazioni in linguaggio naturale per l'assetto
- **local_ai_model.py**: Analisi di deep learning dei dati di prestazione utilizzando TensorFlow
- **config.py**: Gestisce le impostazioni di configurazione dell'applicazione
- **main.py**: Punto di ingresso principale dell'applicazione e controller dell'interfaccia utente
- **backup.py**: Gestisce il backup automatico dei dati e delle configurazioni dell'applicazione
- **data_validator.py**: Valida i dati di input e fornisce valori predefiniti sicuri per i valori nulli

---

## License / Licenza

### 🇬🇧 English
This project is licensed under the MIT License - see the LICENSE file for details.

### 🇮🇹 Italiano
Questo progetto è concesso in licenza secondo i termini della Licenza MIT - vedi il file LICENSE per i dettagli.
