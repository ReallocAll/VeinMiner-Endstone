"""Conservative vanilla-style rewards for unenchanted tools only.

Fortune, Silk Touch, specialized tools and non-vanilla blocks are intentionally not
simulated: incorrect rewards or missing durability must not be silently accepted.
"""

from dataclasses import dataclass
from random import Random

from .mining import LOGS, LEAVES, ORE_TIERS


@dataclass(frozen=True)
class Reward:
    item: str
    count: int
    experience: int


def reward_for(block_id: str, rng: Random) -> Reward | None:
    if block_id in LOGS or block_id in LEAVES:
        return Reward(block_id, 1, 0)
    if not block_id.startswith("minecraft:"):
        return None
    name = block_id.removeprefix("minecraft:")
    if name not in ORE_TIERS:
        return None
    if name.startswith("deepslate_"):
        name = name.removeprefix("deepslate_")

    match name:
        case "coal_ore":
            return Reward("minecraft:coal", 1, rng.randint(0, 2))
        case "iron_ore":
            return Reward("minecraft:raw_iron", 1, 0)
        case "gold_ore":
            return Reward("minecraft:raw_gold", 1, 0)
        case "copper_ore":
            return Reward("minecraft:raw_copper", rng.randint(2, 5), 0)
        case "diamond_ore":
            return Reward("minecraft:diamond", 1, rng.randint(3, 7))
        case "emerald_ore":
            return Reward("minecraft:emerald", 1, rng.randint(3, 7))
        case "lapis_ore":
            return Reward("minecraft:lapis_lazuli", rng.randint(4, 9), rng.randint(2, 5))
        case "redstone_ore":
            return Reward("minecraft:redstone", rng.randint(4, 5), rng.randint(1, 5))
        case "nether_quartz_ore" | "quartz_ore":
            return Reward("minecraft:quartz", 1, rng.randint(2, 5))
        case "nether_gold_ore":
            return Reward("minecraft:gold_nugget", rng.randint(2, 6), rng.randint(0, 1))
        case "ancient_debris":
            return Reward("minecraft:ancient_debris", 1, 0)
    return None
