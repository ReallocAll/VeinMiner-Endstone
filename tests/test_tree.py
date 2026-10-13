from types import SimpleNamespace

from endstone_vein_miner.tree import MAX_TREE_LOGS, blocking_leaves, find_tree


class World:
    def __init__(self, blocks, persistent=()):
        self.blocks = blocks
        self.persistent = set(persistent)
        self.reads = []
        self.loaded_chunks = [SimpleNamespace(x=0, z=0), SimpleNamespace(x=1, z=0)]

    def get_block_at(self, x, y, z):
        self.reads.append((x, y, z))
        block_id = self.blocks.get((x, y, z), "minecraft:air")
        return SimpleNamespace(
            type=block_id,
            data=SimpleNamespace(block_states={"persistent_bit": (x, y, z) in self.persistent}),
        )


def seed(world, point=(2, 64, 2)):
    return SimpleNamespace(type=world.blocks[point], dimension=world, x=point[0], y=point[1], z=point[2])


def test_diagonal_and_leaf_separated_upper_branches():
    blocks = {(2, 64, 2): "minecraft:oak_log"}
    for y in range(65, 72):
        blocks[(2, y, 2)] = "minecraft:oak_log"
    blocks[(3, 72, 2)] = "minecraft:oak_log"
    blocks[(4, 73, 2)] = "minecraft:oak_leaves"
    blocks[(5, 74, 2)] = "minecraft:oak_log"
    blocks[(6, 74, 2)] = "minecraft:oak_leaves"
    blocks[(7, 74, 2)] = "minecraft:oak_log"
    world = World(blocks)
    found = find_tree(seed(world))
    assert (3, 72, 2) in found
    assert (5, 74, 2) in found
    assert (7, 74, 2) in found
    assert (4, 73, 2) not in found
    assert all(p in blocks for p in found)
    assert len(found) < MAX_TREE_LOGS
    assert len(world.reads) <= 2400


def test_persistent_or_other_species_leaf_does_not_bridge():
    blocks = {
        (2, 64, 2): "minecraft:oak_log",
        (2, 65, 2): "minecraft:oak_log",
        (2, 66, 2): "minecraft:oak_log",
        (3, 66, 2): "minecraft:oak_leaves",
        (5, 66, 2): "minecraft:oak_log",
    }
    blocks[(4, 66, 2)] = "minecraft:birch_leaves"
    world = World(blocks)
    assert (5, 66, 2) not in find_tree(seed(world))
    blocks[(4, 66, 2)] = "minecraft:oak_leaves"
    world.persistent.add((4, 66, 2))
    assert (5, 66, 2) not in find_tree(seed(world))


def test_canopy_only_removes_natural_leaves_below_chopped_logs():
    blocks = {
        (2, 64, 2): "minecraft:oak_log",
        (2, 70, 2): "minecraft:oak_log",
        (2, 69, 2): "minecraft:oak_leaves",
        (2, 68, 2): "minecraft:oak_leaves",
        (2, 67, 2): "minecraft:oak_leaves",
        (3, 69, 2): "minecraft:oak_leaves",
    }
    world = World(blocks, persistent={(2, 67, 2)})
    found = blocking_leaves(seed(world), [(2, 70, 2)])
    assert found == [(2, 69, 2), (2, 68, 2)]
    assert (3, 69, 2) not in found


def test_tree_selection_respects_loaded_chunk_boundary():
    world = World(
        {
            (15, 64, 2): "minecraft:oak_log",
            (16, 64, 2): "minecraft:oak_log",
        }
    )
    world.loaded_chunks = [SimpleNamespace(x=0, z=0)]
    assert (16, 64, 2) not in find_tree(seed(world, (15, 64, 2)))
    assert all(x < 16 for x, _, _ in world.reads)


def test_giant_two_by_two_trunk_all_120_logs_found_with_bounded_reads():
    blocks = {(x, y, z): "minecraft:jungle_log" for x in (2, 3) for z in (2, 3) for y in range(64, 94)}
    world = World(blocks)
    found = find_tree(seed(world))
    assert len(found) == 119
    assert len(set(found)) == 119
    assert set(found) == set(blocks) - {(2, 64, 2)}
    assert len(world.reads) <= 5000
