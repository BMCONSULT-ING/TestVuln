import pandas as pd


# ============================================================
#  MOVING AVERAGES  (SMA 20 / SMA 50 + Phase smoothing)
# ============================================================

def compute_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def apply_phase_smooth(series: pd.Series, phase: int) -> pd.Series:
    """
    Lissage supplémentaire avec la phase (identique au paramètre Phase de l'indicateur).
    Utilise une EMA de période = phase pour lisser la MA principale.
    """
    if phase <= 1:
        return series
    return series.ewm(span=phase, adjust=False).mean()


def get_ma_context(df: pd.DataFrame, ind: dict) -> dict:
    """
    Calcule SMA20 et SMA50 avec lissage Phase=15.

    Signal de croisement (PaintArrow: Crossing) :
      SMA20 passe au-dessus SMA50 -> BUY
      SMA20 passe en-dessous SMA50 -> SELL

    Tendance (ColorMethod: Trend) :
      SMA20 > SMA50 -> BULLISH
      SMA20 < SMA50 -> BEARISH
    """
    price_col = ind.get("ma_price", "close")
    phase     = ind.get("ma_phase", 15)

    # Calcul SMA 20 et SMA 50
    sma_fast_raw = compute_sma(df[price_col], ind["ma_fast"])
    sma_slow_raw = compute_sma(df[price_col], ind["ma_slow"])

    # Application du lissage Phase=15
    sma_fast = apply_phase_smooth(sma_fast_raw, phase)
    sma_slow = apply_phase_smooth(sma_slow_raw, phase)

    # Tendance actuelle
    trend = "BULLISH" if sma_fast.iloc[-1] > sma_slow.iloc[-1] else "BEARISH"

    # Croisement sur les 2 dernières bougies fermées
    prev_diff = sma_fast.iloc[-2] - sma_slow.iloc[-2]
    curr_diff = sma_fast.iloc[-1] - sma_slow.iloc[-1]

    cross = None
    if prev_diff < 0 and curr_diff > 0:
        cross = "BUY"    # SMA20 passe au-dessus SMA50
    elif prev_diff > 0 and curr_diff < 0:
        cross = "SELL"   # SMA20 passe en-dessous SMA50

    return {
        "trend":    trend,
        "cross":    cross,
        "sma_fast": sma_fast.iloc[-1],
        "sma_slow": sma_slow.iloc[-1],
    }


# ============================================================
#  DÉTECTION ENGULFING
# ============================================================

def detect_engulfing(df: pd.DataFrame, params: dict) -> str:
    """
    Détecte un signal sur les bougies FERMÉES uniquement (df.iloc[-2] = dernière fermée).

    1. Bullish Engulfing  : bougie haussière avale la précédente baissière → BUY
    2. Bearish Engulfing  : bougie baissière avale la précédente haussière → SELL
    3. Momentum baissier  : 3 bougies baissières consécutives               → SELL
    4. Momentum haussier  : 3 bougies haussières consécutives               → BUY

    Retourne : "BUY", "SELL" ou None
    """
    if len(df) < 4:
        return None

    # !! Utilise uniquement les bougies FERMÉES (ignorer la bougie en cours df.iloc[-1])
    c3   = df.iloc[-4]   # 3 bougies avant
    c2   = df.iloc[-3]   # 2 bougies avant
    prev = df.iloc[-2]   # bougie fermée N-1
    curr = df.iloc[-1]   # bougie fermée N   ← dernière FERMÉE (pas la bougie en cours)
    # Note : avec copy_rates_from_pos offset=1, df.iloc[-1] est bien la dernière fermée

    min_body   = params["min_body_ratio"]
    min_engulf = params["min_engulf_ratio"]

    prev_body  = abs(prev["close"] - prev["open"])
    prev_range = prev["high"] - prev["low"]
    curr_body  = abs(curr["close"] - curr["open"])
    curr_range = curr["high"] - curr["low"]

    if prev_range == 0 or curr_range == 0:
        return None

    prev_bearish = prev["close"] < prev["open"]
    prev_bullish = prev["close"] > prev["open"]
    curr_bullish = curr["close"] > curr["open"]
    curr_bearish = curr["close"] < curr["open"]

    # ── 1. Bullish Engulfing ──────────────────────────────
    if prev_bearish and curr_bullish:
        if curr_body / prev_range < min_body:
            pass  # corps trop petit
        else:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            if engulf_ratio >= min_engulf and curr["close"] >= prev["open"]:
                return "BUY"

    # ── 2. Bearish Engulfing ──────────────────────────────
    if prev_bullish and curr_bearish:
        if curr_body / prev_range < min_body:
            pass
        else:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            if engulf_ratio >= min_engulf and curr["close"] <= prev["open"]:
                return "SELL"

    # ── 3. Momentum : 3 bougies consécutives dans le même sens ──
    c3_bear = c3["close"] < c3["open"]
    c2_bear = c2["close"] < c2["open"]
    curr_bear_mom = curr["close"] < curr["open"]

    c3_bull = c3["close"] > c3["open"]
    c2_bull = c2["close"] > c2["open"]
    curr_bull_mom = curr["close"] > curr["open"]

    if c3_bear and c2_bear and curr_bear_mom:
        # Vérifie que les clôtures descendent progressivement
        if curr["close"] < c2["close"] < c3["close"]:
            return "SELL"

    if c3_bull and c2_bull and curr_bull_mom:
        if curr["close"] > c2["close"] > c3["close"]:
            return "BUY"

    return None


# ============================================================
#  SIGNAL TRIPLE CONFIRMATION  (EMA50 + EMA9/21 + Engulfing)
# ============================================================

def get_signal(df: pd.DataFrame, ind: dict, eng_params: dict) -> dict:
    """
    Signal valide uniquement si les 3 conditions sont réunies :

    BUY  : Prix > EMA50  ET  EMA9 croise EMA21 haussier  ET  Bullish Engulfing (ou momentum)
    SELL : Prix < EMA50  ET  EMA9 croise EMA21 baissier   ET  Bearish Engulfing (ou momentum)

    Retourne : {"signal": "BUY"|"SELL"|None, "trend": ..., "cross": ..., "engulf": ...}
    """
    ma   = get_ma_context(df, ind)
    engulf = detect_engulfing(df, eng_params)

    signal = None

    if ma["trend"] == "BULLISH" and ma["cross"] == "BUY" and engulf == "BUY":
        signal = "BUY"
    elif ma["trend"] == "BEARISH" and ma["cross"] == "SELL" and engulf == "SELL":
        signal = "SELL"

    return {
        "signal":   signal,
        "trend":    ma["trend"],
        "cross":    ma["cross"],
        "engulf":   engulf,
        "sma_fast": ma["sma_fast"],
        "sma_slow": ma["sma_slow"],
    }


# ============================================================
#  SIGNAL DE RETOURNEMENT (sortie anticipée)
# ============================================================

def detect_reversal(df: pd.DataFrame, current_direction: str, params: dict) -> bool:
    """
    Détecte un signal de retournement opposé à la position ouverte.

    Si on est en BUY  et qu'un Bearish Engulfing apparaît → True (sortir)
    Si on est en SELL et qu'un Bullish Engulfing apparaît → True (sortir)
    """
    signal = detect_engulfing(df, params)

    if current_direction == "BUY"  and signal == "SELL":
        return True
    if current_direction == "SELL" and signal == "BUY":
        return True

    return False


# ============================================================
#  CALCUL SL / TP EN DOLLARS
# ============================================================

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


def compute_sl_tp(signal: str, entry: float, atr: float,
                  sl_atr_mult: float, digits: int = 2) -> tuple:
    """
    Calcule SL et TP basés sur ATR.
    Le lot sera calibré pour que le SL = exactement X% du capital.
    """
    sl_dist = atr * sl_atr_mult

    if signal == "BUY":
        sl = round(entry - sl_dist, digits)
        tp = round(entry + sl_dist, digits)   # RR 1:1 (contrôlé par sortie anticipée)
    else:
        sl = round(entry + sl_dist, digits)
        tp = round(entry - sl_dist, digits)

    return sl, tp, sl_dist


def compute_lot(risk_usd: float, sl_distance: float, symbol_info) -> float:
    """
    Calcule le lot pour risquer exactement risk_usd sur ce trade.
    risk_usd    : ex. 100 ($)
    sl_distance : distance SL en prix (ex. 200 pour BTC)
    """
    if symbol_info is None or sl_distance <= 0:
        return symbol_info.volume_min if symbol_info else 0.01

    # Valeur d'1 lot pour 1 unité de prix
    tick_value = symbol_info.trade_tick_value
    tick_size  = symbol_info.trade_tick_size

    value_per_unit = tick_value / tick_size  # valeur par 1 point de prix

    lot = risk_usd / (sl_distance * value_per_unit)
    lot = round(lot, 2)
    lot = max(symbol_info.volume_min, min(lot, symbol_info.volume_max))

    return lot
