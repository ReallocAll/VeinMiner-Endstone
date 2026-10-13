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


def test_silk_touch_and_fortune_resource_drops():
    rng = Random(14)
    assert reward_for("minecraft:diamond_ore", rng, silk_touch=True) == Reward("minecraft:diamond_ore", 1, 0)
    assert reward_for("minecraft:deepslate_redstone_ore", rng, silk_touch=True) == Reward(
        "minecraft:deepslate_redstone_ore", 1, 0
    )
    assert reward_for("minecraft:diamond_ore", rng, silk_touch=True, fortune=1) is None
    for level, max_count in ((1, 2), (2, 3), (3, 4)):
        for _ in range(60):
            assert 1 <= reward_for("minecraft:diamond_ore", rng, fortune=level).count <= max_count
            assert 4 <= reward_for("minecraft:redstone_ore", rng, fortune=level).count <= 5 + level
            assert 2 <= reward_for("minecraft:copper_ore", rng, fortune=level).count <= 5 * max_count
