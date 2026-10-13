"""Minimal, fail-closed Endstone plugin entry point."""

from endstone import Player
from endstone.plugin import Plugin

from .gui import show_menu
from .settings import SettingsStore


class VeinMinerPlugin(Plugin):
    api_version = "0.11"
    version = "2.0.3+server.1"

    commands = {
        "vm": {
            "description": "打开连锁挖掘设置",
            "usages": ["/vm [action: string]"],
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
        self.logger.warning(
            "连锁额外方块破坏已禁用：Endstone 0.11 没有经验证的原版破坏/掉落接口，"
            "Territory 没有 Python 授权 API，Tianyan 没有公开写入 API。"
        )

    def on_command(self, sender, command, args: list[str]) -> bool:
        if len(args) > 1:
            sender.send_message("§c用法：/vm [gui|on|off|reload]")
            return True

        action = args[0].lower() if args else "gui"
        if action == "reload":
            if not sender.has_permission("veinminer.reload"):
                sender.send_message("§c没有权限重新加载设置")
                return True
            try:
                self.settings.load()
            except (OSError, ValueError) as exc:
                self.logger.error(f"重新加载玩家设置失败: {exc}")
                sender.send_message("§c玩家设置加载失败，当前设置未更改")
                return True
            sender.send_message("§a玩家设置已重新加载")
            return True

        if not isinstance(sender, Player):
            sender.send_message("§c该指令只能由玩家使用")
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
            sender.send_tip("§a已开启个人连锁设置" if action == "on" else "§7已关闭个人连锁设置")
        else:
            sender.send_message("§c用法：/vm [gui|on|off|reload]")
        return True
