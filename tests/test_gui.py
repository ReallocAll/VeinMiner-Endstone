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
    player.send_tip = player.tips.append
    plugin = SimpleNamespace(
        settings=store,
        logger=SimpleNamespace(error=lambda _: None),
    )
    plugin.server = SimpleNamespace(
        scheduler=SimpleNamespace(run_task=lambda owner, callback, delay: tasks.append(callback)),
    )

    gui.show_menu(plugin, player)
    assert len(player.forms[-1].buttons) == 5
    assert player.forms[-1].content == ""
    assert "已关闭" in player.forms[-1].buttons[0]
    player.forms[-1].on_submit(player, 0)
    assert store.enabled("uuid-a")
    tasks.pop()()
    assert "已开启" in player.forms[-1].buttons[0]
    assert player.tips == []
    restored = SettingsStore(store.path)
    restored.load()
    assert restored.enabled("uuid-a")
