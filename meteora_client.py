"""
LPAgent API client untuk data posisi Meteora DLMM.
Docs: https://docs.lpagent.io/api-reference/introduction
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LPAGENT_API = "https://api.lpagent.io/open-api/v1"


@dataclass
class PositionData:
    position_address: str
    pool_address: str
    pair_name: str
    # Token info
    token0_address: str
    token0_symbol: str
    token0_decimals: int
    token1_address: str
    token1_symbol: str
    token1_decimals: int
    # Jumlah token saat ini
    amount0: float
    amount1: float
    # Fee belum di-claim (claimable)
    fee0_uncollected: float
    fee1_uncollected: float
    fee_usd_uncollected: float
    fee_usd_collected: float
    # Komponen formula P&L (dalam SOL)
    # PnL = (current_balance + withdraw + claimable_fee + claimed_fee) - deposit
    current_balance_sol: float   # Current Balance
    deposit_sol: float           # All-time Deposits
    withdraw_sol: float          # All-time Withdraw
    claimable_fee_sol: float     # Claimable Fees (belum di-claim)
    claimed_fee_sol: float       # Claimed Fees (sudah di-claim)
    # P&L hasil kalkulasi
    pnl_sol: float
    pnl_pct_sol: float
    # Nilai USD (untuk referensi)
    current_value_usd: float
    pnl_usd: float
    # Harga token
    price0_usd: float
    price1_usd: float
    # Price range [lower, upper, current]
    price_lower: Optional[float]
    price_upper: Optional[float]
    price_current: Optional[float]


async def get_positions(wallet_address: str, api_key: str) -> list[PositionData]:
    """Ambil semua posisi Meteora DLMM yang sedang buka dari LPAgent."""
    headers = {
        "x-api-key": api_key,
        "accept": "application/json",
    }
    url = f"{LPAGENT_API}/lp-positions/opening"
    params = {"owner": wallet_address}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    positions = []
    for item in data.get("data", []):
        try:
            pos = _parse(item)
            if pos:
                positions.append(pos)
        except Exception as e:
            logger.warning(f"Gagal parse posisi {item.get('tokenId', '?')}: {e}")

    logger.info(f"Ditemukan {len(positions)} posisi aktif")
    return positions


def _parse(item: dict) -> Optional[PositionData]:
    if item.get("status") != "Open":
        return None

    t0 = item.get("token0Info", {})
    t1 = item.get("token1Info", {})
    current = item.get("current", {})
    pnl_data = item.get("pnl", {})
    price_range = item.get("priceRange", [None, None, None])

    pair_name = f"{t0.get('token_symbol', 'TOKEN0')}-{t1.get('token_symbol', 'TOKEN1')}"

    # Komponen formula P&L
    current_balance_sol = float(item.get("valueNative", 0))
    deposit_sol        = float(item.get("inputNative", 0))
    withdraw_sol       = float(item.get("outputNative", 0))
    claimable_fee_sol  = float(item.get("unCollectedFeeNative", 0))
    claimed_fee_sol    = float(item.get("collectedFeeNative", 0))

    # PnL (SOL) = (Current Balance + All-time Withdraw + Claimable Fees + Claimed Fees) - All-time Deposits
    pnl_sol = (current_balance_sol + withdraw_sol + claimable_fee_sol + claimed_fee_sol) - deposit_sol
    pnl_pct_sol = (pnl_sol / deposit_sol * 100) if deposit_sol != 0 else 0.0

    return PositionData(
        position_address=item.get("tokenId", item.get("position", "")),
        pool_address=item.get("pool", ""),
        pair_name=item.get("pairName") or pair_name,
        token0_address=item.get("token0", ""),
        token0_symbol=t0.get("token_symbol", "TOKEN0"),
        token0_decimals=int(item.get("decimal0", t0.get("token_decimals", 6))),
        token1_address=item.get("token1", ""),
        token1_symbol=t1.get("token_symbol", "TOKEN1"),
        token1_decimals=int(item.get("decimal1", t1.get("token_decimals", 9))),
        amount0=float(current.get("amount0Adjusted", 0)),
        amount1=float(current.get("amount1Adjusted", 0)),
        fee0_uncollected=float(item.get("unCollectedFee0", 0)),
        fee1_uncollected=float(item.get("unCollectedFee1", 0)),
        fee_usd_uncollected=float(item.get("unCollectedFee", 0)),
        fee_usd_collected=float(item.get("collectedFee", 0)),
        current_balance_sol=current_balance_sol,
        deposit_sol=deposit_sol,
        withdraw_sol=withdraw_sol,
        claimable_fee_sol=claimable_fee_sol,
        claimed_fee_sol=claimed_fee_sol,
        pnl_sol=pnl_sol,
        pnl_pct_sol=pnl_pct_sol,
        current_value_usd=float(item.get("currentValue", 0)),
        pnl_usd=float(pnl_data.get("value", 0)),
        price0_usd=float(item.get("price0", 0)),
        price1_usd=float(item.get("price1", 0)),
        price_lower=float(price_range[0]) if price_range[0] is not None else None,
        price_upper=float(price_range[1]) if len(price_range) > 1 and price_range[1] is not None else None,
        price_current=float(price_range[2]) if len(price_range) > 2 and price_range[2] is not None else None,
    )
