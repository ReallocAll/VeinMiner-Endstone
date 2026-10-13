import json
import sqlite3

import pytest

from endstone_vein_miner.audit import COLUMNS, TianyanAudit, format_states


def create_audit(tmp_path):
    root = tmp_path / "tianyan_data"
    root.mkdir()
    (root / "config.json").write_text(
        json.dumps({"database_type": "sqlite", "log_block_break": True}), encoding="utf-8"
    )
    path = root / "ty_data.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE LOGDATA ("
            + ",".join(
                f"{col} TEXT" if col not in {"pos_x", "pos_y", "pos_z", "time"} else f"{col} REAL" for col in COLUMNS
            )
            + ")"
        )
    return TianyanAudit(tmp_path)


def test_tianyan_precommit_and_completion(tmp_path):
    audit = create_audit(tmp_path)
    assert audit.refresh()
    uid = audit.prepare("Alice", "overworld", (1, 70, 2), "minecraft:diamond_ore", "{}")
    with sqlite3.connect(audit.db_path) as db:
        assert db.execute("SELECT status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == ("veinminer_pending",)
    audit.finish(uid, success=True)
    with sqlite3.connect(audit.db_path) as db:
        assert db.execute("SELECT name, world, type, status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == (
            "Alice",
            "overworld",
            "block_break",
            "",
        )


def test_tianyan_disabled_for_unknown_backend_and_schema(tmp_path):
    audit = create_audit(tmp_path)
    audit.config_path.write_text(json.dumps({"database_type": "mysql", "log_block_break": True}), encoding="utf-8")
    assert not audit.refresh()
    with pytest.raises(RuntimeError):
        audit.prepare("Alice", "overworld", (1, 70, 2), "minecraft:diamond_ore", "{}")
    audit.config_path.write_text(json.dumps({"database_type": "sqlite"}), encoding="utf-8")
    with sqlite3.connect(audit.db_path) as db:
        db.execute("ALTER TABLE LOGDATA ADD COLUMN incompatible TEXT")
    assert not audit.refresh()


def test_tianyan_failed_updates_fail_closed(tmp_path):
    audit = create_audit(tmp_path)
    assert audit.refresh()
    with pytest.raises(RuntimeError, match="记录消失"):
        audit.finish("not-a-record", success=True)
    uid = audit.prepare("Bob", "nether", (8, 25, 3), "minecraft:quartz_ore", "{}")
    audit.finish(uid, success=False)
    with sqlite3.connect(audit.db_path) as db:
        assert db.execute("SELECT status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == ("canceled",)


def test_tianyan_state_suffix_is_bedrock_setblock_compatible():
    assert format_states({}) == ""
    assert format_states({"pillar_axis": "x"}) == ' ["pillar_axis"="x"]'
    assert format_states({"upside_down_bit": True, "facing_direction": 2}) == (
        ' ["facing_direction"=2,"upside_down_bit"=true]'
    )
    with pytest.raises(ValueError):
        format_states({"pillar_axis": 'x" /kill @a'})
    with pytest.raises(ValueError):
        format_states({"invalid key": 3})
    with pytest.raises(ValueError):
        format_states({"foo": [1, 2]})

def test_tianyan_break_logging_disabled_blocks_extra_mining(tmp_path):
    audit = create_audit(tmp_path)
    audit.config_path.write_text(
        json.dumps({"database_type": "sqlite", "log_block_break": False}), encoding="utf-8"
    )
    assert not audit.refresh()
    with pytest.raises(RuntimeError):
        audit.prepare("Alice", "overworld", (1, 70, 2), "minecraft:diamond_ore", "")
