"""Read-only Territory block-break permissions, adapted from Arborist's SQLite guard.

Territory uses `if_break` (not Arborist's `if_build`) for block removal.
The database is re-read at the beginning of each mine attempt, including WAL changes.
Any database, schema, configuration or permission-read failure denies all extra breaks.
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Claim:
    pos1: tuple[float, float, float]
    pos2: tuple[float, float, float]
    dimension: str
    parent: str
    members: frozenset[str]
    public_break: bool

    def contains(self, dimension: str, x: int, y: int, z: int) -> bool:
        return (
            self.dimension == dimension
            and min(self.pos1[0], self.pos2[0]) <= x <= max(self.pos1[0], self.pos2[0])
            and min(self.pos1[1], self.pos2[1]) <= y <= max(self.pos1[1], self.pos2[1])
            and min(self.pos1[2], self.pos2[2]) <= z <= max(self.pos1[2], self.pos2[2])
        )


def _names(raw: object) -> frozenset[str]:
    # Matches Territory's comma-separated owner/manager/member representation.
    values = []
    part = []
    in_braces = False
    for char in str(raw or ""):
        if char == "{":
            in_braces = True
        elif char == "}":
            in_braces = False
        if char == "," and not in_braces:
            if "".join(part).strip():
                values.append("".join(part).strip())
            part.clear()
        else:
            part.append(char)
    if "".join(part).strip():
        values.append("".join(part).strip())
    return frozenset(values)


class TerritoryBreakGuard:
    def __init__(self, plugins_dir: Path) -> None:
        self.db_path = plugins_dir / "territory" / "territory_data.db"
        self.config_path = plugins_dir / "territory" / "config.json"
        self.claims: tuple[Claim, ...] = ()
        self.allow_op_as_member = False
        self.healthy = False
        self.error: str | None = None

    def refresh(self) -> bool:
        # Refresh once per mining operation, not once per target block. Read-only WAL-aware
        # connections see committed territory changes even when the main DB mtime is unchanged.
        self.healthy = False
        self.claims = ()
        if not self.db_path.is_file() or not self.config_path.is_file():
            self.error = "Territory 数据库或配置不存在"
            return False
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or type(config.get("allow_op_as_member")) is not bool:
                raise ValueError("Territory allow_op_as_member 配置异常")
            uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
            db = sqlite3.connect(uri, uri=True, timeout=0.05)
            try:
                rows = db.execute(
                    "SELECT pos1_x,pos1_y,pos1_z,pos2_x,pos2_y,pos2_z,"
                    "owner,manager,member,dim,father_tty,if_break FROM territories"
                ).fetchall()
            finally:
                db.close()
            claims = []
            for row in rows:
                if row[11] not in (0, 1, "0", "1"):
                    raise ValueError("Territory if_break 配置异常")
                claims.append(
                    Claim(
                        (float(row[0]), float(row[1]), float(row[2])),
                        (float(row[3]), float(row[4]), float(row[5])),
                        str(row[9]),
                        str(row[10] or ""),
                        _names(row[6]) | _names(row[7]) | _names(row[8]),
                        bool(int(row[11])),
                    )
                )
            self.claims = tuple(claims)
            self.allow_op_as_member = config["allow_op_as_member"]
        except (OSError, ValueError, TypeError, sqlite3.Error, KeyError) as exc:
            self.error = str(exc)
            return False
        self.healthy = True
        self.error = None
        return True

    def can_break(self, player_name: str, is_op: bool, dimension: str, x: int, y: int, z: int) -> bool:
        if not self.healthy:
            return False
        matches = [claim for claim in self.claims if claim.contains(dimension, x, y, z)]
        if not matches:
            return True
        children = [claim for claim in matches if claim.parent]
        effective = children if children else matches
        if is_op and self.allow_op_as_member:
            return True
        return all(claim.public_break or player_name in claim.members for claim in effective)
