from random import Random

from endstone_vein_miner.rewards import Reward, reward_for


def test_unenchanted_vanilla_ore_drops_and_experience():
    rng = Random(1)
    assert reward_for("minecraft:iron_ore", rng) == Reward("minecraft:raw_iron", 1, 0)
    assert reward_for("minecraft:deepslate_gold_ore", rng) == Reward("minecraft:raw_gold", 1, 0)
    assert reward_for("minecraft:diamond_ore", rng).item == "minecraft:diamond"
    assert reward_for("minecraft:nether_quartz_ore", rng).item == "minecraft:quartz"
    assert reward_for("minecraft:ancient_debris", rng) == Reward("minecraft:ancient_debris", 1, 0)
    assert reward_for("minecraft:oak_log", rng) == Reward("minecraft:oak_log", 1, 0)
    assert reward_for("minecraft:oak_leaves", rng) == Reward("minecraft:oak_leaves", 1, 0)
    assert reward_for("minecraft:chest", rng) is None


def test_random_drops_stay_within_vanilla_ranges():
    rng = Random(2)
    for _ in range(40):
        lapis = reward_for("minecraft:lapis_ore", rng)
        copper = reward_for("minecraft:copper_ore", rng)
        redstone = reward_for("minecraft:redstone_ore", rng)
        assert 4 <= lapis.count <= 9 and 2 <= lapis.experience <= 5
        assert 2 <= copper.count <= 5
        assert 4 <= redstone.count <= 5 and 1 <= redstone.experience <= 5
