"""
Configuración global del sistema de swing trading.
Estrategias: RSI(2) Trend Pullback, CANSLIM (William O'Neil), Minervini SEPA.
Los parámetros de capital y fechas se pasan por CLI en main.py.
"""

# --- Indicadores ---
SMA_TREND = 200             # filtro de tendencia alcista
RSI_PERIOD = 2              # RSI ultra-corto para detectar pullbacks
ATR_PERIOD = 14             # volatilidad para stops y position sizing

# --- Señal de entrada ---
MIN_PRICE = 10.0            # excluir penny stocks (precio mínimo para operar)
RSI_ENTRY_THRESHOLD = 10    # entrar cuando RSI(2) < este valor
RSI_EXIT_THRESHOLD = 90     # cerrar cuando RSI(2) > este valor (salida por fortaleza)
GAP_DOWN_LIMIT = 0.95       # rechazar entrada si close < close_ant * este valor
MARKET_FILTER_TICKER = "SPY"    # ticker para filtro de régimen de mercado
MARKET_FILTER_SMA = 200         # SMA para determinar mercado alcista/bajista

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

# --- Comisiones y divisa ---
COMMISSION_PCT = 0.001      # 0.1% por operación (ida y vuelta = 0.2%)
SLIPPAGE_PCT = 0.0005       # 0.05% de slippage por ejecución
DEFAULT_COMMISSION_USD = 1.0  # comisión por defecto por operación (USD)
BASE_CURRENCY = "EUR"         # moneda base del inversor

# --- CANSLIM ---
CANSLIM_HIGH_PROXIMITY = 0.85      # N: precio >= 85% del máximo 52 semanas
CANSLIM_VOLUME_SURGE = 1.5         # S: volumen > 1.5x media 50 días
CANSLIM_RS_THRESHOLD = 1.0         # L: relative strength > 1.0 (supera SPY)
CANSLIM_MAX_HOLD_DAYS = 60         # CANSLIM es más position trading

# --- Minervini Trend Template (SEPA) ---
MINERVINI_SMA200_RISING_DAYS = 20   # SMA200 debe subir N días para confirmar tendencia
MINERVINI_MAX_PCT_FROM_HIGH = 25    # max % debajo del máximo 52 semanas
MINERVINI_MIN_PCT_FROM_LOW = 25     # min % encima del mínimo 52 semanas
MINERVINI_RSI_LOW = 30              # RSI(14) zona pullback: límite inferior
MINERVINI_RSI_HIGH = 60             # RSI(14) zona pullback: límite superior
MINERVINI_MAX_PCT_FROM_SMA21 = 8    # max % distancia desde SMA(21)
MINERVINI_ATR_STOP_MULT = 2.5      # stop-loss = entrada - ATR * mult
MINERVINI_ATR_TRAIL_MULT = 3.0     # trailing stop = max_close - ATR * mult
MINERVINI_ATR_TRAIL_TRIGGER = 2.0   # activar trailing cuando ganancia >= 2*ATR (dejar correr)
MINERVINI_MAX_HOLD_DAYS = 60        # hold largo para trend-following

# --- Datos ---
CACHE_DIR = "cache"                 # carpeta local para cachear datos descargados
SIGNALS_DIR = "signals_history"     # historial de señales diarias
