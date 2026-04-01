import json
import os
import asyncio
from dataclasses import dataclass, asdict
from typing import List, Optional
 
TRACKER_FILE = os.path.join(os.path.dirname(__file__), "tracked_channels.json")
 
_lock = asyncio.Lock()
 
 
@dataclass
class TrackedChannel:
    channel_id: int
    username: str
    goal: str
    keywords: List[str]
    owner_id: int
    cadence: str = "immediate"  # one of: "immediate", "daily", "weekly"
 
 
def _load() -> List[dict]:
    if not os.path.exists(TRACKER_FILE):
        return []
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)
 
 
def _normalize_id(cid: int) -> int:
    """
    Приводит channel_id к единому виду.
    Telethon иногда возвращает -100XXXXXXXXX, иногда просто XXXXXXXXX.
    Убираем префикс -100 чтобы всегда сравнивать одинаково.
    """
    s = str(abs(cid))
    if s.startswith("100") and len(s) > 10:
        return int(s[3:])
    return int(s)
 
 
def _save(data: List[dict]) -> None:
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
 
 
def add_channel(channel: TrackedChannel) -> bool:
    """
    Добавляет канал в трекер.
    Возвращает True если добавлен, False если уже существует у этого пользователя.
    """
    data = _load()
 
    # Проверяем дубликат по channel_id + owner_id (каждый юзер может трекать один канал один раз)
    if any(c["channel_id"] == channel.channel_id and c["owner_id"] == channel.owner_id for c in data):
        print(f"[TRACKER] @{channel.username} уже отслеживается пользователем {channel.owner_id}")
        return False
 
    data.append(asdict(channel))
    _save(data)
    print(f"[TRACKER] @{channel.username} добавлен — цель: {channel.goal}, ключевые слова: {channel.keywords}, каденс: {channel.cadence}")
    return True
 
 
def remove_channel(channel_id: int, owner_id: int) -> bool:
    """
    Удаляет канал из трекера по channel_id + owner_id.
    Возвращает True если удалён, False если не найден.
    """
    data = _load()
    new_data = [c for c in data if not (c["channel_id"] == channel_id and c["owner_id"] == owner_id)]
 
    if len(new_data) == len(data):
        print(f"[TRACKER] Канал {channel_id} не найден у пользователя {owner_id}")
        return False
 
    _save(new_data)
    print(f"[TRACKER] Канал {channel_id} удалён у пользователя {owner_id}")
    return True
 
 
def get_channel(channel_id: int) -> Optional[TrackedChannel]:
    """
    Возвращает первый TrackedChannel по channel_id или None.
    Используется когда приходит новый пост — проверить отслеживаем ли мы этот канал.
    """
    data = _load()
    norm_incoming = _normalize_id(channel_id)
    print(f"[TRACKER] get_channel: incoming={channel_id} normalized={norm_incoming}")
    for c in data:
        if _normalize_id(c["channel_id"]) == norm_incoming:
            return TrackedChannel(**c)
    return None
 
 
def get_channel_by_owner(channel_id: int, owner_id: int) -> Optional[TrackedChannel]:
    """
    Возвращает TrackedChannel по channel_id + owner_id или None.
    """
    data = _load()
    norm_incoming = _normalize_id(channel_id)
    for c in data:
        if _normalize_id(c["channel_id"]) == norm_incoming and c["owner_id"] == owner_id:
            return TrackedChannel(**c)
    return None
 
 
def list_channels() -> List[TrackedChannel]:
    """
    Возвращает все отслеживаемые каналы.
    """
    return [TrackedChannel(**c) for c in _load()]
    """
    return [TrackedChannel(**c) for c in _load()]
