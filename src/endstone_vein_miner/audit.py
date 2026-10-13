"""Fail-closed Tianyan SQLite logging for additional blocks, without modifying Tianyan.

Tianyan's published C++ API has no write method. This version-specific adapter targets
its existing LOGDATA schema and is disabled for MySQL or unknown schemas. Every extra
break must have an acknowledged pending row *before* a world write.
"""

import json
import re
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


def format_states(states: dict[str, bool | int | str]) -> str:
    """Return a command-compatible Bedrock block-state suffix for Tianyan rollback.

    Tianyan's /tyback constructs 'setblock <coords> <block_id><data>' without
    inserting whitespace before data. The leading space is intentional.
    """
    if not isinstance(states, dict):
        raise ValueError("未知的方块状态类型")
    if not states:
        return ""
    entries = []
    for key, value in sorted(states.items()):
        if not isinstance(key, str) or re.fullmatch(r"[a-z0-9_:]+", key) is None:
            raise ValueError("未知的方块状态名称")
        if type(value) is str and re.fullmatch(r"[a-z0-9_:-]+", value):
            encoded = json.dumps(value, ensure_ascii=True)
        elif type(value) is bool:
            encoded = "true" if value else "false"
        elif type(value) is int:
            encoded = str(value)
        else:
            raise ValueError("未知的方块状态值")
        entries.append(f"{json.dumps(key)}={encoded}")
    return " [" + ",".join(entries) + "]"


class TianyanAudit:
    def __init__(self, plugins_dir: Path):
        root = plugins_dir / "tianyan_data"
        self.db_path = root / "ty_data.db"
        self.config_path = root / "config.json"
        self.healthy = False
        self.error: str | None = None
        self._db: sqlite3.Connection | None = None
        self._db_identity: tuple[int, int] | None = None

    def close(self) -> None:
        self.healthy = False
        if self._db is not None:
            try:
                self._db.close()
            finally:
                self._db = None
                self._db_identity = None

    def refresh(self) -> bool:
        self.healthy = False
        try:
            if not self.db_path.is_file() or not self.config_path.is_file():
                raise ValueError("Tianyan 数据库或配置不存在")
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or config.get("database_type") != "sqlite":
                raise ValueError("Tianyan 未启用 SQLite 后端")
            if config.get("log_block_break") is not True:
                raise ValueError("Tianyan 方块破坏日志功能已关闭")

            stat = self.db_path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self._db is None or self._db_identity != identity:
                self.close()
                # mode=rw must not create a missing Tianyan database.
                self._db = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.05)
                self._db_identity = identity
            columns = tuple(row[1] for row in self._db.execute("PRAGMA table_info(LOGDATA)"))
            if columns != COLUMNS:
                raise ValueError("Tianyan LOGDATA 数据库结构不兼容")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.error = str(exc)
            self.close()
            return False
        self.error = None
        self.healthy = True
        return True

    def _connection(self) -> sqlite3.Connection:
        if not self.healthy or self._db is None:
            raise RuntimeError("Tianyan 审计未就绪")
        return self._db

    def prepare(self, player: str, dimension: str, pos: tuple[int, int, int], block_id: str, states: str) -> str:
        db = self._connection()
        uid = str(uuid4())
        # Each successful return means that the pending record has committed.
        with db:
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
        db = self._connection()
        status = "" if success else "canceled"
        # Remain separately committed so an engine rollback can mark one block
        # canceled without changing any other block's audit row.
        with db:
            updated = db.execute("UPDATE LOGDATA SET status=? WHERE uuid=?", (status, uid))
            if updated.rowcount != 1:
                raise RuntimeError("Tianyan 审计记录消失")
