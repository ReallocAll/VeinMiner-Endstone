import json
import sqlite3

from endstone_vein_miner.protection import TerritoryBreakGuard


def guard_with_database(tmp_path):
    root = tmp_path / "plugins"
    base = root / "territory"
    base.mkdir(parents=True)
    db_file = base / "territory_data.db"
    db = sqlite3.connect(db_file)
    db.execute(
        "CREATE TABLE territories ("
        "pos1_x REAL,pos1_y REAL,pos1_z REAL,pos2_x REAL,pos2_y REAL,pos2_z REAL,"
        "owner TEXT,manager TEXT,member TEXT,dim TEXT,father_tty TEXT,if_break INTEGER)"
    )
    db.commit()
    (base / "config.json").write_text(json.dumps({"allow_op_as_member": False}), encoding="utf-8")
    return TerritoryBreakGuard(root), db


def claim(db, *, x1=0, x2=20, owner="Alice", member="", manager="", parent="", break_allowed=0):
    db.execute(
        "INSERT INTO territories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (x1, 0, 0, x2, 127, 20, owner, manager, member, "overworld", parent, break_allowed),
    )
    db.commit()


def test_missing_or_corrupted_database_fails_closed(tmp_path):
    guard = TerritoryBreakGuard(tmp_path)
    assert not guard.refresh()
    assert not guard.can_break("Alice", True, "overworld", 1, 60, 1)
    guard, db = guard_with_database(tmp_path)
    db.close()
    assert guard.refresh()
    assert guard.can_break("visitor", False, "overworld", 1, 60, 1)
    guard.config_path.write_text("not JSON", encoding="utf-8")
    assert not guard.refresh()
    assert not guard.can_break("visitor", False, "overworld", 1, 60, 1)


def test_claim_permission_is_if_break_not_if_build(tmp_path):
    guard, db = guard_with_database(tmp_path)
    claim(db, owner="owner", manager="manager", member="visitor", break_allowed=0)
    assert guard.refresh()
    for player in ("owner", "manager", "visitor"):
        assert guard.can_break(player, False, "overworld", 5, 64, 5)
    assert not guard.can_break("stranger", False, "overworld", 5, 64, 5)
    assert guard.can_break("stranger", False, "nether", 5, 64, 5)
    assert guard.can_break("stranger", False, "overworld", 22, 64, 5)
    assert not guard.can_break("stranger", True, "overworld", 5, 64, 5)
    db.close()


def test_subclaim_shadows_parent_and_database_refreshes(tmp_path):
    guard, db = guard_with_database(tmp_path)
    claim(db, owner="Alice", x1=0, x2=20)
    claim(db, owner="Bob", x1=5, x2=10, parent="parent")
    assert guard.refresh()
    assert guard.can_break("Alice", False, "overworld", 2, 64, 5)
    assert not guard.can_break("Alice", False, "overworld", 6, 64, 5)
    assert guard.can_break("Bob", False, "overworld", 6, 64, 5)
    db.execute("UPDATE territories SET if_break=1 WHERE father_tty='parent'")
    db.commit()
    assert guard.refresh()
    assert guard.can_break("Alice", False, "overworld", 6, 64, 5)
    db.close()


def test_op_can_break_only_when_config_explicitly_allows(tmp_path):
    guard, db = guard_with_database(tmp_path)
    claim(db)
    guard.config_path.write_text(json.dumps({"allow_op_as_member": True}), encoding="utf-8")
    assert guard.refresh()
    assert guard.can_break("stranger", True, "overworld", 5, 64, 5)
    assert not guard.can_break("stranger", False, "overworld", 5, 64, 5)
    db.close()


def test_schema_change_disables_extra_breaks(tmp_path):
    guard, db = guard_with_database(tmp_path)
    claim(db)
    assert guard.refresh()
    db.execute("ALTER TABLE territories RENAME TO retired")
    db.commit()
    assert not guard.refresh()
    assert not guard.can_break("Alice", False, "overworld", 5, 64, 5)
    db.close()


def test_dimension_index_reduces_unrelated_claim_scans(tmp_path, monkeypatch):
    from endstone_vein_miner.protection import Claim

    guard, db = guard_with_database(tmp_path)
    for dimension in ("nether", "the_end"):
        for offset in range(30):
            db.execute(
                "INSERT INTO territories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (offset, 0, 0, offset + 4, 127, 20, "Other", "", "", dimension, "", 0),
            )
    claim(db, owner="Alice", x1=0, x2=20, break_allowed=0)
    assert guard.refresh()
    original = Claim.contains
    calls = []

    def recorded(self, dimension, x, y, z):
        calls.append(self.dimension)
        return original(self, dimension, x, y, z)

    monkeypatch.setattr(Claim, "contains", recorded)
    assert guard.can_break("Alice", False, "overworld", 2, 60, 2)
    assert not guard.can_break("Bob", False, "overworld", 2, 60, 2)
    assert calls == ["overworld", "overworld"]
    db.close()


def test_reversed_territory_boundaries_still_protect_claim():
    from endstone_vein_miner.protection import Claim

    claim = Claim((20, 127, 20), (0, 0, 0), "overworld", "", frozenset({"Alice"}), False)
    assert claim.pos1 == (0, 0, 0)
    assert claim.pos2 == (20, 127, 20)
    assert claim.contains("overworld", 10, 64, 10)
    assert not claim.contains("nether", 10, 64, 10)
