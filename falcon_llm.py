import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class FalconLLM:
    def __init__(self):
        self.model_id = "tiiuae/falcon-7b-instruct"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,  # o torch.float16 se la tua GPU lo supporta
            trust_remote_code=True,
            device_map="auto"
        )

    def generate_response(self, config_data, telemetry_data):
        """
        Genera una risposta basata sui dati di configurazione e di telemetria.

        :param config_data: Dati della configurazione attuale della vettura (es. modello auto, circuito, gomme)
        :param telemetry_data: Dati di telemetria (ultimo record)
        :return: Risposta generata da Falcon-7B
        """
        prompt = (
            "Sei un ingegnere specializzato in assetto e guida in Gran Turismo 7. "
            "Hai a disposizione due fonti di dati:\n\n"
            "1. Dati di configurazione (impostati tramite la GUI):\n"
            "   - Veicolo: {modello_veicolo}\n"
            "   - Circuito: {nome_circuito}\n"
            "   - Gomme: {tipo_gomme}\n"
            "   - Parametri statici di assetto:\n"
            "       * Altezza dal suolo: anteriore e posteriore, con relativi valori minimi e massimi\n"
            "       * Barre Antirollio: anteriore e posteriore, con relativi minimi e massimi\n"
            "       * Ammortizzazione Compressione: anteriore e posteriore, con minimi e massimi\n"
            "       * Ammortizzazione Estensione: anteriore e posteriore, con minimi e massimi\n"
            "       * Frequenza Naturale: anteriore e posteriore, con relativi minimi e massimi\n"
            "       * Campanatura: anteriore e posteriore, con relativi minimi e massimi\n"
            "       * Angolo di convergenza: anteriore e posteriore (usa il segno '+' per convergente, '-' per divergente)\n"
            "       * Differenziale: coppia iniziale, sensibilità in accelerazione e sensibilità in frenata "
            "         (valori per anteriore e posteriore) e distribuzione di coppia (es. '0:100', '5:95', ecc.)\n"
            "       * Deportanza: anteriore e posteriore, con relativi minimi e massimi\n"
            "       * ECU Regolazione Potenza: valore singolo, con minimi e massimi\n"
            "       * Zavorra: valore singolo (kg) con minimi e massimi\n"
            "       * Posizionamento Zavorra: valore unico da -50 (anteriore) a +50 (posteriore), con una descrizione esplicativa\n"
            "       * Limitatore di Potenza: valore singolo in percentuale, con minimi e massimi\n"
            "       * Bilanciamento Freni: un singolo valore da -5 a +5\n\n"
            "2. Dati di telemetria (ultimo record dinamico):\n"
            "{telemetry}\n\n"
            "Analizza attentamente questi dati per valutare lo stato attuale dell'assetto e della dinamica del veicolo. "
            "Fornisci un consiglio tecnico dettagliato in italiano, indicando quali parametri regolare per migliorare grip, "
            "stabilità e comportamento in curva, spiegando come le modifiche influiranno sulla dinamica del veicolo e suggerendo "
            "come testare e validare le modifiche in pista. Rispondi esclusivamente in italiano utilizzando un linguaggio tecnico e preciso."
        ).format(
            modello_veicolo=config_data.get("modello_veicolo", "N/A"),
            nome_circuito=config_data.get("nome_circuito", "N/A"),
            tipo_gomme=config_data.get("tipo_gomme", "N/A"),
            telemetry=telemetry_data
        )
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=300,   # genera fino a 300 token nuovi
                do_sample=True,       # abilita il campionamento (sampling)
                temperature=0.7       # aumenta leggermente la temperatura per rendere l'output più vario
        )

