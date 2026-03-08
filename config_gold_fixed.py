# ============================================================
#  BOT GOLD FIXE — XAUUSD  |  SMA20/50 + Engulfing + SL/TP ATR
# ============================================================

MT5_CONFIG = {
    "login":    24341433,
    "password": "$^h8pTN*",
    "server":   "VantageInternational-Demo",
}

SYMBOLS = ["XAUUSD"]

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
#  RISK MANAGEMENT
# ============================================================

RISK_GOLD_FIXED = {
    "capital":     1000.0,
    "risk_pct":    10.0,    # Max $100 de perte par trade
    "sl_atr_mult": 1.0,     # SL = 1x ATR
    "tp_atr_mult": 2.0,     # TP = 2x ATR  (RR 1:2 fixe)
}

# ============================================================
#  BOT
# ============================================================

BOT_GOLD_FIXED = {
    "check_interval": 30,
    "magic_number":   20240405,
    "log_file":       "bot_gold_fixed.log",
}
