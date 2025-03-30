# car_setup_manager.py

import sqlite3
import os
import logging

# Configurazione del logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
from car_parameter_templates import CAR_PARAMETER_TEMPLATES

CAR_SETUP_DB = "car_setup.db"

def init_car_db():
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS cars (
        car_id TEXT PRIMARY KEY,
        car_name TEXT
    )
    """)

    # param_value, param_min, param_max possono essere NULL
    c.execute("""
    CREATE TABLE IF NOT EXISTS car_parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        car_id TEXT NOT NULL,
        param_name TEXT NOT NULL,
        param_value REAL,
        param_min REAL,
        param_max REAL,
        param_unit TEXT,
        FOREIGN KEY(car_id) REFERENCES cars(car_id)
    )
    """)

    conn.commit()
    conn.close()


def create_new_car_if_not_exists(car_id, car_name="Sconosciuto"):
    """
    Se car_id non esiste in 'cars', crea l'entry e inizializza
    i parametri con i valori di car_parameter_templates.
    Assicura che i parametri base (peso, potenza, trazione) siano sempre presenti.
    """
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()

    c.execute("SELECT car_id FROM cars WHERE car_id = ?", (car_id,))
    result = c.fetchone()
    if not result:
        # Inserisci in cars
        c.execute("INSERT INTO cars (car_id, car_name) VALUES (?, ?)", (car_id, car_name))
        
        # Assicurati che i parametri base siano impostati
        base_params = {
            "peso": {"value": 1200, "unit": "kg"},
            "potenza": {"value": 600, "unit": "CV"},
            "trazione": {"value": "FR", "unit": ""}
        }
        
        # Inserisci prima i parametri base
        for param_name, param_data in base_params.items():
            c.execute("""
                INSERT INTO car_parameters (
                    car_id, param_name, param_value, param_min, param_max, param_unit
                ) VALUES (?, ?, ?, NULL, NULL, ?)
            """, (car_id, param_name, param_data["value"], param_data["unit"]))

        # Poi inserisci gli altri parametri dal template
        for tmpl in CAR_PARAMETER_TEMPLATES:
            # Salta i parametri base che abbiamo già inserito
            if tmpl["name"] not in base_params:
                c.execute("""
                    INSERT INTO car_parameters (
                        car_id, param_name, param_value, param_min, param_max, param_unit
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    car_id,
                    tmpl["name"],
                    # Se un campo è None, lo salviamo come NULL in DB
                    tmpl["value"] if tmpl["value"] is not None else None,
                    tmpl["min_value"] if tmpl["min_value"] is not None else None,
                    tmpl["max_value"] if tmpl["max_value"] is not None else None,
                    tmpl["unit"] or ""
                ))
        conn.commit()

    conn.close()


def get_car_parameters(car_id):
    """
    Ritorna un dizionario con:
    {
      "car_id": car_id,
      "car_name": ...,
      "parameters": [
         {
           "param_name": ...,
           "value": (REAL o None),
           "min_value": (REAL o None),
           "max_value": (REAL o None),
           "unit": (string)
         }, ...
      ]
    } o None se non esiste
    """
    logging.debug(f"Richiesta parametri per car_id: {car_id}")
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()
    
    try:
        # Ottieni il nome dell'auto
        c.execute("SELECT car_id, car_name FROM cars WHERE car_id = ?", (car_id,))
        row = c.fetchone()
        if not row:
            logging.warning(f"Auto non trovata con ID: {car_id}")
            conn.close()
            return None

        car_name = row[1]
        logging.debug(f"Nome auto trovato: {car_name}")

        # Ottieni tutti i parametri
        c.execute("""
            SELECT param_name, param_value, param_min, param_max, param_unit
            FROM car_parameters
            WHERE car_id = ?
            ORDER BY id ASC
        """, (car_id,))
        
        rows = c.fetchall()
        param_list = []
        
        for r in rows:
            param = {
                "param_name": r[0],
                "value": r[1],
                "min_value": r[2],
                "max_value": r[3],
                "unit": r[4]
            }
            param_list.append(param)
            logging.debug(f"Parametro caricato: {param}")

        result = {
            "car_id": car_id,
            "car_name": car_name,
            "parameters": param_list
        }
        
        logging.debug(f"Caricati {len(param_list)} parametri per l'auto {car_id}")
        return result
        
    except Exception as e:
        logging.error(f"Errore nel caricamento parametri: {str(e)}", exc_info=True)
        return None
        
    finally:
        conn.close()


def update_car_parameter(car_id, param_name, new_value, original_format=None):
    """
    Aggiorna il param_value di un parametro. Se new_value è None o stringa vuota,
    salviamo NULL. Per parametri stringa (es. trazione) salviamo il valore come stringa.
    
    Args:
        car_id: ID dell'auto
        param_name: Nome del parametro
        new_value: Valore da inserire (numerico)
        original_format: Formato originale inserito dall'utente (stringa, opzionale)
    """
    logging.debug(f"Aggiornamento parametro - Car ID: {car_id}, Parametro: {param_name}, Valore: {new_value}, Formato originale: {original_format}")
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()
    
    try:
        # Se new_value è "", usiamo None
        if new_value == "":
            new_value = None
            logging.debug(f"Valore vuoto convertito a None")
        # Per il parametro trazione, assicuriamoci che sia salvato come stringa
        elif param_name == "trazione" and new_value is not None:
            new_value = str(new_value)
            logging.debug(f"Trazione convertita a stringa: {new_value}")
        
        # Aggiungiamo il formato originale nelle colonne extra
        extra_columns = ""
        extra_values = []
        extra_update = ""
        
        if original_format is not None:
            # Creiamo una tabella separata per memorizzare i formati originali
            c.execute("""
                CREATE TABLE IF NOT EXISTS parameter_formats (
                    car_id TEXT NOT NULL,
                    param_name TEXT NOT NULL,
                    original_format TEXT,
                    PRIMARY KEY (car_id, param_name)
                )
            """)
            
            # Inseriamo o aggiorniamo il formato originale
            c.execute("""
                INSERT OR REPLACE INTO parameter_formats (car_id, param_name, original_format)
                VALUES (?, ?, ?)
            """, (car_id, param_name, original_format))
            
            logging.debug(f"Formato originale salvato: {original_format}")
            
        # Verifica se il parametro esiste
        c.execute("""
            SELECT COUNT(*) 
            FROM car_parameters 
            WHERE car_id = ? AND param_name = ?
        """, (car_id, param_name))
        
        if c.fetchone()[0] > 0:
            # Aggiorna il parametro esistente
            c.execute("""
                UPDATE car_parameters
                SET param_value = ? 
                WHERE car_id = ? AND param_name = ?
            """, (new_value, car_id, param_name))
            logging.debug(f"Parametro aggiornato")
        else:
            # Inserisci nuovo parametro
            c.execute("""
                INSERT INTO car_parameters (car_id, param_name, param_value)
                VALUES (?, ?, ?)
            """, (car_id, param_name, new_value))
            logging.debug(f"Nuovo parametro inserito")

        conn.commit()
        logging.debug(f"Salvataggio parametro completato con successo")
        return True
        
    except Exception as e:
        logging.error(f"Errore nell'aggiornamento parametro: {str(e)}", exc_info=True)
        conn.rollback()
        return False
        
    finally:
        conn.close()


def update_car_parameter_range(car_id, param_name, new_min, new_max):
    """
    Aggiorna i campi param_min e param_max per un parametro. Anche qui, se vuoti, salviamo NULL.
    """
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()

    # Se new_min == "", passiamo None; idem per new_max
    if new_min == "":
        new_min = None
    if new_max == "":
        new_max = None

    c.execute("""
        UPDATE car_parameters
        SET param_min = ?, param_max = ?
        WHERE car_id = ? AND param_name = ?
    """, (new_min, new_max, car_id, param_name))

    conn.commit()
    conn.close()


def update_car_name(car_id, new_car_name):
    """
    Aggiorna car_name in cars.
    """
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()

    c.execute("""
        UPDATE cars
        SET car_name = ?
        WHERE car_id = ?
    """, (new_car_name, car_id))

    conn.commit()
    conn.close()


def load_car_parameters_batch(car_id, param_names):
    """
    Carica un gruppo specifico di parametri per un'auto.
    
    Args:
        car_id: ID dell'auto
        param_names: Lista di nomi dei parametri da caricare
    
    Returns:
        Dict con i valori dei parametri richiesti e i formati originali
    """
    logging.debug(f"Caricamento batch di parametri per auto {car_id}: {param_names}")
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()
    
    try:
        # Creiamo i placeholders per la query IN
        placeholders = ', '.join(['?' for _ in param_names])
        
        # Ottieni i parametri specificati
        c.execute(f"""
            SELECT param_name, param_value, param_min, param_max, param_unit
            FROM car_parameters
            WHERE car_id = ? AND param_name IN ({placeholders})
            ORDER BY id ASC
        """, (car_id, *param_names))
        
        rows = c.fetchall()
        result = {}
        
        for row in rows:
            param_name, value, min_val, max_val, unit = row
            
            # Manteniamo sia il valore numerico che il formato originale
            param_data = {
                "value": value,
                "min_value": min_val,
                "max_value": max_val,
                "unit": unit or "",
                "original_format": None  # Inizializzato a None
            }
            
            # Se abbiamo un valore numerico, preserviamo il formato originale
            if value is not None and isinstance(value, (int, float)):
                # Controlliamo se è un numero intero
                if value == int(value):
                    param_data["original_format"] = str(int(value))
                else:
                    # Per i decimali, preserviamo gli zeri finali se disponibili
                    # Per ora li memorizziamo come stringhe, ma dovrebbero essere 
                    # recuperati dall'input originale dell'utente in futuro
                    param_data["original_format"] = str(value)
            
            result[param_name] = param_data
        
        logging.debug(f"Caricati {len(result)} parametri in batch per l'auto {car_id}")
        return result
        
    except Exception as e:
        logging.error(f"Errore nel caricamento batch dei parametri: {str(e)}", exc_info=True)
        return {}
        
    finally:
        conn.close()


def get_car_parameters_for_llm(car_id):
    """
    Ritorna i parametri dell'auto in un formato ottimizzato per il modello LLM.
    Include tutti i valori attuali, minimi e massimi.
    
    Args:
        car_id: ID dell'auto
        
    Returns:
        Dict con i parametri strutturati per categorie con valori attuali, min e max
    """
    conn = sqlite3.connect(CAR_SETUP_DB)
    c = conn.cursor()
    
    # Ottieni tutti i parametri
    c.execute("""
        SELECT param_name, param_value, param_min, param_max, param_unit
        FROM car_parameters
        WHERE car_id = ?
        ORDER BY id ASC
    """, (car_id,))
    
    rows = c.fetchall()
    
    # Verifica se la tabella parameter_formats esiste
    c.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='parameter_formats'
    """)
    
    formats_exist = c.fetchone() is not None
    
    # Se esiste, ottieni i formati originali
    original_formats = {}
    if formats_exist:
        c.execute("""
            SELECT param_name, original_format
            FROM parameter_formats
            WHERE car_id = ?
        """, (car_id,))
        
        format_rows = c.fetchall()
        for param_name, original_format in format_rows:
            original_formats[param_name] = original_format
    
    conn.close()
    
    # Organizza i parametri per categoria
    params_by_category = {
        "Sospensioni": {},
        "Aerodinamica": {},
        "Differenziale": {},
        "Freni": {},
        "Trasmissione": {},
        "Base": {},
        "Altri": {}
    }
    
    for row in rows:
        param_name, value, min_val, max_val, unit = row
        param_data = {
            "value": value,
            "min_value": min_val,
            "max_value": max_val,
            "unit": unit or "",
            "original_format": original_formats.get(param_name, None)
        }
        
        # Classifica il parametro nella categoria appropriata
        if any(k in param_name for k in ["altezza", "ammort", "barre", "frequenza", "camp", "conv"]):
            params_by_category["Sospensioni"][param_name] = param_data
        elif any(k in param_name for k in ["aero", "deport"]):
            params_by_category["Aerodinamica"][param_name] = param_data
        elif any(k in param_name for k in ["diff", "coppia", "acc", "frenata"]):
            params_by_category["Differenziale"][param_name] = param_data
        elif any(k in param_name for k in ["freni", "brake"]):
            params_by_category["Freni"][param_name] = param_data
        elif any(k in param_name for k in ["rapporto", "cambio"]):
            params_by_category["Trasmissione"][param_name] = param_data
        elif any(k in param_name for k in ["peso", "potenza", "trazione"]):
            params_by_category["Base"][param_name] = param_data
        else:
            params_by_category["Altri"][param_name] = param_data
    
    return params_by_category
