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
    "lit_redstone_ore": 2,
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
        if name.endswith("_ore") and not name.startswith(("nether_", "lit_"))
    }
)
ORE_TIERS["lit_deepslate_redstone_ore"] = ORE_TIERS["redstone_ore"]
WOOD_TYPES = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "pale_oak", "poplar")
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
LEAVES.update(
    {
        "minecraft:azalea_leaves",
        "minecraft:azalea_leaves_flowered",
        "minecraft:flowering_azalea_leaves",
        "minecraft:red_poplar_leaves",
        "minecraft:orange_poplar_leaves",
        "minecraft:yellow_poplar_leaves",
    }
)
# Simple single-block vegetation with defined manual loot. Stateful crops, double-
# height plants and block entities are intentionally excluded until vanilla loot is available.
PLANTS = {
    "minecraft:bamboo",
    "minecraft:cactus",
    "minecraft:wheat",
    "minecraft:carrots",
    "minecraft:potatoes",
    "minecraft:beetroot",
    "minecraft:nether_wart",
    "minecraft:cocoa",
    "minecraft:sweet_berry_bush",
    "minecraft:torchflower_crop",
    "minecraft:reeds",
    "minecraft:kelp",
    "minecraft:kelp_plant",
    "minecraft:brown_mushroom",
    "minecraft:red_mushroom",
    "minecraft:red_shrub",
    "minecraft:shelf_mushroom",
    "minecraft:short_grass",
    "minecraft:short_dry_grass",
    "minecraft:tall_dry_grass",
    "minecraft:nether_sprouts",
    "minecraft:dandelion",
    "minecraft:poppy",
    "minecraft:blue_orchid",
    "minecraft:allium",
    "minecraft:azure_bluet",
    "minecraft:red_tulip",
    "minecraft:orange_tulip",
    "minecraft:white_tulip",
    "minecraft:pink_tulip",
    "minecraft:oxeye_daisy",
    "minecraft:cornflower",
    "minecraft:lily_of_the_valley",
    "minecraft:wither_rose",
}

TIERS = {"wooden": 0, "golden": 0, "stone": 1, "copper": 1, "iron": 2, "diamond": 3, "netherite": 4}
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
NEIGHBORS = FACES + tuple(
    (dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if abs(dx) + abs(dy) + abs(dz) >= 2
)


def ore_family(block_id: str) -> str | None:
    """Map supported stone/deepslate and Bedrock lit redstone variants to one ore."""
    if not block_id.startswith("minecraft:"):
        return None
    name = block_id.removeprefix("minecraft:")
    if name not in ORE_TIERS:
        return None
    if name.startswith("lit_"):
        name = name.removeprefix("lit_")
    if name.startswith("deepslate_"):
        name = name.removeprefix("deepslate_")
    return name


def block_category(block_id: str) -> str | None:
    if not block_id.startswith("minecraft:"):
        return None
    if block_id.removeprefix("minecraft:") in ORE_TIERS:
        return "ores"
    if block_id in LOGS:
        return "logs"
    if block_id in LEAVES:
        return "leaves"
    if block_id in PLANTS:
        return "plants"
    return None


def correct_tool(block_id: str, item_id: str) -> bool:
    category = block_category(block_id)
    if category is None or not item_id.startswith("minecraft:"):
        return False
    if category == "leaves":
        prefix, separator, kind = item_id.removeprefix("minecraft:").rpartition("_")
        return bool(separator and kind == "axe" and prefix in TIERS)
    if category == "plants":
        return (
            item_id == "minecraft:air" or item_id == "minecraft:shears" or item_id.endswith(("_axe", "_hoe", "_sword"))
        )
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


def find_connected(seed, max_blocks: int | None = None) -> list[tuple[int, int, int]]:
    """Find at most 23 additional same-type blocks, inside the seed's loaded chunk.

    Read-only by design. The result never grants permission to remove a block.
    """
    block_id = str(seed.type)
    category = block_category(block_id)
    if max_blocks is None:
        max_blocks = 160 if category == "logs" else MAX_BLOCKS
    if type(max_blocks) is not int or not 2 <= max_blocks <= 256:
        return []
    if category is None:
        return []
    if category == "logs":
        from .tree import find_tree

        return find_tree(seed, max_blocks=max_blocks)
    dimension = seed.dimension
    start = seed.x, seed.y, seed.z
    queue = deque([start])
    seen = {start}
    selected = []
    offsets = NEIGHBORS if category == "ores" else FACES
    radius = max(MAX_RADIUS, min(16, int((max_blocks ** (1 / 3)) * 2)))
    chunk_x, chunk_z = seed.x >> 4, seed.z >> 4
    loaded = getattr(dimension, "loaded_chunks", None)
    loaded_chunks = {(chunk.x, chunk.z) for chunk in loaded} if loaded is not None else {(chunk_x, chunk_z)}
    family = ore_family(block_id) if category == "ores" else None

    while queue and len(selected) < max_blocks - 1 and len(seen) < 12000:
        x, y, z = queue.popleft()
        for dx, dy, dz in offsets:
            nx, ny, nz = x + dx, y + dy, z + dz
            point = nx, ny, nz
            if point in seen:
                continue
            seen.add(point)
            if (
                max(abs(nx - start[0]), abs(ny - start[1]), abs(nz - start[2])) > radius
                or (nx >> 4, nz >> 4) not in loaded_chunks
            ):
                continue
            try:
                adjacent = dimension.get_block_at(nx, ny, nz)
            except (ValueError, RuntimeError):
                continue
            if adjacent is not None and (
                (family is not None and ore_family(str(adjacent.type)) == family)
                or (family is None and adjacent.type == block_id)
            ):
                selected.append(point)
                queue.append(point)
                if len(selected) == max_blocks - 1:
                    break
    return selected
