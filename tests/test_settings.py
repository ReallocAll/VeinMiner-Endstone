import json

import pytest

from endstone_vein_miner.settings import DEFAULT_SETTINGS, SettingsStore


def test_first_join_defaults_are_safe(tmp_path):
    store = SettingsStore(tmp_path / "players.json")
    store.load()
    assert store.get("uuid-a") == {
        "enabled": False,
        "require_sneak": True,
        "ores": True,
        "logs": False,
        "leaves": False,
        "plants": False,
    }
    assert not store.enabled("uuid-a")
    assert not store.path.exists()


def test_independent_flags_survive_restart(tmp_path):
    path = tmp_path / "players.json"
    store = SettingsStore(path)
    store.load()
    store.set("uuid-a", "enabled", True)
    store.set("uuid-a", "require_sneak", False)
    store.set("uuid-a", "logs", True)
    store.set("uuid-a", "enabled", False)
    store.set("uuid-b", "leaves", True)

    restored = SettingsStore(path)
    restored.load()
    assert restored.get("uuid-a") == {
        "enabled": False,
        "require_sneak": False,
        "ores": True,
        "logs": True,
        "leaves": False,
    }
    assert restored.get("uuid-b")["leaves"]
    assert not restored.get("uuid-b")["enabled"]
    assert restored.get("uuid-c") == DEFAULT_SETTINGS


def test_invalid_file_does_not_replace_existing_memory_or_file(tmp_path):
    path = tmp_path / "players.json"
    store = SettingsStore(path)
    store.set("uuid-a", "enabled", True)
    path.write_text('{"uuid-a": {"enabled": "yes"}}', encoding="utf-8")
    with pytest.raises(ValueError):
        store.load()
    assert store.enabled("uuid-a")
    assert json.loads(path.read_text())["uuid-a"]["enabled"] == "yes"


def test_failed_persistence_does_not_change_memory(tmp_path, monkeypatch):
    path = tmp_path / "players.json"
    store = SettingsStore(path)
    store.set("uuid-a", "enabled", True)

    def fail_replace(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(type(path), "replace", fail_replace)
    with pytest.raises(OSError):
        store.set("uuid-a", "enabled", False)
    assert store.enabled("uuid-a")
    assert not path.with_name("players.json.tmp").exists()


def test_get_does_not_leak_mutable_state(tmp_path):
    store = SettingsStore(tmp_path / "players.json")
    settings = store.get("uuid-a")
    settings["enabled"] = True
    assert not store.enabled("uuid-a")


def test_unchanged_setting_does_not_touch_disk(tmp_path):
    path = tmp_path / "players.json"
    store = SettingsStore(path)
    store.set("uuid-a", "enabled", False)
    assert not path.exists()
    store.set("uuid-a", "enabled", True)
    before = path.stat().st_mtime_ns
    store.set("uuid-a", "enabled", True)
    assert path.stat().st_mtime_ns == before
