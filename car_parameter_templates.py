# Default parameter templates for car setups
DEFAULT_PARAMETERS = [
    # Sospensioni
    {
        "name": "altezza_ant",
        "display_name": "Altezza suolo anteriore",
        "current_value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "mm"
    },
    {
        "name": "altezza_post",
        "display_name": "Altezza suolo posteriore",
        "current_value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "mm"
    },
    {
        "name": "barre_ant",
        "display_name": "Barre Antirollio anteriori",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "barre_post",
        "display_name": "Barre Antirollio posteriori",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "ammort_compressione_ant",
        "display_name": "Ammortizzazione Compressione anteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_post",
        "display_name": "Ammortizzazione Compressione posteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_ant",
        "display_name": "Ammortizzazione Estensione anteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_post",
        "display_name": "Ammortizzazione Estensione posteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "frequenza_ant",
        "display_name": "Frequenza Naturale anteriore",
        "current_value": 10,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },
    {
        "name": "frequenza_post",
        "display_name": "Frequenza Naturale posteriore",
        "current_value": 10,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },
    # Geometria
    {
        "name": "campanatura_ant",
        "display_name": "Campanatura anteriore",
        "current_value": -2,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "campanatura_post",
        "display_name": "Campanatura posteriore",
        "current_value": -2,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "conv_ant",
        "display_name": "Convergenza anteriore",
        "current_value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "conv_post",
        "display_name": "Convergenza posteriore",
        "current_value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    # Differenziale
    {
        "name": "diff_coppia_ant",
        "display_name": "Differenziale Coppia Iniziale anteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_coppia_post",
        "display_name": "Differenziale Coppia Iniziale posteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_acc_ant",
        "display_name": "Differenziale Sensibilità Accelerazione anteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_acc_post",
        "display_name": "Differenziale Sensibilità Accelerazione posteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_frenata_ant",
        "display_name": "Differenziale Sensibilità Frenata anteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_frenata_post",
        "display_name": "Differenziale Sensibilità Frenata posteriore",
        "current_value": 5,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "diff_distrib",
        "display_name": "Differenziale Distribuzione",
        "current_value": "50:50",
        "min_value": None,
        "max_value": None,
        "unit": None
    },
    # Aerodinamica
    {
        "name": "deportanza_ant",
        "display_name": "Deportanza anteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    {
        "name": "deportanza_post",
        "display_name": "Deportanza posteriore",
        "current_value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "level"
    },
    # Prestazioni
    {
        "name": "ecu_reg_potenza",
        "display_name": "ECU Regolazione Potenza",
        "current_value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "zavorra",
        "display_name": "Zavorra",
        "current_value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "kg"
    },
    {
        "name": "pos_zavorra",
        "display_name": "Posizione Zavorra",
        "current_value": 0,
        "min_value": -50,
        "max_value": 50,
        "unit": None
    },
    {
        "name": "limitatore",
        "display_name": "Limitatore",
        "current_value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "freni",
        "display_name": "Bilanciamento Freni",
        "current_value": 0,
        "min_value": -5,
        "max_value": 5,
        "unit": None
    }
]

