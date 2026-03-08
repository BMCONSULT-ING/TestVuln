# ============================================================
#  BOT GOLD — XAUUSD  |  SMA20/50 + Engulfing + SL/TP Dynamiques
# ============================================================

MT5_CONFIG = {
    "login":    24341433,
    "password": "$^h8pTN*",
    "server":   "VantageInternational-Demo",
}

SYMBOLS = ["XAUUSD"]

TIMEFRAME = "M15"

# ============================================================
#  INDICATEURS (même setup que ton indicateur testé)
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
#  SL / TP DYNAMIQUES (adapté Gold)
# ============================================================

DYNAMIC_SLTP = {
    "swing_lookback":  5,      # Bougies swing detection
    "sl_buffer_pct":   0.0005, # Buffer 0.05% (Gold a des spreads plus serrés que BTC)
    "min_rr":          1.5,    # RR minimum 1:1.5
    "atr_fallback":    True,
    "atr_mult_sl":     1.0,
    "atr_mult_tp":     2.0,
}

# ============================================================
#  RISK MANAGEMENT (adapté Gold)
# ============================================================

RISK_GOLD = {
    "capital":   1000.0,
    "risk_pct":  10.0,         # Max $100 de perte par trade
}

# ============================================================
#  BOT
# ============================================================

BOT_GOLD = {
    "check_interval": 30,
    "magic_number":   20240404,  # Identifiant unique Gold
    "log_file":       "bot_gold.log",
}
