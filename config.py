"""
Configuración global del sistema de swing trading.
Estrategia: RSI(2) Trend Pullback con ATR Trailing Stop.
Los parámetros de capital y fechas se pasan por CLI en main.py.
"""

# --- Indicadores ---
SMA_TREND = 200             # filtro de tendencia alcista
RSI_PERIOD = 2              # RSI ultra-corto para detectar pullbacks
ATR_PERIOD = 14             # volatilidad para stops y position sizing

# --- Señal de entrada ---
RSI_ENTRY_THRESHOLD = 10    # entrar cuando RSI(2) < este valor
GAP_DOWN_LIMIT = 0.95       # rechazar entrada si close < close_ant * este valor

# --- Gestión del riesgo ---
RISK_PER_TRADE = 0.01       # 1% del capital por operación
MAX_POSITIONS = 5           # máximo de posiciones abiertas simultáneas
ATR_STOP_MULT = 2.0         # stop-loss fijo = entrada - ATR * este multiplicador
ATR_TRAIL_MULT = 2.5        # trailing stop = max_close - ATR * este multiplicador
ATR_TRAIL_TRIGGER = 1.0     # activar trailing cuando ganancia >= ATR * este valor
MAX_HOLD_DAYS = 10          # time stop: cerrar si lleva N días abierta

# --- Defaults de CLI ---
DEFAULT_CAPITAL = 10_000.0          # EUR
DEFAULT_START_DATE = "2010-01-01"
DEFAULT_END_DATE = "2025-01-01"
DEFAULT_TICKER = "AAPL"

# --- Datos ---
CACHE_DIR = "cache"                 # carpeta local para cachear datos descargados
