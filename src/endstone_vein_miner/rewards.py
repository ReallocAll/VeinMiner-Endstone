"""Constrained vanilla-style rewards with limited enchant and leaf drop support."""

from dataclasses import dataclass
from random import Random

from .mining import LEAVES, LOGS, ORE_TIERS, PLANTS


@dataclass(frozen=True)
class Reward:
    item: str
    count: int
    experience: int


def reward_for(block_id: str, rng: Random, *, silk_touch: bool = False, fortune: int = 0) -> Reward | None:
    if not 0 <= fortune <= 3:
        return None
    if silk_touch:
        fortune = 0
    if block_id in LOGS or block_id in LEAVES:
        return Reward(block_id, 1, 0)
    if silk_touch:
        if block_id.removeprefix("minecraft:") not in ORE_TIERS:
            return None
        # Bedrock's lit redstone IDs are internal block states, not obtainable items.
        item_id = block_id.replace("minecraft:lit_", "minecraft:", 1)
        return Reward(item_id, 1, 0)
    if not block_id.startswith("minecraft:"):
        return None
    name = block_id.removeprefix("minecraft:")
    if name not in ORE_TIERS:
        return None
    if name.startswith("lit_"):
        name = name.removeprefix("lit_")
    if name.startswith("deepslate_"):
        name = name.removeprefix("deepslate_")

    multiplier = max(1, rng.randint(0, fortune + 1)) if fortune else 1

    match name:
        case "coal_ore":
            return Reward("minecraft:coal", multiplier, rng.randint(0, 2))
        case "iron_ore":
            return Reward("minecraft:raw_iron", multiplier, 0)
        case "gold_ore":
            return Reward("minecraft:raw_gold", multiplier, 0)
        case "copper_ore":
            return Reward("minecraft:raw_copper", rng.randint(2, 5) * multiplier, 0)
        case "diamond_ore":
            return Reward("minecraft:diamond", multiplier, rng.randint(3, 7))
        case "emerald_ore":
            return Reward("minecraft:emerald", multiplier, rng.randint(3, 7))
        case "lapis_ore":
            return Reward("minecraft:lapis_lazuli", rng.randint(4, 9) * multiplier, rng.randint(2, 5))
        case "redstone_ore":
            return Reward("minecraft:redstone", rng.randint(4, 5 + fortune), rng.randint(1, 5))
        case "nether_quartz_ore" | "quartz_ore":
            return Reward("minecraft:quartz", multiplier, rng.randint(2, 5))
        case "nether_gold_ore":
            return Reward("minecraft:gold_nugget", rng.randint(2, 6) * multiplier, rng.randint(0, 1))
        case "ancient_debris":
            return Reward("minecraft:ancient_debris", 1, 0)
    return None


# Leaves can yield more than one independent item. Air/hand breaks never
# grant a leaf block; silk-touch/shears are handled separately by the executor.
def leaf_rewards(block_id: str, rng: Random, *, fortune: int = 0) -> tuple[Reward, ...]:
    if block_id not in LEAVES:
        return ()
    fortune = max(0, min(int(fortune), 3))
    leaf = block_id.removeprefix("minecraft:").removesuffix("_leaves")
    sapling = None
    if leaf == "azalea":
        sapling = "minecraft:azalea"
    elif leaf == "flowering_azalea":
        sapling = "minecraft:flowering_azalea"
    elif leaf in {"flowering_azalea", "azalea_leaves_flowered"}:
        sapling = "minecraft:flowering_azalea"
    elif leaf != "mangrove":
        sapling = f"minecraft:{leaf}_sapling"

    results = []
    if leaf in {"red_poplar", "orange_poplar", "yellow_poplar"}:
        sapling = "minecraft:poplar_sapling"
    if leaf == "azalea_leaves_flowered" or block_id == "minecraft:azalea_leaves_flowered":
        sapling = "minecraft:flowering_azalea"
    sapling_chances = (40, 36, 32, 24) if leaf == "jungle" else (20, 16, 12, 10)
    if sapling and rng.randrange(sapling_chances[fortune]) == 0:
        results.append(Reward(sapling, 1, 0))
    if rng.randrange((50, 45, 40, 30)[fortune]) == 0:
        results.append(Reward("minecraft:stick", rng.randint(1, 2), 0))
    if leaf in {"oak", "dark_oak"} and rng.randrange((200, 180, 160, 120)[fortune]) == 0:
        results.append(Reward("minecraft:apple", 1, 0))
    return tuple(results)


def plant_rewards(
    block_id: str,
    states: dict[str, object],
    rng: Random,
    *,
    silk_touch: bool = False,
    fortune: int = 0,
    shears: bool = False,
) -> tuple[Reward, ...] | None:
    """Bedrock-style block-break loot (not right-click harvesting).

    Fortune on crops uses the Bedrock 8/15 binomial trials; non-crop plants
    only use Fortune when their vanilla loot actually supports it.
    """
    if block_id not in PLANTS or type(fortune) is not int or not 0 <= fortune <= 3:
        return None
    if silk_touch:
        fortune = 0
    crop = block_id.removeprefix("minecraft:")

    if crop in {"wheat", "beetroot", "carrots", "potatoes"}:
        growth = states.get("growth")
        if type(growth) is not int or not 0 <= growth <= 7:
            return None
        if growth != 7:
            seed = {"wheat": "wheat_seeds", "beetroot": "beetroot_seeds",
                    "carrots": "carrot", "potatoes": "potato"}[crop]
            return (Reward(f"minecraft:{seed}", 1, 0),)

        # Bedrock: three Bernoulli trials at p=8/15, plus one per Fortune level.
        extras = sum(rng.randrange(15) < 8 for _ in range(3 + fortune))
        if crop in {"wheat", "beetroot"}:
            produce = "minecraft:wheat" if crop == "wheat" else "minecraft:beetroot"
            seeds = "minecraft:wheat_seeds" if crop == "wheat" else "minecraft:beetroot_seeds"
            return (Reward(produce, 1, 0),) + ((Reward(seeds, extras, 0),) if extras else ())

        item = "minecraft:carrot" if crop == "carrots" else "minecraft:potato"
        result = [Reward(item, rng.randint(1, 1 + fortune) + extras, 0)]
        if crop == "potatoes" and rng.random() < 0.02:
            result.append(Reward("minecraft:poisonous_potato", 1, 0))
        return tuple(result)

    if crop == "nether_wart":
        age = states.get("age")
        if type(age) is not int or not 0 <= age <= 3:
            return None
        return (Reward("minecraft:nether_wart", rng.randint(2, 4 + fortune) if age == 3 else 1, 0),)

    if crop == "cocoa":
        age = states.get("age")
        if type(age) is not int or not 0 <= age <= 2:
            return None
        return (Reward("minecraft:cocoa_beans", 3 if age == 2 else 1, 0),)

    if crop == "sweet_berry_bush":
        # Bedrock has growth 0..7, unlike Java's age 0..3.
        growth = states.get("growth")
        if type(growth) is not int or not 0 <= growth <= 7:
            return None
        if growth < 4:
            return ()
        low, high = (2, 3) if growth == 7 else (1, 2)
        return (Reward("minecraft:sweet_berries", rng.randint(low, high + fortune), 0),)

    if crop == "torchflower_crop":
        growth = states.get("growth")
        if type(growth) is not int or not 0 <= growth <= 1:
            return None
        return (Reward("minecraft:torchflower_seeds", 1, 0),)

    if crop == "shelf_mushroom":
        growth = states.get("growth")
        if type(growth) is not int or growth < 0:
            return None
        return (Reward(block_id, 2 if growth >= 3 else 1, 0),)

    if crop == "short_grass":
        if shears or silk_touch:
            return (Reward(block_id, 1, 0),)
        if rng.randrange(8) == 0:
            return (Reward("minecraft:wheat_seeds", rng.randint(1, 2 * fortune + 1), 0),)
        return ()

    if crop in {"short_dry_grass", "tall_dry_grass"}:
        return (Reward(block_id, 1, 0),) if shears or silk_touch else ()

    if crop == "nether_sprouts":
        return (Reward(block_id, 1, 0),) if shears else ()

    if crop == "reeds":
        return (Reward("minecraft:sugar_cane", 1, 0),)
    if crop in {"kelp", "kelp_plant"}:
        return (Reward("minecraft:kelp", 1, 0),)

    # Bamboo, cactus, small mushrooms and decorative flowers drop themselves.
    # Fortune and Silk Touch do not multiply these simple drops.
    return (Reward(block_id, 1, 0),)
