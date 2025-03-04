from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

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

        :param config_data: Dati della configurazione attuale della vettura (GUI)
        :param telemetry_data: Dati numerici della telemetria
        :return: Risposta generata da Falcon-7B
        """
        prompt = f"""Sei un esperto di assetto e guida in Gran Turismo 7. Il tuo compito è analizzare sia i parametri di configurazione del veicolo che i dati di telemetria, per identificare eventuali criticità e fornire consigli tecnici specifici per l'ottimizzazione dell'assetto.

        1. **Dati della configurazione attuale (inseriti tramite la GUI)**:
           - Veicolo: {config_data.get("modello_veicolo", "N/A")}
           - Circuito: {config_data.get("nome_circuito", "N/A")} – Condizioni: {config_data.get("condizioni_circuito", "N/A")}
           - Gomme: {config_data.get("tipo_gomme", "N/A")}

        2. **Dati di telemetria prelevati dal database**:
        ---------------------------------------------------
        • Altezza dal suolo:
           - Anteriore: {telemetry_data.get("altezza_ant", "N/A")} mm
           - Posteriore: {telemetry_data.get("altezza_post", "N/A")} mm

        • Barre Antirollio:
           - Anteriore: {telemetry_data.get("barre_ant", "N/A")}
           - Posteriore: {telemetry_data.get("barre_post", "N/A")}

        • Ammortizzatori:
           - Compressione: Anteriore {telemetry_data.get("comp_ant", "N/A")}%, Posteriore {telemetry_data.get("comp_post", "N/A")}%
           - Estensione: Anteriore {telemetry_data.get("est_ant", "N/A")}%, Posteriore {telemetry_data.get("est_post", "N/A")}%

        • Frequenza Naturale:
           - Anteriore: {telemetry_data.get("frequenza_ant", "N/A")} Hz
           - Posteriore: {telemetry_data.get("frequenza_post", "N/A")} Hz

        • Campanatura:
           - Anteriore: {telemetry_data.get("camp_ant", "N/A")}°
           - Posteriore: {telemetry_data.get("camp_post", "N/A")}°

        • Angoli di Convergenza:
           - Anteriore: {telemetry_data.get("conv_ant", "N/A")}° (Tipo: {telemetry_data.get("conv_ant_type", "N/A")})
           - Posteriore: {telemetry_data.get("conv_post", "N/A")}° (Tipo: {telemetry_data.get("conv_post_type", "N/A")})

        • Differenziale:
           - Coppia iniziale: Anteriore {telemetry_data.get("diff_coppia_ant", "N/A")}, Posteriore {telemetry_data.get("diff_coppia_post", "N/A")}
           - Sensibilità in accelerazione: Anteriore {telemetry_data.get("diff_acc_ant", "N/A")}, Posteriore {telemetry_data.get("diff_acc_post", "N/A")}
           - Sensibilità in frenata: Anteriore {telemetry_data.get("diff_frenata_ant", "N/A")}, Posteriore {telemetry_data.get("diff_frenata_post", "N/A")}
           - Distribuzione: {telemetry_data.get("diff_distrib", "N/A")} %

        • Deportanza:
           - Anteriore: {telemetry_data.get("deportanza_ant", "N/A")}
           - Posteriore: {telemetry_data.get("deportanza_post", "N/A")}

        • Prestazioni:
           - Zavorra: {telemetry_data.get("zavorra", "N/A")} kg
           - Posizionamento Zavorra: {telemetry_data.get("pos_zavorra", "N/A")} %

        • Limitatore di Potenza: {telemetry_data.get("limitatore", "N/A")} %

        • Bilanciamento Freni: {telemetry_data.get("freni", "N/A")} (valore da -5 a +5)

        • Cambio:
           - Rapporti marce: {telemetry_data.get("rapporti", "N/A")}
           - Rapporto finale: {telemetry_data.get("rapporto_finale", "N/A")}
        ---------------------------------------------------

        **Contestualizzazione**:
        Il veicolo è configurato per una guida in condizioni di {config_data.get("condizioni_di_guida", "N/A")}. 
        Analizza attentamente sia i parametri di configurazione sia i dati di telemetria per identificare eventuali anomalie o criticità, come grip insufficiente in ingresso, instabilità in uscita dalla curva o squilibri tra gli assi.

        **Richiesta**:
        Basandoti sui dati sopra, fornisci un consiglio tecnico dettagliato per ottimizzare l'assetto del veicolo in Gran Turismo 7. Nella tua risposta specifica:
        - Quali parametri modificare (es. camber, toe, rigidità degli ammortizzatori, impostazioni del differenziale, ecc.) per correggere le criticità riscontrate nella telemetria.
        - In che modo le modifiche influenzeranno la dinamica del veicolo (miglior grip, riduzione del rollio, maggiore stabilità, ecc.).
        - Suggerimenti pratici per testare e validare le modifiche in pista.

        Rispondi esclusivamente in italiano, utilizzando termini tecnici appropriati e un tono professionale. Evita risposte generiche o incomplete.
        """

        # Generazione della risposta
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        outputs = self.model.generate(**inputs, max_length=1024)
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response
