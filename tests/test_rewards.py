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
    assert reward_for("minecraft:diamond_ore", rng, silk_touch=True, fortune=1) == Reward("minecraft:diamond_ore", 1, 0)
    for level, max_count in ((1, 2), (2, 3), (3, 4)):
        for _ in range(60):
            assert 1 <= reward_for("minecraft:diamond_ore", rng, fortune=level).count <= max_count
            assert 4 <= reward_for("minecraft:redstone_ore", rng, fortune=level).count <= 5 + level
            assert 2 <= reward_for("minecraft:copper_ore", rng, fortune=level).count <= 5 * max_count


def test_barehand_leaves_use_independent_random_drops():
    from endstone_vein_miner.rewards import leaf_rewards

    rng = Random(61)
    oak = [leaf_rewards("minecraft:oak_leaves", rng) for _ in range(20000)]
    saplings = sum(any(r.item == "minecraft:oak_sapling" for r in drops) for drops in oak)
    sticks = sum(any(r.item == "minecraft:stick" for r in drops) for drops in oak)
    apples = sum(any(r.item == "minecraft:apple" for r in drops) for drops in oak)
    assert 800 < saplings < 1200
    assert 300 < sticks < 500
    assert 60 < apples < 140
    assert all(r.item != "minecraft:oak_leaves" for drops in oak for r in drops)

    mangrove = [leaf_rewards("minecraft:mangrove_leaves", rng) for _ in range(3000)]
    assert all(r.item != "minecraft:mangrove_propagule" for drops in mangrove for r in drops)
    assert all(r.item == "minecraft:stick" for drops in mangrove for r in drops)
    assert any(r.item == "minecraft:azalea" for _ in range(200) for r in leaf_rewards("minecraft:azalea_leaves", rng))
    assert leaf_rewards("minecraft:stone", rng) == ()


def test_bedrock_lit_redstone_ores_never_drop_unobtainable_lit_blocks():
    rng = Random(43)
    for block_id, silk_item in (
        ("minecraft:lit_redstone_ore", "minecraft:redstone_ore"),
        ("minecraft:lit_deepslate_redstone_ore", "minecraft:deepslate_redstone_ore"),
    ):
        normal = reward_for(block_id, rng)
        assert normal.item == "minecraft:redstone"
        assert 4 <= normal.count <= 5
        assert reward_for(block_id, rng, silk_touch=True) == Reward(silk_item, 1, 0)


def test_leaf_drop_helper_supports_fortune_chances_independently_of_axe_behavior():
    from endstone_vein_miner.rewards import leaf_rewards

    def sample(level):
        rng = Random(1973)
        items = [
            reward.item for _ in range(25000) for reward in leaf_rewards("minecraft:oak_leaves", rng, fortune=level)
        ]
        return {item: items.count(item) for item in ("minecraft:oak_sapling", "minecraft:stick", "minecraft:apple")}

    basic = sample(0)
    enhanced = sample(3)
    assert enhanced["minecraft:oak_sapling"] > basic["minecraft:oak_sapling"]
    assert enhanced["minecraft:stick"] > basic["minecraft:stick"]
    assert enhanced["minecraft:apple"] > basic["minecraft:apple"]


def test_bedrock_crop_fortune_uses_binomial_seed_rolls():
    from endstone_vein_miner.rewards import plant_rewards

    rng = Random(2026)
    trials = 5000
    base = [plant_rewards("minecraft:wheat", {"growth": 7}, rng) for _ in range(trials)]
    enhanced = [plant_rewards("minecraft:wheat", {"growth": 7}, rng, fortune=3) for _ in range(trials)]

    def count_seeds(drops):
        return sum(reward.count for reward in drops if reward.item == "minecraft:wheat_seeds")

    assert all(drops[0] == Reward("minecraft:wheat", 1, 0) for drops in base + enhanced)
    assert 1.45 < sum(map(count_seeds, base)) / trials < 1.75
    assert 3.0 < sum(map(count_seeds, enhanced)) / trials < 3.4
    assert max(map(count_seeds, base)) <= 3
    assert max(map(count_seeds, enhanced)) <= 6
    assert plant_rewards("minecraft:wheat", {"growth": 0}, rng, fortune=3) == (Reward("minecraft:wheat_seeds", 1, 0),)


def test_bedrock_carrot_potato_fortune_ranges_and_secondary_drops():
    from endstone_vein_miner.rewards import plant_rewards

    rng = Random(512)
    counts = [plant_rewards("minecraft:carrots", {"growth": 7}, rng, fortune=3)[0].count for _ in range(3000)]
    assert 5.4 < sum(counts) / len(counts) < 6.0
    assert min(counts) >= 1 and max(counts) <= 10
    potatoes = [plant_rewards("minecraft:potatoes", {"growth": 7}, rng) for _ in range(3000)]
    assert 30 < sum(any(reward.item == "minecraft:poisonous_potato" for reward in drops) for drops in potatoes) < 100
    assert plant_rewards("minecraft:potatoes", {"growth": 4}, rng, fortune=3) == (Reward("minecraft:potato", 1, 0),)


def test_bedrock_berry_state_nether_wart_and_decorative_shear_loot():
    from endstone_vein_miner.rewards import plant_rewards

    rng = Random(7)
    assert plant_rewards("minecraft:sweet_berry_bush", {"growth": 1}, rng) == ()
    assert plant_rewards("minecraft:sweet_berry_bush", {"growth": 2}, rng)[0].count in (1, 2)
    assert plant_rewards("minecraft:sweet_berry_bush", {"growth": 3}, rng)[0].count in (2, 3)
    assert plant_rewards("minecraft:sweet_berry_bush", {"growth": 3}, rng, fortune=3)[0].count in range(2, 7)
    assert plant_rewards("minecraft:sweet_berry_bush", {"growth": 7}, rng)[0].count in (2, 3)
    assert plant_rewards("minecraft:sweet_berry_bush", {"age": 3}, rng) is None
    assert plant_rewards("minecraft:nether_wart", {"age": 0}, rng, fortune=3) == (
        Reward("minecraft:nether_wart", 1, 0),
    )
    assert all(
        2 <= plant_rewards("minecraft:nether_wart", {"age": 3}, rng, fortune=3)[0].count <= 7 for _ in range(100)
    )
    assert plant_rewards("minecraft:short_grass", {}, rng, shears=True) == (Reward("minecraft:short_grass", 1, 0),)
    grass_silk = plant_rewards("minecraft:short_grass", {}, rng, silk_touch=True)
    assert all(reward.item != "minecraft:short_grass" for reward in grass_silk)
    assert plant_rewards("minecraft:short_dry_grass", {}, rng) == ()
    assert plant_rewards("minecraft:short_dry_grass", {}, rng, silk_touch=True) == (
        Reward("minecraft:short_dry_grass", 1, 0),
    )
    assert plant_rewards("minecraft:nether_sprouts", {}, rng, shears=True) == (
        Reward("minecraft:nether_sprouts", 1, 0),
    )
    assert plant_rewards("minecraft:nether_sprouts", {}, rng) == ()
    assert plant_rewards("minecraft:kelp", {}, rng) == (Reward("minecraft:kelp", 1, 0),)
    assert plant_rewards("minecraft:kelp_plant", {}, rng) == (Reward("minecraft:kelp", 1, 0),)


def test_silk_touch_never_turns_crop_into_block_item():
    from endstone_vein_miner.rewards import plant_rewards

    rng = Random(16)
    for crop, states in (
        ("wheat", {"growth": 7}),
        ("carrots", {"growth": 7}),
        ("potatoes", {"growth": 7}),
        ("beetroot", {"growth": 7}),
        ("cocoa", {"age": 2}),
        ("nether_wart", {"age": 3}),
    ):
        loot = plant_rewards(f"minecraft:{crop}", states, rng, silk_touch=True, fortune=3)
        assert loot
        if crop in {"carrots", "potatoes", "cocoa"}:
            assert all(reward.item != f"minecraft:{crop}" for reward in loot)
