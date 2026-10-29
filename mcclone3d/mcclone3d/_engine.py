# -*- coding: utf-8 -*-
"""引擎接入层：定位 `world3d` / `cordis`，并把本项目登记成引擎的一个服务。

## 为什么需要这一层（而不是直接 `import world3d`）

引擎 `world3d` 来自**另一个仓**（[`siwpan/3dworld`](https://gitee.com/siwpan/3dworld)，发行名 `3dworld`）。
它现在**是** PyPI 包（`pip install 3dworld`），但开发时也常常要用**本地检出**
（改引擎源码、跑未发布的改动）—— 所以"引擎在哪"仍是**运行期事实**。

两条通路，按优先级（⚠ Phase 3-B 起把顺序倒过来了，理由见下）：

1. **`MC3D_ENGINE_ROOT` 指向本地检出** ⇒ 用它（插到 `sys.path[0]`，**盖住已安装的包**）；
2. 已安装的 PyPI 包 `3dworld`（`requirements.txt` 里那一行）；
3. 都没有 → **抛一条点名说清怎么办的错误**（`EngineNotFound`）。

⚠ **为什么本地检出要优先**：早先的顺序是"先 `import world3d`，失败才看环境变量"。
引擎没上 PyPI 时这没问题（本地没装就 import 不到）；**上了 PyPI 之后就危险了** ——
只要 `pip install -r requirements.txt` 装过包，"先 import"那条**永远成功**，
`MC3D_ENGINE_ROOT` 变成一句被静默忽略的摆设：开发者以为在测本地改动，
实际测的是发布快照（"测量的代码 ≠ 提交的代码"，这一条在本仓的调试铁律里专门记过）。

所以现在：**设了环境变量就认它**，并且加载到的模块若**不在**那个目录下，直接
**响亮抛错**（说明多半是 `world3d` 已被 import 过、包抢先了），而不是默默用别的引擎。

**不做的事**：不在本仓里塞引擎副本、不瞎猜盘符路径（`铁律 5`）、失败时**不静默降级**
（`调试铁律 39 / g17`：SKIP 不是通过，找不到引擎就得响亮地失败）。

## 与引擎的三个扩展点（本项目只用这三个，不改引擎一行）

| 扩展点 | 作用 |
| --- | --- |
| `world3d.host.registry.SERVICES` | 可写封闭表：短名 `mcclone` → 本仓内核类 |
| `WORLD3D_CONFIGS` 环境变量 | 让引擎的 `host.tree.config_path()` 来**本仓** `configs/` 找配置树 |
| `world3d.host.tree.mount_tree(path, want=...)` | 挂载配置树（demo 与 headless 验收共用同一份接线） |

`registry.SERVICES` 是引擎里唯一的"服务短名 → 实现类"表（见 `host/registry.py` 的模块
说明），**登记新服务就是往这张表加一行** —— 引擎作者已把它设计成可写，这里只是照用。
登记后 `bind('mcclone')` 会为短名合成一个只含 `default` 的宿主模块（`_3dwsrv.mcclone`），
而配置树里的 `- name: mcclone` 就能解析到本仓内核。
"""
from __future__ import annotations

import os
import sys

__all__ = [
    'SERVICE_NAME', 'EngineNotFound', 'kernel_path', 'config_dir',
    'ensure_importable', 'register_service', 'setup', 'blocks', 'texproj',
    'geometry', 'registry', 'Service',
]

#: 本项目在引擎注册表里的服务短名（配置树里写 `- name: mcclone`）
SERVICE_NAME = 'mcclone'

#: 本仓根（本文件在 <仓根>/mcclone3d/_engine.py ⇒ 上两级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 配置树目录（`WORLD3D_CONFIGS` 会指向它）
CONFIG_DIR = os.path.join(ROOT, 'configs')

#: 引擎的实现模块路径（`register_service` 把短名映射到这里）
KERNEL_MODULE = 'mcclone3d.kernel'
KERNEL_CLASS = 'McCloneKernel'


class EngineNotFound(RuntimeError):
    """找不到 3dworld 引擎（`world3d`）时抛这个 —— 消息里带着**怎么办**。"""


def kernel_path() -> str:
    """本仓内核在注册表里的登记值（`模块:类`）。"""
    return f'{KERNEL_MODULE}:{KERNEL_CLASS}'


def config_dir() -> str:
    """本仓配置树目录的绝对路径。"""
    return CONFIG_DIR


def _try_import_world3d():
    """尝试 import world3d；成功返回模块，失败返回 None（不抛）。"""
    try:
        import world3d  # noqa: F401
    except ImportError:
        return None
    return sys.modules['world3d']


def ensure_importable(verbose: bool = False):
    """确保 `world3d` 可 import，返回该模块；找不到就**响亮失败**。

    查找顺序（⚠ 详见模块 docstring：本地检出**优先**）：
    ① `MC3D_ENGINE_ROOT` 指到 3dworld 检出 → 插到 `sys.path[0]`，盖住已安装的包；
    ② 已安装的 PyPI 包 `3dworld`；
    ③ 都没有 → `EngineNotFound`。
    """
    root = os.environ.get('MC3D_ENGINE_ROOT')
    if root:
        cand = os.path.abspath(root)
        if not os.path.isdir(os.path.join(cand, 'world3d')):
            raise EngineNotFound(
                f'MC3D_ENGINE_ROOT 指向的目录里没有 world3d/ 包：{cand}\n'
                f'  期望结构：<3dworld 检出>/world3d/__init__.py')
        if cand not in sys.path:
            sys.path.insert(0, cand)
        mod = _try_import_world3d()
        if mod is None:
            raise EngineNotFound(
                f'MC3D_ENGINE_ROOT={cand} 里找到了 world3d/ 目录，但 import 仍然失败。\n'
                f'  多半是那个检出本身有语法错误 / 缺依赖 —— 直接跑一遍：\n'
                f'    cd /d {cand} && python -c "import world3d; print(world3d.__version__)"')
        got = os.path.normcase(os.path.abspath(getattr(mod, '__file__', '') or ''))
        want = os.path.normcase(cand)
        if got and not got.startswith(want):
            # 设了本地检出、却加载到别处 ⇒ 必须**响亮失败**。
            # 静默用别的引擎 = 开发者以为在测本地改动，其实在测发布快照（最坏的一类坑）。
            raise EngineNotFound(
                f'MC3D_ENGINE_ROOT={cand} 没有生效：实际加载到 {got}。\n'
                f'  原因通常是 **world3d 在本进程里已经被 import 过**（已安装的 PyPI 包抢先），\n'
                f'  再插 sys.path 也换不掉（Python 的模块缓存）。怎么修：\n'
                f'    ① 先设环境变量、再启动进程（别在进程里事后设）；或\n'
                f'    ② python -m pip uninstall 3dworld（只用本地检出时）')
        if verbose:
            print(f'[engine] 由 MC3D_ENGINE_ROOT 挂载本地检出：{cand}', flush=True)
        return mod

    mod = _try_import_world3d()
    if mod is not None:
        if verbose:
            print(f'[engine] 用已安装的 3dworld 包：'
                  f'{os.path.abspath(getattr(mod, "__file__", "") or "")}', flush=True)
        return mod

    raise EngineNotFound(
        '找不到 3dworld 引擎（import world3d 失败）。二选一：\n'
        '  ① 装 PyPI 包（推荐，requirements 里已有）：\n'
        '       python -m pip install -r requirements.txt\n'
        '  ② 用本地检出（开发引擎本身时）：设 MC3D_ENGINE_ROOT 指向它\n'
        '       set MC3D_ENGINE_ROOT=<你的 3dworld 检出>\n'
        '本项目**不自带引擎副本**，所以这一步无法省略。')


def register_service(verbose: bool = False) -> str:
    """把本仓内核登记进引擎的服务注册表，返回服务短名。

    幂等：已登记（且指向同一个值）时直接返回；**指向别处时抛错**而不是覆盖 ——
    悄悄覆盖别人的登记是"两个实现抢一个短名"，必须在现场爆出来。
    """
    ensure_importable()
    from world3d.host import registry as _registry

    have = _registry.SERVICES.get(SERVICE_NAME)
    want = kernel_path()
    if have == want:
        return SERVICE_NAME
    if have is not None:
        raise RuntimeError(
            f'服务短名 {SERVICE_NAME!r} 已被占用：现有 {have!r}，本仓想登记 {want!r}。\n'
            f'  ⇒ 要么换短名（改 _engine.SERVICE_NAME 并同步 configs/ 与 WANT），'
            f'要么先查清是谁登记的。**不在此处静默覆盖**。')
    _registry.SERVICES[SERVICE_NAME] = want
    if verbose:
        print(f'[engine] 登记服务短名：{SERVICE_NAME} -> {want}', flush=True)
    return SERVICE_NAME


def setup(verbose: bool = False):
    """一步到位：定位引擎 → 登记服务 → 把配置树目录指给引擎。

    返回 `world3d` 模块。**demo 与 headless 验收都必须先调它** ——
    这样"引擎怎么接的"只有这一处，两边不可能接得不一样。
    """
    mod = ensure_importable()
    register_service(verbose=verbose)
    # 让 host.tree.config_path() 来本仓 configs/ 找配置树（引擎自己读这个变量）
    os.environ.setdefault('WORLD3D_CONFIGS', CONFIG_DIR)
    if verbose:
        print(f'[engine] WORLD3D_CONFIGS={os.environ["WORLD3D_CONFIGS"]}', flush=True)
    return mod


# ------------------------------------------------------------------ 惰性转发
# 这些名字是"引擎侧对象"的转发口。做成模块级 __getattr__ 而不是顶部 import：
# 顶部 import 会让**只看不改**的场景（如 `--help`、文档生成）也必须先有引擎，
# 而模块级 __getattr__ 只在真正取用时才去找引擎。
_FORWARD = {
    'blocks': 'world3d.logic.blocks',
    'texproj': 'world3d.engine.texproj',
    'geometry': 'world3d.engine.geometry',
    'registry': 'world3d.host.registry',
    'tree': 'world3d.host.tree',
}


def __getattr__(name):
    if name == 'Service':
        ensure_importable()
        from cordis import Service
        return Service
    target = _FORWARD.get(name)
    if target is not None:
        ensure_importable()
        import importlib
        return importlib.import_module(target)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
