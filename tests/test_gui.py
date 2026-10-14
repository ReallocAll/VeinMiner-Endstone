import importlib
import sys
import types
from types import SimpleNamespace

from endstone_vein_miner.settings import SettingsStore


class FakeForm:
    def __init__(self, **kwargs):
        self.buttons = []
        self.on_submit = None
        self.content = kwargs["content"]

    def add_button(self, text):
        self.buttons.append(text)


def test_gui_toggle_reopens_and_persists_without_chat(tmp_path, monkeypatch):
    endstone = types.ModuleType("endstone")
    endstone.__path__ = []
    form_module = types.ModuleType("endstone.form")
    form_module.ActionForm = FakeForm
    form_module.ModalForm = FakeForm
    form_module.StepSlider = lambda *args, **kwargs: SimpleNamespace(options=kwargs["options"])
    monkeypatch.setitem(sys.modules, "endstone", endstone)
    monkeypatch.setitem(sys.modules, "endstone.form", form_module)

    sys.modules.pop("endstone_vein_miner.gui", None)
    gui = importlib.import_module("endstone_vein_miner.gui")

    store = SettingsStore(tmp_path / "players.json")
    store.load()
    tasks = []

    player = SimpleNamespace(unique_id="uuid-a", is_valid=True)
    player.forms = []
    player.tips = []
    player.send_form = player.forms.append
    player.has_permission = lambda permission: False
    player.send_tip = player.tips.append
    plugin = SimpleNamespace(
        settings=store,
        logger=SimpleNamespace(error=lambda _: None),
    )
    plugin.server = SimpleNamespace(
        scheduler=SimpleNamespace(run_task=lambda owner, callback, delay: tasks.append(callback)),
    )

    gui.show_menu(plugin, player)
    assert len(player.forms[-1].buttons) == 7
    assert player.forms[-1].content == (
        "先开启总开关及所需连锁类型；默认潜行触发，可关闭。\n"
        "树叶：默认斧子按空手掉落且不耗耐久；开启清叶附魔后按原版附魔掉落并耗耐久。\n"
        "剪刀始终掉落叶块并耗耐久。\n"
        "植被：含甘蔗、竹子、仙人掌、海带和农作物；挖上层保留根部。"
    )
    assert any("潜行触发" in button for button in player.forms[-1].buttons)
    assert "蹲下触发" not in str(player.forms[-1].buttons)
    assert "已关闭" in player.forms[-1].buttons[0]
    assert "树叶连锁（斧/剪刀）" in player.forms[-1].buttons[4]
    assert "斧子清叶附魔（耗耐久）" in player.forms[-1].buttons[5]
    assert "已关闭" in player.forms[-1].buttons[5]
    player.forms[-1].on_submit(player, 5)
    assert store.get("uuid-a")["axe_leaf_enchants"]
    tasks.pop()()
    assert "已开启" in player.forms[-1].buttons[5]
    player.forms[-1].on_submit(player, 0)
    assert store.enabled("uuid-a")
    tasks.pop()()
    assert "已开启" in player.forms[-1].buttons[0]
    assert player.tips == []
    restored = SettingsStore(store.path)
    restored.load()
    assert restored.enabled("uuid-a")


def test_admin_limit_form_is_separate_and_rechecks_permission(tmp_path, monkeypatch):
    import json

    from endstone_vein_miner.server_limits import ServerLimits

    endstone = types.ModuleType("endstone")
    endstone.__path__ = []
    forms = types.ModuleType("endstone.form")
    forms.ActionForm = FakeForm

    class FakeModal:
        def __init__(self, **kwargs):
            self.controls = []
            self.on_submit = None

        def add_control(self, control):
            self.controls.append(control)

    forms.ModalForm = FakeModal
    forms.StepSlider = lambda *args, **kwargs: SimpleNamespace(options=kwargs["options"])
    monkeypatch.setitem(sys.modules, "endstone", endstone)
    monkeypatch.setitem(sys.modules, "endstone.form", forms)
    sys.modules.pop("endstone_vein_miner.gui", None)
    gui = importlib.import_module("endstone_vein_miner.gui")

    tasks = []
    player = SimpleNamespace(unique_id="admin", is_valid=True, allowed=True)
    player.has_permission = lambda name: player.allowed
    player.forms = []
    player.tips = []
    player.send_form = player.forms.append
    player.send_tip = player.tips.append
    plugin = SimpleNamespace(
        limits=ServerLimits(tmp_path / "server.json"),
        settings=SettingsStore(tmp_path / "players.json"),
        logger=SimpleNamespace(warning=lambda msg: None, error=lambda msg: None),
    )
    plugin.server = SimpleNamespace(scheduler=SimpleNamespace(run_task=lambda *args, **kwargs: tasks.append(args[1])))

    gui.show_menu(plugin, player)
    assert len(player.forms[-1].buttons) == 8
    player.forms[-1].on_submit(player, 7)
    modal = player.forms[-1]
    assert isinstance(modal, FakeModal)
    assert modal.controls[0].options == ["默认", "24", "64", "128", "256"]
    player.allowed = False
    modal.on_submit(player, json.dumps([4]))
    assert plugin.limits.override == 0
    player.allowed = True
    modal.on_submit(player, json.dumps([4]))
    assert plugin.limits.override == 256
    assert player.tips[-1] == "§a已保存"
    assert json.loads((tmp_path / "server.json").read_text())["max_blocks"] == 256
