import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    WALLET_ADDRESS: str = os.getenv("WALLET_ADDRESS", "").strip()
    LPAGENT_API_KEY: str = os.getenv("LPAGENT_API_KEY", "").strip()
    HELIUS_API_KEY: str = os.getenv("HELIUS_API_KEY", "").strip()

    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "300"))
    PNL_THRESHOLD: float = float(os.getenv("PNL_THRESHOLD", "3.0"))
    HOLDER_THRESHOLDS: list[float] = [30.0, 35.0]

    @classmethod
    def validate(cls):
        required = {
            "TELEGRAM_BOT_TOKEN": cls.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_CHAT_ID": cls.TELEGRAM_CHAT_ID,
            "WALLET_ADDRESS": cls.WALLET_ADDRESS,
            "LPAGENT_API_KEY": cls.LPAGENT_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Variabel berikut wajib diisi di .env: {', '.join(missing)}")
