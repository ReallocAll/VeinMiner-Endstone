"""Read-only, bounded connected-block selection. No world mutations or loot calculations."""

from collections import deque

MAX_BLOCKS = 24
MAX_RADIUS = 6

ORE_TIERS = {
    "coal_ore": 0,
    "iron_ore": 1,
    "gold_ore": 2,
    "diamond_ore": 2,
    "emerald_ore": 2,
    "lapis_ore": 1,
    "redstone_ore": 2,
    "copper_ore": 1,
    "nether_quartz_ore": 0,
    "quartz_ore": 0,
    "nether_gold_ore": 0,
    "ancient_debris": 3,
}
ORE_TIERS.update(
    {
        f"deepslate_{name}": tier
        for name, tier in tuple(ORE_TIERS.items())
        if name.endswith("_ore") and not name.startswith("nether_")
    }
)
WOOD_TYPES = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "pale_oak")
LOGS = {f"minecraft:{wood}_{form}" for wood in WOOD_TYPES for form in ("log", "wood")}
LOGS.update({f"minecraft:stripped_{wood}_{form}" for wood in WOOD_TYPES for form in ("log", "wood")})
LOGS.update(
    {
        f"minecraft:{prefix}{wood}_{form}"
        for prefix in ("", "stripped_")
        for wood in ("crimson", "warped")
        for form in ("stem", "hyphae")
    }
)
LOGS.update({"minecraft:bamboo_block", "minecraft:stripped_bamboo_block"})
LEAVES = {f"minecraft:{wood}_leaves" for wood in WOOD_TYPES}
LEAVES.update({"minecraft:azalea_leaves", "minecraft:flowering_azalea_leaves"})
TIERS = {"wooden": 0, "golden": 0, "stone": 1, "copper": 1, "iron": 2, "diamond": 3, "netherite": 4}
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
NEIGHBORS = FACES + tuple(
    (dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if abs(dx) + abs(dy) + abs(dz) >= 2
)


def block_category(block_id: str) -> str | None:
    if not block_id.startswith("minecraft:"):
        return None
    if block_id.removeprefix("minecraft:") in ORE_TIERS:
        return "ores"
    if block_id in LOGS:
        return "logs"
    if block_id in LEAVES:
        return "leaves"
    return None


def correct_tool(block_id: str, item_id: str) -> bool:
    category = block_category(block_id)
    if category is None or not item_id.startswith("minecraft:"):
        return False
    if category == "leaves":
        return item_id in {"minecraft:shears", "minecraft:air"}
    required = "pickaxe" if category == "ores" else "axe"
    prefix, separator, kind = item_id.removeprefix("minecraft:").rpartition("_")
    if not separator or kind != required:
        return False
    tier = TIERS.get(prefix)
    if tier is None:
        return False
    return category == "logs" or tier >= ORE_TIERS[block_id.removeprefix("minecraft:")]


def should_scan(settings: dict[str, bool], sneaking: bool, block_id: str, item_id: str) -> bool:
    if not settings["enabled"]:
        return False
    category = block_category(block_id)
    if category is None or not settings[category]:
        return False
    if settings["require_sneak"] and not sneaking:
        return False
    return correct_tool(block_id, item_id)


def find_connected(seed) -> list[tuple[int, int, int]]:
    """Find at most 23 additional same-type blocks, inside the seed's loaded chunk.

    Read-only by design. The result never grants permission to remove a block.
    """
    block_id = seed.type
    category = block_category(block_id)
    if category is None:
        return []
    if category == "logs":
        from .tree import find_tree

        return find_tree(seed)
    dimension = seed.dimension
    start = seed.x, seed.y, seed.z
    queue = deque([start])
    seen = {start}
    selected = []
    offsets = NEIGHBORS if category == "ores" else FACES
    chunk_x, chunk_z = seed.x >> 4, seed.z >> 4

    while queue and len(selected) < MAX_BLOCKS - 1:
        x, y, z = queue.popleft()
        for dx, dy, dz in offsets:
            nx, ny, nz = x + dx, y + dy, z + dz
            point = nx, ny, nz
            if point in seen:
                continue
            seen.add(point)
            if (
                max(abs(nx - start[0]), abs(ny - start[1]), abs(nz - start[2])) > MAX_RADIUS
                or nx >> 4 != chunk_x
                or nz >> 4 != chunk_z
            ):
                continue
            try:
                adjacent = dimension.get_block_at(nx, ny, nz)
            except (ValueError, RuntimeError):
                continue
            if adjacent is not None and adjacent.type == block_id:
                selected.append(point)
                queue.append(point)
                if len(selected) == MAX_BLOCKS - 1:
                    break
    return selected
