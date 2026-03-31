"""
Birdeye API client untuk data top holders dan harga token.

Dokumentasi: https://docs.birdeye.so
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BIRDEYE_API = "https://public-api.birdeye.so"


@dataclass
class HolderInfo:
    rank: int
    address: str
    amount: float
    percentage: float  # % dari total supply


@dataclass
class TopHoldersResult:
    token_address: str
    total_supply: float
    top10_combined_pct: float
    holders: list[HolderInfo]


async def get_top_holders(token_address: str, api_key: str, limit: int = 10) -> TopHoldersResult:
    """Ambil data top holders dari Birdeye."""
    headers = {
        "X-API-KEY": api_key,
        "x-chain": "solana",
        "accept": "application/json",
    }

    params = {
        "address": token_address,
        "offset": 0,
        "limit": limit,
    }

    url = f"{BIRDEYE_API}/defi/token_holder"
    logger.debug(f"Fetching top holders for {token_address}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    holders = []
    items = data.get("data", {}).get("items", [])
    total_supply = float(data.get("data", {}).get("totalSupply", 0))

    for i, item in enumerate(items[:limit]):
        amount = float(item.get("uiAmount", item.get("amount", 0)))
        pct = float(item.get("percentage", 0))

        # Jika API tidak return percentage langsung, hitung manual
        if pct == 0 and total_supply > 0:
            pct = (amount / total_supply) * 100

        holders.append(
            HolderInfo(
                rank=i + 1,
                address=item.get("address", item.get("owner", "")),
                amount=amount,
                percentage=round(pct, 4),
            )
        )

    top10_combined = sum(h.percentage for h in holders)

    return TopHoldersResult(
        token_address=token_address,
        total_supply=total_supply,
        top10_combined_pct=round(top10_combined, 4),
        holders=holders,
    )


async def get_token_price(token_address: str, api_key: str) -> float:
    """Ambil harga token dalam USD dari Birdeye."""
    headers = {
        "X-API-KEY": api_key,
        "x-chain": "solana",
        "accept": "application/json",
    }
    params = {"address": token_address}

    url = f"{BIRDEYE_API}/defi/price"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    price = data.get("data", {}).get("value", 0.0)
    return float(price)
