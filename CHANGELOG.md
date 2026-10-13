# Changelog

基于 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)；正式插件版本采用 `MAJOR.MINOR.PATCH`，Tag 为 `vX.Y.Z`。

## [Unreleased]

## [2.1.0] - 2026-10-14

### Changed
- 在 `/vm` 中文菜单中显示两行简洁使用说明。
- 统一使用标准语义化版本号与 `vX.Y.Z` 标签，移除 `+server.x` 本地版本后缀。
- 使用版本校验、测试、Wheel 构建和 SHA256 校验文件发布正式 GitHub Release。

### Included
- 支持矿物、树木、树叶和植被连锁，玩家独立开关与管理员单次连锁上限。
- 树叶连锁需使用斧子；支持时运和精准采集的对应掉落。
- Territory 逐块权限检查与有界批次执行；保留附魔工具兼容，不写入 Tianyan 日志。

## [2.0.3+server.10] - 2026-10-14

- 历史 Fork 发行版本，保留原始 GitHub Release，不再延续 `+server.x` 编号。
- 完成首轮中文界面、26.52 方块覆盖、领地保护及附魔兼容。
