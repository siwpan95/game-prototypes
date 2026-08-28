# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

- R2 反向重构勘查（2026-08-27）：规则内核接入判定——本作区间随机不含 D&D/GURPS 骰系，alloy.trpg 无同构原语，按「只接同构原语」原则不接入（README 记账）；顺手清理打包产物并重写 .gitignore。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：Windows 可执行程序（PyInstaller，Python 3.14）。
- 发布面：gitee [siwpan/random-dungeon-](https://gitee.com/siwpan/random-dungeon-) release `v1.0.0`（随机地牢 v1.0.0）。