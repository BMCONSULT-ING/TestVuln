import time
import logging
import MetaTrader5 as mt5
import pandas as pd

from config import MT5_CONFIG, SYMBOLS, TIMEFRAMES, RISK, BOT
from strategy import (
    get_market_structure, detect_fresh_bos,
    find_order_block, find_fvg,
    get_premium_discount, is_in_discount, is_in_premium, is_in_ote,
    price_in_zone, compute_atr,
)
from risk_manager import calculate_lot_size, get_sl_tp

# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BOT["log_file"]),
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
    "D1":  mt5.TIMEFRAME_D1,
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
    log.info(f"Connecté | {info.login} | Balance: {info.balance} {info.currency} | {info.server}")
    return True


# ============================================================
#  DONNÉES OHLCV
# ============================================================

def get_ohlcv(symbol: str, timeframe: str, bars: int = 200) -> pd.DataFrame:
    tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# ============================================================
#  ENVOI D'ORDRE
# ============================================================

def place_order(symbol: str, signal: str, lot: float, sl: float, tp: float) -> bool:
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if signal == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action":      mt5.TRADE_ACTION_DEAL,
        "symbol":      symbol,
        "volume":      lot,
        "type":        order_type,
        "price":       price,
        "sl":          sl,
        "tp":          tp,
        "magic":       BOT["magic_number"],
        "comment":     "SMC_Scalp",
        "type_time":   mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"  ORDRE OK | {signal} {symbol} | Lot:{lot} | Prix:{price:.2f} | SL:{sl:.2f} | TP:{tp:.2f}")
        return True
    else:
        log.warning(f"  ORDRE ÉCHOUÉ | {symbol} | Code:{result.retcode} | {result.comment}")
        return False


# ============================================================
#  ÉTAT INITIAL
# ============================================================

def make_state() -> dict:
    return {
        "phase":         "IDLE",   # IDLE | WAITING_ENTRY | IN_TRADE
        "direction":     None,     # BUY | SELL
        "ob":            None,     # Order Block zone
        "fvg":           None,     # Fair Value Gap zone
        "bos_level":     None,
        "ticks_waiting": 0,        # Compteur depuis le BOS
    }


# ============================================================
#  BOUCLE PRINCIPALE
# ============================================================

def run():
    log.info("=" * 60)
    log.info("SMC SCALPING BOT  |  HTF Bias (H4+H1) + BOS + OB + FVG")
    log.info("=" * 60)

    if not connect():
        return

    states = {s: make_state() for s in SYMBOLS}

    while True:
        try:
            balance = mt5.account_info().balance

            for symbol in SYMBOLS:

                # ── 1. DONNÉES MULTI-TF ───────────────────────────────
                df_h4 = get_ohlcv(symbol, TIMEFRAMES["bias_high"])
                df_h1 = get_ohlcv(symbol, TIMEFRAMES["bias_mid"])
                df_m5 = get_ohlcv(symbol, TIMEFRAMES["entry"])

                if df_h4.empty or df_h1.empty or df_m5.empty:
                    log.warning(f"{symbol} | Données manquantes, skip")
                    continue

                # ── 2. BIAS HTF (H4 + H1 doivent être alignés) ────────
                bias_h4 = get_market_structure(df_h4)
                bias_h1 = get_market_structure(df_h1)
                htf_bias = bias_h4 if (bias_h4 == bias_h1 and bias_h4 != "NEUTRAL") else None

                # ── 3. PREMIUM / DISCOUNT + OTE (sur H1) ─────────────
                pd_zones = get_premium_discount(df_h1)

                tick  = mt5.symbol_info_tick(symbol)
                price = tick.bid

                state = states[symbol]

                # Log des zones P/D
                if pd_zones:
                    zone_name = "DISCOUNT" if is_in_discount(price, pd_zones) else "PREMIUM"
                    ote_ok    = is_in_ote(price, pd_zones, htf_bias or "BULLISH")
                    log.info(
                        f"{symbol} | H4:{bias_h4} H1:{bias_h1} | "
                        f"Bias:{'✓ ' + htf_bias if htf_bias else '✗ NEUTRE'} | "
                        f"Zone:{zone_name}{' +OTE' if ote_ok else ''} | "
                        f"Eq:{pd_zones['equilibrium']:.2f} | Prix:{price:.2f} | Phase:{state['phase']}"
                    )
                else:
                    log.info(
                        f"{symbol} | H4:{bias_h4} H1:{bias_h1} | "
                        f"Bias:{'✓ ' + htf_bias if htf_bias else '✗ NEUTRE'} | "
                        f"Prix:{price:.2f} | Phase:{state['phase']}"
                    )

                # ── 4. MACHINE À ÉTATS ────────────────────────────────

                # ┌─ IDLE : cherche un BOS aligné avec le bias HTF ─────
                if state["phase"] == "IDLE":
                    if not htf_bias:
                        continue

                    bos_dir, bos_level, bos_idx = detect_fresh_bos(df_m5)

                    if bos_dir == "BULLISH" and htf_bias == "BULLISH":
                        # Filtre Premium/Discount : on veut être en DISCOUNT pour acheter
                        if pd_zones and not is_in_discount(price, pd_zones):
                            log.info(f"  → BOS BULLISH mais prix en PREMIUM → setup ignoré")
                            continue

                        ob  = find_order_block(df_m5, "BULLISH", bos_idx)
                        fvg = find_fvg(df_m5, "BULLISH", bos_idx)

                        if ob or fvg:
                            states[symbol].update({
                                "phase":     "WAITING_ENTRY",
                                "direction": "BUY",
                                "ob":        ob,
                                "fvg":       fvg,
                                "bos_level": bos_level,
                                "ticks_waiting": 0,
                            })
                            ob_str  = f"OB[{ob['bottom']:.2f}-{ob['top']:.2f}]"  if ob  else "OB:aucun"
                            fvg_str = f"FVG[{fvg['bottom']:.2f}-{fvg['top']:.2f}]" if fvg else "FVG:aucun"
                            log.info(f"  → BOS BULLISH @ {bos_level:.2f} | {ob_str} | {fvg_str} | Attente retracement...")

                    elif bos_dir == "BEARISH" and htf_bias == "BEARISH":
                        # Filtre Premium/Discount : on veut être en PREMIUM pour vendre
                        if pd_zones and not is_in_premium(price, pd_zones):
                            log.info(f"  → BOS BEARISH mais prix en DISCOUNT → setup ignoré")
                            continue

                        ob  = find_order_block(df_m5, "BEARISH", bos_idx)
                        fvg = find_fvg(df_m5, "BEARISH", bos_idx)

                        if ob or fvg:
                            states[symbol].update({
                                "phase":     "WAITING_ENTRY",
                                "direction": "SELL",
                                "ob":        ob,
                                "fvg":       fvg,
                                "bos_level": bos_level,
                                "ticks_waiting": 0,
                            })
                            ob_str  = f"OB[{ob['bottom']:.2f}-{ob['top']:.2f}]"  if ob  else "OB:aucun"
                            fvg_str = f"FVG[{fvg['bottom']:.2f}-{fvg['top']:.2f}]" if fvg else "FVG:aucun"
                            log.info(f"  → BOS BEARISH @ {bos_level:.2f} | {ob_str} | {fvg_str} | Attente retracement...")

                # ┌─ WAITING_ENTRY : attend le retracement sur OB ou FVG
                elif state["phase"] == "WAITING_ENTRY":
                    state["ticks_waiting"] += 1

                    # Invalidation : timeout après 20 ticks
                    if state["ticks_waiting"] > 20:
                        log.info(f"  → Setup invalidé (timeout 20 ticks) | Retour IDLE")
                        states[symbol] = make_state()
                        continue

                    in_ob  = price_in_zone(price, state["ob"])
                    in_fvg = price_in_zone(price, state["fvg"])

                    if in_ob or in_fvg:
                        # Bonus : vérifier si on est aussi dans l'OTE (setup premium)
                        in_ote = is_in_ote(price, pd_zones, state["direction"].replace("BUY","BULLISH").replace("SELL","BEARISH"))
                        zones  = []
                        if in_ob:  zones.append("OB")
                        if in_fvg: zones.append("FVG")
                        if in_ote: zones.append("OTE")
                        zone_type = "+".join(zones)

                        atr = compute_atr(df_m5)
                        sl, tp, sl_pips = get_sl_tp(
                            state["direction"], price, atr,
                            RISK["sl_atr_multiplier"], RISK["tp_ratio"], symbol,
                        )
                        lot = calculate_lot_size(symbol, balance, RISK["risk_per_trade"], sl_pips)

                        log.info(f"  → Prix dans {zone_type} {'⭐ CONFLUENCE MAX' if len(zones) >= 3 else '(confluence)'} | Entrée {state['direction']}")

                        if place_order(symbol, state["direction"], lot, sl, tp):
                            state["phase"] = "IN_TRADE"
                    else:
                        ob_str = f"OB[{state['ob']['bottom']:.2f}-{state['ob']['top']:.2f}]" if state["ob"] else ""
                        fvg_str = f"FVG[{state['fvg']['bottom']:.2f}-{state['fvg']['top']:.2f}]" if state["fvg"] else ""
                        log.info(f"  → Attente retracement ({state['ticks_waiting']}/20) | {ob_str} {fvg_str}")

                # ┌─ IN_TRADE : surveille jusqu'à fermeture SL/TP ──────
                elif state["phase"] == "IN_TRADE":
                    positions = mt5.positions_get(symbol=symbol) or []
                    bot_trades = [p for p in positions if p.magic == BOT["magic_number"]]

                    if not bot_trades:
                        log.info(f"  → Trade fermé (SL/TP) | Retour IDLE")
                        states[symbol] = make_state()
                    else:
                        p = bot_trades[0]
                        log.info(f"  → Trade actif | P&L: {p.profit:.2f} USD")

        except KeyboardInterrupt:
            log.info("Bot arrêté par l'utilisateur.")
            break
        except Exception as e:
            log.error(f"Erreur: {e}", exc_info=True)

        time.sleep(BOT["check_interval"])

    mt5.shutdown()
    log.info("Connexion MT5 fermée.")


if __name__ == "__main__":
    run()
