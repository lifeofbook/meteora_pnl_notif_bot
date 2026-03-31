"""
Solana RPC client untuk data top token holders.
Pakai Helius free RPC: https://dashboard.helius.dev (gratis, tanpa CC)
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HolderInfo:
    rank: int
    address: str
    amount: float
    percentage: float


@dataclass
class TopHoldersResult:
    token_address: str
    total_supply: float
    top10_combined_pct: float
    holders: list[HolderInfo]


async def get_top_holders(mint: str, helius_api_key: str, limit: int = 10) -> TopHoldersResult:
    """Ambil top N token holders via Solana RPC (Helius free)."""
    rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        # Call terpisah (tidak batch) agar kompatibel dengan Helius free plan
        r_accounts = await client.post(rpc_url, headers=headers, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [mint, {"commitment": "finalized"}]
        })
        r_accounts.raise_for_status()

        r_supply = await client.post(rpc_url, headers=headers, json={
            "jsonrpc": "2.0", "id": 2,
            "method": "getTokenSupply",
            "params": [mint]
        })
        r_supply.raise_for_status()

    supply_data = r_supply.json()
    accounts_data = r_accounts.json()

    if "error" in accounts_data:
        raise Exception(f"RPC error: {accounts_data['error']}")
    if "error" in supply_data:
        raise Exception(f"RPC error: {supply_data['error']}")

    total_supply = float(supply_data["result"]["value"]["uiAmount"] or 0)
    raw_accounts = accounts_data["result"]["value"][:limit]

    holders = []
    for i, acc in enumerate(raw_accounts):
        amount = float(acc.get("uiAmount") or 0)
        pct = (amount / total_supply * 100) if total_supply > 0 else 0.0
        holders.append(HolderInfo(
            rank=i + 1,
            address=acc.get("address", ""),
            amount=amount,
            percentage=round(pct, 4),
        ))

    top10_pct = sum(h.percentage for h in holders)
    logger.info(f"Top 10 holders {mint[:8]}...: {top10_pct:.2f}%")

    return TopHoldersResult(
        token_address=mint,
        total_supply=total_supply,
        top10_combined_pct=round(top10_pct, 4),
        holders=holders,
    )
