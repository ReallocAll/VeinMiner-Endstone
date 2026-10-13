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
    if not 0 <= fortune <= 3 or (silk_touch and fortune):
        return None
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
def leaf_rewards(block_id: str, rng: Random) -> tuple[Reward, ...]:
    if block_id not in LEAVES:
        return ()
    leaf = block_id.removeprefix("minecraft:").removesuffix("_leaves")
    sapling = None
    if leaf == "azalea":
        sapling = "minecraft:azalea"
    elif leaf == "flowering_azalea":
        sapling = "minecraft:flowering_azalea"
    elif leaf != "mangrove":
        sapling = f"minecraft:{leaf}_sapling"

    results = []
    if leaf in {"red_poplar", "orange_poplar", "yellow_poplar"}:
        sapling = "minecraft:poplar_sapling"
    if leaf == "azalea_leaves_flowered" or block_id == "minecraft:azalea_leaves_flowered":
        sapling = "minecraft:flowering_azalea"
    if sapling and rng.random() < (0.025 if leaf == "jungle" else 0.05):
        results.append(Reward(sapling, 1, 0))
    if rng.random() < 0.02:
        results.append(Reward("minecraft:stick", rng.randint(1, 2), 0))
    if leaf in {"oak", "dark_oak"} and rng.random() < 0.005:
        results.append(Reward("minecraft:apple", 1, 0))
    return tuple(results)


def plant_rewards(block_id: str, states: dict[str, object], rng: Random) -> tuple[Reward, ...] | None:
    """Hand harvesting for simple one-block plants; never invent crop loot."""
    if block_id not in PLANTS:
        return None
    crop = block_id.removeprefix("minecraft:")
    if crop in {"wheat", "carrots", "potatoes", "beetroot", "nether_wart", "cocoa", "sweet_berry_bush", "torchflower_crop"}:
        key = "age" if crop in {"nether_wart", "cocoa"} else "growth"
        age = states.get(key)
        if type(age) is not int or age < 0:
            return None
        if crop in {"wheat", "carrots", "potatoes"} and age > 7:
            return None
        if crop == "beetroot" and age > 7:
            return None
        if crop in {"nether_wart", "sweet_berry_bush"} and age > 3:
            return None
        if crop == "cocoa" and age > 2:
            return None
        if crop == "torchflower_crop":
            # Torchflowers mature into a different block, not the crop itself.
            return (Reward("minecraft:torchflower_seeds", 1, 0),) if age < 2 else None
        if crop == "nether_wart":
            return (Reward("minecraft:nether_wart", rng.randint(2, 4) if age == 3 else 1, 0),)
        if crop == "cocoa":
            return (Reward("minecraft:cocoa_beans", 3 if age == 2 else 1, 0),)
        if crop == "sweet_berry_bush":
            if age < 2:
                return ()
            return (Reward("minecraft:sweet_berries", rng.randint(2, 3) if age == 3 else rng.randint(1, 2), 0),)
        if crop == "wheat":
            if age >= 7:
                count = rng.randint(0, 3)
                return (Reward("minecraft:wheat", 1, 0),) + ((Reward("minecraft:wheat_seeds", count, 0),) if count else ())
            return (Reward("minecraft:wheat_seeds", 1, 0),)
        if crop == "beetroot":
            if age >= 7:
                count = rng.randint(0, 3)
                return (Reward("minecraft:beetroot", 1, 0),) + ((Reward("minecraft:beetroot_seeds", count, 0),) if count else ())
            return (Reward("minecraft:beetroot_seeds", 1, 0),)
        if crop in {"carrots", "potatoes"}:
            item_id = "minecraft:carrot" if crop == "carrots" else "minecraft:potato"
            count = rng.randint(1, 4) if age >= 7 else 1
            result = [Reward(item_id, count, 0)]
            if crop == "potatoes" and age >= 7 and rng.random() < 0.02:
                result.append(Reward("minecraft:poisonous_potato", 1, 0))
            return tuple(result)
    if block_id == "minecraft:shelf_mushroom":
        growth = states.get("growth")
        if type(growth) is not int:
            return None
        return (Reward(block_id, 2 if growth >= 3 else 1, 0),)
    if block_id in {"minecraft:short_grass", "minecraft:short_dry_grass", "minecraft:tall_dry_grass"}:
        return (Reward("minecraft:wheat_seeds", 1, 0),) if rng.random() < 0.125 else ()
    if block_id == "minecraft:nether_sprouts":
        return ()
    if block_id == "minecraft:reeds":
        return (Reward("minecraft:sugar_cane", 1, 0),)
    if block_id == "minecraft:kelp_plant":
        return (Reward("minecraft:kelp", 1, 0),)
    return (Reward(block_id, 1, 0),)
