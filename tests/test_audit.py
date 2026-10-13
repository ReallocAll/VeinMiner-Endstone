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
    audit.config_path.write_text(json.dumps({"database_type": "sqlite", "log_block_break": False}), encoding="utf-8")
    assert not audit.refresh()
    with pytest.raises(RuntimeError):
        audit.prepare("Alice", "overworld", (1, 70, 2), "minecraft:diamond_ore", "")

def test_reuses_one_connection_with_committed_per_block_audit(tmp_path, monkeypatch):
    audit = create_audit(tmp_path)
    native_connect = sqlite3.connect
    connections = []

    def count_connect(*args, **kwargs):
        connection = native_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", count_connect)
    assert audit.refresh()
    for i in range(3):
        assert audit.refresh()
        uid = audit.prepare("Alice", "overworld", (i, 70, 2), "minecraft:iron_ore", "")
        with native_connect(audit.db_path) as reader:
            assert reader.execute("SELECT status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == (
                "veinminer_pending",
            )
        audit.finish(uid, success=True)
        with native_connect(audit.db_path) as reader:
            assert reader.execute("SELECT status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == ("",)
    assert len(connections) == 1
    audit.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")
    assert not audit.healthy
    assert audit.refresh()
    assert len(connections) == 2
    audit.close()


def test_failed_status_update_rolls_back_and_allows_cancel(tmp_path):
    audit = create_audit(tmp_path)
    assert audit.refresh()
    uid = audit.prepare("Alice", "overworld", (2, 70, 3), "minecraft:diamond_ore", "")
    with pytest.raises(RuntimeError, match="记录消失"):
        audit.finish("unknown-row", success=True)
    # A failed transaction must not poison the reused connection.
    audit.finish(uid, success=False)
    with sqlite3.connect(audit.db_path) as reader:
        assert reader.execute("SELECT status FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == ("canceled",)
    audit.close()


def test_configuration_change_closes_connection_and_fails_closed(tmp_path):
    audit = create_audit(tmp_path)
    assert audit.refresh()
    old = audit._db
    audit.config_path.write_text(json.dumps({"database_type": "mysql", "log_block_break": True}), encoding="utf-8")
    assert not audit.refresh()
    with pytest.raises(sqlite3.ProgrammingError):
        old.execute("SELECT 1")
    with pytest.raises(RuntimeError, match="未就绪"):
        audit.prepare("Alice", "overworld", (1, 70, 2), "minecraft:coal_ore", "")
    audit.config_path.write_text(json.dumps({"database_type": "sqlite", "log_block_break": True}), encoding="utf-8")
    assert audit.refresh()
    assert audit._db is not old
    audit.close()


def test_database_replacement_reopens_instead_of_writing_stale_inode(tmp_path):
    audit = create_audit(tmp_path)
    assert audit.refresh()
    old = audit._db
    other = audit.db_path.parent / "replacement.db"
    with sqlite3.connect(other) as db:
        db.execute(
            "CREATE TABLE LOGDATA ("
            + ",".join(f"{col} TEXT" for col in COLUMNS)
            + ")"
        )
    other.replace(audit.db_path)
    assert audit.refresh()
    assert audit._db is not old
    with pytest.raises(sqlite3.ProgrammingError):
        old.execute("SELECT 1")
    uid = audit.prepare("Bob", "nether", (1, 20, 2), "minecraft:quartz_ore", "")
    with sqlite3.connect(audit.db_path) as reader:
        assert reader.execute("SELECT uuid FROM LOGDATA WHERE uuid=?", (uid,)).fetchone() == (uid,)
    audit.close()
