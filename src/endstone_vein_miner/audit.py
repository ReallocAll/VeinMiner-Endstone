"""Fail-closed Tianyan SQLite logging for additional blocks, without modifying Tianyan.

Tianyan's published C++ API has no write method. This version-specific adapter targets
its existing LOGDATA schema and is disabled for MySQL or unknown schemas. Every extra
break must have an acknowledged pending row *before* a world write.
"""

import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

COLUMNS = (
    "uuid",
    "id",
    "name",
    "pos_x",
    "pos_y",
    "pos_z",
    "world",
    "obj_id",
    "obj_name",
    "time",
    "type",
    "data",
    "status",
)


class TianyanAudit:
    def __init__(self, plugins_dir: Path):
        root = plugins_dir / "tianyan_data"
        self.db_path = root / "ty_data.db"
        self.config_path = root / "config.json"
        self.healthy = False
        self.error: str | None = None

    def refresh(self) -> bool:
        self.healthy = False
        if not self.db_path.is_file() or not self.config_path.is_file():
            self.error = "Tianyan 数据库或配置不存在"
            return False
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or config.get("database_type") != "sqlite":
                raise ValueError("Tianyan 未启用 SQLite 后端")
            with sqlite3.connect(self.db_path, timeout=0.25) as db:
                columns = tuple(row[1] for row in db.execute("PRAGMA table_info(LOGDATA)"))
                if columns != COLUMNS:
                    raise ValueError("Tianyan LOGDATA 数据库结构不兼容")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.error = str(exc)
            return False
        self.error = None
        self.healthy = True
        return True

    def prepare(self, player: str, dimension: str, pos: tuple[int, int, int], block_id: str, states: str) -> str:
        if not self.healthy:
            raise RuntimeError("Tianyan 审计未就绪")
        uid = str(uuid4())
        with sqlite3.connect(self.db_path, timeout=0.25) as db:
            db.execute(
                "INSERT INTO LOGDATA (uuid,id,name,pos_x,pos_y,pos_z,world,obj_id,obj_name,"
                "time,type,data,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    uid,
                    "minecraft:player",
                    player,
                    *pos,
                    dimension,
                    block_id,
                    "",
                    int(time.time()),
                    "block_break",
                    states,
                    "veinminer_pending",
                ),
            )
        return uid

    def finish(self, uid: str, *, success: bool) -> None:
        if not self.healthy:
            raise RuntimeError("Tianyan 审计未就绪")
        status = "" if success else "canceled"
        with sqlite3.connect(self.db_path, timeout=0.25) as db:
            updated = db.execute("UPDATE LOGDATA SET status=? WHERE uuid=?", (status, uid))
            if updated.rowcount != 1:
                raise RuntimeError("Tianyan 审计记录消失")
