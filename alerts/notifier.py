"""
Envío de alertas por Telegram cuando se genera una señal de entrada.

Setup (una vez):
  1. Abre Telegram → busca @BotFather
  2. Escribe /newbot → elige un nombre → obtienes un TOKEN
  3. Escribe /start a tu propio bot para activarlo
  4. Obtén tu chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
  5. Copia TOKEN y CHAT_ID en el archivo .env del proyecto

Variables de entorno requeridas:
    TELEGRAM_TOKEN   — token del bot (ej. 123456:ABC-DEF...)
    TELEGRAM_CHAT_ID — tu chat_id numérico (ej. 987654321)
"""

import os
from typing import Optional


def _get_credentials() -> tuple[Optional[str], Optional[str]]:
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id


def send_message(text: str) -> bool:
    """
    Envía un mensaje de texto por Telegram.

    Args:
        text: mensaje a enviar (soporta Markdown básico)

    Returns:
        True si se envió correctamente, False en caso de error
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("[Telegram] TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados en .env")
        return False

    try:
        import telegram
        import asyncio

        bot = telegram.Bot(token=token)

        async def _send():
            async with bot:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                )

        # Evitar warning "Event loop is closed" en Windows
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(_send())
        return True
    except ImportError:
        print("[!] python-telegram-bot no instalado: pip install python-telegram-bot")
        return False
    except Exception as e:
        print(f"[!] Error enviando alerta Telegram: {e}")
        return False


def format_signal(signal: dict) -> str:
    """
    Formatea un diccionario de señal como mensaje Telegram.
    Usa bloque monospace para alinear los importes.
    """
    w = 10
    price = f"{signal['close']:.2f}"
    rsi = f"{signal['rsi2']:.1f}"
    stop = f"{signal['stop_loss']:.2f}"
    atr = f"{signal['atr']:.2f}"
    shares = str(signal['acciones'])
    cost = f"{signal['coste']:.2f}"
    risk = f"{signal['riesgo']:.2f}"

    nombre = signal.get('nombre', '')
    header = f"🟢 *{signal['ticker']}*"
    if nombre:
        header += f" — {nombre}"

    return (
        f"{header}\n\n"
        f"```\n"
        f"Precio    {price:>{w}}\n"
        f"RSI(2)    {rsi:>{w}}\n"
        f"Stop Loss {stop:>{w}}\n"
        f"ATR       {atr:>{w}}\n"
        f"Acciones  {shares:>{w}}\n"
        f"Coste     {cost:>{w}}\n"
        f"Riesgo    {risk:>{w}}\n"
        f"```"
    )


def format_signals_table(signals: list[dict]) -> str:
    """
    Formatea varias señales como tabla monospace alineada.
    """
    # Calcular anchos dinámicos
    tickers = [s["ticker"] for s in signals]
    wt = max(len(t) for t in tickers)
    wp = max(len(f"{s['close']:.2f}") for s in signals)
    ws = max(len(f"{s['stop_loss']:.2f}") for s in signals)
    wa = max(len(str(s["acciones"])) for s in signals)
    wc = max(len(f"{s['coste']:.2f}") for s in signals)

    header = (
        f"{'TICKER':<{wt}}  "
        f"{'PRECIO':>{wp}}  "
        f"{'STOP':>{ws}}  "
        f"{'ACC':>{wa}}  "
        f"{'COSTE':>{wc}}"
    )
    sep = "-" * len(header)

    rows = []
    for s in signals:
        rows.append(
            f"{s['ticker']:<{wt}}  "
            f"{s['close']:>{wp}.2f}  "
            f"{s['stop_loss']:>{ws}.2f}  "
            f"{str(s['acciones']):>{wa}}  "
            f"{s['coste']:>{wc}.2f}"
        )

    return "📋 *SEÑALES DE ENTRADA HOY*\n\n```\n" + header + "\n" + sep + "\n" + "\n".join(rows) + "\n```"


def send_signals(signals: list[dict]) -> None:
    """
    Envía una alerta por cada señal encontrada.
    Si hay muchas, las agrupa en un solo mensaje tabla.
    """
    if not signals:
        return

    if len(signals) <= 5:
        for sig in signals:
            send_message(format_signal(sig))
    else:
        send_message(format_signals_table(signals))
