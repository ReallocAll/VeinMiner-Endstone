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
    blocks.update({(3, y, 2): block_id for y in range(70, 75)})
    column = Column(blocks)
    found = find_connected(seed(column, hit_y, block_id))
    assert found == [(2, y, 2) for y in expected]
    assert all(x == 2 and z == 2 for x, _, z in column.reads)
    assert len(column.reads) <= 2 * MAX_VERTICAL_SCAN


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
