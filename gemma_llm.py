# -*- coding: utf-8 -*-
"""
Modulo per la gestione delle richieste al modello LLM Gemma
Gestisce coda di richieste, cache, risposte e prompt ottimizzati per l’assistente GT7.
"""

import os
import json
import logging
import multiprocessing
import threading
import hashlib
import time
import queue
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Libreria llama_cpp per inferenza
from llama_cpp import Llama

# Import aggiuntivo richiesto:
from car_setup_manager import get_car_parameters_for_llm

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GemmaLLM")

# Percorsi di default (adatta ai tuoi path)
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "gemma-3-4b-it-Q4_K_M.gguf"
)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backup", "llm")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache", "gemma_cache.json")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "feedback", "prompt_feedback.json")
METRICS_FILE = os.path.join(os.path.dirname(__file__), "metrics", "llm_performance.json")

# Creazione directory se non esistono
for directory in [BACKUP_DIR,
                  os.path.dirname(CACHE_FILE),
                  os.path.dirname(FEEDBACK_FILE),
                  os.path.dirname(METRICS_FILE)]:
    os.makedirs(directory, exist_ok=True)

@dataclass
class SetupParameter:
    """Classe per validazione parametri di setup (opzionale)."""
    name: str
    value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None

    def is_valid(self) -> bool:
        if self.value is None:
            return False
        if self.allowed_values is not None:
            return self.value in self.allowed_values
        if isinstance(self.value, (int, float)):
            if self.min_value is not None and self.value < self.min_value:
                return False
            if self.max_value is not None and self.value > self.max_value:
                return False
        return True

    def __str__(self) -> str:
        return f"{self.name}: {self.value}"


@dataclass
class PerformanceMetrics:
    """Classe per metriche di performance del modello."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    generation_time: float
    tokens_per_second: float
    request_timestamp: float

    def to_dict(self) -> Dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "generation_time": self.generation_time,
            "tokens_per_second": self.tokens_per_second,
            "request_timestamp": self.request_timestamp
        }


class LLMRequest:
    """Classe per gestire le richieste al modello LLM con priorità."""
    def __init__(self, prompt: str, params: Dict = None, priority: int = 1, callback=None):
        self.prompt = prompt
        self.params = params or {}
        self.priority = priority  # 1 (alta) ... 5 (bassa)
        self.callback = callback
        self.result = None
        self.timestamp = time.time()
        self.id = hashlib.md5(f"{prompt}{self.timestamp}".encode()).hexdigest()


class CacheManager:
    """Gestione cache delle risposte del modello."""
    def __init__(self,
                 cache_file: str = CACHE_FILE,
                 max_size: int = 100,
                 ttl: int = 3600):
        self.cache_file = cache_file
        self.max_size = max_size
        self.ttl = ttl
        self.cache = self._load_cache()
        self.lock = threading.Lock()

    def _load_cache(self) -> Dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore caricando cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Errore salvando cache: {e}")

    def _cleanup(self) -> None:
        current_time = time.time()
        expired_keys = [k for k, v in self.cache.items() if current_time - v.get("timestamp", 0) > self.ttl]
        for key in expired_keys:
            del self.cache[key]
        if len(self.cache) > self.max_size:
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1].get("timestamp", 0))
            for key, _ in sorted_items[:len(self.cache) - self.max_size]:
                del self.cache[key]

    def get(self, key: str) -> Optional[Dict]:
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if time.time() - item.get("timestamp", 0) <= self.ttl:
                    logger.debug(f"Cache hit per key: {key[:15]}...")
                    return item
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, value: Dict) -> None:
        with self.lock:
            value["timestamp"] = time.time()
            self.cache[key] = value
            self._cleanup()
            self._save_cache()

    def clear(self) -> None:
        with self.lock:
            self.cache = {}
            self._save_cache()

    def get_stats(self) -> Dict:
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "ttl": self.ttl
            }


class FeedbackSystem:
    """Sistema di feedback per migliorare prompt e risposte."""
    def __init__(self, feedback_file: str = FEEDBACK_FILE):
        self.feedback_file = feedback_file
        self.feedback_data = self._load_feedback()
        self.lock = threading.Lock()

    def _load_feedback(self) -> Dict:
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore caricando feedback: {e}")
                return {"prompts": [], "ratings": {}}
        return {"prompts": [], "ratings": {}}

    def _save_feedback(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
            with open(self.feedback_file, 'w') as f:
                json.dump(self.feedback_data, f)
        except Exception as e:
            logger.error(f"Errore salvando feedback: {e}")

    def add_prompt(self, prompt_text: str, category: str, metadata: Dict = None) -> str:
        with self.lock:
            prompt_id = hashlib.md5(f"{prompt_text}{time.time()}".encode()).hexdigest()
            prompt_data = {
                "id": prompt_id,
                "text": prompt_text,
                "category": category,
                "created_at": time.time(),
                "metadata": metadata or {},
                "versions": [{"text": prompt_text, "created_at": time.time()}]
            }
            self.feedback_data["prompts"].append(prompt_data)
            self._save_feedback()
            return prompt_id

    def rate_response(self, prompt_id: str, response: str, rating: int, feedback: str = None) -> None:
        with self.lock:
            if prompt_id not in self.feedback_data["ratings"]:
                self.feedback_data["ratings"][prompt_id] = []
            self.feedback_data["ratings"][prompt_id].append({
                "response": response,
                "rating": rating,
                "feedback": feedback,
                "timestamp": time.time()
            })
            self._save_feedback()

    def get_best_prompts(self, category: str = None, limit: int = 5) -> List[Dict]:
        with self.lock:
            prompt_ratings = {}
            for prompt in self.feedback_data["prompts"]:
                if category and prompt["category"] != category:
                    continue
                pid = prompt["id"]
                if pid in self.feedback_data["ratings"]:
                    rvals = [r["rating"] for r in self.feedback_data["ratings"][pid]]
                    if rvals:
                        prompt_ratings[pid] = {
                            "prompt": prompt,
                            "avg_rating": sum(rvals) / len(rvals)
                        }
            sorted_prompts = sorted(prompt_ratings.values(), key=lambda x: x["avg_rating"], reverse=True)
            return [p["prompt"] for p in sorted_prompts[:limit]]

    def improve_prompt(self, prompt_id: str, new_text: str) -> None:
        with self.lock:
            for p in self.feedback_data["prompts"]:
                if p["id"] == prompt_id:
                    p["versions"].append({"text": new_text, "created_at": time.time()})
                    p["text"] = new_text
                    break
            self._save_feedback()


class MetricsCollector:
    """Raccolta e analisi metriche su prestazioni del modello."""
    def __init__(self, metrics_file: str = METRICS_FILE):
        self.metrics_file = metrics_file
        self.metrics = self._load_metrics()
        self.lock = threading.Lock()

    def _load_metrics(self) -> Dict:
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore caricando metriche: {e}")
                return {"requests": []}
        return {"requests": []}

    def _save_metrics(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f)
        except Exception as e:
            logger.error(f"Errore salvando metriche: {e}")

    def add_metrics(self, metrics: PerformanceMetrics) -> None:
        with self.lock:
            self.metrics["requests"].append(metrics.to_dict())
            if len(self.metrics["requests"]) > 1000:
                self.metrics["requests"] = self.metrics["requests"][-1000:]
            self._save_metrics()

    def get_stats(self) -> Dict:
        with self.lock:
            if not self.metrics["requests"]:
                return {
                    "count": 0,
                    "avg_tokens": 0,
                    "avg_gen_time": 0,
                    "avg_tokens_per_second": 0
                }
            total_requests = len(self.metrics["requests"])
            avg_tokens = statistics.mean([m["total_tokens"] for m in self.metrics["requests"]])
            avg_gen_time = statistics.mean([m["generation_time"] for m in self.metrics["requests"]])
            avg_tokens_per_second = statistics.mean([m["tokens_per_second"] for m in self.metrics["requests"]])
            return {
                "count": total_requests,
                "avg_tokens": avg_tokens,
                "avg_gen_time": avg_gen_time,
                "avg_tokens_per_second": avg_tokens_per_second
            }


class RequestPoolManager:
    """Gestisce una coda di richieste LLM con priorità."""
    def __init__(self, max_workers: int = 4):
        self.request_queue = queue.PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.active_requests = {}
        self.executor_tasks = {}
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info(f"RequestPoolManager in esecuzione con {max_workers} workers.")

    def _process_queue(self):
        while self.is_running:
            try:
                if self.request_queue.empty():
                    time.sleep(0.1)
                    continue
                priority, reqid, req = self.request_queue.get()
                with self.lock:
                    self.active_requests[reqid] = req
                    task = self.executor.submit(self._execute_request, req)
                    self.executor_tasks[reqid] = task
                    task.add_done_callback(lambda f, rid=reqid: self._request_completed(rid, f))
                self.request_queue.task_done()
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                time.sleep(0.5)

    def _execute_request(self, req: LLMRequest) -> Dict:
        try:
            logger.debug(f"Esecuzione request {req.id}, priority={req.priority}")
            start_t = time.time()
            # In un progetto reale, qui si chiamerebbe il GemmaLLM appropriato
            # Nel nostro esempio "dummy"
            exe_time = time.time() - start_t
            return {
                "status": "executed",
                "execution_time": exe_time,
                "request_id": req.id,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error executing request {req.id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "request_id": req.id,
                "timestamp": time.time()
            }

    def _request_completed(self, reqid: str, future):
        with self.lock:
            try:
                request = self.active_requests.get(reqid)
                if request and request.callback:
                    try:
                        result = future.result()
                        request.result = result
                        request.callback(request, result)
                    except Exception as e:
                        logger.error(f"Errore nel callback: {e}")
                if reqid in self.active_requests:
                    del self.active_requests[reqid]
                if reqid in self.executor_tasks:
                    del self.executor_tasks[reqid]
            except Exception as e:
                logger.error(f"Error completing request {reqid}: {e}")

    def submit_request(self, req: LLMRequest) -> str:
        try:
            self.request_queue.put((req.priority, req.id, req))
            logger.debug(f"Request {req.id} added with priority {req.priority}")
            return req.id
        except Exception as e:
            logger.error(f"Error submitting request: {e}")
            return ""

    def get_request_status(self, reqid: str) -> Dict:
        with self.lock:
            if reqid in self.active_requests:
                r = self.active_requests[reqid]
                return {
                    "status": "active",
                    "request": r,
                    "result": r.result
                }
            return {"status": "not_found"}


class GemmaLLM:
    """
    Interfaccia al Large Language Model Gemma specifico per GT7.
    Usa llama.cpp e integra prompt e meccanismi di cache, feedback, metrics, ecc.
    """

    # Template di prompt per diversi contesti
    PROMPT_TEMPLATES = {
        "general": """Sei un assistente esperto di Gran Turismo 7, il celebre simulatore di guida per PlayStation.
Il tuo compito è aiutare i giocatori a migliorare le loro prestazioni, fornire consigli su setup,
strategie di gara, scelta delle auto e qualsiasi altro aspetto del gioco.

Basati sempre sulle meccaniche reali del gioco GT7, evitando di fare riferimento a versioni precedenti
della serie o ad altri giochi di guida. Sii preciso e dettagliato nelle tue risposte, usando la
terminologia corretta del gioco.

Se ti vengono chiesti consigli su setup specifici, fornisci valori dettagliati per ogni parametro
di regolazione, spiegando il motivo delle tue scelte. Quando suggerisci auto, considera sempre
il loro PP (Performance Points) e le restrizioni degli eventi.""",

        "car_setup": """Sei un ingegnere di pista esperto di Gran Turismo 7, specializzato nella messa a punto delle vetture.
Il tuo compito è fornire configurazioni di setup dettagliate e ottimizzate per le specifiche combinazioni
di auto e circuiti.

Per ogni parametro del setup, devi:
1. Fornire un valore numerico preciso (non range) RISPETTANDO IL FORMATO RICHIESTO PER OGNI PARAMETRO
2. Spiegare brevemente perché hai scelto quel valore
3. Considerare il bilanciamento complessivo della vettura

FORMATI DEI PARAMETRI DA RISPETTARE RIGOROSAMENTE:
- Barre antirollio: SOLO livelli interi da 1 a 10 (incrementi di 1)
- Frequenza naturale: valori con precisione fino a 2 decimali (incrementi di 0.01)
- Campanatura: gradi (°) con precisione fino a 1 decimale (incrementi di 0.1)
- Convergenza/Divergenza: gradi (°) con precisione fino a 2 decimali (incrementi di 0.01)
- Deportanza: livello numerico (non millimetri)

!!! VINCOLI ASSOLUTI INDEROGABILI !!!
È severamente vietato suggerire valori al di fuori dei limiti min/max specificati.
Ogni valore suggerito sarà automaticamente rifiutato se non rispetta i limiti tecnici obbligatori.

IMPORTANTE:
- Usa un linguaggio tecnico diretto e conciso da ingegnere di pista
- Concludi sempre con una breve sintesi dei benefici attesi (es: “Benefici: maggiore stabilità in frenata...”)

Considera sempre:
- Tipo di trazione (FF, FR, MR, RR, 4WD)
- Rapporto peso/potenza
- Caratteristiche del circuito (rettilinei, curve veloci/lente)
- Tipo di pneumatici
- Condizioni meteorologiche (se specificate)
- Rispetta le precisioni e i formati decimali indicati per i vari parametri.

Fornisci un setup completo (Sospensioni, Aerodinamica, Trasmissione, ecc.) equilibrato tra stabilità e velocità.""",

        "telemetry": """Sei un analista di dati telemetrici per Gran Turismo 7, specializzato nell'interpretare
i dati di telemetria per migliorare le prestazioni del pilota.

Analizza i seguenti dati e fornisci indicazioni su:
1. Dove il pilota sta perdendo tempo
2. Problemi di tecnica di guida (frenata, accelerazione, traiettorie)
3. Utilizzo degli pneumatici (temperature, usura, slittamento)
4. Comportamento della vettura (sottosterzo/sovrasterzo, bilanciamento)

Fornisci consigli specifici e applicabili su:
- Tecniche di frenata (punto di frenata, intensità, modulazione)
- Tecniche di accelerazione
- Traiettorie ideali
- Assetti differenziale o trasmissione che possano aiutare

Sii preciso e usa terminologia corretta di GT7.""",

        "lap_improvement": """Sei un coach di guida esperto di Gran Turismo 7, specializzato nel miglioramento dei tempi sul giro.
In base alle informazioni fornite, identifica:
1. Tecniche di guida specifiche per abbassare i tempi
2. Punti di riferimento visivi per frenate e traiettorie
3. Tecniche di frenata e accelerazione
4. Come sfruttare al meglio il circuito

Per ogni settore del circuito, indica:
- Punto ideale di frenata (con riferimenti visivi)
- Marcia ottimale
- Timing di accelerazione
- Corretti input sterzo

Adatta i consigli al tipo di trazione e potenza dell’auto.""",

        "tire_management": """Sei un esperto di gestione pneumatici in Gran Turismo 7.
Fornisci consigli dettagliati su:
1. Gestione degrado pneumatici
2. Tecniche di guida per minimizzare usura
3. Pressioni ottimali in base a condizione e mescola
4. Strategia pit stop

Considera diverse tipologie di gomme e meteo.""",

        "fuel_strategy": """Sei un ingegnere strategico esperto di Gran Turismo 7, focalizzato sul consumo carburante.
Consigli su:
1. Mappa motore per bilanciare consumo/prestazioni
2. Tecniche guida per risparmiare carburante
3. Pit-stop rifornimento
4. Calcolo autonomia e punti critici
Adatta i consigli alla durata di gara e caratteristiche di auto/circuito."""
    }

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        n_ctx: int = 8192,
        n_threads: Optional[int] = None,
        n_batch: int = 512,
        verbose: bool = False
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_batch = n_batch
        self.n_threads = n_threads or multiprocessing.cpu_count()
        self.verbose = verbose
        self.model = None
        self.is_loaded = False
        self._loading_in_progress = False
        self.model_lock = threading.RLock()

        # Parametri di generazione default
        self.default_params = {
            "temperature": 0.2,
            "top_k": 128,
            "top_p": 0.75,
            "repeat_penalty": 1.5,
            "max_tokens": 1024
        }

        # Moduli di supporto (cache, metrics, feedback, request_pool)
        self.cache_manager = CacheManager()
        self.metrics_collector = MetricsCollector()
        self.feedback_system = FeedbackSystem()
        self.request_pool = RequestPoolManager()

        logger.info(f"GemmaLLM creato con {self.n_threads} threads, contesto={self.n_ctx}")
        logger.info(f"Model path: {self.model_path}")

    def load_model(self) -> bool:
        with self.model_lock:
            if self.is_loaded and self.model is not None:
                logger.info("Modello già caricato.")
                return True
            if self._loading_in_progress:
                logger.warning("Caricamento modello già in corso in un altro thread.")
                return False
            self._loading_in_progress = True
            try:
                logger.info(f"Caricamento modello da {self.model_path}")
                if not os.path.exists(self.model_path):
                    logger.error(f"File modello non trovato: {self.model_path}")
                    return False

                if self.model is not None:
                    logger.warning("Esiste già un'istanza di modello, pulizia in corso...")
                    self._cleanup_model_resources()

                self.model = Llama(
                    model_path=self.model_path,
                    n_threads=self.n_threads,
                    n_ctx=self.n_ctx,
                    verbose=self.verbose
                )
                if self.model is None:
                    logger.error("Costruttore Llama ha restituito None.")
                    self.is_loaded = False
                    return False

                # Test rapida
                test_response = self.model.create_chat_completion(
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                if not test_response:
                    logger.warning("La inference di test non ha restituito nulla...")

                self.is_loaded = True
                logger.info("Modello caricato correttamente.")
                return True
            except Exception as e:
                logger.error(f"Errore caricando modello: {e}", exc_info=True)
                self._cleanup_model_resources()
                return False
            finally:
                self._loading_in_progress = False

    def _cleanup_model_resources(self) -> None:
        try:
            if self.model is not None:
                if hasattr(self.model, 'reset'):
                    self.model.reset()
                del self.model
                self.model = None
            import gc
            gc.collect()
            self.is_loaded = False
        except Exception as e:
            logger.error(f"Errore cleaning model resources: {e}", exc_info=True)
            self.is_loaded = False

    def unload_model(self) -> bool:
        with self.model_lock:
            if not self.is_loaded or self.model is None:
                logger.debug("Nessun modello da scaricare.")
                return True
            logger.info("Scaricamento modello in corso...")
            self._cleanup_model_resources()
            if self.model is not None:
                logger.error("Non è stato possibile scaricare completamente il modello.")
                return False
            logger.info("Modello scaricato con successo.")
            return True

    def check_model_state(self) -> bool:
        with self.model_lock:
            if self.is_loaded and self.model is None:
                logger.error("Stato inconsistente: is_loaded=True ma self.model=None.")
                self.is_loaded = False
                return False
            if not self.is_loaded and self.model is not None:
                logger.error("Stato inconsistente: is_loaded=False ma model non è None.")
                self._cleanup_model_resources()
                return False
            return self.is_loaded and self.model is not None

    def generate_response(self, prompt: str, **kwargs) -> str:
        if not prompt or not isinstance(prompt, str):
            logger.error("Prompt vuoto o non valido in generate_response.")
            return "Errore: prompt non valido."

        with self.model_lock:
            if not self.check_model_state():
                logger.info("Modello non pronto, provo a caricarlo...")
                if not self.load_model():
                    return "Errore: impossibile caricare il modello."

        gen_params = {**self.default_params, **kwargs}
        messages = [
            {"role": "system", "content": self.PROMPT_TEMPLATES["general"]},
            {"role": "user", "content": prompt}
        ]
        try:
            resp = self.model.create_chat_completion(
                messages=messages,
                max_tokens=gen_params["max_tokens"],
                temperature=gen_params["temperature"],
                top_p=gen_params["top_p"],
                top_k=gen_params["top_k"],
                repeat_penalty=gen_params["repeat_penalty"]
            )
            if not resp or "choices" not in resp or not resp["choices"]:
                return "Errore: nessuna risposta generata."
            answer = resp["choices"][0]["message"].get("content", "")
            return answer.strip()
        except Exception as e:
            logger.error(f"Errore generando la risposta: {e}")
            return f"Errore durante la generazione: {e}"

    def suggest_car_setup(
        self,
        car_data: Dict[str, Any],
        track_data: Dict[str, Any],
        telemetry_data: Optional[Dict[str, Any]] = None,
        feedback_pilota: str = ""
    ) -> str:
        """
        Genera un setup dettagliato in base al prompt "car_setup", usando i dati auto/pista
        e parametri aggiuntivi. Integra la funzione get_car_parameters_for_llm() per recuperare
        i limiti e formati parametri dal “car_setup_manager”.
        """
        if not self.is_loaded and not self.load_model():
            return "Errore: non è stato possibile caricare il modello per il car setup."

        # Recupera parametri e limiti dal car_setup_manager
        car_id = car_data.get("car_id", "")
        try:
            setup_params = get_car_parameters_for_llm(car_id)
        except Exception as e:
            logger.warning(f"Errore get_car_parameters_for_llm: {e}")
            setup_params = {}

        # Prompt “car_setup”
        sys_prompt = self.PROMPT_TEMPLATES["car_setup"]
        user_prompt = f"Auto: {car_data.get('name','auto sconosciuta')}\n"
        user_prompt += f"Pista: {track_data.get('name','circuito sconosciuto')}\n\n"
        if telemetry_data:
            user_prompt += "Dati telemetria:\n"
            for k, v in telemetry_data.items():
                user_prompt += f"- {k}: {v}\n"
        if feedback_pilota:
            user_prompt += f"\nFeedback pilota: {feedback_pilota}\n"

        # Se abbiamo parametri fetchati da car_setup_manager, potremmo includerli
        if setup_params:
            user_prompt += "\nParametri limite e attuali:\n"
            for cat, plist in setup_params.items():
                user_prompt += f"[{cat}]\n"
                for pname, pvals in plist.items():
                    user_prompt += f"- {pname}: {pvals}\n"

        user_prompt += "\nFornisci un setup rispettando i formati e i limiti, con breve spiegazione di ogni scelta."

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            resp = self.model.create_chat_completion(
                messages=messages,
                max_tokens=1800,
                temperature=self.default_params["temperature"],
                top_p=self.default_params["top_p"],
                top_k=self.default_params["top_k"],
                repeat_penalty=self.default_params["repeat_penalty"]
            )
            if not resp or not resp["choices"]:
                return "Errore: nessuna risposta dal modello."
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Errore in suggest_car_setup: {e}")
            return f"Errore generazione setup: {e}"

    def analyze_telemetry(self, car_name: str, track_name: str,
                          telemetry_data: Dict[str, Any], lap_times: List[float]) -> str:
        """Analisi telemetria usando prompt 'telemetry'."""
        if not self.is_loaded and not self.load_model():
            return "Errore: modello non caricato per l'analisi telemetrica."

        system_prompt = self.PROMPT_TEMPLATES["telemetry"]
        user_prompt = f"Auto: {car_name}\nPista: {track_name}\n\n"
        user_prompt += "Dati telemetrici:\n"
        for k, v in telemetry_data.items():
            user_prompt += f"- {k}: {v}\n"
        if lap_times:
            user_prompt += "\nTempi sul giro:\n"
            for i, t in enumerate(lap_times):
                user_prompt += f"- Giro {i+1}: {t:.3f}s\n"
        user_prompt += "\nAnalizza questi dati e fornisci consigli mirati."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            resp = self.model.create_chat_completion(
                messages=messages,
                max_tokens=1600,
                temperature=self.default_params["temperature"],
                top_p=self.default_params["top_p"],
                top_k=self.default_params["top_k"],
                repeat_penalty=self.default_params["repeat_penalty"]
            )
            if not resp or not resp["choices"]:
                return "Errore: nessuna risposta dal modello sull'analisi telemetria."
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Errore in analyze_telemetry: {e}")
            return f"Errore analizzando telemetria: {e}"

    def generate_response_with_cache(self, prompt: str, **kwargs) -> str:
        """Esempio di generazione con cache e salvataggio metriche."""
        if not self.is_loaded and not self.load_model():
            return "Errore: impossibile caricare il modello per la generazione."

        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        cached = self.cache_manager.get(cache_key)
        if cached:
            logger.info(f"Cache hit: {cache_key[:8]}...")
            return cached["response"]

        logger.info(f"Cache miss, generando nuova risposta per key {cache_key[:8]}")

        start_time = time.time()
        response = self.generate_response(prompt, **kwargs)
        gen_time = time.time() - start_time

        self.cache_manager.set(cache_key, {"response": response, "timestamp": time.time()})
        # Aggiorna metriche
        prompt_tokens = len(prompt.split())
        resp_tokens = len(response.split()) if isinstance(response, str) else 0
        self.metrics_collector.add_metrics(PerformanceMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=resp_tokens,
            total_tokens=prompt_tokens + resp_tokens,
            generation_time=gen_time,
            tokens_per_second=(resp_tokens / gen_time) if gen_time > 0 else 0,
            request_timestamp=time.time()
        ))
        return response


# Esempio test
if __name__ == "__main__":
    llm = GemmaLLM(verbose=True)
    if llm.load_model():
        try:
            print("\n=== Test generazione base ===")
            resp = llm.generate_response("Come migliorare la frenata su una Civic Type R?")
            print("Risposta:\n", resp)

            print("\n=== Test suggerimento setup ===")
            car_info = {"name": "Nissan GT-R Nismo '20", "car_id": "gt-r-nismo-20"}
            track_info = {"name": "Circuit de Spa-Francorchamps"}
            sug = llm.suggest_car_setup(car_info, track_info)
            print("Setup suggestion:\n", sug)

            print("\n=== Test analisi telemetria ===")
            tele_data = {"max_speed": 278.5, "avg_speed": 160.0, "balance": "sottosterzo", "tyre_temp_front": "90°C"}
            laps = [2.02, 2.00, 1.99]
            tele_resp = llm.analyze_telemetry("Porsche 911 GT3 RS", "Nürburgring GP", tele_data, laps)
            print("Telemetry analysis:\n", tele_resp)

        finally:
            llm.unload_model()
