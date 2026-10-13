"""Native Chinese player settings form."""

from endstone.form import ActionForm

from .settings import SETTING_KEYS

LABELS = (
    "连锁总开关",
    "需要蹲下触发",
    "矿石连锁",
    "树木连锁",
    "树叶连锁",
)


def show_menu(plugin, player) -> None:
    player_id = str(player.unique_id)
    values = plugin.settings.get(player_id)
    status = (
        "§e实验性破坏已启用：仅无附魔工具，必须测试后再使用。"
        if getattr(plugin, "_extra_enabled", False)
        else "§c当前安全限制：额外连锁破坏暂不可用。"
    )
    form = ActionForm(
        title="§l§6连锁挖掘",
        content="§7点击切换个人设置。\n§7开启总开关后，默认需要蹲下才能触发矿石连锁。\n" + status,
    )
    for key, label in zip(SETTING_KEYS, LABELS, strict=True):
        form.add_button(f"§f{label}\n{'§a已开启' if values[key] else '§c已关闭'}")

    def on_submit(target, index: int) -> None:
        if not 0 <= index < len(SETTING_KEYS) or not target.is_valid:
            return
        try:
            plugin.settings.toggle(str(target.unique_id), SETTING_KEYS[index])
        except (OSError, ValueError) as exc:
            plugin.logger.error(f"无法保存玩家连锁设置: {exc}")
            target.send_tip("§c设置保存失败")
            return
        plugin.server.scheduler.run_task(
            plugin,
            lambda: show_menu(plugin, target) if target.is_valid else None,
            delay=1,
        )

    form.on_submit = on_submit
    player.send_form(form)
