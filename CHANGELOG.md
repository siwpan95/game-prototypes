# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased] — 3D 重构

### Changed

- **渲染层整体迁移到 3dworld 引擎**（PyPI 发行名 `3dworld` / 导入名 `world3d`）：
  入口改为继承 `world3d.platform.app.DemoApp`，沿用 3dworld-demos 的工程范式
  （`--smoke` / `--shot` / `--size` 命令行、引擎自带 HUD 与截图）。
- 几何改为程序化 3D 盒体拼装（`world3d.core.geometry.box_data`）：车辆、路面、
  路肩、车道虚线、仙人掌、岩石、枯灌木、护栏。
- 坐标系由屏幕像素 (x, y) 改为世界坐标 (x 横向, y 竖向, z 纵深)。
- 新增跟随相机（车后上方，横向缓动 + 转向侧倾）与距离雾（地平线与天空无缝衔接）。
- 操控由"瞬移式"移动改为横向速度模型：转向加速度 + 指数阻尼，漂移施加冲量。
- 音频播放后端由 `pygame.mixer` 换成 `sounddevice`（新增 `audio/sd_mixer.py`，
  与 `pygame.mixer` 同表面 API，`music_system` / `sfx_system` / `audio_manager`
  零改动接入）——pygame 与 pyglet 同进程会争抢事件循环，故 pygame 依赖被彻底移除。
- `config.json` 新增 `threed` 段承载 3D 专属参数（路宽、相机机位、雾、漂移系数等）。

### Added

- `env.bat`：一键设置 `WORLD3D_PROJECT_ROOT` 与虚拟环境（对齐 3dworld-demos 约定）。
- `scripts/smoke_logic.py`：玩法逻辑冒烟测试（不开窗口、不碰 GL），11 项断言。
- `recorder.py` + `scripts/record_demo.py`：实机录像链路——进程内回读 GL 帧缓冲
  喂 ffmpeg rawvideo 管道（不受窗口遮挡影响），音轨由混音输出直接落 WAV 后封装；
  附 `--demo` 演示编排（自动驾驶 + 暂停展示 + 末段撞毁）与 `--autopilot` 自动驾驶。
- `requirements-dev.txt`：录制用依赖（imageio-ffmpeg 自带 ffmpeg 二进制）。
- `docs/highway_3d.png`、`docs/highway_crash.png`：3D 画面抓帧产物。
- `docs/demo_3d.mp4`：3 分钟实机演示视频（1280×720 / 30fps / H.264 + AAC 立体声）。

### Fixed

- **音频混音链三处缺陷**（均在 `audio/sd_mixer.py`，此前导致"日志显示加载成功、
  实际没有声音"或"撞毁后音频彻底哑掉"）：
  - 未暴露 `Channel(id)` 工厂：`mixer.Channel(id)` 每次新建**未注册**的孤立对象，
    播放指令落在没人混音的对象上 → 全部静音。改为按编号返回注册表里的通道。
  - 一次性音效剩余数据长于一个音频块时，`seg[:take] = d[start:]` 形状不匹配
    抛广播异常 → 整个混音链每帧中断（撞毁音效即触发）。
  - 淡出斜坡与 `seg` 形状不匹配（`(n,)` vs `(n,2)`）→ 广播异常，且异常发生在
    `playing=False` 之前导致通道永不停止、异常持续。

### Removed

- 依赖 `pygame-ce`；2D 专用的 `RectRender` / `LineRender` / `DashedLineRender` /
  `RoadSurface` / `RoadEdge` 组件与对应的 2D 渲染系统。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：Windows 可执行程序（PyInstaller，Python 3.14）。
- 发布面：gitee [siwpan/lonely-desert-road](https://gitee.com/siwpan/lonely-desert-road) release `v1.0.0`（孤独的沙漠公路 v1.0.0）。