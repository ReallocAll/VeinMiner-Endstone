"""Native Endstone entry point for the production-intended, fail-closed VeinMiner fork."""

import time

from endstone import GameMode, Player
from endstone.event import BlockBreakEvent, EventPriority, event_handler
from endstone.plugin import Plugin

from .audit import TianyanAudit
from .engine import mine_extra
from .gui import show_menu
from .mining import block_category, find_connected, should_scan
from .tree import blocking_leaves, leaf_family
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
        self._active_players: set[str] = set()
        self.register_events(self)

    def on_disable(self) -> None:
        self._last_scan.clear()
        self._active_players.clear()

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
        tool_id = str(item.type) if item is not None else "minecraft:air"
        if player_id in self._active_players or not should_scan(values, bool(player.is_sneaking), block_id, tool_id):
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
        canopy = []
        if block_category(block_id) == "logs":
            leaf_id = leaf_family(block_id)
            if leaf_id is not None:
                canopy = blocking_leaves(original, [(original.x, original.y, original.z), *positions])
        dimension_name = str(original.dimension.name)
        seed = (original.x, original.y, original.z)
        jobs = ([(leaf_id, canopy, True)] if canopy else []) + [(block_id, positions, False)]
        self._active_players.add(player_id)
        try:
            self.server.scheduler.run_task(
                self,
                lambda: self._finish_break(player, player_id, block_id, dimension_name, seed, jobs),
                delay=1,
            )
        except Exception:
            self._active_players.discard(player_id)
            raise

    def _finish_break(
        self,
        player: Player,
        player_id: str,
        seed_block_id: str,
        dimension_name: str,
        seed: tuple[int, int, int],
        jobs: list[tuple[str, list[tuple[int, int, int]], bool]],
    ) -> None:
        index = 0
        offset = 0
        total = 0

        def step() -> None:
            nonlocal index, offset, total
            try:
                if not player.is_valid or player.game_mode != GameMode.SURVIVAL:
                    return
                if str(player.dimension.name) != dimension_name:
                    return
                tool = player.inventory.item_in_main_hand
                tool_id = str(tool.type) if tool is not None else "minecraft:air"
                if not should_scan(self.settings.get(player_id), bool(player.is_sneaking), seed_block_id, tool_id):
                    return
                if str(player.dimension.get_block_at(*seed).type) != "minecraft:air":
                    return
                location = player.location
                if max(
                    abs(location.block_x - seed[0]),
                    abs(location.block_y - seed[1]),
                    abs(location.block_z - seed[2]),
                ) > 8:
                    return
                if not self._guard.refresh() or not self._audit.refresh():
                    return
                while index < len(jobs) and offset >= len(jobs[index][1]):
                    index += 1
                    offset = 0
                if index >= len(jobs):
                    return
                block_id, positions, canopy = jobs[index]
                batch = positions[offset:offset + 8]
                offset += len(batch)
                total += mine_extra(
                    player, block_id, batch, self._guard, self._audit, self.logger, canopy=canopy
                )
                if offset >= len(positions):
                    index += 1
                    offset = 0
                if index < len(jobs):
                    self.server.scheduler.run_task(self, step, delay=1)
                    return
            except Exception as exc:
                self.logger.error(f"连锁挖掘失败: {exc}")
            finally:
                # A scheduled follow-up keeps the per-player session active.
                if index >= len(jobs) or not player.is_valid:
                    self._active_players.discard(player_id)

        step()
        if player_id in self._active_players and index >= len(jobs):
            self._active_players.discard(player_id)
        if total:
            player.send_tip(f"§a连锁挖掘 +{total}")

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
