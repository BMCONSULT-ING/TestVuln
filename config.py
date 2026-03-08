# ============================================================
#  CONFIGURATION - Modifie ces valeurs avec ton compte Vantage
# ============================================================

MT5_CONFIG = {
    "login": 24341433,
    "password": "$^h8pTN*",
    "server": "VantageInternational-Demo",
}

# Paires à trader
SYMBOLS = [
    "BTCUSD",   # Bitcoin CFD - disponible 24/7
]

# Timeframes (Top-Down Analysis)
TIMEFRAMES = {
    "bias_high": "H4",   # Tendance macro
    "bias_mid":  "H1",   # Confirmation intermédiaire
    "entry":     "M5",   # Entrée précise (OB / FVG)
}

# ============================================================
#  GESTION DU RISQUE (scalping SMC)
# ============================================================

RISK = {
    "risk_per_trade":    0.5,   # 0.5% du capital par trade
    "max_trades":        1,     # 1 trade à la fois sur BTC
    "sl_atr_multiplier": 1.0,   # SL serré = 1x ATR (entrée précise sur OB)
    "tp_ratio":          3.0,   # RR 1:3
    "atr_period":        14,
}

# ============================================================
#  PARAMÈTRES DU BOT
# ============================================================

BOT = {
    "check_interval": 60,      # Vérification toutes les 60 secondes
    "magic_number": 20240101,  # Identifiant unique des ordres du bot
    "log_file": "bot.log",
}
