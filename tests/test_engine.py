from types import SimpleNamespace

from endstone_vein_miner import engine


class FakeType:
    def __init__(self, item_id):
        self.id = item_id
        self.max_durability = 10

    def __str__(self):
        return self.id


class FakeTool:
    def __init__(self, enchanted=False):
        self.type = FakeType("minecraft:iron_pickaxe")
        self.item_meta = SimpleNamespace(has_enchants=enchanted, damage=0, is_unbreakable=False)

    def set_item_meta(self, meta):
        self.item_meta = meta
        return True


class FakeBlock:
    def __init__(self, events):
        self.type = "minecraft:iron_ore"
        self.events = events
        self.data = SimpleNamespace(block_states={})

    def capture_state(self):
        block = self

        class State:
            location = "place"

            def update(self, force=True, apply_physics=False):
                block.type = "minecraft:iron_ore"
                return True

        return State()

    def set_type(self, block_id, apply_physics=False):
        self.events.append("block_removed")
        self.type = block_id


def make_world(events):
    positions = [(1, 70, 1), (2, 70, 1)]
    blocks = {point: FakeBlock(events) for point in positions}
    drops = []
    world = SimpleNamespace(name="overworld")
    world.get_block_at = lambda *point: blocks[point]
    world.drop_item = lambda loc, stack: drops.append((loc, stack))
    player = SimpleNamespace(
        dimension=world,
        name="Alice",
        is_op=False,
        is_valid=True,
        inventory=SimpleNamespace(item_in_main_hand=FakeTool()),
        give_exp=lambda xp: None,
    )
    return player, blocks, positions, drops


def test_permissions_and_audit_precede_each_write(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)

    class Guard:
        def can_break(self, player, is_op, world, x, y, z):
            return (x, y, z) == positions[0]

    class Audit:
        def prepare(self, *args):
            events.append("audit_prepare")
            return "row"

        def finish(self, row, *, success):
            events.append("audit_success" if success else "audit_cancel")

    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    count = engine.mine_extra(player, "minecraft:iron_ore", positions, Guard(), Audit(), logger)
    assert count == 1
    assert events == ["audit_prepare", "block_removed", "audit_success"]
    assert len(drops) == 1
    assert drops[0][1] == ("minecraft:raw_iron", 1)
    assert blocks[positions[1]].type == "minecraft:iron_ore"
    assert player.inventory.item_in_main_hand.item_meta.damage == 1


def test_audit_failure_is_fail_closed(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)

    class Guard:
        def can_break(self, *args):
            return True

    class Audit:
        def prepare(self, *args):
            raise OSError("audit database unavailable")

    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:iron_ore", positions, Guard(), Audit(), logger) == 0
    assert events == []
    assert not drops
    assert all(block.type == "minecraft:iron_ore" for block in blocks.values())


def test_enchanted_tool_is_not_processed(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    player.inventory.item_in_main_hand.item_meta.has_enchants = True
    guard = SimpleNamespace(can_break=lambda *args: True)
    audit = SimpleNamespace(prepare=lambda *args: "row", finish=lambda *args, **kwargs: None)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:iron_ore", positions, guard, audit, logger) == 0
    assert not events and not drops


def test_failed_tool_update_rolls_back_block_and_marks_audit_cancelled(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    player.inventory.item_in_main_hand.set_item_meta = lambda meta: False

    class Guard:
        def can_break(self, *args):
            return True

    class Audit:
        def prepare(self, *args):
            events.append("audit_prepare")
            return "row"

        def finish(self, row, *, success):
            events.append("audit_success" if success else "audit_cancel")

    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    count = engine.mine_extra(player, "minecraft:iron_ore", positions[:1], Guard(), Audit(), logger)
    assert count == 0
    assert blocks[positions[0]].type == "minecraft:iron_ore"
    assert events == ["audit_prepare", "block_removed", "audit_success", "audit_cancel"]
    assert not drops


def test_failed_audit_completion_never_spawns_rewards(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)

    class Guard:
        def can_break(self, *args):
            return True

    class Audit:
        def prepare(self, *args):
            events.append("audit_prepare")
            return "row"

        def finish(self, row, *, success):
            if success:
                raise OSError("database locked")
            events.append("audit_cancel")

    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    count = engine.mine_extra(player, "minecraft:iron_ore", positions[:1], Guard(), Audit(), logger)
    assert count == 0
    assert blocks[positions[0]].type == "minecraft:iron_ore"
    assert events == ["audit_prepare", "block_removed", "audit_cancel"]
    assert not drops
