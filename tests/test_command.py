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
    assert cls.commands["vm"]["usages"] == ["/vm [gui|on|off|status|reload]"]
    assert cls.commands["vm"]["aliases"] == ["veinminer"]
    assert cls.permissions["veinminer.command"]["default"] is True
    assert cls.permissions["veinminer.reload"]["default"] == "op"

    plugin = cls()
    plugin.settings = SettingsStore(tmp_path / "players.json")
    from endstone_vein_miner.server_limits import ServerLimits

    plugin.limits = ServerLimits(tmp_path / "server.json")
    plugin.logger = SimpleNamespace(error=lambda _: None)
    player = Player()
    assert plugin.on_command(player, None, ["on"])
    assert plugin.settings.enabled("uuid-a")
    assert not player.messages
    assert player.tips[-1] == "§a连锁挖掘已开启"

    assert plugin.on_command(player, None, ["reload"])
    assert not player.allowed
    assert any("无权限" in msg for msg in player.messages)

    plugin.settings.set("uuid-a", "enabled", False)
    player.allowed = True
    assert plugin.on_command(player, None, ["reload"])
    assert not plugin.settings.enabled("uuid-a")
    assert "§a设置已重载" in player.messages

    assert plugin.on_command(player, None, ["off"])
    assert not plugin.settings.enabled("uuid-a")
    assert player.tips[-1] == "§7连锁挖掘已关闭"

    # Mobile clients can stop reporting crouch immediately after the break event.
    # The accepted activation must not be rejected on the scheduled next tick.
    plugin.settings.set("uuid-a", "enabled", True)
    plugin.settings.set("uuid-a", "require_sneak", True)
    player.game_mode = endstone.GameMode.SURVIVAL
    player.is_valid = True
    player.is_sneaking = False
    player.location = SimpleNamespace(block_x=2, block_y=64, block_z=2)
    player.dimension = SimpleNamespace(
        name="overworld",
        get_block_at=lambda *coords: SimpleNamespace(type="minecraft:air"),
    )
    player.inventory = SimpleNamespace(item_in_main_hand=SimpleNamespace(type="minecraft:iron_pickaxe"))
    plugin._guard = SimpleNamespace(refresh=lambda: True)
    plugin._active_players = {"uuid-a"}
    harvested = []
    monkeypatch.setattr(loaded, "mine_extra", lambda *args, **kwargs: harvested.append(args) or 1)
    plugin.logger = SimpleNamespace(error=lambda msg: (_ for _ in ()).throw(AssertionError(msg)))
    plugin._finish_break(
        player, "uuid-a", "minecraft:iron_ore", "overworld", (2, 64, 2), [("minecraft:iron_ore", [(2, 64, 3)], False)]
    )
    assert len(harvested) == 1
    assert player.tips[-1] == "§a连锁挖掘 +1"
    assert "uuid-a" not in plugin._active_players


def test_server_level_experimental_gate_removed():
    from pathlib import Path

    source = Path("src/endstone_vein_miner/plugin.py").read_text(encoding="utf-8")
    assert "experimental_extra_breaks" not in source
    assert "_extra_enabled" not in source
