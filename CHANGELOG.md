# Changelog

## 2.0.3+server.10 — Chinese server specialization

- Added UUID-keyed Chinese GUI settings for mining, trees, leaves, plants and optional crouching.
- Added an administrator-only GUI for persisted total block caps (default / 24 / 64 / 128 / 256).
- Enabled bounded extra mining with per-block Territory checks, read-only chunk discovery and at most eight extra removals per tick.
- Added mixed stone/deepslate ore matching, giant-tree diagonal branches, natural-leaf bridges and selected Bedrock 26.52 vegetation.
- Leaf chains now require an axe. Normal leaves yield probabilistic saplings, sticks or apples; Fortune adjusts chances and Silk Touch yields leaf blocks. Bare hands and shears no longer activate leaf chains.
- Improved Territory hot-path checks with per-dimension snapshots and pre-normalized claim bounds. Dynamic claim updates are still refreshed before each mining batch.
- Handled unrelated enchantments without disabling chains and added guarded Fortune, Silk Touch, Unbreaking and held-tool Mending calculations.
- Removed the runtime dependency on Tianyan; extra blocks are not written to Tianyan's audit log.
- Added Python 3.12–3.15 CI and independent BDS startup verification through bds-test-lab only.

Known limitations: exact native Bedrock drops for all exotic blocks, multi-slot Mending XP allocation, mobile-client mining and live claim-boundary behavior have not been end-to-end verified.
