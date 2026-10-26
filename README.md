# 孤独的沙漠公路 · Endless Highway 3D

> 仓库：<https://gitee.com/siwpan/lonely-desert-road> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

一款基于 **ECS 架构**的无尽沙漠公路驾驶游戏，含漂移玩法与电子风（synthwave）配乐。
**渲染层已整体迁移到 [3dworld 引擎](https://gitee.com/siwpan/3dworld)**（PyPI 发行名 `3dworld` / 导入名 `world3d`），
从原来的 pygame 2D 俯视画面变为真正的 3D 透视公路。

![3D 画面](docs/highway_3d.png)

## 实机演示视频

**[▶ Endless Highway 3D — 3 分钟实机演示](docs/demo_3d.mp4)**（1280×720 / 30fps / H.264 + AAC 立体声 / 20.1 MB）

画面取自**本进程回读的 GL 帧缓冲**（不是抓屏），音轨来自混音输出，保留自适应电子配乐。
内容覆盖：

| 时间 | 内容 |
| --- | --- |
| 0–6s | 开场行驶：透视公路、车道虚线、路旁装饰物、HUD 里程爬升 |
| 6–9.5s | **PAUSED** 覆盖层（暂停界面） |
| 9.5–162s | 主体驾驶：自动驾驶维持居中，转向侧倾、随机漂移、里程 0→470 km、漂移计数累积 |
| 162–180s | 冲出路肩撞毁 → **GAME OVER** 覆盖层（里程 / 漂移统计 / 红色闪车身） |

## 语言 / 类型

- Python / pyglet 3D 图形界面驾驶游戏（ECS 架构，基于 3dworld 引擎）

## 3D 重构做了什么

| 维度 | 重构前（pygame 2D） | 重构后（3dworld 3D） |
| --- | --- | --- |
| 图形 | `pygame.draw` 画矩形/多边形 | 3dworld `DemoApp` + pyglet OpenGL 透视渲染 |
| 几何 | 2D 像素图元 | `world3d.core.geometry.box_data` 程序化盒体拼装（车 / 路 / 仙人掌 / 岩石 / 枯灌木 / 护栏） |
| 坐标 | 屏幕像素 (x, y) | 世界坐标 (x 横向, y 竖向, z 纵深)，-z 为屏幕深处 |
| 相机 | 无（正交俯视） | 跟随相机：车后上方，带横向缓动与转向侧倾 |
| 纵深 | 靠"向下滚动"伪 3D | 真正的透视 + 距离雾（地平线与天空无缝衔接） |
| 操控 | 瞬移式左右移动 | 横向**速度 + 加速度 + 阻尼**，转向与漂移有惯性感 |
| 音频 | `pygame.mixer` | `sounddevice` 混音器（`audio/sd_mixer.py`），与 pyglet 同进程无冲突 |
| 框架 | 自建窗口/主循环 | 沿用 3dworld-demos 同一套范式：`world3d.platform.app.DemoApp` |

**保留不变的部分**：ECS 框架（`ecs/__init__.py` 的 World/Entity/Component/System）、
玩法手感（无尽滚动、随机漂移、撞路肩判死）、配置项语义（`config.json`）、以及整套
faatt 电子配乐与音效资产（19 个 WAV，合成器 `audio/synthesizer.py` 原样保留）。

## 安装与运行

```bat
:: ① 建虚拟环境并安装依赖（引擎在 PyPI，包名 3dworld / 导入名 world3d）
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

:: ② 运行
python main.py                 :: 正常游玩
python main.py --smoke 3       :: 冒烟 3 秒自动关闭
python main.py --shot          :: 抓帧到 docs/ 后自动关闭
python main.py --size 1280x720 :: 指定窗口尺寸
```

> 也可先执行 `env.bat` 一键设好环境变量与虚拟环境。
> `WORLD3D_PROJECT_ROOT` 指向本仓根目录（3dworld 的 `platform.app` 在**导入时**就用它
> 定位截图落点，pip 安装后若不设置会落到 site-packages 下）。

## 操作

| 按键 | 作用 |
| --- | --- |
| ← / → | 左右转向（带惯性与阻尼） |
| SPACE | 暂停 / 继续 |
| ESC | 退出 |

路面会随机把车往一边推（**漂移**），强度随里程增长——越跑越远，路面越滑。
撞上路肩即结束旅程。

## 目录

```
main.py            入口：HighwayApp(DemoApp) —— 装配 ECS 世界 + 3D 场景 + 音频 + 覆盖层
highway_scene.py   3D 表现层：程序化几何、着色器（带距离雾）、跟随相机、绘制
ecs/               玩法逻辑（与渲染无关，不 import 任何图形库）
  __init__.py        ECS 框架（World / Entity / Component / System）
  components.py      组件：Position(3D) / Lateral / Drift / Decoration / GameState ...
  systems.py         系统：Input / Motion / Drift / Collision / Scroll / Decoration*
audio/             电子配乐与音效（sounddevice 播放，pygame 已完全移除）
  sd_mixer.py        sounddevice 版轻量混音器（替代 pygame.mixer）
  synthesizer.py     faatt 程序化合成（numpy/scipy）
  music_system.py    分层自适应音乐（按里程淡入）
  sfx_system.py      引擎音 / 漂移 / 撞击 / UI / 奖励音效
  ecs_system.py      ECS 音频系统（由 GameState 驱动）
config.json        参数：窗口、公路、玩家、漂移、装饰物 + threed 段（3D 专属）
faatt.py           独立的音频工作站 GUI 工具（开发用，游戏不依赖）
scripts/
  smoke_logic.py    玩法逻辑冒烟测试（不开窗口、不碰 GL）
  record_demo.py    实机录像：一键录制 + 音视频封装出片
docs/              抓帧产物 + 实机演示视频
```

## 实机录像

```bat
:: 录制 3 分钟实机演示（自动驾驶 + 演示编排 + 配乐）
pip install -r requirements-dev.txt          :: 提供 ffmpeg（imageio-ffmpeg 自带）
python scripts/record_demo.py --duration 180 --out docs/demo_3d.mp4
```

实现要点：

- **画面**：进程内 `glReadPixels` 回读 GL 帧缓冲 → rawvideo 管道 → ffmpeg（libx264）。
  不是抓屏，因此不受窗口遮挡/最小化/桌面壁纸影响；`glReadPixels` 是自下而上的，
  写入前按行翻转，否则成片上下颠倒。
- **音频**：`audio/sd_mixer.py` 把混音输出直接落成 WAV，最后与视频封装成 mp4。
- **节流**：按墙钟时间节流到目标帧率，保证成片是**实时**速度而非快放。
- **演示编排**（`--demo`）：自动驾驶维持居中 → 6s 暂停展示 PAUSED → 末段冲出路肩
  展示 GAME OVER；提前意外撞毁会自动复活，保证录到完整内容。
- ffmpeg 查找顺序：`WORLD3D_FFMPEG` → PATH → `imageio-ffmpeg` → 常见安装位置。

## 配置

`config.json` 的 `threed` 段是 3D 专属参数：

| 键 | 含义 |
| --- | --- |
| `road_half_width` | 公路半宽（世界单位）—— 也是碰撞判定边界 |
| `road_far_z` / `road_near_z` | 公路的远/近端深度 |
| `deco_spawn_z` | 装饰物生成深度（比路面尽头近，保证一进场就有东西） |
| `world_scroll` | 世界朝镜头滚动的速度（世界单位/秒） |
| `camera_height` / `camera_back` / `camera_look_ahead` | 跟随相机机位 |
| `steer_accel` / `lateral_drag` | 转向加速度与横向阻尼 |
| `drift_world_scale` | 漂移冲量换算到世界速度的系数 |
| `fog_near` / `fog_far` | 距离雾起止（雾色默认取天空色） |

## 测试状态

- `py_compile` 语法检查通过（13 个 .py）
- `python scripts/smoke_logic.py` —— 玩法逻辑冒烟 **11 项全通过**
  （里程累计 / 装饰生成 / 装饰回收 / 转向 / 阻尼 / 漂移冲量 / 撞路肩判死 / 死亡后停止推进）
- `python main.py --shot` —— 实机抓帧通过，渲染 3D 画面正常，**59.5 fps**（1280×720）
- `python scripts/record_demo.py` —— 实机录像 3 分钟出片（5402 帧 / 30.0 fps），
  音轨 mean -16.9 dB、peak -0.8 dB
- 音频链路：sounddevice 混音器启动成功，5 个音乐分层 + 14 个音效加载并播放，退出时干净关闭

## 许可

MIT-0（MIT No Attribution），见 [LICENSE](LICENSE)。
