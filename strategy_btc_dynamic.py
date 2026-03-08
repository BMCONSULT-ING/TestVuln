import pandas as pd


# ============================================================
#  MOVING AVERAGES  (SMA 20/50 + Phase smoothing)
# ============================================================

def compute_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def apply_phase_smooth(series: pd.Series, phase: int) -> pd.Series:
    if phase <= 1:
        return series
    return series.ewm(span=phase, adjust=False).mean()


def get_ma_context(df: pd.DataFrame, ind: dict) -> dict:
    price_col = ind.get("ma_price", "close")
    phase     = ind.get("ma_phase", 15)

    sma_fast = apply_phase_smooth(compute_sma(df[price_col], ind["ma_fast"]), phase)
    sma_slow = apply_phase_smooth(compute_sma(df[price_col], ind["ma_slow"]), phase)

    trend = "BULLISH" if sma_fast.iloc[-1] > sma_slow.iloc[-1] else "BEARISH"

    prev_diff = sma_fast.iloc[-2] - sma_slow.iloc[-2]
    curr_diff = sma_fast.iloc[-1] - sma_slow.iloc[-1]

    cross = None
    if prev_diff < 0 and curr_diff > 0:
        cross = "BUY"
    elif prev_diff > 0 and curr_diff < 0:
        cross = "SELL"

    return {
        "trend":    trend,
        "cross":    cross,
        "sma_fast": sma_fast.iloc[-1],
        "sma_slow": sma_slow.iloc[-1],
    }


# ============================================================
#  ENGULFING + MOMENTUM
# ============================================================

def detect_engulfing(df: pd.DataFrame, params: dict) -> str:
    if len(df) < 4:
        return None

    c3   = df.iloc[-4]
    c2   = df.iloc[-3]
    prev = df.iloc[-2]
    curr = df.iloc[-1]

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

    if prev_bearish and curr_bullish:
        if curr_body / prev_range >= min_body:
            if (curr_body / prev_body if prev_body > 0 else 0) >= min_engulf:
                if curr["close"] >= prev["open"]:
                    return "BUY"

    if prev_bullish and curr_bearish:
        if curr_body / prev_range >= min_body:
            if (curr_body / prev_body if prev_body > 0 else 0) >= min_engulf:
                if curr["close"] <= prev["open"]:
                    return "SELL"

    # Momentum : 3 bougies consécutives
    if all(df.iloc[i]["close"] < df.iloc[i]["open"] for i in [-4, -3, -2, -1]):
        if curr["close"] < c2["close"] < c3["close"]:
            return "SELL"
    if all(df.iloc[i]["close"] > df.iloc[i]["open"] for i in [-4, -3, -2, -1]):
        if curr["close"] > c2["close"] > c3["close"]:
            return "BUY"

    return None


# ============================================================
#  SWING HIGHS / LOWS
# ============================================================

def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> list:
    pivots = []
    for i in range(lookback, len(df) - lookback):
        if df["high"].iloc[i] == df["high"].iloc[i - lookback: i + lookback + 1].max():
            pivots.append(i)
    return pivots


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> list:
    pivots = []
    for i in range(lookback, len(df) - lookback):
        if df["low"].iloc[i] == df["low"].iloc[i - lookback: i + lookback + 1].min():
            pivots.append(i)
    return pivots


# ============================================================
#  SL / TP DYNAMIQUES
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


def get_dynamic_sltp(df: pd.DataFrame, signal: str, entry: float,
                     params: dict, digits: int = 2) -> dict:
    """
    Calcule SL et TP basés sur la structure du marché (swing highs/lows).

    BUY :
      SL = dernier swing low - buffer
      TP = prochain swing high au-dessus de l'entrée

    SELL :
      SL = dernier swing high + buffer
      TP = prochain swing low en-dessous de l'entrée

    Retourne : {sl, tp, sl_dist, tp_dist, rr, method}
    """
    lookback = params["swing_lookback"]
    buffer   = params["sl_buffer_pct"]
    atr      = compute_atr(df)

    sh_idx = find_swing_highs(df, lookback)
    sl_idx = find_swing_lows(df, lookback)

    sl = tp = None
    method = "swing"

    if signal == "BUY":
        # SL : dernier swing low sous l'entrée
        lows_below = [df["low"].iloc[i] for i in sl_idx if df["low"].iloc[i] < entry]
        if lows_below:
            nearest_low = max(lows_below)  # le plus proche sous l'entrée
            sl = round(nearest_low * (1 - buffer), digits)

        # TP : prochain swing high au-dessus de l'entrée
        highs_above = [df["high"].iloc[i] for i in sh_idx if df["high"].iloc[i] > entry]
        if highs_above:
            nearest_high = min(highs_above)  # le plus proche au-dessus
            tp = round(nearest_high * (1 - buffer), digits)

    elif signal == "SELL":
        # SL : dernier swing high au-dessus de l'entrée
        highs_above = [df["high"].iloc[i] for i in sh_idx if df["high"].iloc[i] > entry]
        if highs_above:
            nearest_high = min(highs_above)
            sl = round(nearest_high * (1 + buffer), digits)

        # TP : prochain swing low sous l'entrée
        lows_below = [df["low"].iloc[i] for i in sl_idx if df["low"].iloc[i] < entry]
        if lows_below:
            nearest_low = max(lows_below)
            tp = round(nearest_low * (1 + buffer), digits)

    # Fallback ATR si swing non trouvé
    if sl is None or tp is None:
        method = "atr_fallback"
        sl_dist_atr = atr * params["atr_mult_sl"]
        tp_dist_atr = atr * params["atr_mult_tp"]
        if signal == "BUY":
            sl = round(entry - sl_dist_atr, digits)
            tp = round(entry + tp_dist_atr, digits)
        else:
            sl = round(entry + sl_dist_atr, digits)
            tp = round(entry - tp_dist_atr, digits)

    sl_dist = abs(entry - sl)
    tp_dist = abs(tp - entry)
    rr      = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0

    return {
        "sl":      sl,
        "tp":      tp,
        "sl_dist": sl_dist,
        "tp_dist": tp_dist,
        "rr":      rr,
        "method":  method,
    }


# ============================================================
#  SIGNAL FINAL
# ============================================================

def get_signal(df: pd.DataFrame, ind: dict, eng_params: dict) -> dict:
    ma     = get_ma_context(df, ind)
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
#  RETOURNEMENT
# ============================================================

def detect_reversal(df: pd.DataFrame, current_direction: str, params: dict) -> bool:
    signal = detect_engulfing(df, params)
    if current_direction == "BUY"  and signal == "SELL":
        return True
    if current_direction == "SELL" and signal == "BUY":
        return True
    return False


# ============================================================
#  CALCUL LOT
# ============================================================

def compute_lot(risk_usd: float, sl_distance: float, symbol_info) -> float:
    if symbol_info is None or sl_distance <= 0:
        return symbol_info.volume_min if symbol_info else 0.01

    tick_value = symbol_info.trade_tick_value
    tick_size  = symbol_info.trade_tick_size
    value_per_unit = tick_value / tick_size

    lot = risk_usd / (sl_distance * value_per_unit)
    lot = round(lot, 2)
    lot = max(symbol_info.volume_min, min(lot, symbol_info.volume_max))
    return lot
