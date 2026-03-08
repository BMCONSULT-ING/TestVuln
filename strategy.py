import pandas as pd
import numpy as np


# ============================================================
#  PIVOTS (Swing Highs / Lows)
# ============================================================

def find_pivot_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> list:
    pivots = []
    for i in range(left, len(df) - right):
        if df["high"].iloc[i] == df["high"].iloc[i - left: i + right + 1].max():
            pivots.append(i)
    return pivots


def find_pivot_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> list:
    pivots = []
    for i in range(left, len(df) - right):
        if df["low"].iloc[i] == df["low"].iloc[i - left: i + right + 1].min():
            pivots.append(i)
    return pivots


# ============================================================
#  STRUCTURE DE MARCHÉ (HTF)
# ============================================================

def get_market_structure(df: pd.DataFrame, lookback: int = 3) -> str:
    """
    Retourne la structure de marché : 'BULLISH', 'BEARISH' ou 'NEUTRAL'
    Basé sur la comparaison des 2 derniers swing highs et swing lows.
    """
    ph = find_pivot_highs(df, lookback, lookback)
    pl = find_pivot_lows(df, lookback, lookback)

    if len(ph) < 2 or len(pl) < 2:
        return "NEUTRAL"

    last_sh = df["high"].iloc[ph[-1]]
    prev_sh = df["high"].iloc[ph[-2]]
    last_sl = df["low"].iloc[pl[-1]]
    prev_sl = df["low"].iloc[pl[-2]]

    if last_sh > prev_sh and last_sl > prev_sl:
        return "BULLISH"   # Higher High + Higher Low
    elif last_sh < prev_sh and last_sl < prev_sl:
        return "BEARISH"   # Lower High + Lower Low
    return "NEUTRAL"


# ============================================================
#  BOS (Break of Structure) — LTF
# ============================================================

def detect_fresh_bos(df: pd.DataFrame, lookback: int = 3, max_age: int = 15):
    """
    Détecte un BOS récent (dans les max_age dernières bougies).
    Retourne : (direction, bos_level, bos_candle_idx) ou (None, None, None)
    """
    ph = find_pivot_highs(df, lookback, lookback)
    pl = find_pivot_lows(df, lookback, lookback)
    total = len(df)

    # BOS Bullish : close qui casse au-dessus du dernier swing high
    for ph_idx in reversed(ph):
        sh_level = df["high"].iloc[ph_idx]
        for j in range(ph_idx + 1, total):
            if df["close"].iloc[j] > sh_level:
                if total - j <= max_age:
                    return "BULLISH", sh_level, j
                break  # trop vieux

    # BOS Bearish : close qui casse en-dessous du dernier swing low
    for pl_idx in reversed(pl):
        sl_level = df["low"].iloc[pl_idx]
        for j in range(pl_idx + 1, total):
            if df["close"].iloc[j] < sl_level:
                if total - j <= max_age:
                    return "BEARISH", sl_level, j
                break

    return None, None, None


# ============================================================
#  ORDER BLOCK
# ============================================================

def find_order_block(df: pd.DataFrame, direction: str, bos_idx: int = None) -> dict:
    """
    Bullish OB : dernière bougie baissière avant le BOS haussier
    Bearish OB : dernière bougie haussière avant le BOS baissier
    """
    end = bos_idx if bos_idx else len(df) - 1
    start = max(0, end - 30)

    if direction == "BULLISH":
        for i in range(end - 1, start, -1):
            c = df.iloc[i]
            if c["close"] < c["open"]:
                return {"top": c["open"], "bottom": c["close"], "index": i}

    elif direction == "BEARISH":
        for i in range(end - 1, start, -1):
            c = df.iloc[i]
            if c["close"] > c["open"]:
                return {"top": c["close"], "bottom": c["open"], "index": i}

    return None


# ============================================================
#  FAIR VALUE GAP (FVG)
# ============================================================

def find_fvg(df: pd.DataFrame, direction: str, bos_idx: int = None) -> dict:
    """
    Bullish FVG : low[i] > high[i-2]
    Bearish FVG : high[i] < low[i-2]
    """
    end = bos_idx if bos_idx else len(df) - 1
    start = max(2, end - 20)

    for i in range(end, start, -1):
        if i >= len(df):
            continue
        c0 = df.iloc[i - 2]
        c2 = df.iloc[i]

        if direction == "BULLISH" and c2["low"] > c0["high"]:
            return {"top": c2["low"], "bottom": c0["high"], "index": i}

        if direction == "BEARISH" and c2["high"] < c0["low"]:
            return {"top": c0["low"], "bottom": c2["high"], "index": i}

    return None


# ============================================================
#  PREMIUM / DISCOUNT + OTE (Optimal Trade Entry)
# ============================================================

def get_premium_discount(df: pd.DataFrame, lookback: int = 3) -> dict:
    """
    Calcule les zones Premium/Discount basées sur le dernier range swing.

    Discount zone : prix < equilibrium (50%) → zone BUY
    Premium zone  : prix > equilibrium (50%) → zone SELL

    OTE (Optimal Trade Entry) : retracement Fibonacci 61.8% - 78.6%
    → Zone idéale d'entrée institutionnelle
    """
    ph = find_pivot_highs(df, lookback, lookback)
    pl = find_pivot_lows(df, lookback, lookback)

    if not ph or not pl:
        return None

    swing_high = df["high"].iloc[ph[-1]]
    swing_low  = df["low"].iloc[pl[-1]]
    rang       = swing_high - swing_low

    if rang <= 0:
        return None

    equilibrium = swing_low + rang * 0.5

    # OTE Bullish : 61.8% – 78.6% de retracement depuis le high
    # (prix redescend dans cette zone avant de remonter)
    ote_bull_top    = swing_high - rang * 0.618
    ote_bull_bottom = swing_high - rang * 0.786

    # OTE Bearish : 61.8% – 78.6% de retracement depuis le low
    # (prix remonte dans cette zone avant de redescendre)
    ote_bear_bottom = swing_low + rang * 0.618
    ote_bear_top    = swing_low + rang * 0.786

    return {
        "swing_high":   swing_high,
        "swing_low":    swing_low,
        "equilibrium":  equilibrium,
        "premium_zone": {"bottom": equilibrium, "top": swing_high},
        "discount_zone": {"bottom": swing_low,  "top": equilibrium},
        "ote_bullish":  {"bottom": ote_bull_bottom, "top": ote_bull_top},
        "ote_bearish":  {"bottom": ote_bear_bottom, "top": ote_bear_top},
    }


def is_in_discount(price: float, pd_zones: dict) -> bool:
    """Prix dans la Discount Zone (en dessous de l'équilibre) → favorable BUY"""
    if not pd_zones:
        return False
    return price <= pd_zones["equilibrium"]


def is_in_premium(price: float, pd_zones: dict) -> bool:
    """Prix dans la Premium Zone (au dessus de l'équilibre) → favorable SELL"""
    if not pd_zones:
        return False
    return price >= pd_zones["equilibrium"]


def is_in_ote(price: float, pd_zones: dict, direction: str) -> bool:
    """Prix dans l'Optimal Trade Entry (Fibo 61.8-78.6%) → entrée idéale"""
    if not pd_zones:
        return False
    if direction == "BULLISH":
        z = pd_zones["ote_bullish"]
    else:
        z = pd_zones["ote_bearish"]
    return z["bottom"] <= price <= z["top"]


# ============================================================
#  UTILITAIRES
# ============================================================

def price_in_zone(price: float, zone: dict) -> bool:
    if not zone:
        return False
    return zone["bottom"] <= price <= zone["top"]


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    high  = df["high"]
    low   = df["low"]
    close = df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean().iloc[-1]
