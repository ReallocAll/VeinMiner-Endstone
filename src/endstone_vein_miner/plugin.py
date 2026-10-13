"""Native Endstone entry point for the production-intended, fail-closed VeinMiner fork."""

import time

from endstone import GameMode, Player
from endstone.event import BlockBreakEvent, EventPriority, event_handler
from endstone.plugin import Plugin

from .audit import TianyanAudit
from .engine import mine_extra
from .gui import show_menu
from .mining import find_connected, should_scan
from .protection import TerritoryBreakGuard
from .settings import SettingsStore


class VeinMinerPlugin(Plugin):
    api_version = "0.11"
    version = "2.0.3+server.4"

    commands = {
        "vm": {
            "description": "连锁挖掘设置",
            "usages": ["/vm [gui|on|off|reload]"],
            "aliases": ["veinminer"],
            "permissions": ["veinminer.command"],
        },
    }
    permissions = {
        "veinminer.command": {"description": "允许玩家使用连锁挖掘菜单", "default": True},
        "veinminer.reload": {"description": "允许管理员重新加载玩家设置", "default": "op"},
    }

    def on_enable(self) -> None:
        self.settings = SettingsStore(self.data_folder / "players.json")
        self.settings.load()
        self._guard = TerritoryBreakGuard(self.data_folder.parent)
        self._audit = TianyanAudit(self.data_folder.parent)
        self._last_scan: dict[str, float] = {}
        self.register_events(self)

    def on_disable(self) -> None:
        self._last_scan.clear()

    @event_handler(priority=EventPriority.MONITOR, ignore_cancelled=True)
    def on_block_break(self, event: BlockBreakEvent) -> None:
        if event.is_cancelled:
            return
        player = event.player
        if not player.is_valid or player.game_mode != GameMode.SURVIVAL:
            return
        player_id = str(player.unique_id)
        values = self.settings.get(player_id)
        original = event.block
        block_id = str(original.type)
        item = player.inventory.item_in_main_hand
        if item is None:
            return
        if not should_scan(values, bool(player.is_sneaking), block_id, str(item.type)):
            return
        now = time.monotonic()
        if now - self._last_scan.get(player_id, -100.0) < 0.12:
            return
        self._last_scan[player_id] = now
        try:
            positions = find_connected(original)
        except (ValueError, RuntimeError) as exc:
            self.logger.warning(f"连锁挖掘读取目标失败: {exc}")
            return
        if not positions:
            return
        dimension_name = str(original.dimension.name)
        seed = (original.x, original.y, original.z)
        self.server.scheduler.run_task(
            self,
            lambda: self._finish_break(player, player_id, block_id, dimension_name, seed, positions),
            delay=1,
        )

    def _finish_break(
        self,
        player: Player,
        player_id: str,
        block_id: str,
        dimension_name: str,
        seed: tuple[int, int, int],
        positions: list[tuple[int, int, int]],
    ) -> None:
        if not player.is_valid or player.game_mode != GameMode.SURVIVAL:
            return
        if str(player.dimension.name) != dimension_name:
            return
        values = self.settings.get(player_id)
        tool = player.inventory.item_in_main_hand
        if tool is None or not should_scan(values, bool(player.is_sneaking), block_id, str(tool.type)):
            return
        # A cancelled or unsuccessful original block break leaves the seed present.
        try:
            if player.dimension.get_block_at(*seed).type != "minecraft:air":
                return
            location = player.location
            if (
                max(
                    abs(location.block_x - seed[0]),
                    abs(location.block_y - seed[1]),
                    abs(location.block_z - seed[2]),
                )
                > 8
            ):
                return
            if not self._guard.refresh() or not self._audit.refresh():
                return
            count = mine_extra(player, block_id, positions, self._guard, self._audit, self.logger)
            if count:
                player.send_tip(f"§a连锁挖掘 +{count}")
        except Exception as exc:
            self.logger.error(f"连锁挖掘执行异常，已停止: {exc}")

    def on_command(self, sender, command, args: list[str]) -> bool:
        if len(args) > 1:
            sender.send_message("§c用法：/vm [gui|on|off|reload]")
            return True

        action = args[0].lower() if args else "gui"
        if action == "reload":
            if not sender.has_permission("veinminer.reload"):
                sender.send_message("§c无权限")
                return True
            try:
                self.settings.load()
            except (OSError, ValueError) as exc:
                self.logger.error(f"重新加载玩家设置失败: {exc}")
                sender.send_message("§c设置加载失败")
                return True
            sender.send_message("§a设置已重载")
            return True

        if not isinstance(sender, Player):
            sender.send_message("§c仅限玩家使用")
            return True

        if action == "gui":
            show_menu(self, sender)
        elif action in ("on", "off"):
            try:
                self.settings.set(str(sender.unique_id), "enabled", action == "on")
            except (OSError, ValueError) as exc:
                self.logger.error(f"无法保存玩家连锁设置: {exc}")
                sender.send_tip("§c设置保存失败")
                return True
            sender.send_tip("§a连锁挖掘已开启" if action == "on" else "§7连锁挖掘已关闭")
        else:
            sender.send_message("§c用法：/vm [gui|on|off|reload]")
        return True
