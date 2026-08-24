"""任务进度面板：展示每个任务及其需求的收集进度。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple

from yuanbao.tasks.task import Task


class TaskPanel(ttk.Frame):
    """右侧任务进度面板。"""

    def __init__(self, master, tasks: List[Task], **kwargs):
        super().__init__(master, **kwargs)
        self.tasks = tasks
        # 每个任务对应一组控件：(frame, progressbar, status_label, req_labels)
        self._rows: List[Tuple[ttk.LabelFrame, ttk.Progressbar, ttk.Label, List[ttk.Label]]] = []
        self._build()

    def _build(self) -> None:
        for t in self.tasks:
            grp = ttk.LabelFrame(self, text=t.name, padding=6)
            grp.pack(fill='x', padx=6, pady=4)

            pb = ttk.Progressbar(grp, maximum=1.0, value=t.progress, length=200)
            pb.pack(fill='x', pady=(0, 4))

            req_labels: List[ttk.Label] = []
            for req in t.requirements:
                lbl = ttk.Label(grp, text=self._req_text(req), font=('Microsoft YaHei', 9))
                lbl.pack(anchor='w')
                req_labels.append(lbl)

            status = ttk.Label(
                grp, text=self._status_text(t),
                font=('Microsoft YaHei', 9, 'bold'),
                foreground='#3E63DD',
            )
            status.pack(anchor='w', pady=(2, 0))
            self._rows.append((grp, pb, status, req_labels))

    @staticmethod
    def _req_text(req) -> str:
        mark = "✅" if req.done else "•"
        return f"{mark} {req.description}: {req.collected}/{req.count}"

    @staticmethod
    def _status_text(t: Task) -> str:
        return "状态: ✅ 完成" if t.completed else "状态: 进行中"

    def refresh(self) -> None:
        """根据任务对象当前数据刷新所有显示。"""
        for t, (grp, pb, status, req_labels) in zip(self.tasks, self._rows):
            pb['value'] = t.progress
            for lbl, req in zip(req_labels, t.requirements):
                lbl.config(text=self._req_text(req))
            if t.completed:
                status.config(text="状态: ✅ 完成", foreground='#30A46C')
            else:
                status.config(text="状态: 进行中", foreground='#3E63DD')
