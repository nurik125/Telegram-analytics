import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional

TRACKER_FILE = "tracked_channels.json"

@dataclass
class TrackedChannel:
  channel_id: int
  username: str
  goal: str
  keywords: List[str]
  owner_id: int 

def _load() -> List[dict]:
    if not os.path.exists(TRACKER_FILE):
        return []
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: List[dict]) -> None:
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_channel(channel: TrackedChannel) -> bool:
    """
    Добавляет канал в трекер.
    Возвращает True если добавлен, False если уже существует.
    """
    data = _load()

    # проверяем дубликат по channel_id
    if any(c["channel_id"] == channel.channel_id for c in data):
        print(f"[TRACKER] @{channel.username} уже отслеживается")
        return False

    data.append(asdict(channel))
    _save(data)
    print(f"[TRACKER] @{channel.username} добавлен — цель: {channel.goal}, ключевые слова: {channel.keywords}")
    return True

def remove_channel(channel_id: int) -> bool:
    """
    Удаляет канал из трекера по channel_id.
    Возвращает True если удалён, False если не найден.
    """
    data = _load()
    new_data = [c for c in data if c["channel_id"] != channel_id]

    if len(new_data) == len(data):
        print(f"[TRACKER] Канал {channel_id} не найден")
        return False

    _save(new_data)
    print(f"[TRACKER] Канал {channel_id} удалён")
    return True


def get_channel(channel_id: int) -> Optional[TrackedChannel]:
    """
    Возвращает TrackedChannel по channel_id или None если не найден.
    Используется когда приходит новый пост — проверить отслеживаем ли мы этот канал.
    """
    data = _load()
    for c in data:
        if c["channel_id"] == channel_id:
            return TrackedChannel(**c)
    return None


def list_channels() -> List[TrackedChannel]:
    """
    Возвращает все отслеживаемые каналы.
    """
    return [TrackedChannel(**c) for c in _load()]
