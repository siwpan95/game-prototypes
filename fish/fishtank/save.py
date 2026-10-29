"""存档读写：在引擎 `SaveLoadManager` 之上补三件它没做的事。

🔴 禁止 `from __future__ import annotations`（E6）。

引擎实读结论（`allin_engine/systems/save_load.py`）与我们的补丁：

===========================  ==========================================
引擎行为                      本模块的处理
===========================  ==========================================
`_write_save` 直接 open+write  ★ 改为 `.tmp` → `os.replace` → `.bak`
（断电/崩溃会写出半截文件）      三段式原子落盘（ARCHITECTURE §6.5）
`load()` 只返回 `state_data`,  ★ 我们在载荷里**冗余存** `saved_at_utc`
信封里的 `timestamp` 被丢弃     （E4），离线结算不依赖信封
无损坏回退                     ★ 主档解析失败自动回退 `.bak`
===========================  ==========================================

存档落点：`%APPDATA%\\LazyFishTank\\saves\\autosave.json`
（由 `engine_bootstrap` 通过 `ALLIN_USER_DATA` 重定向，见 E3）。
"""

import json
import os
import time

from fishtank.constants import BACKUP_SUFFIX, SCHEMA_VERSION, TEMP_SUFFIX
from fishtank.engine_bootstrap import SaveLoadManager, get_logger, save_dir
from fishtank.state import GameState, now_utc

_log = get_logger("fishtank")


class SaveManager:
    """自动存档管理器（单槽 autosave）。

    用法::

        sm = SaveManager()
        sm.save(state)          # 原子写
        st = sm.load()          # 主档坏了自动回退 .bak，都坏了返回 None
    """

    def __init__(self, directory="", enabled=True, logger=None, keep_backups=1):
        """:param directory: 存档目录；留空则用引擎（重定向后）的 saves 目录。
        :param enabled: False 时 :meth:`save` 变成空操作（对应 CLI ``--no-save``）。
        """
        self._log = logger or _log
        self.enabled = bool(enabled)
        self.keep_backups = max(0, int(keep_backups))
        self.directory = directory or save_dir()
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError as e:
            self._log.warning("存档目录不可创建(%s)：%s" % (self.directory, e))
        # 复用引擎的槽位命名 / 信封格式，只接管落盘那一步
        self._mgr = SaveLoadManager(self.directory, version=SCHEMA_VERSION,
                                    logger=self._log)
        self.last_error = ""

    # ── 路径 ──

    def path(self):
        """主存档路径。"""
        return self._mgr._auto_path()

    def backup_path(self):
        """备份存档路径。"""
        return self.path() + BACKUP_SUFFIX

    def temp_path(self):
        """临时文件路径。"""
        return self.path() + TEMP_SUFFIX

    def exists(self):
        """是否存在可读的存档（主档或备份）。"""
        return os.path.isfile(self.path()) or os.path.isfile(self.backup_path())

    # ── 写 ──

    def save(self, state, when=None):
        """原子保存。

        🔴 三段式：先写 `.tmp` 并 `fsync`，把旧主档改名成 `.bak`，
        再 `os.replace(tmp, main)`。`os.replace` 在 Windows/POSIX 上都是原子的，
        因此任何时刻磁盘上至少有一份完整存档。

        🔴 时间锚点单调：`saved_at_utc = max(旧值, now)`，
        系统时钟被回拨也不会让玩家凭空损失一段离线收益（准则 L2）。

        :returns: 是否成功
        """
        if not self.enabled:
            return True
        ts = int(when) if when is not None else now_utc()
        state.saved_at_utc = max(int(state.saved_at_utc), ts)

        envelope = {
            "version": SCHEMA_VERSION,
            "timestamp": float(ts),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
            "state_data": state.to_dict(),
        }
        try:
            text = json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=False)
        except (TypeError, ValueError) as e:
            self.last_error = "序列化失败：%s" % e
            self._log.error("[save] " + self.last_error)
            return False

        tmp = self.temp_path()
        main = self.path()
        bak = self.backup_path()
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            if self.keep_backups > 0 and os.path.isfile(main):
                try:
                    os.replace(main, bak)
                except OSError as e:
                    # 备份失败不阻断主流程：主档马上就会被完整覆盖
                    self._log.warning("[save] 备份失败：%s" % e)
            os.replace(tmp, main)
            self.last_error = ""
            return True
        except OSError as e:
            self.last_error = "落盘失败：%s" % e
            self._log.error("[save] " + self.last_error)
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False

    # ── 读 ──

    def load(self):
        """读取存档。主档损坏时自动回退备份。

        :returns: GameState 或 None（两份都没有/都坏了）
        """
        for path, tag in ((self.path(), "主档"), (self.backup_path(), "备份")):
            payload = self._read_payload(path)
            if payload is None:
                continue
            try:
                st = GameState.from_dict(payload)
            except (TypeError, ValueError, AttributeError) as e:
                self._log.warning("[save] %s 解析为状态失败：%s" % (tag, e))
                continue
            if tag != "主档":
                self._log.warning("[save] 主档不可用，已从备份恢复：%s" % path)
            return st
        return None

    def _read_payload(self, path):
        """读出信封里的 `state_data`；文件不存在/损坏返回 None。

        兼容两种布局：带信封的（引擎格式）与裸载荷的（手工导入）。
        """
        if not os.path.isfile(path):
            return None
        MAX_SAVE_SIZE = 50 * 1024 * 1024  # 50MB
        try:
            fsize = os.path.getsize(path)
        except OSError:
            fsize = 0
        if fsize > MAX_SAVE_SIZE:
            self._log.warning("[save] 存档文件过大(%d bytes)，拒绝加载" % fsize)
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            self._log.warning("[save] 读取失败(%s)：%s" % (path, e))
            return None
        if not isinstance(data, dict):
            return None
        payload = data.get("state_data")
        if isinstance(payload, dict):
            file_ver = data.get("version", 0)
            if file_ver != SCHEMA_VERSION:
                self._log.warning("[save] 存档版本 v%s ≠ 当前 v%s，按兼容模式读取"
                                  % (file_ver, SCHEMA_VERSION))
            return payload
        # 裸载荷
        if "fishes" in data or "coins_milli" in data:
            return data
        return None

    # ── 其他 ──

    def delete(self):
        """删除主档与备份（用于"重开一局"）。返回删掉的文件数。"""
        n = 0
        for p in (self.path(), self.backup_path(), self.temp_path()):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    n += 1
                except OSError as e:
                    self._log.warning("[save] 删除失败(%s)：%s" % (p, e))
        return n

    def info(self):
        """返回主档的元信息 dict（供调试 / 设置页展示）。"""
        path = self.path()
        if not os.path.isfile(path):
            return {"exists": False, "path": path}
        try:
            stat = os.stat(path)
            size = stat.st_size
            mtime = int(stat.st_mtime)
        except OSError:
            size, mtime = 0, 0
        return {"exists": True, "path": path, "size": size, "mtime": mtime,
                "backup": os.path.isfile(self.backup_path())}
