# Trading Bot - EMA Crossover + RSI | Vantage MT5

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Ouvre `config.py` et modifie :
- `login` : ton numéro de compte MT5 Vantage
- `password` : ton mot de passe MT5
- `server` : le serveur Vantage (visible dans MT5 → Fichier → Connexion)

## Lancer le bot

```bash
python bot.py
```

## Structure

```
trading_bot/
├── bot.py           # Boucle principale
├── strategy.py      # Logique EMA + RSI
├── risk_manager.py  # Calcul lot size, SL/TP
├── config.py        # Configuration
└── requirements.txt
```

## Paramètres importants (config.py)

| Paramètre | Défaut | Description |
|---|---|---|
| risk_per_trade | 1% | % du capital risqué par trade |
| max_trades | 3 | Trades simultanés max |
| sl_atr_multiplier | 1.5 | Distance SL en multiple d'ATR |
| tp_ratio | 2.0 | Ratio Risk/Reward (1:2) |

## Prérequis

- MetaTrader 5 installé et connecté à Vantage
- Python 3.8+
- Compte Vantage actif (démo ou live)
