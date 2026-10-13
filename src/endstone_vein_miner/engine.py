"""Main-thread experimental executor with per-block Territory and Tianyan checks.

This is deliberately limited to unenchanted tools. It is not a replacement for
BDS's native player-break and loot pipeline.
"""

from random import Random

from .mining import correct_tool
from .rewards import reward_for


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

def mine_extra(player, block_id: str, positions: list[tuple[int, int, int]], guard, audit, logger) -> int:
    dimension = player.dimension
    inventory = player.inventory
    tool = inventory.item_in_main_hand
    if tool is None or not correct_tool(block_id, str(tool.type)):
        return 0
    meta = tool.item_meta
    enchantments = _enchant_levels(meta)
    if enchantments is None:
        return 0
    durability = int(tool.type.max_durability)
    if durability <= 0:
        return 0

    count = 0
    rng = Random()
    for x, y, z in positions[:23]:
        live_tool = inventory.item_in_main_hand
        if live_tool is None or live_tool != tool:
            break
        if not player.is_valid or str(player.dimension.name) != str(dimension.name):
            break
        if not guard.can_break(str(player.name), bool(player.is_op), str(dimension.name), x, y, z):
            continue

        try:
            block = dimension.get_block_at(x, y, z)
            if block.type != block_id:
                continue
            reward = reward_for(
                block_id,
                rng,
                silk_touch=bool(enchantments.get("minecraft:silk_touch")),
                fortune=enchantments.get("minecraft:fortune", 0),
            )
            if reward is None:
                break
            previous = block.capture_state()
            states = str(block.data.block_states)
            uid = audit.prepare(str(player.name), str(dimension.name), (x, y, z), block_id, states)
        except Exception as exc:
            logger.warning(f"连锁挖掘预检失败，已停止: {exc}")
            break

        old_damage = meta.damage
        item_changed = False
        try:
            block.set_type("minecraft:air", apply_physics=False)
            if block.type != "minecraft:air":
                raise RuntimeError("方块未被移除")
            audit.finish(uid, success=True)

            # Settle tool wear before spawning drops or granting experience so a
            # failed inventory update can be rolled back without duplicating rewards.
            if not meta.is_unbreakable and rng.randrange(enchantments.get("minecraft:unbreaking", 0) + 1) == 0:
                meta.damage = old_damage + 1
                if meta.damage >= durability:
                    inventory.item_in_main_hand = None
                else:
                    if not tool.set_item_meta(meta):
                        raise RuntimeError("无法更新工具耐久")
                    inventory.item_in_main_hand = tool
                item_changed = True

            dimension.drop_item(previous.location, _new_item(reward.item, reward.count))
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

        # The drop has already been spawned and the block broken. An XP error
        # cannot safely be undone without duping the drop or block.
        if reward.experience:
            try:
                player.give_exp(reward.experience)
            except Exception as exc:
                logger.error(f"连锁挖掘经验发放失败 ({x},{y},{z}): {exc}")
                count += 1
                break
        count += 1
        if inventory.item_in_main_hand is None:
            break
    return count
