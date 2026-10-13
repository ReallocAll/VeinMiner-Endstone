"""Small main-thread-only executor for carefully constrained extra block removals.

Only unenchanted tools are handled while proper native player-break and loot
interfaces remain unavailable. Every target is checked against Territory and
pre-logged in Tianyan. No synthetic BlockBreakEvent or privileged command is used.
"""

from random import Random

from .mining import correct_tool
from .rewards import reward_for


def _new_item(item_id: str, count: int):
    from endstone.inventory import ItemStack

    return ItemStack(item_id, count)


def mine_extra(player, block_id: str, positions: list[tuple[int, int, int]], guard, audit, logger) -> int:
    dimension = player.dimension
    inventory = player.inventory
    tool = inventory.item_in_main_hand
    if tool is None or not correct_tool(block_id, str(tool.type)):
        return 0
    meta = tool.item_meta
    if meta.has_enchants:
        # Fortune, Silk Touch, Unbreaking and other enchantments need exact vanilla semantics.
        return 0
    durability = int(tool.type.max_durability)
    if durability <= 0:
        return 0
    count = 0
    rng = Random()
    for x, y, z in positions:
        # Do not continue once a later callback has changed the player's equipment.
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
            reward = reward_for(block_id, rng)
            if reward is None:
                break
            previous = block.capture_state()
            states = str(block.data.block_states)
            uid = audit.prepare(str(player.name), str(dimension.name), (x, y, z), block_id, states)
        except Exception as exc:
            logger.warning(f"连锁挖掘预检失败，已停止: {exc}")
            break
        try:
            block.set_type("minecraft:air", apply_physics=False)
            if block.type != "minecraft:air":
                raise RuntimeError("方块未被移除")
            audit.finish(uid, success=True)
            dimension.drop_item(previous.location, _new_item(reward.item, reward.count))
            if reward.experience:
                player.give_exp(reward.experience)
            if not meta.is_unbreakable:
                meta.damage += 1
                if meta.damage >= durability:
                    inventory.item_in_main_hand = None
                    count += 1
                    break
                if not tool.set_item_meta(meta):
                    raise RuntimeError("无法更新工具耐久")
                inventory.item_in_main_hand = tool
            count += 1
        except Exception as exc:
            # Best-effort reversal is preferable to silently losing an item or unlogged block.
            try:
                if block.type == "minecraft:air":
                    if not previous.update(force=True, apply_physics=False):
                        logger.error(f"连锁挖掘回滚失败 ({x},{y},{z})")
                audit.finish(uid, success=False)
            except Exception as rollback_exc:
                logger.error(f"连锁挖掘回滚/审计失败 ({x},{y},{z}): {rollback_exc}")
            logger.error(f"连锁挖掘执行失败，已停止: {exc}")
            break
    return count
