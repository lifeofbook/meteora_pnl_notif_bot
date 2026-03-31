"""
Entry point bot notifikasi Meteora DLMM.

Mode lokal (loop):  python main.py
Mode GitHub Actions: python main.py --once
"""

import argparse
import asyncio
import logging
import sys

from telegram import Bot
from telegram.error import TelegramError

from config import Config
from monitor import Monitor

# Di GitHub Actions tidak ada file, stream saja
handlers = [logging.StreamHandler(sys.stdout)]
try:
    handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)


async def verify_telegram(bot: Bot) -> bool:
    try:
        me = await bot.get_me()
        logger.info(f"Bot terkoneksi: @{me.username}")
        await bot.get_chat(Config.TELEGRAM_CHAT_ID)
        return True
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        return False


async def main(once: bool = False):
    try:
        Config.validate()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

    if not await verify_telegram(bot):
        logger.error("Gagal terhubung ke Telegram.")
        sys.exit(1)

    logger.info(f"Wallet: {Config.WALLET_ADDRESS}")
    logger.info(f"P&L threshold: ±{Config.PNL_THRESHOLD}%")
    logger.info(f"Helius holders: {'aktif' if Config.HELIUS_API_KEY else 'nonaktif'}")

    monitor = Monitor(bot)

    if once:
        logger.info("Mode: single run (GitHub Actions)")
        await monitor.run_once()
    else:
        logger.info(f"Mode: loop setiap {Config.CHECK_INTERVAL}s")
        await monitor.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Jalankan sekali lalu keluar (untuk GitHub Actions)")
    args = parser.parse_args()

    try:
        asyncio.run(main(once=args.once))
    except KeyboardInterrupt:
        logger.info("Bot dihentikan.")
