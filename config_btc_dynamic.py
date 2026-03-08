# ============================================================
#  STRATÉGIE 3 — SMA 20/50 + Engulfing + SL/TP Dynamiques
# ============================================================

MT5_CONFIG = {
    "login":    24341433,
    "password": "$^h8pTN*",
    "server":   "VantageInternational-Demo",
}

SYMBOLS = ["BTCUSD"]

TIMEFRAME = "M15"

# ============================================================
#  INDICATEURS
# ============================================================

INDICATORS = {
    "ma_type":  "SMA",
    "ma_fast":  20,
    "ma_slow":  50,
    "ma_price": "close",
    "ma_phase": 15,
}

ENGULFING = {
    "min_body_ratio":   0.4,
    "min_engulf_ratio": 1.0,
}

# ============================================================
#  SL / TP DYNAMIQUES
# ============================================================

DYNAMIC_SLTP = {
    "swing_lookback":  5,     # Bougies de chaque côté pour détecter un swing
    "sl_buffer_pct":   0.001, # Buffer SL = 0.1% au-delà du swing (évite le stop hunt)
    "min_rr":          1.5,   # RR minimum pour accepter le trade (ex: 1.5 = RR 1:1.5)
    "atr_fallback":    True,  # Si aucun swing trouvé, utilise ATR comme fallback
    "atr_mult_sl":     1.0,
    "atr_mult_tp":     2.0,
}

# ============================================================
#  RISK MANAGEMENT
# ============================================================

RISK3 = {
    "capital":   1000.0,
    "risk_pct":  10.0,     # SL = 10% du capital max → $100
}

# ============================================================
#  BOT
# ============================================================

BOT3 = {
    "check_interval": 30,
    "magic_number":   20240303,
    "log_file":       "bot3.log",
}
