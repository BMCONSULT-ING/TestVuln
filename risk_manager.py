import MetaTrader5 as mt5


def calculate_lot_size(symbol: str, balance: float, risk_pct: float, sl_pips: float) -> float:
    """
    Calcule la taille de lot selon le risque défini.
    risk_pct : % du capital à risquer (ex: 1.0 pour 1%)
    sl_pips  : Distance du Stop Loss en pips
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 0.01

    risk_amount = balance * (risk_pct / 100)
    pip_value = symbol_info.trade_tick_value / symbol_info.trade_tick_size * symbol_info.point

    if pip_value <= 0 or sl_pips <= 0:
        return 0.01

    lot = risk_amount / (sl_pips * pip_value)

    # Respecter les limites du broker
    lot = round(lot, 2)
    lot = max(symbol_info.volume_min, min(lot, symbol_info.volume_max))

    return lot


def count_open_trades(magic: int) -> int:
    """Compte les positions ouvertes par ce bot."""
    positions = mt5.positions_get()
    if positions is None:
        return 0
    return sum(1 for p in positions if p.magic == magic)


def get_sl_tp(signal: str, entry: float, atr: float, sl_mult: float, tp_ratio: float, symbol: str):
    """Calcule SL et TP basés sur ATR."""
    symbol_info = mt5.symbol_info(symbol)
    digits = symbol_info.digits if symbol_info else 5

    sl_distance = atr * sl_mult
    tp_distance = sl_distance * tp_ratio

    if signal == "BUY":
        sl = round(entry - sl_distance, digits)
        tp = round(entry + tp_distance, digits)
    else:
        sl = round(entry + sl_distance, digits)
        tp = round(entry - tp_distance, digits)

    sl_pips = sl_distance / (symbol_info.point * 10) if symbol_info else sl_distance * 10000

    return sl, tp, sl_pips
