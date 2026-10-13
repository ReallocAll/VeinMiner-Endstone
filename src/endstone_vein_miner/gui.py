"""Native Chinese player settings form."""

import json

from endstone.form import ActionForm, ModalForm, StepSlider

from .server_limits import OPTIONS
from .settings import SETTING_KEYS

LABELS = (
    "连锁挖掘",
    "蹲下触发",
    "矿石连锁",
    "树木连锁",
    "树叶连锁（斧子）",
    "植被连锁",
)


def show_menu(plugin, player) -> None:
    player_id = str(player.unique_id)
    values = plugin.settings.get(player_id)
    form = ActionForm(
        title="§l§6连锁挖掘",
        content="先开启总开关和对应类型。\n默认蹲下；树叶：斧子自然掉落，剪刀掉叶块。",
    )
    for key, label in zip(SETTING_KEYS, LABELS, strict=True):
        form.add_button(f"§f{label}\n{'§a已开启' if values[key] else '§c已关闭'}")

    admin = player.has_permission("veinminer.admin")
    if admin:
        choice = plugin.limits.override
        form.add_button(f"§e连锁上限\n§f{choice or '默认'}")

    def on_submit(target, index: int) -> None:
        if not target.is_valid:
            return
        if index == len(SETTING_KEYS) and target.has_permission("veinminer.admin"):
            show_admin_limit(plugin, target)
            return
        if not 0 <= index < len(SETTING_KEYS):
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


def show_admin_limit(plugin, player) -> None:
    if not player.has_permission("veinminer.admin"):
        return
    form = ModalForm(title="§l§6连锁上限")
    form.add_control(
        StepSlider(
            "单次连锁方块数",
            options=["默认", "24", "64", "128", "256"],
            default_index=OPTIONS.index(plugin.limits.override),
        )
    )

    def on_submit(target, response: str) -> None:
        if not target.is_valid or not target.has_permission("veinminer.admin"):
            return
        try:
            data = json.loads(response)
            if not isinstance(data, list) or len(data) != 1 or type(data[0]) is not int:
                return
            plugin.limits.set(OPTIONS[data[0]])
        except (OSError, ValueError, IndexError) as exc:
            plugin.logger.warning(f"无法保存连锁上限: {exc}")
            target.send_tip("§c保存失败")
            return
        target.send_tip("§a已保存")
        plugin.server.scheduler.run_task(
            plugin, lambda: show_menu(plugin, target) if target.is_valid else None, delay=1
        )

    form.on_submit = on_submit
    player.send_form(form)
