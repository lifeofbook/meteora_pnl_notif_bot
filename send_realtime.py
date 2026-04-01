"""Kirim notifikasi real-time berdasarkan data aktual dari LPAgent + Helius."""
import asyncio
from telegram import Bot
from config import Config
from monitor import _build_message, Monitor
import meteora_client as meteora
import solana_client as solana

SKIP_HOLDER_MINTS = {
    "So11111111111111111111111111111111111111112",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

async def main():
    Config.validate()
    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
    monitor = Monitor(bot)

    print("Mengambil data posisi dari LPAgent...")
    positions = await meteora.get_positions(Config.WALLET_ADDRESS, Config.LPAGENT_API_KEY)
    if not positions:
        print("Tidak ada posisi aktif.")
        return

    holders_cache = {}
    if Config.HELIUS_API_KEY:
        mints = (
            {p.token0_address for p in positions} |
            {p.token1_address for p in positions}
        ) - SKIP_HOLDER_MINTS
        results = await asyncio.gather(
            *[solana.get_top_holders(m, Config.HELIUS_API_KEY) for m in mints],
            return_exceptions=True,
        )
        for mint, result in zip(mints, results):
            if not isinstance(result, Exception):
                holders_cache[mint] = result

    for pos in positions:
        holders_x = holders_cache.get(pos.token0_address)
        holders_y = holders_cache.get(pos.token1_address)
        print(f"Mengirim notifikasi untuk {pos.pair_name} | P&L: {pos.pnl_pct_sol:+.4f}%")
        msg = _build_message(pos, "📊 Status Real-time (manual trigger)", holders_x, holders_y)
        await monitor.send(msg)
        await asyncio.sleep(1)

    print("Selesai! Cek Telegram kamu.")

asyncio.run(main())
