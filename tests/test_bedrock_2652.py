from random import Random
from types import SimpleNamespace

from endstone_vein_miner.mining import LEAVES, LOGS, PLANTS, block_category, correct_tool, find_connected
from endstone_vein_miner.rewards import leaf_rewards, plant_rewards
from endstone_vein_miner.tree import blocking_leaves, find_tree


def test_new_poplar_and_bedrock_azalea_ids():
    assert "minecraft:poplar_log" in LOGS
    assert "minecraft:stripped_poplar_wood" in LOGS
    for color in ("red", "orange", "yellow"):
        ident = f"minecraft:{color}_poplar_leaves"
        assert ident in LEAVES
        assert block_category(ident) == "leaves"
        assert correct_tool(ident, "minecraft:air")
        rewards = [r for _ in range(500) for r in leaf_rewards(ident, Random(_))]
        assert all(r.item != f"minecraft:{color}_poplar_sapling" for r in rewards)
    assert "minecraft:azalea_leaves_flowered" in LEAVES
    rewards = [r for _ in range(500) for r in leaf_rewards("minecraft:azalea_leaves_flowered", Random(_))]
    assert all(r.item != "minecraft:azalea_leaves_flowered_sapling" for r in rewards)


def test_simple_vegetation_covered_without_custom_crop_loot():
    for block in ("bamboo", "cactus", "reeds", "kelp", "shelf_mushroom", "red_shrub", "poppy"):
        ident = f"minecraft:{block}"
        assert ident in PLANTS
        assert correct_tool(ident, "minecraft:air")
    assert block_category("minecraft:potatoes") is None
    assert plant_rewards("minecraft:potatoes", {}, Random(1)) is None
    assert plant_rewards("minecraft:reeds", {}, Random(1))[0].item == "minecraft:sugar_cane"
    assert plant_rewards("minecraft:shelf_mushroom", {"growth": 3}, Random(1))[0].count == 2


def test_configured_cap_expands_ore_search_without_crossing_unloaded_chunks():
    blocks = {(x, 63, 2): "minecraft:coal_ore" for x in range(2, 35)}

    class Dimension:
        loaded_chunks = [SimpleNamespace(x=i, z=0) for i in range(3)]

        def get_block_at(self, x, y, z):
            return SimpleNamespace(type=blocks.get((x, y, z), "minecraft:stone"))

    dim = Dimension()
    seed = SimpleNamespace(x=2, y=63, z=2, type="minecraft:coal_ore", dimension=dim)
    assert len(find_connected(seed)) == 6  # Default radius 6 prevents reaching the far end.
    assert len(find_connected(seed, max_blocks=256)) > 10


def test_colored_poplar_leaves_bridge_detached_branch_and_canopy():
    blocks = {(2, y, 2): "minecraft:poplar_log" for y in range(64, 70)}
    blocks.update(
        {
            (3, 70, 2): "minecraft:red_poplar_leaves",
            (4, 71, 2): "minecraft:poplar_log",
            (4, 70, 2): "minecraft:orange_poplar_leaves",
        }
    )

    class Dim:
        loaded_chunks = [SimpleNamespace(x=0, z=0)]

        def get_block_at(self, x, y, z):
            pos = (x, y, z)
            return SimpleNamespace(
                type=blocks.get(pos, "minecraft:air"),
                data=SimpleNamespace(block_states={"persistent_bit": False}),
            )

    dim = Dim()
    origin = SimpleNamespace(x=2, y=64, z=2, type="minecraft:poplar_log", dimension=dim)
    assert (4, 71, 2) in find_tree(origin)
    assert (4, 70, 2) in blocking_leaves(origin, [(4, 71, 2)])
