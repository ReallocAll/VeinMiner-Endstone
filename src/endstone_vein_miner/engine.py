"""Main-thread experimental executor with per-block Territory and Tianyan checks.

Vanilla leaf rolls and selected enchantments are simulated. This is not a replacement for
BDS's native player-break and loot pipeline.
"""

from random import Random

from .audit import format_states
from .mining import correct_tool, ore_family
from .rewards import leaf_rewards, reward_for


def _new_item(item_id: str, count: int):
    from endstone.inventory import ItemStack

    return ItemStack(item_id, count)


ENCHANTMENTS = {"minecraft:efficiency", "minecraft:fortune", "minecraft:silk_touch", "minecraft:unbreaking"}


def _enchant_levels(meta) -> dict[str, int] | None:
    if not meta.has_enchants:
        return {}
    levels = {}
    for enchantment, level in meta.enchants.items():
        name = str(enchantment.id)
        if name not in ENCHANTMENTS or type(level) is not int or level < 1:
            return None
        if level > (1 if name == "minecraft:silk_touch" else 3 if name != "minecraft:efficiency" else 5):
            return None
        levels[name] = level
    if levels.get("minecraft:silk_touch") and levels.get("minecraft:fortune"):
        return None
    return levels


def mine_extra(
    player, block_id: str, positions: list[tuple[int, int, int]], guard, audit, logger, *, canopy: bool = False
) -> int:
    dimension = player.dimension
    inventory = player.inventory
    tool = inventory.item_in_main_hand
    tool_id = str(tool.type) if tool is not None else "minecraft:air"
    hand = tool_id == "minecraft:air"
    if not correct_tool(block_id, tool_id) and not (canopy and block_id.endswith("_leaves")):
        return 0
    meta = tool.item_meta if not hand else None
    enchantments = _enchant_levels(meta) if meta is not None else {}
    if enchantments is None:
        return 0
    durability = int(tool.type.max_durability) if meta is not None else 0
    if meta is not None and durability <= 0:
        return 0

    count = 0
    family = ore_family(block_id)
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
            if (family is not None and ore_family(actual_id) != family) or (
                family is None and actual_id != block_id
            ):
                continue
            if not correct_tool(actual_id, tool_id) and not (canopy and actual_id.endswith("_leaves")):
                continue
            if canopy or hand:
                rewards = leaf_rewards(actual_id, rng)
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
            states = format_states(block.data.block_states)
            uid = audit.prepare(str(player.name), str(dimension.name), (x, y, z), actual_id, states)
        except Exception as exc:
            logger.warning(f"连锁挖掘预检失败，已停止: {exc}")
            break

        old_damage = meta.damage if meta is not None else 0
        item_changed = False
        try:
            block.set_type("minecraft:air", apply_physics=False)
            if block.type != "minecraft:air":
                raise RuntimeError("方块未被移除")
            audit.finish(uid, success=True)

            # Settle tool wear before spawning drops or granting experience so a
            # failed inventory update can be rolled back without duplicating rewards.
            if (
                meta is not None
                and not canopy
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
                player.give_exp(experience)
            except Exception as exc:
                logger.error(f"连锁挖掘经验发放失败 ({x},{y},{z}): {exc}")
                count += 1
                break
        count += 1
        if not hand and inventory.item_in_main_hand is None:
            break
    return count
