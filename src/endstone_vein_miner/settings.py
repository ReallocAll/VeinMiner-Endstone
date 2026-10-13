"""Small, fail-safe per-player preferences store."""

import json
from pathlib import Path

DEFAULT_SETTINGS = {
    "enabled": False,
    "require_sneak": True,
    "ores": True,
    "logs": False,
    "leaves": False,
    "plants": False,
}
SETTING_KEYS = tuple(DEFAULT_SETTINGS)


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self._players: dict[str, dict[str, bool]] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._players = {}
            return

        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("玩家设置文件格式无效")

        players: dict[str, dict[str, bool]] = {}
        for player_id, values in data.items():
            if not isinstance(player_id, str) or not isinstance(values, dict):
                raise ValueError("玩家设置文件格式无效")
            current = DEFAULT_SETTINGS.copy()
            for key in SETTING_KEYS:
                if key in values:
                    if type(values[key]) is not bool:
                        raise ValueError(f"玩家设置类型错误: {player_id}/{key}")
                    current[key] = values[key]
            players[player_id] = current
        self._players = players

    def get(self, player_id: str) -> dict[str, bool]:
        return self._players.get(player_id, DEFAULT_SETTINGS).copy()

    def enabled(self, player_id: str) -> bool:
        return self._players.get(player_id, DEFAULT_SETTINGS)["enabled"]

    def set(self, player_id: str, key: str, value: bool) -> None:
        if key not in DEFAULT_SETTINGS or type(value) is not bool:
            raise ValueError("无效设置")
        if self.get(player_id)[key] == value:
            return
        updated = self._players.copy()
        state = self.get(player_id)
        state[key] = value
        updated[player_id] = state

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            temp_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)
        self._players = updated

    def toggle(self, player_id: str, key: str) -> None:
        self.set(player_id, key, not self.get(player_id)[key])
