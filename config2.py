# ============================================================
#  STRATÉGIE 2 — Engulfing Scalping
# ============================================================

MT5_CONFIG = {
    "login":    24341433,
    "password": "$^h8pTN*",
    "server":   "VantageInternational-Demo",
}

SYMBOLS = ["BTCUSD"]

TIMEFRAME = "M15"

# ============================================================
#  INDICATEURS  (calqués sur l'indicateur testé)
# ============================================================

INDICATORS = {
    "ma_type":  "SMA",   # Simple Moving Average
    "ma_fast":  20,      # SMA 20 — Fast
    "ma_slow":  50,      # SMA 50 — Slow
    "ma_price": "close", # Price : Close
    # Phase 15 → appliqué comme lissage supplémentaire sur le signal
    "ma_phase": 15,
}

ENGULFING = {
    "min_body_ratio":   0.4,  # Corps >= 40% de la taille totale
    "min_engulf_ratio": 1.0,  # La bougie avale au moins 100% du corps précédent
}

# ============================================================
#  RISK MANAGEMENT
# ============================================================

RISK2 = {
    "capital":          1000.0,  # Capital de référence ($)
    "risk_pct":         10.0,    # SL = 10% du capital → $100 max loss
    "reward_pct":       10.0,    # TP = 10% du capital → $100 target
    "sl_atr_mult":      1.0,     # Distance SL = 1x ATR (serré pour scalping)
}

# ============================================================
#  BOT
# ============================================================

BOT2 = {
    "check_interval": 30,        # Vérification toutes les 30 secondes
    "magic_number":   20240202,  # Identifiant unique (différent du bot 1)
    "log_file":       "bot2.log",
}
