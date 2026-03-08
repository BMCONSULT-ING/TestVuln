import time
import logging
import MetaTrader5 as mt5
import pandas as pd

from config3 import MT5_CONFIG, SYMBOLS, TIMEFRAME, INDICATORS, ENGULFING, DYNAMIC_SLTP, RISK3, BOT3
from strategy3 import get_signal, get_dynamic_sltp, detect_reversal, compute_lot

# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BOT3["log_file"], encoding="utf-8"),
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


# ============================================================
#  CONNEXION
# ============================================================

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


# ============================================================
#  DONNEES
# ============================================================

def get_ohlcv(symbol: str, bars: int = 200) -> pd.DataFrame:
    tf    = TF_MAP.get(TIMEFRAME, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 1, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# ============================================================
#  ORDRES
# ============================================================

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
        "magic":        BOT3["magic_number"],
        "comment":      "SMC_DynSLTP",
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
        "magic":        BOT3["magic_number"],
        "comment":      "DynSLTP_Close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"  POSITION FERMEE | P&L: {position.profit:.2f} USD")
        return True
    log.warning(f"  FERMETURE ECHOUEE | Code:{result.retcode}")
    return False


# ============================================================
#  ETAT
# ============================================================

def make_state() -> dict:
    return {"phase": "IDLE", "direction": None, "ticket": None}


# ============================================================
#  BOUCLE PRINCIPALE
# ============================================================

def run():
    log.info("=" * 65)
    log.info("BOT 3 | SMA20/50 + Engulfing + SL/TP Dynamiques (Swing)")
    log.info("=" * 65)

    if not connect():
        return

    risk_usd = RISK3["capital"] * (RISK3["risk_pct"] / 100)
    log.info(f"Risk/Trade: ${risk_usd:.0f} | RR minimum: {DYNAMIC_SLTP['min_rr']}")

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
                        info = mt5.symbol_info(symbol)
                        sltp = get_dynamic_sltp(df, signal, price, DYNAMIC_SLTP, info.digits)

                        # Filtre RR minimum
                        if sltp["rr"] < DYNAMIC_SLTP["min_rr"]:
                            log.info(
                                f"  -> Setup rejeté | RR:{sltp['rr']} < "
                                f"min:{DYNAMIC_SLTP['min_rr']} | "
                                f"SL:{sltp['sl']:.2f} TP:{sltp['tp']:.2f}"
                            )
                            continue

                        lot = compute_lot(risk_usd, sltp["sl_dist"], info)

                        log.info(
                            f"  -> ENTREE {signal} | "
                            f"SL:{sltp['sl']:.2f} TP:{sltp['tp']:.2f} | "
                            f"RR:1:{sltp['rr']} | Lot:{lot} | "
                            f"Methode:{sltp['method']}"
                        )

                        ticket = place_order(symbol, signal, lot, sltp["sl"], sltp["tp"])
                        if ticket:
                            state["phase"]     = "IN_TRADE"
                            state["direction"] = signal
                            state["ticket"]    = ticket

                # ── IN_TRADE ─────────────────────────────────────────
                elif state["phase"] == "IN_TRADE":
                    positions = mt5.positions_get(symbol=symbol) or []
                    bot_pos   = [p for p in positions if p.magic == BOT3["magic_number"]]

                    if not bot_pos:
                        log.info(f"{symbol} | Trade ferme (SL/TP) | Retour IDLE")
                        states[symbol] = make_state()
                        continue

                    pos = bot_pos[0]
                    log.info(
                        f"{symbol} | {state['direction']} actif | "
                        f"P&L:{pos.profit:+.2f} USD | Prix:{price:.2f}"
                    )

                    # Signal de retournement -> fermeture + re-entree
                    if detect_reversal(df, state["direction"], ENGULFING):
                        log.info(f"  -> Retournement detecte ! Fermeture...")
                        if close_position(pos):
                            new_signal = "SELL" if state["direction"] == "BUY" else "BUY"
                            info       = mt5.symbol_info(symbol)
                            sltp       = get_dynamic_sltp(df, new_signal, price, DYNAMIC_SLTP, info.digits)

                            if sltp["rr"] >= DYNAMIC_SLTP["min_rr"]:
                                lot    = compute_lot(risk_usd, sltp["sl_dist"], info)
                                log.info(
                                    f"  -> Re-entree {new_signal} | "
                                    f"SL:{sltp['sl']:.2f} TP:{sltp['tp']:.2f} | RR:1:{sltp['rr']}"
                                )
                                ticket = place_order(symbol, new_signal, lot, sltp["sl"], sltp["tp"])
                                if ticket:
                                    state["direction"] = new_signal
                                    state["ticket"]    = ticket
                                else:
                                    states[symbol] = make_state()
                            else:
                                log.info(f"  -> Re-entree annulee | RR:{sltp['rr']} trop faible")
                                states[symbol] = make_state()

        except KeyboardInterrupt:
            log.info("Bot arrete.")
            break
        except Exception as e:
            log.error(f"Erreur: {e}", exc_info=True)

        time.sleep(BOT3["check_interval"])

    mt5.shutdown()


if __name__ == "__main__":
    run()
