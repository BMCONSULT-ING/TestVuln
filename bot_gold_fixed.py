import time
import logging
import MetaTrader5 as mt5
import pandas as pd

from config_gold_fixed import MT5_CONFIG, SYMBOLS, TIMEFRAME, INDICATORS, ENGULFING, RISK_GOLD_FIXED, BOT_GOLD_FIXED
from strategy_btc import get_signal, detect_reversal, compute_atr, compute_sl_tp, compute_lot

# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BOT_GOLD_FIXED["log_file"], encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
}


def connect() -> bool:
    if not mt5.initialize():
        log.error("Echec initialisation MT5")
        return False
    if not mt5.login(MT5_CONFIG["login"], MT5_CONFIG["password"], MT5_CONFIG["server"]):
        log.error(f"Echec connexion : {mt5.last_error()}")
        mt5.shutdown()
        return False
    info = mt5.account_info()
    log.info(f"Connecte | {info.login} | Balance: {info.balance} {info.currency}")
    return True


def get_ohlcv(symbol: str, bars: int = 200) -> pd.DataFrame:
    tf    = TF_MAP.get(TIMEFRAME, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 1, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def place_order(symbol: str, signal: str, lot: float, sl: float, tp: float) -> int:
    tick  = mt5.symbol_info_tick(symbol)
    price = tick.ask if signal == "BUY" else tick.bid
    otype = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lot,
        "type":         otype,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "magic":        BOT_GOLD_FIXED["magic_number"],
        "comment":      "Gold_Fixed",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(
            f"  ORDRE OK | {signal} {symbol} | Lot:{lot} | "
            f"Prix:{price:.2f} | SL:{sl:.2f} | TP:{tp:.2f}"
        )
        return result.order
    else:
        log.warning(f"  ORDRE ECHOUE | Code:{result.retcode} | {result.comment}")
        return 0


def close_position(position) -> bool:
    symbol = position.symbol
    is_buy = position.type == mt5.ORDER_TYPE_BUY
    otype  = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    tick   = mt5.symbol_info_tick(symbol)
    price  = tick.bid if is_buy else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       position.volume,
        "type":         otype,
        "position":     position.ticket,
        "price":        price,
        "magic":        BOT_GOLD_FIXED["magic_number"],
        "comment":      "Gold_Fixed_Close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"  POSITION FERMEE | P&L: {position.profit:.2f} USD")
        return True
    log.warning(f"  FERMETURE ECHOUEE | Code:{result.retcode}")
    return False


def make_state() -> dict:
    return {"phase": "IDLE", "direction": None, "ticket": None}


def run():
    log.info("=" * 65)
    log.info("BOT GOLD FIXE | XAUUSD | SMA20/50 + Engulfing + ATR SL/TP")
    log.info("=" * 65)

    if not connect():
        return

    risk_usd = RISK_GOLD_FIXED["capital"] * (RISK_GOLD_FIXED["risk_pct"] / 100)
    log.info(f"Symbole: XAUUSD | Risk/Trade: ${risk_usd:.0f} | SL:1xATR | TP:2xATR")

    states = {s: make_state() for s in SYMBOLS}

    while True:
        try:
            for symbol in SYMBOLS:

                df = get_ohlcv(symbol)
                if df.empty:
                    continue

                tick  = mt5.symbol_info_tick(symbol)
                price = tick.bid
                state = states[symbol]

                # ── IDLE ─────────────────────────────────────────────
                if state["phase"] == "IDLE":
                    result = get_signal(df, INDICATORS, ENGULFING)
                    signal = result["signal"]

                    log.info(
                        f"{symbol} | Prix:{price:.2f} | "
                        f"SMA20:{result['sma_fast']:.2f} SMA50:{result['sma_slow']:.2f} | "
                        f"Trend:{result['trend']} Cross:{result['cross'] or '-'} "
                        f"Engulf:{result['engulf'] or '-'} | Signal:{signal or 'AUCUN'}"
                    )

                    if signal:
                        atr  = compute_atr(df)
                        info = mt5.symbol_info(symbol)
                        sl, tp, sl_dist = compute_sl_tp(
                            signal, price, atr,
                            RISK_GOLD_FIXED["sl_atr_mult"], info.digits
                        )
                        # Override TP avec tp_atr_mult
                        if signal == "BUY":
                            tp = round(price + atr * RISK_GOLD_FIXED["tp_atr_mult"], info.digits)
                        else:
                            tp = round(price - atr * RISK_GOLD_FIXED["tp_atr_mult"], info.digits)

                        lot = compute_lot(risk_usd, sl_dist, info)

                        log.info(
                            f"  -> ENTREE {signal} | "
                            f"SL:{sl:.2f} TP:{tp:.2f} | RR:1:2 | Lot:{lot}"
                        )

                        ticket = place_order(symbol, signal, lot, sl, tp)
                        if ticket:
                            state["phase"]     = "IN_TRADE"
                            state["direction"] = signal
                            state["ticket"]    = ticket

                # ── IN_TRADE ─────────────────────────────────────────
                elif state["phase"] == "IN_TRADE":
                    positions = mt5.positions_get(symbol=symbol) or []
                    bot_pos   = [p for p in positions if p.magic == BOT_GOLD_FIXED["magic_number"]]

                    if not bot_pos:
                        log.info(f"{symbol} | Trade ferme (SL/TP) | Retour IDLE")
                        states[symbol] = make_state()
                        continue

                    pos = bot_pos[0]
                    log.info(
                        f"{symbol} | {state['direction']} actif | "
                        f"P&L:{pos.profit:+.2f} USD | Prix:{price:.2f}"
                    )

                    if detect_reversal(df, state["direction"], ENGULFING):
                        log.info(f"  -> Retournement detecte ! Fermeture...")
                        if close_position(pos):
                            new_signal = "SELL" if state["direction"] == "BUY" else "BUY"
                            atr  = compute_atr(df)
                            info = mt5.symbol_info(symbol)
                            sl, tp, sl_dist = compute_sl_tp(
                                new_signal, price, atr,
                                RISK_GOLD_FIXED["sl_atr_mult"], info.digits
                            )
                            if new_signal == "BUY":
                                tp = round(price + atr * RISK_GOLD_FIXED["tp_atr_mult"], info.digits)
                            else:
                                tp = round(price - atr * RISK_GOLD_FIXED["tp_atr_mult"], info.digits)

                            lot = compute_lot(risk_usd, sl_dist, info)
                            log.info(f"  -> Re-entree {new_signal} | SL:{sl:.2f} TP:{tp:.2f}")
                            ticket = place_order(symbol, new_signal, lot, sl, tp)
                            if ticket:
                                state["direction"] = new_signal
                                state["ticket"]    = ticket
                            else:
                                states[symbol] = make_state()

        except KeyboardInterrupt:
            log.info("Bot arrete.")
            break
        except Exception as e:
            log.error(f"Erreur: {e}", exc_info=True)

        time.sleep(BOT_GOLD_FIXED["check_interval"])

    mt5.shutdown()


if __name__ == "__main__":
    run()
