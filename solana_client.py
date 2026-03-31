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

    async with httpx.AsyncClient(timeout=30) as client:
        r_accounts, r_supply = await _batch_rpc(client, rpc_url, [
            {"method": "getTokenLargestAccounts", "params": [mint, {"commitment": "finalized"}]},
            {"method": "getTokenSupply", "params": [mint]},
        ])

    total_supply = float(r_supply["result"]["value"]["uiAmount"] or 0)
    raw_accounts = r_accounts["result"]["value"][:limit]

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
    logger.debug(f"Top 10 holders {mint[:8]}...: {top10_pct:.2f}%")

    return TopHoldersResult(
        token_address=mint,
        total_supply=total_supply,
        top10_combined_pct=round(top10_pct, 4),
        holders=holders,
    )


async def _batch_rpc(client: httpx.AsyncClient, url: str, calls: list) -> list:
    """Kirim beberapa RPC call sekaligus (batch)."""
    batch = [{"jsonrpc": "2.0", "id": i + 1, **call} for i, call in enumerate(calls)]
    resp = await client.post(url, json=batch)
    resp.raise_for_status()
    results = sorted(resp.json(), key=lambda x: x["id"])
    return results
