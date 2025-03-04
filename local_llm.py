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
        # Se il tokenizer non ha un token di padding, impostalo uguale a eos_token_id
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

    def generate_response(self, context_text):
        prompt = f"""Sei un esperto di assetto e guida in Gran Turismo 7. Il tuo compito è analizzare sia i parametri di configurazione del veicolo che i dati di telemetria, per identificare eventuali criticità e fornire consigli tecnici specifici per l'ottimizzazione dell'assetto.

1. Dati della configurazione attuale (inseriti tramite la GUI):
   - Veicolo: [modello_veicolo] ([anno], se disponibile)
   - Circuito: [nome_circuito] – Condizioni: [condizioni_circuito]
   - Gomme: [tipo_gomme]

2. Dati di telemetria prelevati dal database:
---------------------------------------------------
• Altezza dal suolo:
   - Anteriore: [altezza_ant] mm
   - Posteriore: [altezza_post] mm

• Barre Antirollio:
   - Anteriore: [barre_ant] (scala 1-10)
   - Posteriore: [barre_post] (scala 1-10)

• Ammortizzatori:
   - Compressione: Anteriore [comp_ant] %, Posteriore [comp_post] %
   - Estensione: Anteriore [est_ant] %, Posteriore [est_post] %

• Frequenza Naturale:
   - Anteriore: [frequenza_ant] Hz
   - Posteriore: [frequenza_post] Hz

• Campanatura:
   - Anteriore: [camp_ant]°
   - Posteriore: [camp_post]°

• Angoli di Convergenza:
   - Anteriore: [conv_ant]° (Tipo: [conv_ant_type])
   - Posteriore: [conv_post]° (Tipo: [conv_post_type])

• Differenziale:
   - Coppia iniziale: Anteriore [diff_coppia_ant], Posteriore [diff_coppia_post]
   - Sensibilità in accelerazione: Anteriore [diff_acc_ant], Posteriore [diff_acc_post]
   - Sensibilità in frenata: Anteriore [diff_frenata_ant], Posteriore [diff_frenata_post]
   - Distribuzione: [diff_distrib] %

• Deportanza:
   - Anteriore: [deportanza_ant]
   - Posteriore: [deportanza_post]

• Prestazioni:
   - Zavorra: [zavorra] kg
   - Posizionamento Zavorra: [pos_zavorra] %

• Limitatore di Potenza: [limitatore] %

• Bilanciamento Freni: [freni] (valore da -5 a +5)

• Cambio:
   - Rapporti marce: [rapporti] (es. "2.83,2.10,1.70,1.45,1.30,1.20,0.00,0.00")
   - Rapporto finale: [rapporto_finale]
---------------------------------------------------

Contestualizzazione:
Il veicolo è configurato per una guida in condizioni di [condizioni_di_guida, ad es. "pista asciutta con curve strette" o "condizioni miste"]. 
Analizza attentamente sia i parametri di configurazione sia i dati di telemetria per identificare eventuali anomalie o criticità, come grip insufficiente in ingresso, instabilità in uscita dalla curva o squilibri tra gli assi.

Richiesta:
Basandoti sui dati sopra, fornisci un consiglio tecnico dettagliato per ottimizzare l'assetto del veicolo in Gran Turismo 7. Nella tua risposta specifica:
- Quali parametri modificare (es. camber, toe, rigidità degli ammortizzatori, impostazioni del differenziale, ecc.) per correggere le criticità riscontrate nella telemetria.
- In che modo le modifiche influenzeranno la dinamica del veicolo (miglior grip, riduzione del rollio, maggiore stabilità, ecc.).
- Suggerimenti pratici per testare e validare le modifiche in pista.

Rispondi esclusivamente in italiano, utilizzando termini tecnici appropriati e un tono professionale. Evita risposte generiche o incomplete.
"""
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        attention_mask = torch.ones_like(input_ids)
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_new_tokens=100,  # Genera 100 token nuovi
                do_sample=True,              # Abilita il campionamento
                temperature=0.4,             # Temperatura più bassa per output più deterministici
                num_return_sequences=1,
                pad_token_id=self.tokenizer.pad_token_id,
                attention_mask=attention_mask
            )
        gen_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        response = gen_text[len(prompt):].strip()
        return response