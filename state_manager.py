"""
Menyimpan dan memuat state bot ke disk (state.json).

State yang disimpan:
- initial_value: nilai USD saat posisi pertama kali terdeteksi (untuk hitung P&L)
- pnl_notified: threshold P&L yang sudah pernah dinotifikasi (hindari spam)
- holder_notified: threshold holder % yang sudah pernah dinotifikasi
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "state.json")


def _load() -> dict:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Gagal load state: {e}")
        return {}


def _save(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


class StateManager:
    def __init__(self):
        self._state: dict = _load()

    def _pos_key(self, position_address: str) -> str:
        return f"pos_{position_address}"

    def get_initial_value(self, position_address: str) -> float | None:
        """Ambil nilai USD awal posisi (saat pertama kali terdeteksi)."""
        return self._state.get(self._pos_key(position_address), {}).get("initial_value")

    def set_initial_value(self, position_address: str, value_usd: float):
        """Simpan nilai USD awal posisi."""
        key = self._pos_key(position_address)
        if key not in self._state:
            self._state[key] = {}
        self._state[key]["initial_value"] = value_usd
        _save(self._state)
        logger.info(f"Initial value disimpan untuk {position_address[:8]}...: ${value_usd:.2f}")

    def get_pnl_notified(self, position_address: str) -> set[str]:
        """Ambil set threshold P&L yang sudah dinotifikasi (misal: '+3', '-3')."""
        key = self._pos_key(position_address)
        return set(self._state.get(key, {}).get("pnl_notified", []))

    def mark_pnl_notified(self, position_address: str, threshold_key: str):
        """Tandai bahwa threshold P&L ini sudah dinotifikasi."""
        key = self._pos_key(position_address)
        if key not in self._state:
            self._state[key] = {}
        notified = set(self._state[key].get("pnl_notified", []))
        notified.add(threshold_key)
        self._state[key]["pnl_notified"] = list(notified)
        _save(self._state)

    def reset_pnl_notified(self, position_address: str):
        """Reset notifikasi P&L (jika posisi baru terbuka atau P&L balik ke normal)."""
        key = self._pos_key(position_address)
        if key in self._state:
            self._state[key]["pnl_notified"] = []
            _save(self._state)

    def get_holder_notified(self, token_address: str) -> set[str]:
        """Ambil set threshold holder yang sudah dinotifikasi (misal: '30', '35')."""
        key = f"holder_{token_address}"
        return set(self._state.get(key, {}).get("notified", []))

    def mark_holder_notified(self, token_address: str, threshold_key: str):
        """Tandai bahwa threshold holder ini sudah dinotifikasi."""
        key = f"holder_{token_address}"
        if key not in self._state:
            self._state[key] = {}
        notified = set(self._state[key].get("notified", []))
        notified.add(threshold_key)
        self._state[key]["notified"] = list(notified)
        _save(self._state)

    def cleanup_closed_positions(self, active_addresses: set[str]):
        """Hapus state posisi yang sudah ditutup."""
        closed_keys = [
            k for k in self._state
            if k.startswith("pos_") and k[4:] not in active_addresses
        ]
        for k in closed_keys:
            logger.info(f"Posisi ditutup, hapus state: {k}")
            del self._state[k]
        if closed_keys:
            _save(self._state)
