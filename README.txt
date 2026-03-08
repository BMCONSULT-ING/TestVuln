================================================================
  TRADING BOT - VANTAGE MT5
  Compte Demo : 24341433 | Serveur : VantageInternational-Demo
================================================================

STRUCTURE DES BOTS
------------------

1. bot_smc_btc.py        → Stratégie SMC avancée sur BTCUSD
   config.py             → Config SMC
   strategy.py           → Logique SMC

   Fonctionnement :
   - Top-Down Analysis : H4 + H1 (bias) + M5 (entrée)
   - Détecte BOS (Break of Structure)
   - Attend retracement sur Order Block (OB) ou Fair Value Gap (FVG)
   - Filtre Premium / Discount zones + OTE Fibonacci (61.8-78.6%)
   - SL/TP basé sur ATR (SL:1x, TP:3x)
   - RR 1:3

   Lancer : python bot_smc_btc.py


2. bot_btc.py            → SMA20/50 + Engulfing sur BTCUSD (SL/TP FIXE)
   config_btc.py
   strategy_btc.py

   Fonctionnement :
   - Timeframe : M15
   - Signal : SMA20 croise SMA50 (Phase 15) + Engulfing + Momentum
   - SL = 1x ATR | TP = 1x ATR (RR 1:1)
   - Sortie anticipée si signal de retournement détecté
   - Re-entrée automatique dans l'autre sens

   Lancer : python bot_btc.py


3. bot_btc_dynamic.py    → SMA20/50 + Engulfing sur BTCUSD (SL/TP DYNAMIQUE)
   config_btc_dynamic.py
   strategy_btc_dynamic.py

   Fonctionnement :
   - Même signal que bot_btc.py
   - SL = dernier swing low/high (structure du marché)
   - TP = prochain swing high/low
   - Filtre RR minimum 1:1.5 (trade rejeté si RR insuffisant)
   - Fallback ATR si aucun swing trouvé

   Lancer : python bot_btc_dynamic.py


4. bot_gold.py           → SMA20/50 + Engulfing sur XAUUSD (SL/TP DYNAMIQUE)
   config_gold.py
   strategy_btc_dynamic.py (partagé)

   Fonctionnement :
   - Même logique que bot_btc_dynamic.py
   - Optimisé pour XAUUSD (buffer 0.05%)
   - Timeframe : M15
   - RR minimum : 1:1.5

   Lancer : python bot_gold.py


5. bot_gold_fixed.py     → SMA20/50 + Engulfing sur XAUUSD (SL/TP FIXE)
   config_gold_fixed.py
   strategy_btc.py (partagé)

   Fonctionnement :
   - Même signal que bot_gold.py
   - SL = 1x ATR | TP = 2x ATR (RR 1:2 fixe)
   - Plus simple, moins adaptatif

   Lancer : python bot_gold_fixed.py


INDICATEUR DE BASE (testé)
---------------------------
   Fast MA  : SMA 20  | Price: Close | Phase: 15 | Shift: 0
   Slow MA  : SMA 50  | Price: Close | Phase: 15 | Shift: 0
   Signal   : Croisement (Crossing)
   Couleur  : Trend (SMA20 > SMA50 = haussier)


PARAMETRES DE RISQUE
---------------------
   Capital de référence : $1000
   Risque par trade     : 10% = $100 max de perte
   Magic numbers uniques par bot (évite les conflits) :
     bot_smc_btc     → 20240101
     bot_btc         → 20240202
     bot_btc_dynamic → 20240303
     bot_gold        → 20240404
     bot_gold_fixed  → 20240405


INSTALLATION
-------------
   pip install -r requirements.txt
   (MetaTrader5, pandas, numpy)


IMPORTANT
----------
   - MT5 doit être ouvert et connecté au compte demo
   - Activer "Algo Trading" dans MT5 (bouton en haut)
   - Les bots peuvent tourner simultanément dans des terminaux séparés
   - Logs sauvegardés : bot_smc_btc.log, bot_btc.log, bot_btc_dynamic.log,
                        bot_gold.log, bot_gold_fixed.log


PROCHAINES AMELIORATIONS POSSIBLES
-------------------------------------
   - Backtesting sur données historiques
   - Dashboard de suivi en temps réel
   - Notifications Telegram/Email sur les trades
   - Optimisation automatique des paramètres
   - Ajout d'autres paires (EURUSD, GBPUSD, NASDAQ...)

================================================================
