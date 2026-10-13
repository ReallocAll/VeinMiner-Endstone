from types import SimpleNamespace

import pytest

from endstone_vein_miner.mining import MAX_VERTICAL_SCAN, find_connected


class Column:
    def __init__(self, blocks):
        self.blocks = blocks
        self.reads = []

    def get_block_at(self, x, y, z):
        point = x, y, z
        self.reads.append(point)
        if y < 0 or y >= 320:
            raise ValueError("outside world")
        return SimpleNamespace(type=self.blocks.get(point, "minecraft:air"))


def seed(column, y, block_id):
    return SimpleNamespace(type=block_id, x=2, y=y, z=2, dimension=column)


@pytest.mark.parametrize("block_id", ("minecraft:reeds", "minecraft:bamboo", "minecraft:cactus"))
@pytest.mark.parametrize(
    ("hit_y", "expected"),
    [
        (70, [74, 73, 72, 71]),
        (71, [74, 73, 72]),
        (72, [74, 73, 71]),
        (74, [73, 72, 71]),
    ],
)
def test_stacked_plant_break_protects_base_unless_base_was_hit(block_id, hit_y, expected):
    blocks = {(2, y, 2): block_id for y in range(70, 75)}
    column = Column(blocks)
    found = find_connected(seed(column, hit_y, block_id))
    assert found == [(2, y, 2) for y in expected]
    assert all(x == 2 and z == 2 for x, _, z in found)
    assert len(column.reads) < MAX_VERTICAL_SCAN


def test_vertical_chain_respects_the_total_cap_and_keeps_root():
    block_id = "minecraft:reeds"
    column = Column({(2, y, 2): block_id for y in range(70, 100)})
    found = find_connected(seed(column, 99, block_id), max_blocks=3)
    assert len(found) == 2
    assert (2, 70, 2) not in found
    assert (2, 99, 2) not in found


def test_kelp_top_and_kelp_plant_stem_share_one_column():
    blocks = {(2, y, 2): "minecraft:kelp_plant" for y in range(70, 74)}
    blocks[(2, 74, 2)] = "minecraft:kelp"
    column = Column(blocks)
    assert find_connected(seed(column, 74, "minecraft:kelp")) == [(2, y, 2) for y in (73, 72, 71)]
    assert find_connected(seed(column, 70, "minecraft:kelp_plant")) == [(2, y, 2) for y in (74, 73, 72, 71)]


def test_root_probe_fails_closed_when_support_is_unreadable():
    class InaccessibleRoot(Column):
        def get_block_at(self, x, y, z):
            if y == 69:
                raise RuntimeError("unknown support")
            return super().get_block_at(x, y, z)

    block_id = "minecraft:reeds"
    column = InaccessibleRoot({(2, y, 2): block_id for y in (70, 71, 72)})
    assert find_connected(seed(column, 71, block_id)) == []


def test_blocked_column_does_not_connect_via_nearby_crops():
    column = Column(
        {
            (2, 70, 2): "minecraft:reeds",
            (2, 71, 2): "minecraft:reeds",
            (2, 72, 2): "minecraft:air",
            (2, 73, 2): "minecraft:reeds",
            (3, 71, 2): "minecraft:reeds",
        }
    )
    assert find_connected(seed(column, 71, "minecraft:reeds")) == []


@pytest.mark.parametrize("block_id", ("minecraft:reeds", "minecraft:bamboo", "minecraft:cactus"))
@pytest.mark.parametrize("hit_y", (70, 71, 72, 74))
def test_neighboring_columns_share_the_same_harvest_mode(block_id, hit_y):
    blocks = {(x, y, z): block_id for x, z in ((2, 2), (3, 2), (3, 3)) for y in range(70, 75)}
    column = Column(blocks)
    found = find_connected(seed(column, hit_y, block_id))
    expected = {(x, y, z) for x, z in ((2, 2), (3, 2), (3, 3)) for y in range(70 if hit_y == 70 else 71, 75)} - {
        (2, hit_y, 2)
    }
    assert set(found) == expected
    assert len(found) == len(expected)
    for x, z in ((2, 2), (3, 2), (3, 3)):
        heights = [y for xx, y, zz in found if (xx, zz) == (x, z)]
        assert heights == sorted(heights, reverse=True)


def test_horizontal_chain_does_not_jump_an_air_gap_or_another_species():
    cane = "minecraft:reeds"
    blocks = {(x, y, 2): cane for x in (2, 3, 5) for y in range(70, 73)}
    blocks.update({(4, y, 2): "minecraft:bamboo" for y in range(70, 73)})
    column = Column(blocks)
    found = find_connected(seed(column, 71, cane))
    assert set(found) == {(2, 72, 2), (3, 72, 2), (3, 71, 2)}
    assert not any(x in (4, 5) for x, _, _ in found)


def test_horizontal_bfs_connects_columns_overlapping_at_different_heights():
    cane = "minecraft:reeds"
    blocks = {
        **{(2, y, 2): cane for y in range(70, 74)},
        **{(3, y, 2): cane for y in range(72, 75)},
        **{(4, y, 2): cane for y in range(74, 77)},
    }
    found = find_connected(seed(Column(blocks), 71, cane))
    assert {(3, 73, 2), (3, 72, 2), (4, 76, 2), (4, 75, 2)} <= set(found)
    assert (2, 70, 2) not in found
    assert (3, 72, 2) not in found  # Preserve each neighbor's own root.
    assert (4, 74, 2) not in found


def test_harvest_cap_applies_across_columns_instead_of_per_column():
    cane = "minecraft:reeds"
    blocks = {(x, y, 2): cane for x in range(2, 11) for y in range(70, 75)}
    found = find_connected(seed(Column(blocks), 71, cane), max_blocks=8)
    assert len(found) == 7
    assert len(set(found)) == 7
    assert all(y > 70 for _, y, _ in found)
    assert not any((x, y, z) == (2, 71, 2) for x, y, z in found)


def test_horizontal_search_never_queries_unloaded_neighbor_chunks():
    cane = "minecraft:reeds"
    blocks = {(x, y, 2): cane for x in (15, 16) for y in range(70, 73)}
    column = Column(blocks)
    column.loaded_chunks = [SimpleNamespace(x=0, z=0)]
    column.blocks[(15, 70, 2)] = cane
    column.blocks[(15, 71, 2)] = cane
    column.blocks[(15, 72, 2)] = cane
    origin = SimpleNamespace(type=cane, x=15, y=71, z=2, dimension=column)
    found = find_connected(origin)
    assert all(x < 16 for x, _, _ in found)
    assert not any(x >= 16 for x, _, _ in column.reads)
    column.loaded_chunks = [SimpleNamespace(x=0, z=0), SimpleNamespace(x=1, z=0)]
    assert any(x == 16 for x, _, _ in find_connected(origin))


def test_horizontal_search_is_bounded_in_dense_farms():
    cane = "minecraft:reeds"
    column = Column({(x, y, z): cane for x in range(32) for z in range(32) for y in range(70, 73)})
    origin = SimpleNamespace(type=cane, x=2, y=71, z=2, dimension=column)
    found = find_connected(origin, max_blocks=256)
    assert len(found) == 255
    assert len(set(found)) == 255
    assert len(column.reads) <= 12000
    assert all(max(abs(x - 2), abs(z - 2)) <= 16 for x, _, z in found)


def test_kelp_horizontal_chain_matches_stem_and_top_variants():
    blocks = {(x, y, 2): "minecraft:kelp_plant" for x in (2, 3) for y in range(70, 74)}
    blocks.update({(x, 74, 2): "minecraft:kelp" for x in (2, 3)})
    column = Column(blocks)
    found = find_connected(seed(column, 74, "minecraft:kelp"))
    assert (3, 74, 2) in found
    assert (3, 71, 2) in found
    assert (3, 70, 2) not in found
