import torch
import logging
import sys
import os
import traceback
import gc
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, StoppingCriteriaList
class FalconLLM:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG, 
                           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                           handlers=[
                               logging.StreamHandler(sys.stdout),
                               logging.FileHandler('falcon_llm.log')
                           ])
        self.logger = logging.getLogger(__name__)
        self.logger.info("Inizializzazione FalconLLM...")
        self.logger.debug(f"Python Version: {sys.version}")
        self.logger.debug(f"Working Directory: {os.getcwd()}")
        
        # Log CUDA/GPU information if available
        try:
            self.logger.debug(f"CUDA Available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                self.logger.debug(f"CUDA Version: {torch.version.cuda}")
                self.logger.debug(f"GPU Device: {torch.cuda.get_device_name(0)}")
                self.logger.debug(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
                self.logger.debug(f"Current Memory Usage: {torch.cuda.memory_allocated(0) / 1e9:.2f} GB")
        except Exception as e:
            self.logger.debug(f"Error checking CUDA info: {str(e)}")
        
        self.model_id = "tiiuae/falcon-7b-instruct"
        
        # Check if CUDA is available
        self.use_cuda = torch.cuda.is_available()
        self.logger.info(f"Using CUDA: {self.use_cuda}")
        
        # Configure based on device availability
        if self.use_cuda:
            # Configurazione quantizzazione 4-bit for CUDA
            self.logger.info("Setting up 4-bit quantization for CUDA")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            device_map = "auto"
        else:
            # CPU configuration
            self.logger.info("Setting up CPU-only mode (no 4-bit quantization)")
            quantization_config = None
            device_map = "cpu"
        
        self.logger.debug(f"Attempting to load tokenizer from {self.model_id}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self.logger.info("Tokenizer caricato")
            self.logger.debug(f"Tokenizer config: {self.tokenizer.init_kwargs}")
        except Exception as e:
            self.logger.error(f"Failed to load tokenizer: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise
        
        # Log memory status before loading model
        self.logger.debug("Memory status before loading model:")
        if torch.cuda.is_available():
            self.logger.debug(f"CUDA Memory Allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
            self.logger.debug(f"CUDA Memory Reserved: {torch.cuda.memory_reserved() / 1e9:.2f} GB")
        
        if self.use_cuda:
            self.logger.debug(f"Attempting to load model from {self.model_id} with 4-bit quantization")
            self.logger.debug(f"Quantization config: {quantization_config}")
        else:
            self.logger.debug(f"Attempting to load model from {self.model_id} in CPU-only mode")
        self.logger.debug(f"Device map: {device_map}, Using official Hugging Face implementation (integrated in transformers)")
        
        # Clear memory before loading model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            self.logger.debug(f"Cleared CUDA cache. Available: {torch.cuda.memory_allocated() / 1e9:.2f} GB used")
        
        # Strategies for loading the model with fallback
        if self.use_cuda:
            # Strategy 1: Optimal GPU loading with 4-bit quantization
            try:
                self.logger.info("Tentativo 1: Caricamento ottimale su GPU con quantizzazione 4-bit")
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    quantization_config=quantization_config,
                    device_map="auto"
                )
                self.logger.info("Caricamento ottimale su GPU riuscito!")
            except Exception as e:
                self.logger.warning(f"Fallito il caricamento ottimale su GPU: {str(e)}")
                gc.collect()
                torch.cuda.empty_cache()
                
                # Strategy 2: GPU with CPU offload for memory-intensive parts
                if "CUDA out of memory" in str(e) or "cannot be allocated" in str(e):
                    try:
                        self.logger.info("Tentativo 2: Caricamento con offload CPU-GPU")
                        quantization_config = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_compute_dtype=torch.float16,
                            bnb_4bit_use_double_quant=True,
                            bnb_4bit_quant_type="nf4"
                        )
                        # Custom device map to offload memory-intensive layers to CPU
                        device_map = {
                            "transformer.word_embeddings": "cpu",
                            "transformer.h": "auto",  # Distribuisce i layer tra CPU e GPU
                            "transformer.ln_f": "gpu",
                            "lm_head": "cpu"
                        }
                        self.model = AutoModelForCausalLM.from_pretrained(
                            self.model_id,
                            quantization_config=quantization_config,
                            device_map=device_map
                        )
                        self.logger.info("Caricamento con offload CPU-GPU riuscito!")
                    except Exception as e2:
                        self.logger.warning(f"Fallito anche il caricamento con offload CPU-GPU: {str(e2)}")
                        gc.collect()
                        torch.cuda.empty_cache()
                        
                        # Strategy 3: CPU-only as last resort
                        self.logger.info("Tentativo 3: Caricamento su CPU come ultima risorsa")
                        self.use_cuda = False  # Override to CPU mode
                        self._load_on_cpu()
                else:
                    # If the error is not related to memory, try CPU directly
                    self.logger.info("Passaggio a caricamento su CPU a causa di errori non relativi alla memoria")
                    self.use_cuda = False  # Override to CPU mode
                    self._load_on_cpu()
        else:
            # Direct CPU loading if CUDA is not available
            self.logger.info("Caricamento diretto su CPU (CUDA non disponibile)")
            self._load_on_cpu()
            
        # Log successful loading with details
        self.logger.info("Modello caricato con successo")
        self.logger.debug(f"Model loaded to device: {self.model.device}")
        self.logger.debug(f"Model dtype: {self.model.dtype}")
        if torch.cuda.is_available():
            self.logger.debug(f"CUDA Memory After Loading: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
            
    def _load_on_cpu(self):
        """Helper method to load the model on CPU with optimizations"""
        try:
            self.logger.debug("Caricamento modello su CPU con ottimizzazioni di memoria")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=torch.float32,  # Use float32 for CPU
                low_cpu_mem_usage=True,     # Enable memory optimization for CPU
                device_map="cpu"
            )
            self.logger.info("Caricamento su CPU completato")
        except Exception as e:
            self.logger.error(f"Errore critico nel caricamento del modello su CPU: {str(e)}")
            self.logger.debug(f"Detailed error: {traceback.format_exc()}")
            
            # Provide context about the error
            if "401 Client Error" in str(e):
                self.logger.error("Authentication error accessing model. Check your Hugging Face credentials.")
            elif "Connection error" in str(e):
                self.logger.error("Network error. Check your internet connection.")
            
            raise

    def generate_response(self, config_data, telemetry_data):
        try:
            # Formattazione dei dati telemetrici in modo più chiaro e strutturato
            formatted_telemetry = ""
            if isinstance(telemetry_data, dict):
                for key, value in telemetry_data.items():
                    formatted_telemetry += f"    - {key}: {value}\n"
            else:
                formatted_telemetry = str(telemetry_data)
            
            prompt = f"""Sei un esperto di assetto vetture da corsa per Gran Turismo 7. Analizza questi dati e fornisci consigli tecnici precisi.

Veicolo: {config_data.get("modello_veicolo", "N/A")}
Circuito: {config_data.get("nome_circuito", "N/A")}
Gomme: {config_data.get("tipo_gomme", "N/A")}
            
Telemetria:
{formatted_telemetry}

Fornisci una lista numerata con valori numerici specifici per:
1. Setup sospensioni (rigidità, altezza, smorzamento)
2. Aerodinamica (carico anteriore/posteriore)
3. Pneumatici (pressione, convergenza, camber)
4. Tecniche di guida per questo circuito
5. Differenziale (accelerazione/decelerazione)
"""

            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
            self.logger.info("Generazione risposta...")
            self.logger.debug(f"Input token length: {inputs['input_ids'].shape[1]}")
            # Move inputs to the correct device
            if self.use_cuda:
                input_ids = inputs['input_ids'].to('cuda')
                attention_mask = inputs['attention_mask'].to('cuda')
            else:
                input_ids = inputs['input_ids']
                attention_mask = inputs['attention_mask']
                
            # Stop words per evitare generazione di codice e HTML
            stop_words = ["```", "<html>", "<code>", "<?php", "<!DOCTYPE", "<script", "function", "def ", "class ", "#include"]
            stop_token_ids = [self.tokenizer.encode(word, add_special_tokens=False)[0] for word in stop_words]
            
            # Bad words per evitare caratteri speciali e markup
            bad_chars = ["<", ">", "/", "=", "{", "}", "[", "]", "\\", "|", "@", "$", "&", "*", ";", "<!--", "-->"]
            bad_words_ids = [self.tokenizer.encode(char, add_special_tokens=False) for char in bad_chars]
            
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=300,
                    min_new_tokens=100,
                    do_sample=True,
                    temperature=0.45,
                    top_p=0.9,
                    top_k=50,
                    num_beams=4,
                    no_repeat_ngram_size=3,
                    repetition_penalty=1.8,
                    length_penalty=1.2,  # Aumentato come richiesto
                    bad_words_ids=bad_words_ids,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.eos_token_id,
                    forced_bos_token_id=self.tokenizer.bos_token_id,
                    forced_eos_token_id=self.tokenizer.eos_token_id,
                    num_return_sequences=1
                )

            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Migliorata pulizia della risposta
            # Se il prompt è ancora nella risposta, rimuovilo
            if prompt in response:
                response = response.replace(prompt, "").strip()
            
            # Rimuovi tutti i tag HTML e markdown con regex
            import re
            response = re.sub(r'<[^>]*>', '', response)  # Rimuove qualsiasi tag HTML
            response = re.sub(r'```[\s\S]*?```', '', response)  # Rimuove blocchi di codice
            response = re.sub(r'`.*?`', '', response)  # Rimuove inline code
            
            # Rimuovi caratteri speciali e tag
            for tag in ["<pre>", "</pre>", "<code>", "</code>", "</s>", "<s>", "```", "#", "*", "==", "__"]:
                response = response.replace(tag, "")
                
            # Rimuovi testo in inglese e formattazioni non desiderate
            english_phrases = ["Analysis:", "Recommendations:", "Here is", "I recommend", "Let me", 
                              "Based on", "Looking at", "In conclusion", "To summarize", "First", "Second",
                              "Finally", "Note:", "Important:", "Example:"]
            for phrase in english_phrases:
                if phrase in response:
                    sections = response.split(phrase)
                    response = sections[-1].strip()
            
            # Mantieni solo dalla prima lista numerata
            numbered_list_match = re.search(r'\b[1]\.[\s\S]*', response)
            if numbered_list_match:
                response = numbered_list_match.group(0).strip()
            elif "Analisi" in response:
                response = response[response.find("Analisi"):].strip()
                
            # Rimuovi domande o contenuti non pertinenti
            lines = response.split('\n')
            filtered_lines = []
            for line in lines:
                # Rimuovi linee che sembrano codice PHP, HTML, o altre formattazioni
                if (not line.strip().endswith("?") and 
                    not re.search(r'<.*?>', line) and 
                    not re.search(r'function\s*\(', line) and
                    not re.search(r'class\s*\{', line) and
                    not any(x in line.lower() for x in ["how", "what", "why", "when", "è corretto", "suggestions", 
                                                      "additional", "php", "html", "script", "function", "def ", "class"])):
                    filtered_lines.append(line)
            response = '\n'.join(filtered_lines)
            
            self.logger.info("Risposta generata con successo e pulita")
            self.logger.debug(f"Output token length: {outputs.shape[1]}")
            return response

        except Exception as e:
            self.logger.error(f"Errore nella generazione della risposta: {str(e)}")
            return f"Si è verificato un errore: {str(e)}"

