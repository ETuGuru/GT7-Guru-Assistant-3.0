# -*- coding: utf-8 -*-
"""
Modulo per la gestione delle richieste al modello LLM Gemma
Gestisce la coda di richieste, la cache e le risposte del modello
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
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama
from car_setup_manager import get_car_parameters_for_llm
# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GemmaLLM")

# Configurazione percorsi
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "gemma-3-4b-it-Q4_K_M.gguf")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backup", "llm")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache", "gemma_cache.json")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "feedback", "prompt_feedback.json")
METRICS_FILE = os.path.join(os.path.dirname(__file__), "metrics", "llm_performance.json")

# Creazione directory se non esistono
for directory in [BACKUP_DIR, os.path.dirname(CACHE_FILE), os.path.dirname(FEEDBACK_FILE), os.path.dirname(METRICS_FILE)]:
    os.makedirs(directory, exist_ok=True)


@dataclass
class SetupParameter:
    """Classe per validazione parametri di setup"""
    name: str
    value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    
    def is_valid(self) -> bool:
        """Verifica se il valore è valido in base ai limiti e valori consentiti"""
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
    """Classe per metriche di performance del modello"""
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
    """Classe per gestire le richieste al modello LLM con priorità"""
    def __init__(self, prompt: str, params: Dict = None, priority: int = 1, callback=None):
        self.prompt = prompt
        self.params = params or {}
        self.priority = priority  # 1 (alta) a 5 (bassa)
        self.callback = callback
        self.result = None
        self.timestamp = time.time()
        self.id = hashlib.md5(f"{prompt}{self.timestamp}".encode()).hexdigest()


class CacheManager:
    """Gestione della cache per le risposte del modello"""
    def __init__(self, cache_file: str = CACHE_FILE, max_size: int = 100, ttl: int = 3600):
        self.cache_file = cache_file
        self.max_size = max_size
        self.ttl = ttl  # Time-to-live in secondi
        self.cache = self._load_cache()
        self.lock = threading.Lock()
        
    def _load_cache(self) -> Dict:
        """Carica la cache dal file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore nel caricamento della cache: {e}")
                return {}
        return {}
        
    def _save_cache(self) -> None:
        """Salva la cache su file"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Errore nel salvataggio della cache: {e}")
            
    def _cleanup(self) -> None:
        """Rimuove elementi scaduti e mantiene la cache entro la dimensione massima"""
        current_time = time.time()
        # Rimuovi elementi scaduti
        expired_keys = [k for k, v in self.cache.items() if current_time - v.get("timestamp", 0) > self.ttl]
        for key in expired_keys:
            del self.cache[key]
            
        # Se la cache è ancora troppo grande, rimuovi gli elementi più vecchi
        if len(self.cache) > self.max_size:
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1].get("timestamp", 0))
            for key, _ in sorted_items[:len(self.cache) - self.max_size]:
                del self.cache[key]
                
    def get(self, key: str) -> Optional[Dict]:
        """Ottiene un elemento dalla cache se esiste e non è scaduto"""
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if time.time() - item.get("timestamp", 0) <= self.ttl:
                    logger.debug(f"Cache hit per key: {key[:15]}...")
                    return item
                else:
                    # Elemento scaduto
                    del self.cache[key]
            return None
            
    def set(self, key: str, value: Dict) -> None:
        """Aggiunge un elemento alla cache"""
        with self.lock:
            value["timestamp"] = time.time()
            self.cache[key] = value
            self._cleanup()
            self._save_cache()
            
    def clear(self) -> None:
        """Svuota la cache"""
        with self.lock:
            self.cache = {}
            self._save_cache()
            
    def get_stats(self) -> Dict:
        """Restituisce statistiche sulla cache"""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "ttl": self.ttl
            }


class FeedbackSystem:
    """Sistema di feedback per miglioramento prompt"""
    def __init__(self, feedback_file: str = FEEDBACK_FILE):
        self.feedback_file = feedback_file
        self.feedback_data = self._load_feedback()
        self.lock = threading.Lock()
        
    def _load_feedback(self) -> Dict:
        """Carica i dati di feedback dal file"""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore nel caricamento dei feedback: {e}")
                return {"prompts": [], "ratings": {}}
        return {"prompts": [], "ratings": {}}
        
    def _save_feedback(self) -> None:
        """Salva i dati di feedback su file"""
        try:
            os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
            with open(self.feedback_file, 'w') as f:
                json.dump(self.feedback_data, f)
        except Exception as e:
            logger.error(f"Errore nel salvataggio dei feedback: {e}")
            
    def add_prompt(self, prompt_text: str, category: str, metadata: Dict = None) -> str:
        """Aggiunge un nuovo prompt al sistema"""
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
        """Valuta una risposta del modello (rating da 1 a 5)"""
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
        """Ottiene i migliori prompt in base alle valutazioni"""
        with self.lock:
            prompt_ratings = {}
            
            # Calcola il rating medio per ogni prompt
            for prompt in self.feedback_data["prompts"]:
                if category and prompt["category"] != category:
                    continue
                    
                prompt_id = prompt["id"]
                if prompt_id in self.feedback_data["ratings"]:
                    ratings = [r["rating"] for r in self.feedback_data["ratings"][prompt_id]]
                    if ratings:
                        prompt_ratings[prompt_id] = {
                            "prompt": prompt,
                            "avg_rating": sum(ratings) / len(ratings)
                        }
            
            # Ordina per rating medio in ordine decrescente
            sorted_prompts = sorted(prompt_ratings.values(), key=lambda x: x["avg_rating"], reverse=True)
            return [p["prompt"] for p in sorted_prompts[:limit]]
            
    def improve_prompt(self, prompt_id: str, new_text: str) -> None:
        """Aggiorna un prompt con una versione migliorata"""
        with self.lock:
            for prompt in self.feedback_data["prompts"]:
                if prompt["id"] == prompt_id:
                    prompt["versions"].append({
                        "text": new_text,
                        "created_at": time.time()
                    })
                    prompt["text"] = new_text
                    break
            self._save_feedback()


class MetricsCollector:
    """Raccolta e analisi delle metriche di performance del modello"""
    def __init__(self, metrics_file: str = METRICS_FILE):
        self.metrics_file = metrics_file
        self.metrics = self._load_metrics()
        self.lock = threading.Lock()
        
    def _load_metrics(self) -> Dict:
        """Carica le metriche dal file"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore nel caricamento delle metriche: {e}")
                return {"requests": []}
        return {"requests": []}
        
    def _save_metrics(self) -> None:
        """Salva le metriche su file"""
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f)
        except Exception as e:
            logger.error(f"Errore nel salvataggio delle metriche: {e}")
    
    def add_metrics(self, metrics: PerformanceMetrics) -> None:
        """Aggiunge nuove metriche alla collezione
        
        Args:
            metrics: PerformanceMetrics object con i dati da aggiungere
        """
        with self.lock:
            self.metrics["requests"].append(metrics.to_dict())
            # Limita il numero di metriche salvate per evitare file troppo grandi
            if len(self.metrics["requests"]) > 1000:
                self.metrics["requests"] = self.metrics["requests"][-1000:]
            self._save_metrics()
    
    def get_stats(self) -> Dict:
        """Ottiene statistiche sulle metriche raccolte
        
        Returns:
            Dict: Statistiche calcolate sui dati raccolti
        """
        with self.lock:
            if not self.metrics["requests"]:
                return {
                    "count": 0,
                    "avg_tokens": 0,
                    "avg_gen_time": 0,
                    "avg_tokens_per_second": 0
                }
            
            # Calcola statistiche
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
    """Gestisce la coda di richieste LLM con priorità"""
    def __init__(self, max_workers: int = 4):
        self.request_queue = queue.PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.active_requests = {}
        self.executor_tasks = {}
        self.is_running = True
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
        logger.info(f"Request pool manager initialized with {max_workers} workers")
    
    def _process_queue(self):
        while self.is_running:
            try:
                if self.request_queue.empty():
                    time.sleep(0.1)
                    continue
                    
                priority, request_id, request = self.request_queue.get()
                
                with self.lock:
                    self.active_requests[request_id] = request
                    task = self.executor.submit(self._execute_request, request)
                    self.executor_tasks[request_id] = task
                    task.add_done_callback(lambda f, rid=request_id: self._request_completed(rid, f))
                    
                self.request_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                time.sleep(0.5)
    
    def _execute_request(self, request: LLMRequest) -> Dict:
        try:
            logger.debug(f"Executing request {request.id} with priority {request.priority}")
            logger.debug(f"Request prompt length: {len(request.prompt)} chars")
            
            start_time = time.time()
            # Here would be the actual execution of the request
            # In this implementation, we're just returning a status
            # In a complete implementation, this would process the request
            execution_time = time.time() - start_time
            
            logger.debug(f"Request {request.id} executed in {execution_time:.2f}s")
            return {
                "status": "executed",
                "execution_time": execution_time,
                "request_id": request.id,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error executing request {request.id}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "request_id": request.id,
                "timestamp": time.time()
            }
    
    def _request_completed(self, request_id: str, future):
        with self.lock:
            try:
                request = self.active_requests.get(request_id)
                if request and request.callback:
                    try:
                        result = future.result()
                        request.result = result
                        request.callback(request, result)
                    except Exception as e:
                        logger.error(f"Error in request callback: {e}")
                
                # Clean up
                if request_id in self.active_requests:
                    del self.active_requests[request_id]
                if request_id in self.executor_tasks:
                    del self.executor_tasks[request_id]
                    
            except Exception as e:
                logger.error(f"Error completing request {request_id}: {e}")
    
    def submit_request(self, request: LLMRequest) -> str:
        try:
            self.request_queue.put((request.priority, request.id, request))
            logger.debug(f"Request {request.id} added to queue with priority {request.priority}")
            return request.id
        except Exception as e:
            logger.error(f"Error submitting request: {e}")
            return None
    
    def get_request_status(self, request_id: str) -> Dict:
        with self.lock:
            if request_id in self.active_requests:
                request = self.active_requests[request_id]
                return {
                    "status": "active",
                    "request": request,
                    "result": request.result
                }
            return {"status": "not_found"}


class GemmaLLM:
    """Large Language Model interface using Gemma for GT7 assistant."""
    
    # Dizionario di template per diversi tipi di prompt
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
        2. Spiegare BREVEMENTE perché hai scelto quel valore
        3. Considerare il bilanciamento complessivo della vettura

        FORMATI DEI PARAMETRI DA RISPETTARE RIGOROSAMENTE:
        - Barre antirollio: SOLO livelli interi da 1 a 10 (incrementi di 1)
        - Frequenza naturale: valori con precisione fino a 2 decimali (incrementi di 0.01)
        - Campanatura: gradi (°) con precisione fino a 1 decimale (incrementi di 0.1)
        - Convergenza/Divergenza: gradi (°) con precisione fino a 2 decimali (incrementi di 0.01)
        - Deportanza: livello numerico (non millimetri)

        !!! VINCOLI ASSOLUTI INDEROGABILI !!!
        È SEVERAMENTE VIETATO suggerire valori al di fuori dei limiti min/max specificati per ciascun parametro

        - I limiti forniti sono REQUISITI TECNICI OBBLIGATORI, non semplici linee guida
- Se un parametro ha un limite min-max (es. 40-60mm), il valore proposto DEVE essere compreso in tale intervallo
- OGNI VALORE SUGGERITO SARÀ AUTOMATICAMENTE RIFIUTATO SE NON RISPETTA I LIMITI SPECIFICATI
- Il mancato rispetto di questi vincoli renderà il setup inutilizzabile

IMPORTANTE:
- Usa un linguaggio tecnico diretto e conciso da ingegnere di pista
- Concludi SEMPRE con una breve sintesi dei benefici attesi (es. "Benefici: maggiore stabilità in frenata, migliore trazione in uscita")

Considera sempre:
- Il tipo di trazione (FF, FR, MR, RR, 4WD)
- Il rapporto peso/potenza
- Le caratteristiche del circuito (rettilinei, curve veloci/lente)
- Il tipo di pneumatici
- Le condizioni meteorologiche (se specificate)

- La campanatura (in gradi °) va specificata con precisione fino a 1 decimale (es. 2.5°, incrementi di 0.1)
- La convergenza/divergenza (in gradi °) va specificata con precisione fino a 2 decimali (es. 0.05°, incrementi di 0.01)
- Le barre antirollio sono SOLO livelli da 1 a 10 con incrementi di 1 (non millimetri)
- La frequenza naturale va specificata con precisione fino a 2 decimali (es. 2.85, incrementi di 0.01)
- La deportanza è un livello numerico (non millimetri)
Fornisci valori precisi per questi parametri rispettando rigorosamente i formati indicati e considerando il tipo di circuito e lo stile di guida.
Fornisci valori precisi per questi parametri considerando il tipo di circuito e lo stile di guida.

Organizza i parametri in sezioni logiche (Sospensioni, Aerodinamica, Trasmissione, ecc.).
Fornisci un setup completo che garantisca un buon equilibrio tra stabilità, velocità e maneggevolezza.""",

        "telemetry": """Sei un analista di dati telemetrici per Gran Turismo 7, specializzato nell'interpretare 
        i dati di telemetria per migliorare le prestazioni del pilota.

Analizza attentamente i seguenti dati e fornisci indicazioni chiare su:
1. Dove il pilota sta perdendo tempo
2. Problemi di tecnica di guida (frenata, accelerazione, traiettorie)
3. Utilizzo degli pneumatici (temperature, slittamento)
4. Comportamento della vettura (sottosterzo, sovrasterzo, bilanciamento)

Fornisci consigli specifici e applicabili su:
- Tecniche di frenata (punto di frenata, intensità, modulazione)
- Tecniche di accelerazione (gestione del throttle, trazione)
- Traiettorie ideali per le curve critiche
- Uso del differenziale e altre impostazioni che potrebbero aiutare

Sii preciso e utilizza la terminologia corretta di GT7.""",

        "lap_improvement": """Sei un coach di guida esperto di Gran Turismo 7, specializzato nel miglioramento dei tempi sul giro.

In base alle informazioni fornite, identifica:
1. Tecniche avanzate di guida specifiche per migliorare i tempi sul giro
2. Punti di riferimento visivi per ottimizzare le traiettorie
3. Tecniche di frenata e accelerazione per massimizzare la velocità
4. Come sfruttare al meglio le caratteristiche del circuito

Per ogni sezione del circuito, indica:
- Il punto ideale di frenata (con riferimenti visivi)
- La marcia ottimale per ogni curva
- Il punto di corda ideale
- La migliore tecnica di accelerazione in uscita

Considera le caratteristiche specifiche dell'auto (trazione, potenza, peso) per personalizzare i consigli.""",

        "tire_management": """Sei un esperto di gestione pneumatici in Gran Turismo 7, specializzato nel massimizzare le prestazioni
e la durata degli pneumatici durante le gare.

Fornisci consigli dettagliati su:
1. Come gestire il degrado degli pneumatici durante le gare lunghe
2. Tecniche di guida per minimizzare l'usura (specialmente in curve veloci)
3. Migliori impostazioni di pressione per diverse condizioni
4. Quando è ottimale effettuare un pit stop per cambio gomme

Considera i diversi tipi di pneumatici (Comfort, Sports, Racing, ecc.) e le loro caratteristiche specifiche.
Indica come cambia la strategia in base alle condizioni meteo e all'usura della pista.""",

        "fuel_strategy": """Sei un ingegnere strategico esperto di Gran Turismo 7, specializzato nell'ottimizzazione
del consumo di carburante durante le gare.

Fornisci strategie precise per:
1. Mappa motore ottimale per bilanciare velocità e consumo
2. Tecniche di guida per risparmiare carburante
3. Strategie di pit stop per rifornimenti
4. Calcolo autonomia e punti critici della gara

Considera la durata della gara, il consumo specifico dell'auto e le caratteristiche del circuito.
Personalizza i consigli in base al livello di difficoltà e obiettivi del giocatore."""
    }
    
    def __init__(
        self,
        model_path: str = "models/gemma-3-4b-it-Q4_K_M.gguf",
        n_ctx: int = 8192,  # Aumentato da 4096 a 8192
        n_threads: Optional[int] = None,
        n_batch: int = 512,
        verbose: bool = False
    ) -> None:
        """Initialize the GemmaLLM instance.
        
        Args:
            model_path: Path to the Gemma model file
            n_ctx: Context window size (increased to 8192 for better performance)
            n_threads: Number of threads to use (default: CPU count)
            n_batch: Batch size for inference
            verbose: Enable verbose logging
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_batch = n_batch
        self.n_threads = n_threads or multiprocessing.cpu_count()
        self.verbose = verbose
        self.model = None
        self.is_loaded = False
        
        # Lock for thread-safe model loading/unloading operations
        self.model_lock = threading.RLock()
        
        # Flag to track if model is currently in loading/unloading process
        self._loading_in_progress = False

        self.default_params = {
            "temperature": 0.2,
            "top_k": 128,
            "top_p": 0.75,
            "repeat_penalty": 1.5,
            "max_tokens": 1024
        }

        # Inizializza i componenti di supporto
        self.cache_manager = CacheManager()
        self.metrics_collector = MetricsCollector()
        self.feedback_system = FeedbackSystem()
        self.request_pool = RequestPoolManager()

        logger.info(f"GemmaLLM initialized with {self.n_threads} threads and context size {self.n_ctx}")
        logger.info(f"Model path set to: {self.model_path}")

    def load_model(self) -> bool:
        """Load the Gemma model into memory.
        
        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        # Use a lock to ensure thread-safe model loading
        with self.model_lock:
            # If model is already loaded, return immediately
            if self.is_loaded and self.model is not None:
                logger.info("Model already loaded and ready to use")
                return True
                
            # Prevent concurrent load attempts
            if self._loading_in_progress:
                logger.warning("Model loading already in progress in another thread, waiting...")
                return False
                
            # Set loading flag to prevent concurrent attempts
            self._loading_in_progress = True
            
            try:
                logger.info(f"Starting model loading process from {self.model_path}")
                
                # Validate model file existence
                if not os.path.exists(self.model_path):
                    logger.error(f"Model file not found at path: {self.model_path}")
                    return False
                    
                # Ensure any previous model is properly unloaded
                if self.model is not None:
                    logger.warning("Found existing model instance while loading. Cleaning up...")
                    self._cleanup_model_resources()
                
                # Initialize the model
                logger.info(f"Initializing Llama with n_threads={self.n_threads}, n_ctx={self.n_ctx}")
                self.model = Llama(
                    model_path=self.model_path,
                    n_threads=self.n_threads,
                    n_ctx=self.n_ctx,
                    verbose=self.verbose
                )
                
                # Verify model was properly initialized
                if self.model is None:
                    logger.error("Model initialization failed: Llama constructor returned None")
                    self.is_loaded = False
                    return False
                
                # Test model with a minimal inference to ensure it's functional
                try:
                    logger.debug("Testing model with minimal inference...")
                    test_response = self.model.create_chat_completion(
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=1
                    )
                    if not test_response:
                        logger.warning("Model test inference returned empty response, but continuing...")
                except Exception as test_e:
                    logger.error(f"Model test inference failed: {test_e}")
                    self._cleanup_model_resources()
                    return False
                
                # Update state only after successful initialization
                self.is_loaded = True
                logger.info(f"Model loaded successfully with context size {self.n_ctx} and {self.n_threads} threads")
                return True
                
            except ImportError as ie:
                logger.error(f"Import error loading model, llama-cpp-python may not be installed correctly: {ie}")
                self._cleanup_model_resources()
                return False
            except RuntimeError as re:
                logger.error(f"Runtime error loading model (possibly CUDA/GPU related): {re}")
                self._cleanup_model_resources()
                return False
            except Exception as e:
                logger.error(f"Unexpected error loading model: {e}", exc_info=True)
                self._cleanup_model_resources()
                return False
            finally:
                # Reset loading flag regardless of outcome
                self._loading_in_progress = False

    def _cleanup_model_resources(self) -> None:
        """Internal helper method to clean up model resources."""
        try:
            if self.model is not None:
                # Explicit cleanup if available
                if hasattr(self.model, 'reset'):
                    self.model.reset()
                
                # Delete the model object
                del self.model
                self.model = None
            
            # Force garbage collection to ensure memory is released
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during model resource cleanup: {e}", exc_info=True)
        finally:
            # Always ensure model state is consistent
            self.is_loaded = False
            
    def unload_model(self) -> bool:
        """Unload the model from memory and free resources.
        
        Returns:
            bool: True if unload was successful, False otherwise
        """
        # Use a lock to ensure thread-safe model unloading
        with self.model_lock:
            if not self.is_loaded and self.model is None:
                logger.debug("No model to unload, model was not loaded")
                return True
                
            logger.info("Starting model unloading process")
            
            # Perform actual resource cleanup
            self._cleanup_model_resources()
            
            # Check if unload was successful
            if self.model is not None:
                logger.error("Failed to fully unload model resources")
                return False
                
            logger.info("Model unloaded successfully, memory should be released")
            return True

    def check_model_state(self) -> bool:
        """Check and validate the model state.
        
        Returns:
            bool: True if model is in a valid state, False otherwise
        """
        with self.model_lock:
            # Check if state flags are consistent
            if self.is_loaded and self.model is None:
                logger.error("Inconsistent model state: is_loaded=True but model=None")
                self.is_loaded = False
                return False
                
            if not self.is_loaded and self.model is not None:
                logger.error("Inconsistent model state: is_loaded=False but model is not None")
                self._cleanup_model_resources()
                return False
                
            return self.is_loaded and self.model is not None
    
    def generate_response(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response using the loaded model.
        
        Args:
            prompt: Input prompt for the model
            **kwargs: Override default generation parameters
            
        Returns:
            str: Generated response or error message
        """
        if prompt is None or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            logger.error("Invalid empty prompt provided to generate_response")
            return "Errore: prompt vuoto o non valido."
            
        logger.debug(f"generate_response called with prompt length: {len(prompt)} chars")
        
        # First check model state with lock to prevent race conditions
        with self.model_lock:
            model_ready = self.check_model_state()
            
            # If model is not ready, try to load it
            if not model_ready:
                logger.info("Model not in ready state, attempting to load it now")
                if not self.load_model():
                    logger.error("Failed to load the model for response generation")
                    return "Errore: impossibile caricare il modello. Verifica che il file del modello esista e sia accessibile."
            
            # Double-check that model is properly initialized
            if not self.check_model_state():
                logger.error("Model state validation failed after loading attempt")
                return "Errore: stato del modello inconsistente. Riavvio del modello richiesto."

        # Aggiorna i parametri di default con valori ottimizzati
        self.default_params.update({
            "temperature": 0.2,
            "top_k": 128,
            "top_p": 0.75,
            "repeat_penalty": 1.5,
            "max_tokens": 2000  # Aumentato a 2000 per evitare troncamenti
        })

        params = {**self.default_params, **kwargs}
        logger.debug(f"Using generation parameters: {params}")

        messages = [
            {"role": "system", "content": self._get_general_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            logger.debug("Starting LLM inference...")
            start_time = time.time()
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=params["max_tokens"],
                temperature=params["temperature"],
                top_p=params["top_p"],
                top_k=params["top_k"],
                repeat_penalty=params["repeat_penalty"]
            )
            generation_time = time.time() - start_time
            
            # Validate response structure
            if not response or not isinstance(response, dict):
                logger.error(f"Invalid response format from LLM: {type(response)}")
                return "Errore: formato risposta non valido dal modello LLM."
                
            if "choices" not in response or not response["choices"]:
                logger.error(f"No choices in LLM response: {response}")
                return "Errore: nessuna scelta disponibile nella risposta del modello."
                
            if "message" not in response["choices"][0]:
                logger.error(f"No message in LLM response choice: {response['choices'][0]}")
                return "Errore: nessun messaggio nella risposta del modello."
                
            if "content" not in response["choices"][0]["message"]:
                logger.error(f"No content in LLM response message: {response['choices'][0]['message']}")
                return "Errore: nessun contenuto nel messaggio della risposta."
            
            # Extract content and validate it's a non-empty string
            content = response["choices"][0]["message"]["content"]
            
            # Detailed content logging
            logger.debug(f"Raw LLM response content type: {type(content)}")
            if isinstance(content, str):
                preview = content[:100] + "..." if len(content) > 100 else content
                logger.debug(f"LLM response content preview: {preview}")
                logger.debug(f"LLM response content length: {len(content)} characters")
            
            if not isinstance(content, str):
                logger.warning(f"Non-string content in LLM response, type: {type(content)}")
                content = str(content) if content is not None else ""
                logger.debug(f"Converted content to string, new length: {len(content)}")
                
            if not content.strip():
                logger.warning("Empty content in LLM response")
                return "Errore: risposta vuota dal modello LLM."
            
            # Log successful generation
            logger.info(f"LLM response generated successfully in {generation_time:.2f}s, length: {len(content)} chars")
            return content

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return f"Errore nella generazione della risposta: {e}"

    def suggest_car_setup(
        self, 
        car_data: Dict[str, Any], 
        track_data: Dict[str, Any], 
        telemetry_data: Optional[Dict[str, Any]] = None,
        feedback_pilota: str = ""
    ) -> str:
        """Suggest optimal car setup based on provided data.
        
        Args:
            car_data: Dictionary containing car information and current setup
            track_data: Dictionary containing track information
            telemetry_data: Optional telemetry data to inform setup recommendations
            feedback_pilota: Optional feedback from the driver
            
        Returns:
            str: Detailed car setup recommendations
        """
        # Debug logging the input parameters
        logger.debug(f"suggest_car_setup called with car_data: {type(car_data)}, track_data: {type(track_data)}")
        logger.debug(f"Car name: {car_data.get('name', 'unknown')}, Track: {track_data.get('name', 'unknown')}")
        
        if telemetry_data:
            logger.debug(f"Telemetry data provided, keys: {list(telemetry_data.keys())}")
        if feedback_pilota:
            logger.debug(f"Feedback pilota provided, length: {len(feedback_pilota)}")
        
        # Check if model is loaded and initialize if needed
        if not self.is_loaded or self.model is None:
            logger.info("Model not loaded for car setup suggestion, attempting to load it now")
            if not self.load_model():
                logger.error("Failed to load the model for car setup suggestion")
                return "Errore: impossibile caricare il modello per suggerimenti di setup. Verifica che il file del modello esista e sia accessibile."

        # Validate input data
        if not isinstance(car_data, dict) or not car_data:
            logger.error("Invalid or empty car_data provided to suggest_car_setup")
            return "Errore: dati auto non validi o mancanti."
            
        if not isinstance(track_data, dict) or not track_data:
            logger.error("Invalid or empty track_data provided to suggest_car_setup")
            return "Errore: dati circuito non validi o mancanti."

        try:
            auto_nome = car_data.get("name", "Auto sconosciuta")
            circuito = track_data.get("name", "Circuito sconosciuto")
            
            logger.info(f"Generating car setup for {auto_nome} on {circuito}")
            
            # Extract and validate parameters
            gomme = car_data.get("setup", {}).get("tipo_gomme", "Sconosciute")
            car_id = car_data.get("car_id", "")
            
            # Log input data summary
            logger.debug(f"Car setup request - Car: {auto_nome}, Track: {circuito}, Tires: {gomme}, Car ID: {car_id}")
            if feedback_pilota:
                logger.debug(f"Driver feedback provided, length: {len(feedback_pilota)} chars")
            
            # Format the prompt
            prompt = self._format_car_setup_prompt(
                auto_nome=auto_nome,
                circuito=circuito,
                gomme=gomme,
                car_id=car_id,
                dati_telemetria=telemetry_data or {},
                feedback_pilota=feedback_pilota
            )
            
            logger.debug(f"Car setup prompt generated, length: {len(prompt)} chars")
            logger.debug(f"Car setup prompt generated, length: {len(prompt)} chars")
            
            # Generate and validate response
            logger.info("Calling generate_response for car setup suggestion")
            response = self.generate_response(prompt)
            
            # Detailed response validation and logging
            logger.debug(f"Response received from generate_response, type: {type(response)}")
            
            if response is None:
                logger.error("Null response received from generate_response")
                return "Errore: risposta nulla dal modello LLM."
            
            if not isinstance(response, str):
                logger.error(f"Non-string response received from generate_response: {type(response)}")
                try:
                    response = str(response)
                    logger.debug(f"Converted response to string, length: {len(response)}")
                except:
                    logger.error("Failed to convert response to string")
                    return "Errore: impossibile convertire la risposta in testo."
            
            # Log response preview and length for debugging
            if isinstance(response, str):
                preview = response[:100] + "..." if len(response) > 100 else response
                logger.debug(f"Response preview: {preview}")
                logger.debug(f"Response length: {len(response)} characters")
            
            # Validate response content
            if not response or not response.strip():
                logger.error("Empty or whitespace-only response received from generate_response")
                return "Errore: impossibile generare suggerimenti validi per il setup."
                
            # Check if response contains error message
            if response.startswith("Errore:"):
                logger.error(f"Error response from generate_response: {response}")
                return response
                
            # Log successful response
            logger.info(f"Successfully generated car setup suggestion, length: {len(response)} characters")
            return response
        except Exception as e:
            logger.error(f"Error in car setup suggestion: {e}", exc_info=True)
            return f"Errore nella generazione del setup: {e}"
            
    def analyze_telemetry(
        self, car_name: str, track_name: str, telemetry_data: Dict[str, Any], lap_times: List[float]
    ) -> str:
        """Analyze telemetry data and provide insights.
        
        Args:
            car_name: Name of the car
            track_name: Name of the track
            telemetry_data: Dictionary containing telemetry metrics 
            lap_times: List of lap times in seconds
            
        Returns:
            str: Analysis and recommendations
        """
        try:
            # Validate input parameters
            if not car_name or not track_name:
                logger.error("Invalid car_name or track_name provided")
                return "Error: Missing car or track information"
                
            if not telemetry_data or not isinstance(telemetry_data, dict):
                logger.error("Invalid telemetry_data provided")
                return "Error: Invalid telemetry data format"
                
            if not lap_times or not isinstance(lap_times, list):
                logger.error("Invalid lap_times provided")
                return "Error: Invalid lap times data"
            
            # Format telemetry analysis prompt
            prompt = self._format_telemetry_analysis_prompt(
                car_name=car_name,
                track_name=track_name,
                telemetry_data=telemetry_data,
                lap_times=lap_times
            )
            
            # Generate analysis using the LLM
            return self.generate_response(prompt)
            
        except Exception as e:
            logger.error(f"Error in telemetry analysis: {e}")
            return f"Error analyzing telemetry data: {str(e)}"

    def _get_general_system_prompt(self) -> str:
        """Return the system prompt for general GT7 queries.
        
        Returns:
            str: System prompt setting context for the model
        """
        return self.PROMPT_TEMPLATES["general"]

    def format_system_prompt(self) -> str:
        """Format the system prompt for GT7 Guru Assistant.
        
        Returns:
            str: System prompt setting context"""
        return """Sei l'assistente GT7 Guru, un esperto di Gran Turismo 7, il simulatore di guida per PlayStation.
        Il tuo compito è aiutare i giocatori a migliorare le loro prestazioni in pista, ottimizzare i setup delle auto,
        e fornire consigli strategici basati sui dati telemetrici e sulle caratteristiche del circuito.

        Rispondi sempre in italiano, usando termini tecnici appropriati ma comprensibili.
        Quando analizzi dati telemetrici o suggerisci modifiche al setup, spiega sempre il motivo
        delle tue raccomandazioni e come queste influenzeranno il comportamento dell'auto in pista.

        Se non hai informazioni sufficienti per dare una risposta precisa, chiedi dettagli aggiuntivi
        invece di fare supposizioni non fondate."""

    def format_tire_management_prompt(self, tire_data: Dict[str, Any], lap_count: int) -> str:
        """Format prompt for tire management strategy.
        
        Args:
            tire_data: Dictionary with tire wear and temperature data
            lap_count: Number of laps in the race
            
        Returns:
            str: Formatted prompt"""
        base_prompt = self.PROMPT_TEMPLATES["tire_management"]
        formatted_data = "\n".join(f"- {k}: {v}" for k,v in tire_data.items())
        
        return f"{base_prompt}\n\nDati pneumatici attuali:\n{formatted_data}\n\nLunghezza gara: {lap_count} giri\n\nAnalizza questi dati specifici e fornisci una strategia personalizzata per questo caso."

    def format_fuel_strategy_prompt(self, fuel_data: Dict[str, Any], race_length: int) -> str:
        """Format prompt for fuel strategy.
        
        Args:
            fuel_data: Dictionary with fuel consumption data
            race_length: Race length in minutes or laps
            
        Returns:
            str: Formatted prompt"""
        base_prompt = self.PROMPT_TEMPLATES["fuel_strategy"]
        formatted_data = "\n".join(f"- {k}: {v}" for k, v in fuel_data.items())
        
        return f"{base_prompt}\n\nDati carburante attuali:\n{formatted_data}\n\nLunghezza gara: {race_length} giri/minuti\n\nAnalizza questi dati specifici e fornisci una strategia personalizzata per questo caso."
    def _format_telemetry_analysis_prompt(
        self,
        car_name: str,
        track_name: str,
        telemetry_data: Dict[str, Any],
        lap_times: List[float]
    ) -> str:
        """Format telemetry data into a prompt for analysis.
        
        Args:
            car_name: Name of the car
            track_name: Name of the track
            telemetry_data: Dictionary containing telemetry metrics
            lap_times: List of lap times in seconds
            
        Returns:
            str: Formatted prompt for telemetry analysis
        """
        base_prompt = self.PROMPT_TEMPLATES["telemetry"]
        sections = []
        
        # Velocità
        speed_metrics = [
            ("Velocità massima", telemetry_data.get("max_speed", "N/A")),
            ("Velocità media", telemetry_data.get("avg_speed", "N/A")),
            ("Velocità minima", telemetry_data.get("min_speed", "N/A"))
        ]
        sections.append("VELOCITÀ:\n" + "\n".join([f"- {k}: {v}" for k, v in speed_metrics]))
        
        # Tempi
        time_metrics = [
            ("Tempo sul giro", telemetry_data.get("lap_time", "N/A")),
            ("Tempo settore 1", telemetry_data.get("sector1_time", "N/A")),
            ("Tempo settore 2", telemetry_data.get("sector2_time", "N/A")),
            ("Tempo settore 3", telemetry_data.get("sector3_time", "N/A"))
        ]
        sections.append("TEMPI:\n" + "\n".join([f"- {k}: {v}" for k, v in time_metrics]))
        
        # Dinamica
        dynamic_metrics = [
            ("Accelerazione laterale max", telemetry_data.get("max_lateral_g", "N/A")),
            ("Accelerazione longitudinale max", telemetry_data.get("max_accel_g", "N/A")),
            ("Decelerazione max", telemetry_data.get("max_brake_g", "N/A")),
            ("Bilanciamento sottosterzo/sovrasterzo", telemetry_data.get("balance", "N/A"))
        ]
        sections.append("DINAMICA:\n" + "\n".join([f"- {k}: {v}" for k, v in dynamic_metrics]))
        
        # Input guidatore
        input_metrics = [
            ("Uso medio acceleratore", telemetry_data.get("avg_throttle", "N/A")),
            ("Uso medio freno", telemetry_data.get("avg_brake", "N/A")),
            ("Cambi marcia per giro", telemetry_data.get("gear_changes", "N/A"))
        ]
        sections.append("INPUT GUIDATORE:\n" + "\n".join([f"- {k}: {v}" for k, v in input_metrics]))
        
        # Format all times
        times_str = "\n".join([f"- Giro {i + 1}: {lt:.3f}s" for i, lt in enumerate(lap_times)])
        
        join_str = "\n\n"
        sections_text = join_str.join(sections)
        return f"{base_prompt}\n\nAnalisi telemetria per {car_name} su {track_name}:\n\n{sections_text}\n\nTEMPI SUL GIRO:\n{times_str}\n\nAnalizza questi dati specifici e fornisci indicazioni dettagliate personalizzate per questo caso."
    def _format_car_setup_prompt(
        self,
        auto_nome: str,
        circuito: str,
        gomme: str,
        car_id: str,
        dati_telemetria: dict = None,
        feedback_pilota: str = ""
    ) -> str:
        """
        Formato aggiornato del prompt per setup auto che utilizza i parametri categorizzati.
        """
        # Ottieni i parametri strutturati per il LLM con gestione errori
        try:
            params = get_car_parameters_for_llm(car_id)
            if not params:
                logger.warning(f"Nessun parametro trovato per car_id: {car_id}")
                params = {
                    "Base": {},
                    "Sospensioni": {},
                    "Aerodinamica": {},
                    "Differenziale": {},
                    "Freni": {},
                    "Trasmissione": {},
                    "Altri": {}
                }
        except Exception as e:
            logger.error(f"Errore nel recupero dei parametri auto: {e}")
            params = {
                "Base": {},
                "Sospensioni": {},
                "Aerodinamica": {},
                "Differenziale": {},
                "Freni": {},
                "Trasmissione": {},
                "Altri": {}
            }
        
        # Ottieni i parametri base con gestione valori nulli
        base_params = params.get("Base", {})
        peso = base_params.get("peso", {}).get("value", "N/D")
        potenza = base_params.get("potenza", {}).get("value", "N/D")
        trazione = base_params.get("trazione", {}).get("value", "N/D")
        
        # Formatta ogni categoria di parametri
        formatted_sections = []
        
        for categoria, parametri in params.items():
            if parametri:  # Se ci sono parametri in questa categoria
                section = f"\n{categoria.upper()}:\n"
                for nome, dati in parametri.items():
                    value = dati.get("value")
                    min_val = dati.get("min_value")
                    max_val = dati.get("max_value")
                    unit = dati.get("unit", "")
                    
                    # Formatta il valore con i limiti se disponibili - evidenziando i limiti come requisiti obbligatori
                    value_str = f"{value}{unit}" if value is not None else "N/D"
                    limits_str = ""
                    if min_val is not None or max_val is not None:
                        limits = []
                        if min_val is not None:
                            limits.append(f"min: {min_val}{unit}")
                        if max_val is not None:
                            limits.append(f"max: {max_val}{unit}")
                        if limits:
                            # Aggiungi informazioni aggiuntive sulle unità di misura e incrementi per parametri specifici
                            additional_info = ""
                            if "barra antirollio" in nome.lower():
                                additional_info = ", SOLO livelli da 1 a 10 con incrementi di 1"
                            elif "frequenza naturale" in nome.lower():
                                additional_info = ", valori con precisione fino a 2 decimali (incrementi di 0.01)"
                            elif "campanatura" in nome.lower():
                                additional_info = ", gradi (°) con precisione fino a 1 decimale (incrementi di 0.1)"
                            elif "convergenza" in nome.lower() or "divergenza" in nome.lower():
                                additional_info = ", gradi (°) con precisione fino a 2 decimali (incrementi di 0.01)"
                            elif "deportanza" in nome.lower():
                                additional_info = ", livello numerico (non millimetri)"
                            
                            limits_str = f" [LIMITE OBBLIGATORIO: {', '.join(limits)}{additional_info}]"
                    
                    section += f"- {nome}: {value_str}{limits_str}\n"
                formatted_sections.append(section)

        # Formatta i dati telemetrici se disponibili
        telemetry_section = ""
        if dati_telemetria:
            telemetry_section = "\nDATI TELEMETRICI:\n"
            for key, value in dati_telemetria.items():
                telemetry_section += f"- {key}: {value}\n"

        # Ottieni il prompt base dal template
        base_prompt = self.PROMPT_TEMPLATES["car_setup"]

        # Costruisci il prompt completo
        setup_info = "\n".join(formatted_sections)
        
        try:
            rapporto_peso_potenza = peso/potenza if (isinstance(peso, (int, float)) and isinstance(potenza, (int, float)) and potenza > 0) else "N/D"
        except:
            rapporto_peso_potenza = "N/D"
        
        return f"""{base_prompt}

        DATI AUTO:
        Circuito: {circuito}
        Auto: {auto_nome}
        Gomme: {gomme}
        Peso: {peso} kg
        Potenza: {potenza} CV
        Rapporto peso/potenza: {rapporto_peso_potenza} kg/CV
        Trazione: {trazione}

        SETUP ATTUALE:
        {setup_info}
        {telemetry_section}

        FEEDBACK PILOTA:
        {feedback_pilota if feedback_pilota else 'Nessun feedback specifico fornito.'}

        Analizza questi dati specifici e fornisci un setup ottimizzato con valori precisi per ogni parametro.
        Spiega brevemente il motivo di ciascuna scelta e come influenzerà il comportamento dell'auto.
        
        !!! ATTENZIONE !!!
        DEVI RISPETTARE RIGOROSAMENTE:
        1. I LIMITI MIN/MAX DI CIASCUN PARAMETRO
        2. LE UNITÀ DI MISURA SPECIFICATE PER OGNI PARAMETRO
        3. LA PRECISIONE DECIMALE INDICATA PER OGNI PARAMETRO:
           - Barre antirollio: SOLO livelli interi da 1 a 10 (incrementi di 1)
           - Frequenza naturale: valori con precisione fino a 2 decimali (incrementi di 0.01)
           - Campanatura: gradi (°) con precisione fino a 1 decimale (incrementi di 0.1)
           - Convergenza: gradi (°) con precisione fino a 2 decimali (incrementi di 0.01)
           - Deportanza: livello numerico (non millimetri)
        
        QUALSIASI VALORE FUORI DAI LIMITI SPECIFICATI O CON FORMATO NON CORRETTO RENDERÀ L'INTERO SETUP INUTILIZZABILE.
        I LIMITI E I FORMATI INDICATI SONO REQUISITI TECNICI INDEROGABILI, NON SEMPLICI LINEE GUIDA.
        """
    def format_performance_improvement_prompt(
        self, 
        car_name: str,
        track_name: str,
        telemetry_data: Dict[str, Any],
        lap_issues: List[str]
    ) -> str:
        """Format prompt for performance improvement analysis.
        
        Args:
            car_name: Name of the car
            track_name: Name of the track
            telemetry_data: Telemetry data dictionary
            lap_issues: List of identified issues
            
        Returns:
            str: Formatted prompt"""
        sector_times = telemetry_data.get("sector_times", ["--", "--", "--"])
        lap_time = telemetry_data.get("best_lap_time", "tempo sconosciuto")
        
        issues_str = "\n".join([f"- {issue}" for issue in lap_issues]) if lap_issues else "- Nessun problema specifico identificato"
        
        return f"""Analizza le prestazioni e fornisci consigli per migliorare i tempi sul giro:

DETTAGLI PRESTAZIONI:
- Auto: {car_name}
- Circuito: {track_name}
- Miglior tempo sul giro: {lap_time}
- Tempi di settore: S1: {sector_times[0]}, S2: {sector_times[1]}, S3: {sector_times[2]}

PROBLEMI IDENTIFICATI:
{issues_str}

Fornisci consigli dettagliati per:
1. Migliorare i tempi nei settori più lenti
2. Correggere i problemi di guida identificati
3. Ottimizzare le traiettorie e i punti di frenata
4. Tecniche di guida avanzate specifiche per questo circuito

Concentrati sui consigli pratici che il pilota può applicare immediatamente per migliorare i tempi sul giro."""

    def format_track_specific_prompt(
        self,
        track_name: str,
        track_conditions: Dict[str, Any],
        car_characteristics: Dict[str, Any]
    ) -> str:
        """Format prompt for track-specific advice.
        
        Args:
            track_name: Name of the track
            track_conditions: Current track conditions
            car_characteristics: Car specifications and handling characteristics
            
        Returns:
            str: Formatted prompt"""
        conditions_str = "\n".join([f"- {k}: {v}" for k, v in track_conditions.items()])
        car_str = "\n".join([f"- {k}: {v}" for k, v in car_characteristics.items()])
        
        return f"Sono alla guida sul circuito {track_name}.\n\nCONDIZIONI ATTUALI:\n{conditions_str}\n\nCARATTERISTICHE AUTO:\n{car_str}\n\nFornisci consigli specifici su:\n1. Punti di frenata ottimali per ogni curva principale\n2. Traiettorie ideali considerando le caratteristiche dell'auto\n3. Gear selection per ogni sezione del tracciato\n4. Aree critiche dove prestare particolare attenzione\n5. Tecniche specifiche per sfruttare al meglio le caratteristiche del circuito\n\nOrganizza la risposta sezione per sezione del tracciato."

    def analyze_race_performance(
        self,
        car_name: str,
        track_name: str,
        telemetry_data: Dict[str, Any],
        lap_issues: List[str],
        **kwargs
    ) -> str:
        """Analyze race performance and provide improvement suggestions.
        
        Args:
            car_name: Name of the car
            track_name: Name of the track
            telemetry_data: Telemetry data dictionary
            lap_issues: List of identified issues
            **kwargs: Additional parameters for generation
            
        Returns:
            str: Performance analysis and suggestions"""
        prompt = self.format_performance_improvement_prompt(
            car_name=car_name,
            track_name=track_name,
            telemetry_data=telemetry_data,
            lap_issues=lap_issues
        )
        return self.generate_response_with_cache(prompt, **kwargs)
    def format_lap_improvement_prompt(
        self,
        car_name: str,
        track_name: str,
        lap_data: Dict[str, Any],
        target_time: Optional[float] = None
    ) -> str:
        """Format prompt for lap time improvement analysis.
        
        Args:
            car_name: Name of the car
            track_name: Name of the track
            lap_data: Dictionary with lap time and sector data
            target_time: Optional target lap time to achieve
            
        Returns:
            str: Formatted prompt for lap improvement
        """
        base_prompt = self.PROMPT_TEMPLATES["lap_improvement"]
        
        # Format lap data
        lap_data_str = "\n".join([f"- {k}: {v}" for k, v in lap_data.items()])
        
        # Add target time info if provided
        target_info = f"\nTempo target da raggiungere: {target_time:.3f}s" if target_time else ""
        
        return f"{base_prompt}\n\nAUTO: {car_name}\nCIRCUITO: {track_name}\n\nDATI ATTUALI:\n{lap_data_str}{target_info}\n\nFornisci consigli specifici per migliorare il tempo sul giro, considerando le caratteristiche di questa auto e di questo circuito specifico."
    def get_track_specific_advice(
        self,
        track_name: str,
        track_conditions: Dict[str, Any],
        car_characteristics: Dict[str, Any],
        **kwargs
    ) -> str:
        """Get track-specific driving advice.
        
        Args:
            track_name: Name of the track
            track_conditions: Current track conditions
            car_characteristics: Car specifications
            **kwargs: Additional parameters for generation
            
        Returns:
            str: Track-specific driving advice"""
        prompt = self.format_track_specific_prompt(
            track_name=track_name,
            track_conditions=track_conditions,
            car_characteristics=car_characteristics
        )
        return self.generate_response_with_cache(prompt, **kwargs)

    def get_tire_strategy(
        self,
        tire_data: Dict[str, Any],
        lap_count: int,
        **kwargs
    ) -> str:
        """Get tire management strategy for a race.
        
        Args:
            tire_data: Dictionary with tire wear and temperature data
            lap_count: Number of laps in the race
            **kwargs: Additional parameters for generation
            
        Returns:
            str: Tire management strategy"""
        prompt = self.format_tire_management_prompt(
            tire_data=tire_data,
            lap_count=lap_count
        )
        return self.generate_response_with_cache(prompt, **kwargs)

    def get_fuel_strategy(
        self,
        fuel_data: Dict[str, Any],
        race_length: int,
        **kwargs
    ) -> str:
        """Get fuel management strategy for a race.
        
        Args:
            fuel_data: Dictionary with fuel consumption data
            race_length: Race length in minutes or laps
            **kwargs: Additional parameters for generation
            
        Returns:
            str: Fuel management strategy"""
        prompt = self.format_fuel_strategy_prompt(
            fuel_data=fuel_data,
            race_length=race_length
        )
        return self.generate_response_with_cache(prompt, **kwargs)

    def submit_request(self, prompt: str, priority: int = 1, callback=None) -> str:
        """Sottomette una richiesta al pool con priorità.
        
        Args:
            prompt: Il prompt da elaborare
            priority: Priorità della richiesta (1=alta, 5=bassa)
            callback: Funzione da chiamare al completamento
            
        Returns:
            str: ID univoco della richiesta
        """
        request = LLMRequest(prompt, priority=priority, callback=callback)
        return self.request_pool.submit_request(request)

    def get_request_status(self, request_id: str) -> Dict:
        """Ottiene lo stato di una richiesta.
        
        Args:
            request_id: ID della richiesta
            
        Returns:
            Dict: Stato della richiesta contenente:
                - status: stato attuale ('active' o 'not_found')
                - request: oggetto richiesta se attiva
                - result: risultato se disponibile
        """
        return self.request_pool.get_request_status(request_id)

    def add_feedback(self, prompt_id: str, response: str, rating: int, feedback: str = None) -> None:
        """Aggiunge feedback per migliorare la qualità delle risposte.
        
        Args:
            prompt_id: ID del prompt
            response: Risposta generata
            rating: Valutazione da 1 a 5
            feedback: Commento opzionale
        """
        self.feedback_system.rate_response(prompt_id, response, rating, feedback)

    def get_metrics(self) -> Dict:
        """Ottiene le metriche di performance del modello.
        
        Returns:
            Dict: Statistiche contenenti:
                - count: numero totale richieste
                - avg_tokens: media token per richiesta
                - avg_gen_time: tempo medio generazione
                - avg_tokens_per_second: velocità generazione
        """
        return self.metrics_collector.get_stats()

    def generate_response_with_cache(self, prompt: str, **kwargs) -> str:
        """Genera una risposta usando la cache quando possibile.

        Args:
            prompt: Il prompt da elaborare
            **kwargs: Parametri addizionali per generate_response

        Returns:
            str: Risposta generata o recuperata dalla cache
        """
        # Check if model is loaded
        if not self.is_loaded and not self.load_model():
            logger.error("Model not loaded and failed to load for cached response")
            return "Errore: impossibile caricare il modello per la generazione della risposta."

        # Check cache first
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        cached = self.cache_manager.get(cache_key)
        if cached:
            logger.info(f"Cache hit for prompt with key {cache_key[:8]}...")
            return cached["response"]
        
        logger.info(f"Cache miss, generating new response for prompt with key {cache_key[:8]}...")
        
        # Generate new response
        start_time = time.time()
        response = self.generate_response(prompt, **kwargs)
        
        # Add to cache and collect metrics
        self.cache_manager.set(cache_key, {"response": response, "timestamp": time.time()})
        self.metrics_collector.add_metrics(PerformanceMetrics(
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
            total_tokens=len(prompt.split()) + len(response.split()),
            generation_time=time.time() - start_time,
            tokens_per_second=len(response.split()) / (time.time() - start_time),
            request_timestamp=time.time()
        ))
        
        return response

# Test di base per verificare il funzionamento
if __name__ == "__main__":
    llm = GemmaLLM(verbose=True)
    if llm.load_model():
        try:
            # Test base
            print("\n=== Test generazione risposta base ===")
            response = llm.generate_response("Come migliorare il sottosterzo della mia auto?")
            print(response)
            
            # Test con cache
            print("\n=== Test generazione risposta con cache ===")
            cached_response = llm.generate_response_with_cache("Come migliorare il sottosterzo della mia auto?")
            print("Risposta dalla cache:", cached_response)
            
            # Test richiesta asincrona
            print("\n=== Test richiesta asincrona ===")
            def callback(request, result):
                print(f"Richiesta {request.id} completata:", result)
                
            request_id = llm.submit_request(
                "Quali sono le migliori auto per gare di endurance?",
                priority=1,
                callback=callback
            )
            print(f"Richiesta sottomessa con ID: {request_id}")
            
            # Test metriche
            print("\n=== Test metriche ===")
            metrics = llm.get_metrics()
            print("Metriche di performance:", metrics)
            
            # Test delle nuove funzionalità
            print("\n=== Test analisi prestazioni ===")
            perf_analysis = llm.analyze_race_performance(
                car_name="Porsche 911 GT3 RS",
                track_name="Nürburgring GP",
                telemetry_data={
                    "best_lap_time": "1:59.234",
                    "sector_times": ["39.123", "42.456", "37.655"],
                    "max_speed": 285.4,
                    "avg_speed": 168.2
                },
                lap_issues=[
                    "Sottosterzo in curva 1",
                    "Frenata tardiva alla chicane"
                ]
            )
            print(perf_analysis)

            print("\n=== Test strategia gomme ===")
            tire_strategy = llm.get_tire_strategy(
                tire_data={
                    "front_left_wear": 82,
                    "front_right_wear": 85,
                    "rear_left_wear": 78,
                    "rear_right_wear": 80,
                    "compound": "Racing Medium"
                },
                lap_count=30
            )
            print(tire_strategy)
            
        except Exception as e:
            print(f"Errore durante i test: {e}")
        finally:
            llm.unload_model()
    else:
        logger.error("Failed to load model for testing")
