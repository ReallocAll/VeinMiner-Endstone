# VeinMiner-Endstone（服务器特化 Fork）

基于 [EuphoriaDevelopmentOrg/VeinMiner-Endstone v2.0.3](https://github.com/EuphoriaDevelopmentOrg/VeinMiner-Endstone) 的中文生存服特化分支，保留原始 MIT 许可证及版权声明。

> **当前为未完成的安全改造，禁止替代正式服务器上的连锁挖矿插件。** 本分支实现了玩家设置、中文原生 GUI、命令、持久化和未接入破坏流程的只读连通搜索；**额外连锁方块破坏明确禁用**。切换设置只保存偏好，不会产生自动挖掘。

## 已实现

- 玩家五项独立设置：总开关默认关闭、需要蹲下默认开启、矿石默认开启、树木及树叶默认关闭。
- UUID 字符串索引的 JSON 持久化，每次设置变更原子替换写入；普通读取不产生磁盘 I/O。
- Endstone 原生 ActionForm 中文 GUI，点击一键切换，重进服务器及重启后保留。
- 玩家可执行 `/vm` 或 `/vm gui`，`/veinminer` 是别名；`/vm on`、`/vm off` 仅改变个人开关。
- `/vm reload` 仅限具有 `veinminer.reload` 权限的管理员，重新读取玩家设置文件。
- 内置针对有限原版方块的严格工具等级判断和只读有界 BFS：每次最多选中 24 个方块（含起始方块），搜索范围为 6 格半径及同一区块；尚未接入玩家挖掘事件，也不执行世界修改。\n- 不运行 HTTP 更新检查、MySQL、统计存储或额外粒子与音效。不会向聊天栏发送连锁成功提示。

## 安全阻塞

Endstone 0.11 的公开 Python Block API 只有直接修改方块状态的 `set_type`/`set_data`/`BlockState.update`，没有经证实可完成玩家授权、原版掉落、经验、附魔、耐久和事件审计的原版玩家挖掘入口。

现有 [Territory](https://github.com/yuhangle/endstone-territory) 保护判断是 C++ 内部实现，未公开稳定的 Python 逐方块授权服务；[Tianyan](https://github.com/yuhangle/endstone-tianyan-plugin) 的公开 C++ `ITianyanAPI` 仅用于读取日志，不提供额外方块破坏的可调用写入接口。

直接调用 `set_type("minecraft:air")`、`setblock`、`fill destroy` 或手工发奖都会绕过必要的保护、审计或原版结算，因此**不启用这些变通方法**。在得到可证实且可测试的安全接口前，所有额外挖掘均 fail-closed。未实现实际矿石/树木/树叶连锁破坏、掉落、耐久及成功提示，这些功能不能作为已完成项验收。

## 安装与操作

要求 Endstone 0.11、Python 3.12～3.15；BDS 26.51 需要实机验证。构建：`python -m build --wheel`。只在隔离测试服安装 Wheel 到 `plugins/` 并重启。

ClockMenu 使用玩家身份执行 `vm`（不带斜杠的命令字符串按 ClockMenu 当前配置格式填写）；VeinMiner 无 ClockMenu 依赖。

数据文件：`plugins/vein-miner/players.json`（具体目录由 Endstone 的 `data_folder` 决定）。如文件损坏，加载将报错而非覆盖原有玩家设置。

## 开发验证

`ruff check src tests`、`PYTHONPATH=src pytest -q`、`python -m build --wheel`。

以上自动测试只覆盖设置与 GUI mock，不代表 BDS、Territory、Tianyan 或 ClockMenu 实机验证通过。PR 合并前必须先解决安全接口和额外破坏实现，再完成原版掉落、耐久及保护实机回归验证。
