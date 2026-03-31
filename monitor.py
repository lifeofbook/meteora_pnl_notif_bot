"""
Loop utama monitoring: cek posisi Meteora via LPAgent dan top holders via Solana RPC.
Kirim notifikasi Telegram saat threshold P&L atau holder terpenuhi.
"""

import asyncio
import logging
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode

import meteora_client as meteora
import solana_client as solana
from config import Config
from meteora_client import PositionData
from solana_client import TopHoldersResult
from state_manager import StateManager

logger = logging.getLogger(__name__)


def _fmt(n: float, d: int = 4) -> str:
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n:,.2f}"
    return f"{n:.{d}f}"


def _sign(n: float) -> str:
    return "+" if n >= 0 else ""


def _pnl_emoji(pnl: float) -> str:
    if pnl >= Config.PNL_THRESHOLD:
        return "🟢"
    if pnl <= -Config.PNL_THRESHOLD:
        return "🔴"
    return "🟡"


def _e(text: str) -> str:
    """Escape semua karakter khusus MarkdownV2 Telegram."""
    for c in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(c, f"\\{c}")
    return text


def _build_message(
    pos: PositionData,
    alert_reason: str,
    holders_x: "TopHoldersResult | None" = None,
    holders_y: "TopHoldersResult | None" = None,
) -> str:
    pnl_sign = _sign(pos.pnl_pct_sol)
    emoji = _pnl_emoji(pos.pnl_pct_sol)
    pair = f"{pos.token0_symbol}-{pos.token1_symbol}"

    lines = [
        f"{emoji} *METEORA DLMM ALERT*",
        f"_{_e(alert_reason)}_",
        "",
        f"*Pair:* `{_e(pair)}`",
        f"*Posisi:* `{_e(pos.position_address[:8])}\\.\\.\\. `",
        "",
        f"💧 *Liquidity*",
        f"  {_e(pos.token0_symbol)}: `{_e(_fmt(pos.amount0))}`",
        f"  {_e(pos.token1_symbol)}: `{_e(_fmt(pos.amount1, 6))}` SOL",
        f"  Total: `{_e(_fmt(pos.current_balance_sol, 6))}` SOL \\(\\~\\${_e(_fmt(pos.current_value_usd, 2))}\\)",
        "",
        f"💰 *Claimable Fees*",
        f"  {_e(pos.token0_symbol)}: `{_e(_fmt(pos.fee0_uncollected))}`",
        f"  {_e(pos.token1_symbol)}: `{_e(_fmt(pos.fee1_uncollected, 6))}` SOL",
        f"  Total \\(SOL\\): `{_e(_fmt(pos.claimable_fee_sol, 8))}` SOL",
        "",
    ]

    if pos.price_lower is not None and pos.price_upper is not None:
        lines += [
            f"📊 *Price Range*",
            f"  Bawah:    `{_e(_fmt(pos.price_lower, 8))}`",
            f"  Atas:     `{_e(_fmt(pos.price_upper, 8))}`",
            f"  Sekarang: `{_e(_fmt(pos.price_current or 0, 8))}`",
            "",
        ]

    lines += [
        f"📈 *P&L \\(SOL\\)*",
        f"  _PnL \\= \\(Balance \\+ Withdraw \\+ Claimable \\+ Claimed\\) \\- Deposit_",
        f"  All\\-time Deposit:   `{_e(_fmt(pos.deposit_sol, 6))}` SOL",
        f"  Current Balance:    `{_e(_fmt(pos.current_balance_sol, 6))}` SOL",
        f"  All\\-time Withdraw: `{_e(_fmt(pos.withdraw_sol, 6))}` SOL",
        f"  Claimable Fees:     `{_e(_fmt(pos.claimable_fee_sol, 8))}` SOL",
        f"  Claimed Fees:       `{_e(_fmt(pos.claimed_fee_sol, 8))}` SOL",
        f"  ──────────────────────",
        f"  *P&L:* `{_e(pnl_sign + _fmt(pos.pnl_sol, 8))}` SOL",
        f"  *P&L %:* `{_e(pnl_sign + f'{pos.pnl_pct_sol:.4f}%')}`",
        "",
    ]

    for label, holders in [(pos.token0_symbol, holders_x), (pos.token1_symbol, holders_y)]:
        if holders and holders.holders:
            lines.append(
                f"👥 *Top 10 Holder {_e(label)}* "
                f"\\({_e(f'{holders.top10_combined_pct:.2f}')}% supply\\)"
            )
            for h in holders.holders[:10]:
                short = h.address[:6] + "\\.\\.\\." + h.address[-4:] if len(h.address) > 12 else h.address
                lines.append(f"  {h.rank}\\. `{short}` — {_e(f'{h.percentage:.2f}')}%")
            lines.append("")

    lines.append(f"_⏰ {_e(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}_")
    return "\n".join(lines)


class Monitor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.state = StateManager()
        self._holders_enabled = bool(Config.HELIUS_API_KEY)

    async def send(self, text: str):
        try:
            await self.bot.send_message(
                chat_id=Config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            logger.error(f"Gagal kirim pesan Telegram: {e}")
            try:
                plain = text.replace("*", "").replace("`", "").replace("_", "").replace("\\", "")
                await self.bot.send_message(chat_id=Config.TELEGRAM_CHAT_ID, text=plain)
            except Exception as e2:
                logger.error(f"Fallback juga gagal: {e2}")

    async def run(self):
        """Loop monitoring tanpa henti (untuk local / Railway)."""
        logger.info(f"Monitor dimulai. Cek setiap {Config.CHECK_INTERVAL}s")
        await self.bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text="✅ Meteora DLMM Bot aktif\\!\nMonitoring posisi dimulai\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        while True:
            try:
                await self._check_all()
            except Exception as e:
                logger.error(f"Error saat check: {e}", exc_info=True)
            await asyncio.sleep(Config.CHECK_INTERVAL)

    async def run_once(self):
        """Jalankan satu kali saja (untuk GitHub Actions cron)."""
        try:
            await self._check_all()
        except Exception as e:
            logger.error(f"Error saat check: {e}", exc_info=True)

    async def _check_all(self):
        logger.info("Mengecek posisi...")
        positions = await meteora.get_positions(Config.WALLET_ADDRESS, Config.LPAGENT_API_KEY)

        if not positions:
            logger.info("Tidak ada posisi aktif.")
            return

        self.state.cleanup_closed_positions({p.position_address for p in positions})

        # Fetch top holders paralel jika Helius key tersedia
        holders_cache: dict[str, TopHoldersResult | None] = {}
        if self._holders_enabled:
            mints = {p.token0_address for p in positions} | {p.token1_address for p in positions}
            results = await asyncio.gather(
                *[solana.get_top_holders(m, Config.HELIUS_API_KEY) for m in mints],
                return_exceptions=True,
            )
            for mint, result in zip(mints, results):
                if isinstance(result, Exception):
                    logger.warning(f"Gagal fetch holders {mint[:8]}: {result}")
                    holders_cache[mint] = None
                else:
                    holders_cache[mint] = result
        else:
            logger.debug("HELIUS_API_KEY tidak diset, skip pengecekan holders.")

        for pos in positions:
            await self._check_position(pos, holders_cache)

    async def _check_position(self, pos: PositionData, holders_cache: dict):
        logger.info(
            f"{pos.pair_name} | P&L: {_sign(pos.pnl_pct_sol)}{pos.pnl_pct_sol:.4f}% "
            f"({_sign(pos.pnl_sol)}{_fmt(pos.pnl_sol, 6)} SOL) | "
            f"Balance: {_fmt(pos.current_balance_sol, 6)} SOL"
        )
        holders_x = holders_cache.get(pos.token0_address)
        holders_y = holders_cache.get(pos.token1_address)

        await self._check_pnl(pos, holders_x, holders_y)
        if self._holders_enabled:
            await self._check_holders(pos, holders_x, holders_y)

    async def _check_pnl(self, pos, holders_x, holders_y):
        threshold = Config.PNL_THRESHOLD
        pnl = pos.pnl_pct_sol
        notified = self.state.get_pnl_notified(pos.position_address)

        alert_reason = None
        threshold_key = None

        if pnl >= threshold and f"+{threshold}" not in notified:
            alert_reason = f"P&L menyentuh +{threshold}%! 🚀"
            threshold_key = f"+{threshold}"
        elif pnl <= -threshold and f"-{threshold}" not in notified:
            alert_reason = f"P&L menyentuh -{threshold}%! ⚠️"
            threshold_key = f"-{threshold}"

        if alert_reason and threshold_key:
            msg = _build_message(pos, alert_reason, holders_x, holders_y)
            await self.send(msg)
            self.state.mark_pnl_notified(pos.position_address, threshold_key)

        if -threshold < pnl < threshold and notified:
            self.state.reset_pnl_notified(pos.position_address)

    async def _check_holders(self, pos, holders_x, holders_y):
        for token_addr, holders in [
            (pos.token0_address, holders_x),
            (pos.token1_address, holders_y),
        ]:
            if not holders:
                continue
            pct = holders.top10_combined_pct
            notified = self.state.get_holder_notified(token_addr)
            token_sym = pos.token0_symbol if token_addr == pos.token0_address else pos.token1_symbol

            for threshold in sorted(Config.HOLDER_THRESHOLDS):
                key = str(int(threshold))
                if pct >= threshold and key not in notified:
                    alert_reason = (
                        f"Top 10 holder {token_sym} pegang {pct:.2f}% supply "
                        f"(ambang {threshold}%) 🐋"
                    )
                    msg = _build_message(pos, alert_reason, holders_x, holders_y)
                    await self.send(msg)
                    self.state.mark_holder_notified(token_addr, key)
                    break
