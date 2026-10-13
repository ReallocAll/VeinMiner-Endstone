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


def test_mending_and_unrelated_enchants_do_not_block_mining(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    meta = player.inventory.item_in_main_hand.item_meta
    meta.has_enchants = True
    meta.enchants = {
        type("Enchantment", (), {"id": "minecraft:mending"})(): 1,
        type("Enchantment", (), {"id": "minecraft:efficiency"})(): 5,
        type("Enchantment", (), {"id": "minecraft:unbreaking"})(): 3,
        type("Enchantment", (), {"id": "minecraft:vanishing"})(): 1,
    }
    guard = SimpleNamespace(can_break=lambda *args: True)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:iron_ore", positions, guard, None, logger) == 2
    assert len(drops) == 2
    assert player.inventory.item_in_main_hand.item_meta.enchants == meta.enchants


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


def test_all_enchantment_combinations_ignore_unrelated_effects():
    from itertools import combinations

    from endstone_vein_miner.engine import _enchant_levels

    class Enchantment:
        def __init__(self, identifier):
            self.id = identifier

    names = (
        "efficiency",
        "fortune",
        "silk_touch",
        "unbreaking",
        "mending",
        "vanishing",
        "binding",
        "sharpness",
        "looting",
        "soul_speed",
        "fire_aspect",
        "unregistered_custom_enchantment",
    )
    for length in range(len(names) + 1):
        for selection in combinations(names, length):
            enchants = {Enchantment(f"minecraft:{name}"): (5 if name == "efficiency" else 3) for name in selection}
            meta = SimpleNamespace(has_enchants=bool(enchants), enchants=enchants)
            levels = _enchant_levels(meta)
            assert set(levels) <= {
                "minecraft:fortune",
                "minecraft:silk_touch",
                "minecraft:unbreaking",
                "minecraft:mending",
            }
            assert levels.get("minecraft:fortune", 0) <= 3
            assert levels.get("minecraft:unbreaking", 0) <= 3
            if "silk_touch" in selection:
                assert levels.get("minecraft:silk_touch") == 1
                assert "minecraft:fortune" not in levels
            assert meta.enchants == enchants
    invalid = SimpleNamespace(
        has_enchants=True,
        enchants={Enchantment("minecraft:fortune"): -3, Enchantment("minecraft:unbreaking"): 999},
    )
    assert _enchant_levels(invalid) == {"minecraft:unbreaking": 3}


def test_mending_repairs_held_tool_before_granting_remaining_xp(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    for block in blocks.values():
        block.type = "minecraft:diamond_ore"
    tool = player.inventory.item_in_main_hand
    tool.item_meta.damage = 4
    tool.item_meta.has_enchants = True
    tool.item_meta.enchants = {type("Enchantment", (), {"id": "minecraft:mending"})(): 1}
    granted = []
    player.give_exp = granted.append
    guard = SimpleNamespace(can_break=lambda *args: True)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:diamond_ore", positions[:1], guard, None, logger) == 1
    assert tool.item_meta.damage == 0
    assert len(drops) == 1
    assert sum(granted) >= 0


def test_silk_touch_precedes_fortune_even_on_command_enchanted_tools(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    for block in blocks.values():
        block.type = "minecraft:diamond_ore"
    meta = player.inventory.item_in_main_hand.item_meta
    meta.has_enchants = True
    meta.enchants = {
        type("Enchantment", (), {"id": "minecraft:fortune"})(): 3,
        type("Enchantment", (), {"id": "minecraft:silk_touch"})(): 1,
    }
    guard = SimpleNamespace(can_break=lambda *args: True)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:diamond_ore", positions[:1], guard, None, logger) == 1
    assert drops == [("place", ("minecraft:diamond_ore", 1))]


def test_drop_spawn_raising_after_entity_creation_does_not_duplicate_block(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)

    def spawn_then_fail(location, stack):
        drops.append((location, stack))
        raise RuntimeError("entity spawned, return failed")

    player.dimension.drop_item = spawn_then_fail
    guard = SimpleNamespace(can_break=lambda *args: True)
    audit = SimpleNamespace(
        prepare=lambda *args: "row",
        finish=lambda row, *, success: events.append("audit_success" if success else "audit_cancel"),
    )
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    count = engine.mine_extra(player, "minecraft:iron_ore", positions[:1], guard, audit, logger)
    assert count == 1
    assert blocks[positions[0]].type == "minecraft:air"
    assert len(drops) == 1
    assert events == ["block_removed", "audit_success"]


def test_axe_mines_leaves_with_normal_drops_but_bare_hand_does_not(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    for block in blocks.values():
        block.type = "minecraft:oak_leaves"
    guard = SimpleNamespace(can_break=lambda *args: True)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    player.inventory.item_in_main_hand = None
    assert engine.mine_extra(player, "minecraft:oak_leaves", positions, guard, None, logger) == 0
    assert not drops
    player.inventory.item_in_main_hand = FakeTool()
    player.inventory.item_in_main_hand.type = FakeType("minecraft:iron_axe")
    assert engine.mine_extra(player, "minecraft:oak_leaves", positions, guard, None, logger) == 2
    assert all(block.type == "minecraft:air" for block in blocks.values())
    assert not any(item == "minecraft:oak_leaves" for _, (item, count) in drops)


def test_silk_touch_axe_returns_leaf_blocks(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    player, blocks, positions, drops = make_world([])
    tool = player.inventory.item_in_main_hand
    tool.type = FakeType("minecraft:diamond_axe")
    tool.item_meta.has_enchants = True
    tool.item_meta.enchants = {type("Enchant", (), {"id": "minecraft:silk_touch"})(): 1}
    for block in blocks.values():
        block.type = "minecraft:oak_leaves"
    guard = SimpleNamespace(can_break=lambda *args: True)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:oak_leaves", positions, guard, None, logger) == 2
    assert drops == [("place", ("minecraft:oak_leaves", 1))] * 2


def test_tree_canopy_clear_keeps_axe_durability(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    player.inventory.item_in_main_hand.type = FakeType("minecraft:iron_axe")
    for block in blocks.values():
        block.type = "minecraft:oak_leaves"
    guard = SimpleNamespace(can_break=lambda *args: True)
    audit = SimpleNamespace(prepare=lambda *args: "row", finish=lambda *args, **kwargs: None)
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    assert engine.mine_extra(player, "minecraft:oak_leaves", positions, guard, audit, logger, canopy=True) == 2
    assert player.inventory.item_in_main_hand.item_meta.damage == 0


def test_mixed_stone_and_deepslate_ores_audit_actual_ids_and_drop_correctly(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    blocks[positions[1]].type = "minecraft:deepslate_iron_ore"
    audited = []

    class Audit:
        def prepare(self, player_name, dimension, point, block_id, states):
            audited.append((point, block_id))
            return "row"

        def finish(self, *args, **kwargs):
            return None

    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    guard = SimpleNamespace(can_break=lambda *args: True)
    assert engine.mine_extra(player, "minecraft:iron_ore", positions, guard, Audit(), logger) == 2
    assert audited == [
        (positions[0], "minecraft:iron_ore"),
        (positions[1], "minecraft:deepslate_iron_ore"),
    ]
    assert [item for _, (item, count) in drops] == ["minecraft:raw_iron", "minecraft:raw_iron"]
    assert all(block.type == "minecraft:air" for block in blocks.values())


def test_mixed_ore_mining_skips_different_families_even_if_passed_as_targets(monkeypatch):
    monkeypatch.setattr(engine, "_new_item", lambda item, count: (item, count))
    events = []
    player, blocks, positions, drops = make_world(events)
    blocks[positions[1]].type = "minecraft:gold_ore"
    audited = []
    audit = SimpleNamespace(
        prepare=lambda *args: audited.append(args) or "row",
        finish=lambda *args, **kwargs: None,
    )
    logger = SimpleNamespace(error=lambda msg: None, warning=lambda msg: None)
    guard = SimpleNamespace(can_break=lambda *args: True)
    assert engine.mine_extra(player, "minecraft:iron_ore", positions, guard, audit, logger) == 1
    assert len(audited) == 1
    assert blocks[positions[1]].type == "minecraft:gold_ore"
