"""Test kirim notifikasi dummy ke Telegram."""
import asyncio
from monitor import _build_message, Monitor
from meteora_client import PositionData
from telegram import Bot
from config import Config

# Dummy: deposit 2.5 SOL, sekarang 2.5763 SOL → +3.05%
# PnL = (2.5688 + 0 + 0.00103 + 0) - 2.5 = +0.07 SOL
dummy_pos = PositionData(
    position_address="2bmgXjp6t6c9b27DxdQFccdAjzMAprSsSjpt8gA2dEDH",
    pool_address="AGCBHFULSCgbukocriy15e2T3LaU1UiKHB2KEwdXovG4",
    pair_name="abcdefg-SOL",
    token0_address="89S7oVB4hui8ceJqhHreWB7fcxdthfvoB7z2pfJtpump",
    token0_symbol="abcdefg",
    token0_decimals=6,
    token1_address="So11111111111111111111111111111111111111112",
    token1_symbol="SOL",
    token1_decimals=9,
    amount0=132.20,
    amount1=2.497,
    fee0_uncollected=3.857,
    fee1_uncollected=0.000075,
    fee_usd_uncollected=0.0061,
    fee_usd_collected=0.0,
    current_balance_sol=2.5688,
    deposit_sol=2.5000,
    withdraw_sol=0.0,
    claimable_fee_sol=0.00103,
    claimed_fee_sol=0.0,
    pnl_sol=0.06983,       # (2.5688 + 0 + 0.00103 + 0) - 2.5
    pnl_pct_sol=2.7932,    # 0.06983 / 2.5 * 100
    current_value_usd=208.15,
    pnl_usd=6.16,
    price0_usd=0.001582,
    price1_usd=81.12,
    price_lower=0.0001664,
    price_upper=0.0016742,
    price_current=0.0015616,
)

async def main():
    Config.validate()
    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
    monitor = Monitor(bot)

    print("Kirim notif 1: P&L +3%...")
    msg1 = _build_message(dummy_pos, "P&L menyentuh +3%! 🚀")
    await monitor.send(msg1)
    await asyncio.sleep(1)

    print("Kirim notif 2: P&L -3%...")
    # PnL = (2.4236 + 0 + 0.00103 + 0) - 2.5 = -0.0754
    neg_pos = PositionData(**{
        **dummy_pos.__dict__,
        "current_balance_sol": 2.4236,
        "pnl_sol": -0.07537,
        "pnl_pct_sol": -3.0148,
        "current_value_usd": 195.83,
        "pnl_usd": -6.16,
    })
    msg2 = _build_message(neg_pos, "P&L menyentuh -3%! ⚠️")
    await monitor.send(msg2)

    print("Selesai! Cek Telegram kamu.")

asyncio.run(main())
