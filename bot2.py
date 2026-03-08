import time
import logging
import MetaTrader5 as mt5
import pandas as pd

from config2 import MT5_CONFIG, SYMBOLS, TIMEFRAME, INDICATORS, ENGULFING, RISK2, BOT2
from strategy2 import get_signal, detect_reversal, compute_atr, compute_sl_tp, compute_lot

# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BOT2["log_file"], encoding="utf-8"),
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
        log.error("Échec initialisation MT5")
        return False
    if not mt5.login(MT5_CONFIG["login"], MT5_CONFIG["password"], MT5_CONFIG["server"]):
        log.error(f"Échec connexion : {mt5.last_error()}")
        mt5.shutdown()
        return False
    info = mt5.account_info()
    log.info(f"Connecté | {info.login} | Balance: {info.balance} {info.currency}")
    return True


# ============================================================
#  DONNÉES
# ============================================================

def get_ohlcv(symbol: str, bars: int = 100) -> pd.DataFrame:
    tf = TF_MAP.get(TIMEFRAME, mt5.TIMEFRAME_M5)
    # offset=1 -> ignore la bougie en cours de formation, utilise uniquement les bougies fermées
    rates = mt5.copy_rates_from_pos(symbol, tf, 1, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# ============================================================
#  ENVOI D'ORDRE
# ============================================================

def place_order(symbol: str, signal: str, lot: float, sl: float, tp: float) -> int:
    """Retourne le ticket de l'ordre ou 0 si échec."""
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if signal == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lot,
        "type":         order_type,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "magic":        BOT2["magic_number"],
        "comment":      "Engulf_Scalp",
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
        log.warning(f"  ORDRE ÉCHOUÉ | Code:{result.retcode} | {result.comment}")
        return 0


def close_position(position) -> bool:
    """Ferme une position ouverte."""
    symbol     = position.symbol
    lot        = position.volume
    is_buy     = position.type == mt5.ORDER_TYPE_BUY
    order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    tick       = mt5.symbol_info_tick(symbol)
    price      = tick.bid if is_buy else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lot,
        "type":         order_type,
        "position":     position.ticket,
        "price":        price,
        "magic":        BOT2["magic_number"],
        "comment":      "Engulf_Scalp_Close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"  POSITION FERMÉE | P&L: {position.profit:.2f} USD")
        return True
    else:
        log.warning(f"  FERMETURE ÉCHOUÉE | Code:{result.retcode}")
        return False


# ============================================================
#  ÉTAT
# ============================================================

def make_state() -> dict:
    return {
        "phase":     "IDLE",   # IDLE | IN_TRADE
        "direction": None,
        "ticket":    None,
    }


# ============================================================
#  BOUCLE PRINCIPALE
# ============================================================

def run():
    log.info("=" * 60)
    log.info("ENGULFING SCALPING BOT  |  SL/TP 10% | Exit on Reversal")
    log.info("=" * 60)

    if not connect():
        return

    risk_usd    = RISK2["capital"] * (RISK2["risk_pct"] / 100)    # $100
    reward_usd  = RISK2["capital"] * (RISK2["reward_pct"] / 100)  # $100

    log.info(f"Risk/Trade: ${risk_usd:.0f} | Target: ${reward_usd:.0f}")

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

                # ── IDLE : triple confirmation EMA50 + EMA9/21 + Engulfing ──
                if state["phase"] == "IDLE":
                    result = get_signal(df, INDICATORS, ENGULFING)
                    signal = result["signal"]

                    log.info(
                        f"{symbol} | Prix:{price:.2f} | "
                        f"SMA20:{result['sma_fast']:.2f} SMA50:{result['sma_slow']:.2f} | "
                        f"Trend:{result['trend']} | "
                        f"Cross:{result['cross'] or '-'} | "
                        f"Engulf:{result['engulf'] or '-'} | "
                        f"Signal:{signal or 'AUCUN'}"
                    )

                    if signal:
                        atr  = compute_atr(df)
                        info = mt5.symbol_info(symbol)
                        sl, tp, sl_dist = compute_sl_tp(
                            signal, price, atr, RISK2["sl_atr_mult"], info.digits
                        )
                        lot = compute_lot(risk_usd, sl_dist, info)

                        log.info(
                            f"  -> ENTRÉE {signal} | "
                            f"SL:{sl:.2f} | TP:{tp:.2f} | Lot:{lot}"
                        )

                        ticket = place_order(symbol, signal, lot, sl, tp)
                        if ticket:
                            state["phase"]     = "IN_TRADE"
                            state["direction"] = signal
                            state["ticket"]    = ticket

                # ── IN_TRADE : surveille P&L + signal de retournement ─
                elif state["phase"] == "IN_TRADE":
                    positions = mt5.positions_get(symbol=symbol) or []
                    bot_pos   = [p for p in positions if p.magic == BOT2["magic_number"]]

                    # Trade fermé par SL ou TP automatiquement
                    if not bot_pos:
                        log.info(f"{symbol} | Trade fermé (SL/TP atteint) | Retour IDLE")
                        states[symbol] = make_state()
                        continue

                    pos = bot_pos[0]
                    log.info(
                        f"{symbol} | {state['direction']} actif | "
                        f"P&L: {pos.profit:+.2f} USD | Prix:{price:.2f}"
                    )

                    # ── Vérification signal de retournement ───────────
                    reversal = detect_reversal(df, state["direction"], ENGULFING)

                    if reversal:
                        log.info(f"  -> Signal de retournement détecté ! Fermeture...")
                        if close_position(pos):
                            # Re-entrée immédiate dans l'autre sens
                            new_signal = "SELL" if state["direction"] == "BUY" else "BUY"
                            atr        = compute_atr(df)
                            info       = mt5.symbol_info(symbol)
                            sl, tp, sl_dist = compute_sl_tp(
                                new_signal, price, atr, RISK2["sl_atr_mult"], info.digits
                            )
                            lot = compute_lot(risk_usd, sl_dist, info)

                            log.info(f"  -> Re-entrée {new_signal} | Prix:{price:.2f}")
                            ticket = place_order(symbol, new_signal, lot, sl, tp)

                            if ticket:
                                state["direction"] = new_signal
                                state["ticket"]    = ticket
                            else:
                                states[symbol] = make_state()

        except KeyboardInterrupt:
            log.info("Bot arrêté par l'utilisateur.")
            break
        except Exception as e:
            log.error(f"Erreur: {e}", exc_info=True)

        time.sleep(BOT2["check_interval"])

    mt5.shutdown()
    log.info("Connexion MT5 fermée.")


if __name__ == "__main__":
    run()
