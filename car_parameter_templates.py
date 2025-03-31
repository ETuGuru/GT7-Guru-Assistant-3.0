# car_parameter_templates.py

CAR_PARAMETER_TEMPLATES = [
    # --- Altezza suolo (mm) ---
    {
        "name": "altezza_ant",
        "display_name": "Altezza suolo anteriore",
        "value": 52,        # Default
        "min_value": 40,    # Default min
        "max_value": 60,    # Default max
        "unit": "mm"
    },
    {
        "name": "altezza_post",
        "display_name": "Altezza suolo posteriore",
        "value": 57,
        "min_value": 40,
        "max_value": 60,
        "unit": "mm"
    },
    {
        "name": "altezza_ant_min",
        "display_name": "Altezza suolo ant. minima impostabile",
        "value": 40,
        "min_value": None,  # Se vuoi, lasci None
        "max_value": None,
        "unit": "mm"
    },
    {
        "name": "altezza_ant_max",
        "display_name": "Altezza suolo ant. massima impostabile",
        "value": 60,
        "min_value": None,
        "max_value": None,
        "unit": "mm"
    },
    {
        "name": "altezza_post_min",
        "display_name": "Altezza suolo post. minima impostabile",
        "value": 40,
        "min_value": None,
        "max_value": None,
        "unit": "mm"
    },
    {
        "name": "altezza_post_max",
        "display_name": "Altezza suolo post. massima impostabile",
        "value": 60,
        "min_value": None,
        "max_value": None,
        "unit": "mm"
    },

    # --- Barre Antirollio ---
    {
        "name": "barre_ant",
        "display_name": "Barre Antirollio anteriori",
        "value": 5,
        "min_value": 1,
        "max_value": 10,
        "unit": ""
    },
    {
        "name": "barre_post",
        "display_name": "Barre Antirollio posteriori",
        "value": 6,
        "min_value": 1,
        "max_value": 10,
        "unit": ""
    },
    {
        "name": "barre_ant_min",
        "display_name": "Barre anteriori min",
        "value": 1,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "barre_ant_max",
        "display_name": "Barre anteriori max",
        "value": 10,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "barre_post_min",
        "display_name": "Barre posteriori min",
        "value": 1,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "barre_post_max",
        "display_name": "Barre posteriori max",
        "value": 10,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    # --- Ammortizzazione Compressione ---
    {
        "name": "ammort_compressione_ant",
        "display_name": "Ammort. Compressione ant (%)",
        "value": 25,
        "min_value": 20,
        "max_value": 40,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_post",
        "display_name": "Ammort. Compressione post (%)",
        "value": 25,
        "min_value": 20,
        "max_value": 40,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_ant_min",
        "display_name": "Ammort. Comp. ant min",
        "value": 20,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_ant_max",
        "display_name": "Ammort. Comp. ant max",
        "value": 40,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_post_min",
        "display_name": "Ammort. Comp. post min",
        "value": 20,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_compressione_post_max",
        "display_name": "Ammort. Comp. post max",
        "value": 40,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },

    # --- Ammortizzazione Estensione ---
    {
        "name": "ammort_estensione_ant",
        "display_name": "Ammort. Estensione ant (%)",
        "value": 45,
        "min_value": 30,
        "max_value": 50,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_post",
        "display_name": "Ammort. Estensione post (%)",
        "value": 45,
        "min_value": 30,
        "max_value": 50,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_ant_min",
        "display_name": "Ammort. Estens. ant min",
        "value": 30,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_ant_max",
        "display_name": "Ammort. Estens. ant max",
        "value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_post_min",
        "display_name": "Ammort. Estens. post min",
        "value": 30,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ammort_estensione_post_max",
        "display_name": "Ammort. Estens. post max",
        "value": 50,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },

    # --- Frequenza Naturale ---
    {
        "name": "frequenza_ant",
        "display_name": "Frequenza ant (Hz)",
        "value": 4.80,
        "min_value": 4.60,
        "max_value": 5.50,
        "unit": "Hz"
    },
    {
        "name": "frequenza_post",
        "display_name": "Frequenza post (Hz)",
        "value": 4.90,
        "min_value": 4.60,
        "max_value": 5.50,
        "unit": "Hz"
    },
    {
        "name": "frequenza_ant_min",
        "display_name": "Frequenza ant min",
        "value": 4.60,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },
    {
        "name": "frequenza_ant_max",
        "display_name": "Frequenza ant max",
        "value": 5.50,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },
    {
        "name": "frequenza_post_min",
        "display_name": "Frequenza post min",
        "value": 4.60,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },
    {
        "name": "frequenza_post_max",
        "display_name": "Frequenza post max",
        "value": 5.50,
        "min_value": None,
        "max_value": None,
        "unit": "Hz"
    },

    # --- Campanatura / Convergenza ---
    {
        "name": "campanatura_ant",
        "display_name": "Campanatura ant (°)",
        "value": 3.5,
        "min_value": 0.0,
        "max_value": 6.0,
        "unit": "°"
    },
    {
        "name": "campanatura_post",
        "display_name": "Campanatura post (°)",
        "value": 2.0,
        "min_value": 0.0,
        "max_value": 6.0,
        "unit": "°"
    },
    {
        "name": "campanatura_ant_min",
        "display_name": "Campanatura ant min",
        "value": 0.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "campanatura_ant_max",
        "display_name": "Campanatura ant max",
        "value": 6.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "campanatura_post_min",
        "display_name": "Campanatura post min",
        "value": 0.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "campanatura_post_max",
        "display_name": "Campanatura post max",
        "value": 6.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },

    {
        "name": "conv_ant",
        "display_name": "Convergenza ant (°)",
        "value": 0.10,
        "min_value": -1.0,
        "max_value": 1.0,
        "unit": "°"
    },
    {
        "name": "conv_post",
        "display_name": "Convergenza post (°)",
        "value": 0.25,
        "min_value": -1.0,
        "max_value": 1.0,
        "unit": "°"
    },
    {
        "name": "conv_ant_min",
        "display_name": "Conv ant min",
        "value": -1.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "conv_ant_max",
        "display_name": "Conv ant max",
        "value": 1.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "conv_post_min",
        "display_name": "Conv post min",
        "value": -1.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },
    {
        "name": "conv_post_max",
        "display_name": "Conv post max",
        "value": 1.0,
        "min_value": None,
        "max_value": None,
        "unit": "°"
    },

    # --- Differenziale ---
    {
        "name": "diff_coppia_ant",
        "display_name": "Diff. Coppia ant (iniziale)",
        "value": None,  # Se l'auto non ha anteriore
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_coppia_post",
        "display_name": "Diff. Coppia post (iniziale)",
        "value": 5,
        "min_value": 5,
        "max_value": 60,
        "unit": ""
    },
    {
        "name": "diff_coppia_ant_min",
        "display_name": "Diff. Coppia ant min",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_coppia_ant_max",
        "display_name": "Diff. Coppia ant max",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_coppia_post_min",
        "display_name": "Diff. Coppia post min",
        "value": 5,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_coppia_post_max",
        "display_name": "Diff. Coppia post max",
        "value": 60,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    {
        "name": "diff_acc_ant",
        "display_name": "Diff. Sens. Accel. ant",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_acc_post",
        "display_name": "Diff. Sens. Accel. post",
        "value": 22,
        "min_value": 5,
        "max_value": 60,
        "unit": ""
    },
    {
        "name": "diff_acc_ant_min",
        "display_name": "Diff. Accel ant min",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_acc_ant_max",
        "display_name": "Diff. Accel ant max",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_acc_post_min",
        "display_name": "Diff. Accel post min",
        "value": 5,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_acc_post_max",
        "display_name": "Diff. Accel post max",
        "value": 60,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    {
        "name": "diff_frenata_ant",
        "display_name": "Diff. Sens. Frenata ant",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_frenata_post",
        "display_name": "Diff. Sens. Frenata post",
        "value": 5,
        "min_value": 5,
        "max_value": 60,
        "unit": ""
    },
    {
        "name": "diff_frenata_ant_min",
        "display_name": "Diff. Frenata ant min",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_frenata_ant_max",
        "display_name": "Diff. Frenata ant max",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_frenata_post_min",
        "display_name": "Diff. Frenata post min",
        "value": 5,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "diff_frenata_post_max",
        "display_name": "Diff. Frenata post max",
        "value": 60,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    {
        "name": "diff_distrib",
        "display_name": "Diff. Distribuzione Coppia (es. 50:50)",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    # --- Aerodinamica ---
    {
        "name": "deportanza_ant",
        "display_name": "Deportanza anteriore",
        "value": 1200,
        "min_value": 900,
        "max_value": 1200,
        "unit": ""
    },
    {
        "name": "deportanza_post",
        "display_name": "Deportanza posteriore",
        "value": 1650,
        "min_value": 1400,
        "max_value": 1800,
        "unit": ""
    },
    {
        "name": "deportanza_ant_min",
        "display_name": "Deportanza ant min",
        "value": 900,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "deportanza_ant_max",
        "display_name": "Deportanza ant max",
        "value": 1200,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "deportanza_post_min",
        "display_name": "Deportanza post min",
        "value": 1400,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "deportanza_post_max",
        "display_name": "Deportanza post max",
        "value": 1800,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    # --- ECU Reg. Potenza, Zavorra, Limitatore ---
    {
        "name": "ecu_reg_potenza",
        "display_name": "ECU Reg. Potenza (%)",
        "value": 0,
        "min_value": 0,
        "max_value": 100,
        "unit": "%"
    },
    {
        "name": "ecu_reg_potenza_min",
        "display_name": "ECU Reg. Potenza min (%)",
        "value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "ecu_reg_potenza_max",
        "display_name": "ECU Reg. Potenza max (%)",
        "value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },

    {
        "name": "zavorra",
        "display_name": "Zavorra (kg)",
        "value": 0,
        "min_value": 0,
        "max_value": 0,  
        "unit": "kg"
    },
    {
        "name": "zavorra_min",
        "display_name": "Zavorra min (kg)",
        "value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "kg"
    },
    {
        "name": "zavorra_max",
        "display_name": "Zavorra max (kg)",
        "value": 0,
        "min_value": None,
        "max_value": None,
        "unit": "kg"
    },

    {
        "name": "pos_zavorra",
        "display_name": "Pos. Zavorra (es. -50..+50)",
        "value": 0,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    {
        "name": "limitatore",
        "display_name": "Limitatore (%)",
        "value": 100,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "limitatore_min",
        "display_name": "Limitatore min (%)",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },
    {
        "name": "limitatore_max",
        "display_name": "Limitatore max (%)",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": "%"
    },

    # --- Bilanc. Freni ---
    {
        "name": "freni",
        "display_name": "Bilanciamento Freni",
        "value": -2,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "freni_min",
        "display_name": "Freni min",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "freni_max",
        "display_name": "Freni max",
        "value": None,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },

    # --- Cambio: rapporti ---
    {
        "name": "rapporti",
        "display_name": "Rapporti (lista di valori)",
        "value": "2.826,2.103,1.704,1.450,1.295,1.203,,",
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    {
        "name": "rapporto_finale",
        "display_name": "Rapporto Finale",
        "value": 4.50,
        "min_value": None,
        "max_value": None,
        "value": 4.50,
        "min_value": None,
        "max_value": None,
        "unit": ""
    },
    # --- Parametri Base Auto ---
    {
        "name": "peso",
        "display_name": "Peso",
        "value": 1200,
        "min_value": None,
        "max_value": None,
        "unit": "kg"
    },
    {
        "name": "potenza",
        "display_name": "Potenza",
        "value": 600,
        "min_value": None,
        "max_value": None,
        "unit": "CV"
    },
    {
        "name": "trazione",
        "display_name": "Tipo Trazione",
        "value": "FR",
        "min_value": None,
        "max_value": None,
        "unit": ""
    }
]
