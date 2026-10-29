# kid_a_walker

KID-A WALKER：暗色赛博风格的第一人称步行模拟器（伪无限地图，模块化随机拼接）。

## 语言/类型
Python 3（pygame-ce），桌面 GUI 游戏。

## 目录要点
- `kid_a_walker.py`：入口（**文件名不可改**，arcade 合集按 `games/kid-a-walker/kid_a_walker.py` 拉起）
- `kaw/`：实现（2026-10-09 由单文件 2951 行拆包而来）
  - `config.py` `state.py`：常量 / 状态机
  - `world/`：43 个 21×21 房间模板 + 无限区块网格
  - `systems/`：能量 / 碎片 / 交互 / 能力 / 探索
  - `audio/`：区域合成 BGM + 音效
  - `render/`：渲染后端（`raycast.py` 原始伪 3D、`enhanced.py` 增强版、`textures.py` 程序化纹理；
    `gl.py` + `camera.py` + `meshgen.py` = ModernGL 真 3D）
  - `ui/`：HUD / 图鉴 / 加载界面 / 结算
  - `game.py`：主控状态机
- `kid_a_walker.spec`：PyInstaller 打包配置（`pathex` 带 SPECPATH，`hiddenimports` 列全 kaw 子模块，
  并用 hook 工具收 `moderngl` / `glcontext`）
- `tools/regression.py`：渲染/逻辑回归（见下）
- `tests/test_map.py`：地图系统不变量测试（见下）

## 运行方式与依赖
```
<PATH>/python.exe kid_a_walker.py     # 装有 pygame、numpy、moderngl 的解释器
```
依赖：`pygame-ce`、`numpy`、`moderngl`（`gl` 后端用；缺失时自动回退 `enhanced`）。
GUI 窗口游戏，运行后会阻塞等待交互。

## 操作
| 键 | 作用 |
|---|---|
| W/A/S/D 或方向键 | 移动 / 转向 |
| 鼠标 | 视角（横转 + 俯仰） |
| R / F | 俯仰（无鼠标时的备用） |
| E | 交互拾取 |
| Tab | 碎片图鉴 |
| R（结算页） | 重开 |
| Esc | 退出 |

## 渲染后端
`kaw/config.py` 的 `RENDER_BACKEND` 切换（三后端接口一致 `draw_world`，可直接 A/B 对比）：

- `"gl"`（默认）：**ModernGL 真 3D + 后处理管线**。区块网格（地板/墙/天花板，面剔除 +
  向量化烘焙）+ 装饰物 billboard（实例化渲染，软发光）+ shader 里的距离雾/程序化网格/重力照明，
  再经 **EEVEE 式 bloom mip 链**（软膝亮通 → Karis 加权 box 下采样 → 9-tap tent 上采样累加，
  半精度 HDR：R11F_G11F_B10F → RGBA16F → RGBA8 自动回退）→ 扫描线→暗角→曝光 合成上屏；
  粒子为世界坐标（透视投影）。
  - 有显示时走 **window 模式**：`pygame.OPENGL` 真窗口，3D 渲进 FBO、后处理后直接上屏，
    2D 覆盖层（HUD/界面）作为纹理叠加，**无像素读回**（真机实测 p50≈5.6ms / 177 FPS）。
  - 无 GL 窗口（无头/兼容）自动退 **offscreen 模式**：同一套管线渲染后读回 blit 到 2D 主屏。
  - 再不行自动回退 `enhanced`。
- `"enhanced"`：伪 3D 增强版。地面/天花板透视投影（Doom 式 shade table + mip）、
  俯仰视角、装饰物 billboard 精灵。无 GL 环境的稳妥选择。
- `"raycast"`：原始实现，纯色渐变地板/天花板、装饰物渲染成整面彩色墙。

`FLOOR_BUFFER_SCALE` 控制 `enhanced` 地面投射的降采样倍率（2 为默认，3 更快、略糊）。
`GL_FOV_Y` / `GL_FOG_DENSITY` / `GL_REGION_RADIUS` / `GL_EXPOSURE` / `GL_BLOOM_*` 等控制
`gl` 后端。

## 测试
```
<PATH>/python.exe tools/regression.py
<PATH>/python.exe tools/perf_window.py      # 真机 window 模式帧时（无头无效）
<PATH>/python.exe tools/bloom_probe.py      # bloom/网格观感对比样张（无头可跑）
<PATH>/python.exe tools/capture_gameplay.py # 完整流程录制 → build_test/gameplay_full.mp4
<PATH>/python.exe tests/test_map.py
```

**tools/regression.py（渲染/逻辑回归）**

- **A 段 确定性回放**：固定种子 + 脚本化输入跑 120 帧，打印 5 个关键帧的逐像素画面哈希
  与终局玩法状态。改代码后对比输出，可确认有没有动到不该动的东西。**渲染后端的切换会改变
  画面哈希（预期），但玩法状态应当始终稳定。**
- **B 段 完整生命周期**：开始界面 → 预加载 → 游戏 → 死亡结算 → 重开 → 再进游戏。
  （B 段的世界用随机种子，只做流程联调，不做确定性比对。）

**tests/test_map.py（地图系统三个不变量）**

- 模版出口一致性（43 模版"声明出口 == 网格开口"）
- 门洞互通（同模版各门内格互相连通——防"通而不达"/死路）
- 区块出口互连 + 出生点可达（防单边出口 / 出生点牢笼）

> 2026-10-09：地图测试上线时即抓到并修复三类真实缺陷——分组错放
> （tech_nook / data_temple / generator_room 声明出口与实现不符）、
> 单边出口（随机扩充不检查已生成邻居）、门洞通而不达
> （energy_core / portal_gate 四门与大厅之间隔着两行墙、
> generator_room 西侧门廊被发电机块封死）。修复已随拆包移植进 `kaw/world/`。
