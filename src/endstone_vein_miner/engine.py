"""Main-thread bounded miner with per-block Territory checks and Bedrock loot simulation."""

from random import Random

from .audit import format_states
from .mining import LEAVES, PLANTS, VERTICAL_PLANTS, correct_tool, ore_family
from .rewards import Reward, leaf_rewards, plant_rewards, reward_for


def _new_item(item_id: str, count: int):
    from endstone.inventory import ItemStack

    return ItemStack(item_id, count)


# Only enchantments that affect this plugin's settlement need interpretation.
# Other enchantments are retained untouched in the original ItemMeta.
MINING_LEVEL_CAPS = {
    "minecraft:fortune": 3,
    "minecraft:silk_touch": 1,
    "minecraft:unbreaking": 3,
    "minecraft:mending": 1,
}


def _enchant_levels(meta) -> dict[str, int]:
    if not meta.has_enchants:
        return {}
    levels = {}
    for enchantment, level in meta.enchants.items():
        name = str(enchantment.id)
        if name in MINING_LEVEL_CAPS and type(level) is int and level > 0:
            levels[name] = min(level, MINING_LEVEL_CAPS[name])
    # Command-created tools may carry both. Vanilla uses Silk Touch first.
    if levels.get("minecraft:silk_touch"):
        levels.pop("minecraft:fortune", None)
    return levels


def _award_experience(player, inventory, tool, meta, enchants: dict[str, int], experience: int) -> None:
    # give_exp directly adds levels and does not create collectible Mending XP orbs.
    # Repair the held Mending tool first; Endstone cannot currently route this XP
    # through the full vanilla equipped-item Mending selection mechanism.
    if experience > 0 and enchants.get("minecraft:mending") and meta is not None:
        if inventory.item_in_main_hand is not None and not meta.is_unbreakable:
            damage = int(meta.damage)
            if damage > 0:
                spent = min(experience, (damage + 1) // 2)
                meta.damage = max(0, damage - spent * 2)
                if not tool.set_item_meta(meta):
                    meta.damage = damage
                    raise RuntimeError("无法修复经验修补工具")
                inventory.item_in_main_hand = tool
                experience -= spent
    if experience > 0:
        player.give_exp(experience)


def mine_extra(
    player, block_id: str, positions: list[tuple[int, int, int]], guard, audit, logger, *,
    canopy: bool = False, axe_leaf_enchants: bool = False
) -> int:
    dimension = player.dimension
    inventory = player.inventory
    tool = inventory.item_in_main_hand
    tool_id = str(tool.type) if tool is not None else "minecraft:air"
    hand = tool_id == "minecraft:air"
    axe_leaf_enchants = axe_leaf_enchants and tool_id.endswith("_axe")
    if not correct_tool(block_id, tool_id) and not (canopy and block_id.endswith("_leaves")):
        return 0
    meta = tool.item_meta if not hand else None
    enchantments = _enchant_levels(meta) if meta is not None else {}
    durability = int(tool.type.max_durability) if meta is not None else 0
    if (
        meta is not None
        and durability <= 0
        and (tool_id == "minecraft:shears" or tool_id.endswith(("_pickaxe", "_axe", "_hoe", "_shovel", "_sword")))
    ):
        # A real tool with missing durability metadata is unsafe to consume.
        return 0

    count = 0
    family = ore_family(block_id)
    vertical_family = VERTICAL_PLANTS.get(block_id)
    rng = Random()
    for x, y, z in positions[:8]:
        live_tool = inventory.item_in_main_hand
        if hand:
            if live_tool is not None and str(live_tool.type) != "minecraft:air":
                break
        elif live_tool is None or live_tool != tool:
            break
        if not player.is_valid or str(player.dimension.name) != str(dimension.name):
            break
        if not guard.can_break(str(player.name), bool(player.is_op), str(dimension.name), x, y, z):
            continue

        try:
            block = dimension.get_block_at(x, y, z)
            actual_id = str(block.type)
            if family is not None:
                matched = ore_family(actual_id) == family
            elif vertical_family is not None:
                matched = VERTICAL_PLANTS.get(actual_id) == vertical_family
            else:
                matched = actual_id == block_id
            if not matched:
                continue
            if not correct_tool(actual_id, tool_id) and not (canopy and actual_id.endswith("_leaves")):
                continue
            if actual_id in PLANTS:
                rewards = plant_rewards(
                    actual_id,
                    block.data.block_states,
                    rng,
                    silk_touch=bool(enchantments.get("minecraft:silk_touch")),
                    fortune=enchantments.get("minecraft:fortune", 0),
                    shears=tool_id == "minecraft:shears",
                )
                if rewards is None:
                    continue
            elif actual_id in LEAVES:
                # Opt-in axe leaf enchantments; otherwise natural hand-break loot.
                if tool_id == "minecraft:shears" or (
                    axe_leaf_enchants and enchantments.get("minecraft:silk_touch")
                ):
                    rewards = (Reward(actual_id, 1, 0),)
                else:
                    fortune = enchantments.get("minecraft:fortune", 0) if axe_leaf_enchants else 0
                    rewards = leaf_rewards(actual_id, rng, fortune=fortune)
            else:
                reward = reward_for(
                    actual_id,
                    rng,
                    silk_touch=bool(enchantments.get("minecraft:silk_touch")),
                    fortune=enchantments.get("minecraft:fortune", 0),
                )
                if reward is None:
                    break
                rewards = (reward,)
            previous = block.capture_state()
            uid = (
                audit.prepare(
                    str(player.name), str(dimension.name), (x, y, z), actual_id, format_states(block.data.block_states)
                )
                if audit is not None
                else None
            )
        except Exception as exc:
            logger.warning(f"连锁挖掘预检失败，已停止: {exc}")
            break

        old_damage = meta.damage if meta is not None else 0
        item_changed = False
        try:
            block.set_type("minecraft:air", apply_physics=False)
            if block.type != "minecraft:air":
                raise RuntimeError("方块未被移除")
            if audit is not None:
                audit.finish(uid, success=True)

            # Settle tool wear before spawning drops or granting experience so a
            # failed inventory update can be rolled back without duplicating rewards.
            if (
                meta is not None
                and durability > 0
                and (actual_id not in LEAVES or tool_id == "minecraft:shears" or axe_leaf_enchants)
                and not meta.is_unbreakable
                and rng.randrange(enchantments.get("minecraft:unbreaking", 0) + 1) == 0
            ):
                meta.damage = old_damage + 1
                if meta.damage >= durability:
                    inventory.item_in_main_hand = None
                else:
                    if not tool.set_item_meta(meta):
                        raise RuntimeError("无法更新工具耐久")
                    inventory.item_in_main_hand = tool
                item_changed = True

        except Exception as exc:
            try:
                if block.type == "minecraft:air" and not previous.update(force=True, apply_physics=False):
                    logger.error(f"连锁挖掘回滚失败 ({x},{y},{z})")
                if item_changed:
                    meta.damage = old_damage
                    tool.set_item_meta(meta)
                    inventory.item_in_main_hand = tool
                if audit is not None:
                    audit.finish(uid, success=False)
            except Exception as rollback_exc:
                logger.error(f"连锁挖掘回滚/审计失败 ({x},{y},{z}): {rollback_exc}")
            logger.error(f"连锁挖掘执行失败，已停止: {exc}")
            break

        # Once an item spawn is attempted, the call may raise *after* creating
        # an entity. Do not restore the block in that ambiguous case: it could
        # duplicate both the block and spawned reward.
        try:
            for reward in rewards:
                dimension.drop_item(previous.location, _new_item(reward.item, reward.count))
        except Exception as exc:
            logger.error(f"连锁挖掘掉落生成状态不明，停止且不回滚 ({x},{y},{z}): {exc}")
            count += 1
            break

        # The drop has already been spawned and the block broken. An XP error
        # cannot safely be undone without duping the drop or block.
        experience = sum(reward.experience for reward in rewards)
        if experience:
            try:
                _award_experience(player, inventory, tool, meta, enchantments, experience)
            except Exception as exc:
                logger.error(f"连锁挖掘经验/经验修补结算失败 ({x},{y},{z}): {exc}")
                count += 1
                break
        count += 1
        if not hand and inventory.item_in_main_hand is None:
            break
    return count
