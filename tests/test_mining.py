from types import SimpleNamespace

from endstone_vein_miner.mining import (
    MAX_BLOCKS,
    block_category,
    correct_tool,
    find_connected,
    should_scan,
)
from endstone_vein_miner.settings import DEFAULT_SETTINGS


class FakeDimension:
    def __init__(self, blocks):
        self.blocks = blocks
        self.reads = []

    def get_block_at(self, x, y, z):
        point = x, y, z
        self.reads.append(point)
        return SimpleNamespace(type=self.blocks.get(point, "minecraft:stone"))


def seed_at(dimension, point=(2, 64, 2)):
    return SimpleNamespace(
        dimension=dimension,
        type=dimension.blocks[point],
        x=point[0],
        y=point[1],
        z=point[2],
    )


def test_safe_defaults_and_activation_requirements():
    settings = DEFAULT_SETTINGS.copy()
    assert not should_scan(settings, True, "minecraft:diamond_ore", "minecraft:iron_pickaxe")
    settings["enabled"] = True
    assert not should_scan(settings, False, "minecraft:diamond_ore", "minecraft:iron_pickaxe")
    assert should_scan(settings, True, "minecraft:diamond_ore", "minecraft:iron_pickaxe")
    settings["require_sneak"] = False
    assert should_scan(settings, False, "minecraft:diamond_ore", "minecraft:iron_pickaxe")
    settings["ores"] = False
    assert not should_scan(settings, False, "minecraft:diamond_ore", "minecraft:iron_pickaxe")
    assert not should_scan(settings, True, "minecraft:oak_log", "minecraft:iron_axe")
    settings["logs"] = True
    assert should_scan(settings, False, "minecraft:oak_log", "minecraft:iron_axe")


def test_tool_material_tiers_and_strict_allowlist():
    assert not correct_tool("minecraft:diamond_ore", "minecraft:wooden_pickaxe")
    assert not correct_tool("minecraft:ancient_debris", "minecraft:iron_pickaxe")
    assert correct_tool("minecraft:ancient_debris", "minecraft:diamond_pickaxe")
    assert correct_tool("minecraft:copper_ore", "minecraft:stone_pickaxe")
    assert not correct_tool("minecraft:iron_ore", "minecraft:golden_pickaxe")
    assert not correct_tool("minecraft:oak_log", "minecraft:diamond_pickaxe")
    assert correct_tool("minecraft:oak_log", "minecraft:wooden_axe")
    assert correct_tool("minecraft:oak_leaves", "minecraft:shears")
    assert not correct_tool("minecraft:oak_leaves", "minecraft:iron_axe")
    assert not correct_tool("minecraft:chest", "minecraft:iron_axe")
    assert block_category("modded:diamond_ore") is None


def test_bfs_is_bounded_and_never_changes_world():
    original = {(x, 64, z): "minecraft:coal_ore" for x in range(2, 15) for z in range(2, 15)}
    world = FakeDimension(original.copy())
    positions = find_connected(seed_at(world))
    assert len(positions) == MAX_BLOCKS - 1
    assert len(set(positions)) == len(positions)
    assert (2, 64, 2) not in positions
    assert all(p[0] < 16 and p[2] < 16 for p in world.reads)
    assert len(world.reads) <= MAX_BLOCKS * 26
    assert world.blocks == original


def test_bfs_protects_unloaded_chunk_edge_and_radius():
    blocks = {(15, 64, 2): "minecraft:diamond_ore", (16, 64, 2): "minecraft:diamond_ore"}
    for y in range(65, 85):
        blocks[(15, y, 2)] = "minecraft:diamond_ore"
    world = FakeDimension(blocks)
    found = find_connected(seed_at(world, (15, 64, 2)))
    assert (16, 64, 2) not in found
    assert (15, 70, 2) in found
    assert (15, 71, 2) not in found
    assert all(x < 16 for x, _, _ in world.reads)


def test_bfs_uses_six_neighbors_for_logs_and_fails_closed_for_unknown_blocks():
    blocks = {(2, 64, 2): "minecraft:oak_log", (3, 65, 2): "minecraft:oak_log", (2, 65, 2): "minecraft:oak_log"}
    world = FakeDimension(blocks)
    found = find_connected(seed_at(world))
    assert (2, 65, 2) in found
    assert (3, 65, 2) in found
    unknown = SimpleNamespace(type="minecraft:chest", dimension=world, x=2, y=64, z=2)
    before = len(world.reads)
    assert find_connected(unknown) == []
    assert len(world.reads) == before


def test_bfs_skips_invalid_dimension_coordinates():
    blocks = {
        (2, 0, 2): "minecraft:oak_log",
        (2, 1, 2): "minecraft:oak_log",
    }

    class HeightBoundedDimension(FakeDimension):
        def get_block_at(self, x, y, z):
            if y < 0 or y >= 128:
                raise ValueError("outside dimension height")
            return super().get_block_at(x, y, z)

    world = HeightBoundedDimension(blocks)
    assert find_connected(seed_at(world, (2, 0, 2))) == [(2, 1, 2)]
    assert world.blocks == blocks


def test_nether_stems_hyphae_and_bamboo_are_supported_wood():
    for block_id in (
        "minecraft:crimson_stem",
        "minecraft:stripped_warped_hyphae",
        "minecraft:warped_stem",
        "minecraft:bamboo_block",
        "minecraft:stripped_bamboo_block",
    ):
        assert block_category(block_id) == "logs"
        assert correct_tool(block_id, "minecraft:iron_axe")


def test_hand_can_chain_leaves_when_player_enables_leaf_category():
    settings = DEFAULT_SETTINGS.copy()
    settings["enabled"] = True
    settings["leaves"] = True
    assert should_scan(settings, True, "minecraft:oak_leaves", "minecraft:air")
    assert not should_scan(settings, False, "minecraft:oak_leaves", "minecraft:air")
    assert not should_scan(settings, True, "minecraft:diamond_ore", "minecraft:air")
    assert not should_scan(settings, True, "minecraft:oak_log", "minecraft:air")


def test_normal_and_deepslate_ore_variants_share_a_vein_across_loaded_chunks():
    world = FakeDimension(
        {
            (15, 64, 2): "minecraft:iron_ore",
            (16, 64, 2): "minecraft:deepslate_iron_ore",
            (17, 65, 3): "minecraft:iron_ore",
            (17, 64, 3): "minecraft:gold_ore",
        }
    )
    world.loaded_chunks = [SimpleNamespace(x=0, z=0), SimpleNamespace(x=1, z=0)]
    found = find_connected(seed_at(world, (15, 64, 2)))
    assert set(found) == {(16, 64, 2), (17, 65, 3)}
    assert (17, 64, 3) not in found
    assert all(x >> 4 in (0, 1) for x, _, _ in world.reads)


def test_bedrock_lit_redstone_ids_are_the_same_ore_family():
    from endstone_vein_miner.mining import ore_family

    ids = (
        "minecraft:redstone_ore",
        "minecraft:lit_redstone_ore",
        "minecraft:deepslate_redstone_ore",
        "minecraft:lit_deepslate_redstone_ore",
    )
    assert {ore_family(identifier) for identifier in ids} == {"redstone_ore"}
    assert all(correct_tool(identifier, "minecraft:iron_pickaxe") for identifier in ids)
    world = FakeDimension({(3 + i, 60, 3): name for i, name in enumerate(ids)})
    assert find_connected(seed_at(world, (3, 60, 3))) == [(4, 60, 3), (5, 60, 3), (6, 60, 3)]


def test_ore_variants_never_bridge_through_filler_or_load_unloaded_chunks():
    world = FakeDimension(
        {
            (15, 64, 2): "minecraft:iron_ore",
            (16, 64, 2): "minecraft:tuff",
            (17, 64, 2): "minecraft:deepslate_iron_ore",
            (15, 65, 2): "minecraft:deepslate_iron_ore",
            (15, 66, 2): "minecraft:gold_ore",
        }
    )
    world.loaded_chunks = [SimpleNamespace(x=0, z=0)]
    assert find_connected(seed_at(world, (15, 64, 2))) == [(15, 65, 2)]
    assert not any(x >= 16 for x, _, _ in world.reads)
