"""Command-entry regression checks with only the Endstone-facing types stubbed."""

import importlib
import sys
import types
from types import SimpleNamespace

from endstone_vein_miner.settings import SettingsStore


def test_command_permissions_and_player_entry(tmp_path, monkeypatch):
    endstone = types.ModuleType("endstone")
    endstone.__path__ = []
    plugin_module = types.ModuleType("endstone.plugin")

    class Player:
        def __init__(self):
            self.unique_id = "uuid-a"
            self.messages = []
            self.tips = []
            self.allowed = False

        def has_permission(self, permission):
            return self.allowed

        def send_message(self, message):
            self.messages.append(message)

        def send_tip(self, message):
            self.tips.append(message)

    class Plugin:
        pass

    endstone.GameMode = SimpleNamespace(SURVIVAL=0)
    endstone.Player = Player
    plugin_module.Plugin = Plugin
    gui_module = types.ModuleType("endstone_vein_miner.gui")
    gui_module.show_menu = lambda plugin, player: None
    monkeypatch.setitem(sys.modules, "endstone_vein_miner.gui", gui_module)
    monkeypatch.setitem(sys.modules, "endstone", endstone)
    monkeypatch.setitem(sys.modules, "endstone.plugin", plugin_module)
    event_module = types.ModuleType("endstone.event")
    event_module.BlockBreakEvent = type("BlockBreakEvent", (), {})
    event_module.EventPriority = SimpleNamespace(MONITOR=5)
    event_module.event_handler = lambda **kwargs: lambda func: func
    inventory_module = types.ModuleType("endstone.inventory")
    inventory_module.ItemStack = type("ItemStack", (), {})
    monkeypatch.setitem(sys.modules, "endstone.event", event_module)
    monkeypatch.setitem(sys.modules, "endstone.inventory", inventory_module)
    monkeypatch.delitem(sys.modules, "endstone_vein_miner.plugin", raising=False)

    loaded = importlib.import_module("endstone_vein_miner.plugin")
    cls = loaded.VeinMinerPlugin
    assert cls.commands["vm"]["usages"] == ["/vm [gui|on|off|reload]"]
    assert cls.commands["vm"]["aliases"] == ["veinminer"]
    assert cls.permissions["veinminer.command"]["default"] is True
    assert cls.permissions["veinminer.reload"]["default"] == "op"

    plugin = cls()
    plugin.settings = SettingsStore(tmp_path / "players.json")
    plugin.logger = SimpleNamespace(error=lambda _: None)
    player = Player()
    assert plugin.on_command(player, None, ["on"])
    assert plugin.settings.enabled("uuid-a")
    assert not player.messages
    assert player.tips

    assert plugin.on_command(player, None, ["reload"])
    assert not player.allowed
    assert any("没有权限" in msg for msg in player.messages)

    plugin.settings.set("uuid-a", "enabled", False)
    player.allowed = True
    assert plugin.on_command(player, None, ["reload"])
    assert not plugin.settings.enabled("uuid-a")

    assert plugin.on_command(player, None, ["off"])
    assert not plugin.settings.enabled("uuid-a")


def test_server_level_experimental_gate_removed():
    from pathlib import Path

    source = Path("src/endstone_vein_miner/plugin.py").read_text(encoding="utf-8")
    assert "experimental_extra_breaks" not in source
    assert "_extra_enabled" not in source
