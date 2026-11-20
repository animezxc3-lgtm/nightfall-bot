import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value or value.startswith("YOUR_"):
        raise RuntimeError(f"Переменная {name} не задана.")
    return value

def _int(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        if default is not None:
            return default
        raise RuntimeError(f"Переменная {name} обязательна")
    return int(raw)

@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    group_id: int
    creator_id: int
    rp_photo_token: str = ""
    applications_peer_id: int = 2000000011
    log_level: str = "INFO"

    main_chats: tuple[int, ...] = (2000000007, 2000000006, 2000000005, 2000000012, 2000000013, 2000000014)
    anarchy_chat: int = 2000000008
    casino_chat: int = 2000000009
    citadel_chat: int = 2000000004
    control_chat: int = 2000000015

    pin_community_link: str = "https://vk.ru/nightfa11"
    pin_rules_link: str = "https://vk.ru/@nightfa11-osnovnye-polozheniya-i-pravila-proekta"
    pin_casino_link: str = "https://vk.me/join/AZQ1d_4fuybFrKCTIpJBVO0Y"
    pin_anarchy_link: str = "https://vk.me/join/AZQ1dz_85ybXLVjKd6O3v2QJ"

    rp_albums: dict[str, int] = field(default_factory=lambda: {
        "обнять": 314310270, "поцеловать": 314310277, "пожать руку": 314310278,
        "погладить": 314310281, "ущипнуть": 314310285, "укусить": 314310286,
        "дать пять": 314310289, "пнуть": 314310291, "положить в дурку": 314310292,
        "посадить на бутылку": 314310296, "уснуть": 314310297, "разбудить": 314310299,
        "накормить": 314310300, "подарить": 314310301,
        "подрочить": 314892913, "секс": 314892915, "футджоб": 314892918,
        "принять душ": 314892920, "минет": 314892924, "куни": 314892925, "69": 314892928,
    })

    @property
    def extra_chats(self) -> tuple[int, ...]:
        return (self.anarchy_chat, self.casino_chat)

    @property
    def admin_chats(self) -> tuple[int, ...]:
        return (self.citadel_chat, self.control_chat, self.applications_peer_id)

    @property
    def all_bot_chats(self) -> tuple[int, ...]:
        return self.main_chats + self.extra_chats + self.admin_chats

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.db"

    @property
    def logs_dir(self) -> Path:
        return BASE_DIR / "logs"


def load_settings() -> Settings:
    return Settings(
        token=_require("VK_TOKEN"),
        group_id=_int("VK_GROUP_ID"),
        creator_id=_int("CREATOR_ID"),
        rp_photo_token=os.getenv("RP_PHOTO_TOKEN", "").strip(),
        applications_peer_id=_int("APPLICATIONS_PEER_ID", 2000000011),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


class _SettingsProxy:
    """Ленивая загрузка .env при первом обращении к settings.*"""

    def __getattr__(self, item: str) -> Any:
        return getattr(get_settings(), item)


# cast нужен, чтобы Pylance/Pyright видели поля Settings (token, db_path, ...)
settings: Settings = cast(Settings, _SettingsProxy())
