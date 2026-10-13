# VeinMiner-Endstone — 中文生存服特化 Fork（Draft）

基于 EuphoriaDevelopmentOrg/VeinMiner-Endstone v2.0.3，保留上游 MIT 许可证及版权声明。

> **尚未完成全部任务，不能合并或部署正式服务器。** 本分支包含实际连锁挖掘代码，但未完成原版行为和第三方插件兼容性验收。

## 已开发的部分

- 中文原生 ActionForm 和玩家命令 /vm（别名 /veinminer），五项独立设置：总开关默认关闭、要求蹲下默认开启、矿石默认开启、树木/树叶默认关闭。
- UUID JSON 持久化；原子写入，未变更时不写盘。
- 有界 BFS：每次最多额外选择 23 格；半径 6，限制在起始区块内。矿石 26 方向，树木与树叶 6 方向。
- 监听真实 BlockBreakEvent，原版玩家破坏成功后的下一 tick 再检查目标方块、游戏模式和工具，避免处理被取消的原始事件。
- 参考 ReallocAll/endstone-arborist 的只读 SQLite 方式读取 Territory 数据库和配置。采用 if_break（不是 Arborist 的 if_build）逐方块校验，包含成员、父子领地与 OP 规则；查询异常时 fail-closed。
- 为每个实验性额外破坏写入 Tianyan SQLite LOGDATA 审计记录（执行前记录 pending，确认后修改为成功，失败改为 canceled）。这是基于上游数据库结构的兼容代码，**不是 Tianyan 稳定公开的写入 API**。
- 实验性奖励结算仅覆盖明确支持的原版矿石、原木及树叶；已有时运、精准采集、耐久、效率的受限计算，其他附魔（包括经验修补）仍拒绝连锁。当前结算不能保证全部特殊原版行为一致。
- 成功使用 Tip 提示，不刷聊天栏，不依赖 ClockMenu。

## 启用条件

**服务器级连锁挖掘默认启用，不再读取 experimental.json。** 玩家个人总开关继续默认关闭；玩家使用 `/vm on` 或菜单开启后，按其“蹲下触发”和矿石/树木/树叶设置工作。每个额外目标仍要求 Territory 数据库中具有逐方块 `if_break` 权限，且 Tianyan SQLite 破坏日志功能可用。依赖或权限检查失败，额外破坏自动拒绝。

**注意：尚未实测的原版掉落和跨插件细节不应视为已经验收；首次部署建议保留可恢复的世界备份。**

### 安装与 CI

要求 Endstone 0.11、Python 3.12～3.15。成功的 GitHub Actions CI 页面底部 Artifacts 提供 veinminer-wheel-py3，解压后为通用 .whl 包。只可用于隔离测试服。ClockMenu 执行 vm 可打开中文 GUI。

### 尚未完成的验收

1. **完整原版行为：** 已有时运、精准采集与耐久的受限计算，但未实测验证随机分布、所有方块状态/掉落、经验修补、工具破损、原版挖掘事件及邻近物理更新一致性。
2. **跨插件稳定性：** Territory 动态变化与子领地边界；Tianyan 审计查询、回溯、部分失败恢复；其他保护插件。
3. **Tianyan 兼容范围：** 目前仅 SQLite 后端；MySQL 和稳定服务接口尚未实现。
4. **真实 BDS 验证与性能：** 已通过真实 BDS 的插件加载、控制台命令、正常关服冒烟测试；尚未实测玩家连锁挖掘、玩家并发、原始事件取消、权限突变、读盘延迟、数据库竞争及 MSPT。
5. **发布质量：** 未满足以上内容之前，PR 保持 Draft，不创建正式 Release，不宣称插件完成。

目前 CI 已覆盖静态检查、单元测试、Wheel 构建、Endstone API 导入和真实 BDS 插件生命周期；**不能替代真实玩家挖掘、领地边界和 Tianyan 回溯验收**。BDS 启停成功日志参见 https://github.com/ReallocAll/VeinMiner-Endstone/actions/runs/38384995024。
