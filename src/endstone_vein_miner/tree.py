"""Bounded Bedrock tree traversal with diagonal branches and natural-leaf bridges."""

from collections import deque

from .mining import LEAVES, LOGS, NEIGHBORS

MAX_TREE_LOGS = 160
MAX_TREE_LEAVES = 256
MAX_TREE_READS = 5000
MAX_TREE_HEIGHT = 40
MAX_TREE_HORIZONTAL = 10
MAX_LEAF_BRIDGE = 2
MAX_BLOCKER_DEPTH = 4


def leaf_family(log_id: str) -> frozenset[str]:
    """Candidate natural leaves for a timber family, including colored poplars."""
    if log_id.removeprefix("minecraft:").removeprefix("stripped_").startswith("poplar_"):
        return frozenset(
            {"minecraft:red_poplar_leaves", "minecraft:orange_poplar_leaves", "minecraft:yellow_poplar_leaves"}
        )
    wood = log_id.removeprefix("minecraft:").removeprefix("stripped_")
    for suffix in ("_log", "_wood"):
        if wood.endswith(suffix):
            family = wood.removesuffix(suffix)
            result = f"minecraft:{family}_leaves"
            return frozenset({result}) if result in LEAVES else frozenset()
    return frozenset()


def is_natural_leaf(block, expected_id: str | frozenset[str] | None = None) -> bool:
    if block is None:
        return False
    if isinstance(expected_id, frozenset) and str(block.type) not in expected_id:
        return False
    if isinstance(expected_id, str) and str(block.type) != expected_id:
        return False
    if str(block.type) not in LEAVES:
        return False
    try:
        return block.data.block_states.get("persistent_bit") is False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def find_tree(seed, max_blocks: int = MAX_TREE_LOGS) -> list[tuple[int, int, int]]:
    block_id = str(seed.type)
    if block_id not in LOGS or not 2 <= max_blocks <= 256:
        return []
    dimension = seed.dimension
    origin = (seed.x, seed.y, seed.z)
    leaf_id = leaf_family(block_id)
    loaded = getattr(dimension, "loaded_chunks", None)
    chunks = {(c.x, c.z) for c in loaded} if loaded is not None else {(seed.x >> 4, seed.z >> 4)}
    logs = {origin}
    leaf_seen = set()
    cached = {}
    queue = deque([origin])
    found = []

    def read(pos):
        if pos in cached:
            return cached[pos]
        if len(cached) >= MAX_TREE_READS:
            return None
        x, y, z = pos
        if (
            abs(x - origin[0]) > MAX_TREE_HORIZONTAL
            or abs(z - origin[2]) > MAX_TREE_HORIZONTAL
            or not origin[1] - 2 <= y <= origin[1] + MAX_TREE_HEIGHT
            or (x >> 4, z >> 4) not in chunks
        ):
            return None
        try:
            block = dimension.get_block_at(x, y, z)
        except (ValueError, RuntimeError):
            block = None
        cached[pos] = block
        return block

    while queue and len(found) < max_blocks - 1 and len(cached) < MAX_TREE_READS:
        source = queue.popleft()
        for dx, dy, dz in NEIGHBORS:
            point = (source[0] + dx, source[1] + dy, source[2] + dz)
            block = read(point)
            if block is None:
                continue
            if str(block.type) == block_id:
                if point not in logs:
                    logs.add(point)
                    queue.append(point)
                    found.append(point)
                continue
            if not leaf_id or point in leaf_seen or not is_natural_leaf(block, leaf_id):
                continue
            if point[1] < origin[1] + 2:
                continue
            leaf_seen.add(point)
            pending = deque([(point, 1)])
            while pending and len(found) < max_blocks - 1 and len(cached) < MAX_TREE_READS:
                leaf_pos, depth = pending.popleft()
                for ox, oy, oz in NEIGHBORS:
                    neighbour = (leaf_pos[0] + ox, leaf_pos[1] + oy, leaf_pos[2] + oz)
                    candidate = read(neighbour)
                    if candidate is None:
                        continue
                    if str(candidate.type) == block_id and max(abs(neighbour[i] - source[i]) for i in range(3)) <= 3:
                        if neighbour not in logs:
                            logs.add(neighbour)
                            queue.append(neighbour)
                            found.append(neighbour)
                    elif depth < MAX_LEAF_BRIDGE and neighbour not in leaf_seen and is_natural_leaf(candidate, leaf_id):
                        leaf_seen.add(neighbour)
                        pending.append((neighbour, depth + 1))
    return found


def blocking_leaves(
    seed, logs: list[tuple[int, int, int]], max_blocks: int = MAX_TREE_LEAVES
) -> list[tuple[int, int, int]]:
    family = leaf_family(str(seed.type))
    if not family:
        return []
    dimension = seed.dimension
    loaded = getattr(dimension, "loaded_chunks", None)
    chunks = {(c.x, c.z) for c in loaded} if loaded is not None else {(seed.x >> 4, seed.z >> 4)}
    result = []
    checked = set()
    for x, y, z in logs:
        for offset in range(1, MAX_BLOCKER_DEPTH + 1):
            point = (x, y - offset, z)
            if point in checked or (x >> 4, z >> 4) not in chunks:
                break
            checked.add(point)
            try:
                block = dimension.get_block_at(*point)
            except (ValueError, RuntimeError):
                break
            if not is_natural_leaf(block, family):
                break
            result.append(point)
            if len(result) >= min(max_blocks, MAX_TREE_LEAVES):
                return result
    return result
