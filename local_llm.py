# local_llm.py

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from config import LOCAL_LLM_MODEL_NAME

class LocalLLM:
    def __init__(self):
        print(f"[LocalLLM] Caricamento modello: {LOCAL_LLM_MODEL_NAME}")
        self.tokenizer = AutoTokenizer.from_pretrained(LOCAL_LLM_MODEL_NAME)
        self.model = AutoModelForCausalLM.from_pretrained(LOCAL_LLM_MODEL_NAME)
        self.model.eval()

    def generate_response(self, context_text):
        prompt = f"""Sei un assistente per Gran Turismo 7.
Dati:
{context_text}
Fornisci un consiglio di assetto e guida:
"""
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_length=200,
                temperature=0.8,
                num_return_sequences=1
            )
        gen_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        response = gen_text[len(prompt):].strip()
        return response
