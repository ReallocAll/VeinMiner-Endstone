"""Small persisted server-wide mining limit (0 keeps category defaults)."""

import json
from pathlib import Path

OPTIONS = (0, 24, 64, 128, 256)
DEFAULT_BY_CATEGORY = {"ores": 24, "logs": 160, "leaves": 24, "plants": 24}


class ServerLimits:
    def __init__(self, path: Path):
        self.path = path
        self.override = 0

    def load(self) -> None:
        if not self.path.exists():
            self.override = 0
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("max_blocks")) is not int:
            raise ValueError("连锁上限配置无效")
        value = data["max_blocks"]
        if value not in OPTIONS:
            raise ValueError("连锁上限配置无效")
        self.override = value

    def for_category(self, category: str) -> int:
        return self.override or DEFAULT_BY_CATEGORY[category]

    def set(self, value: int) -> None:
        if type(value) is not int or value not in OPTIONS:
            raise ValueError("连锁上限无效")
        if value == self.override:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.write_text(json.dumps({"max_blocks": value}) + "\n", encoding="utf-8")
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)
        self.override = value
