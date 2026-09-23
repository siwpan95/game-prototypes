# 文字传奇 · 点怪就打 （MVP + ECS + MVVM 混合架构）

> 仓库：<https://gitee.com/siwpan/legend> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

原单文件 `demo.py` 按以下架构拆分为多模块：

## 架构说明

| 模块 | 架构 | 说明 |
|------|------|------|
| `ecs/` | ECS | 游戏逻辑（战斗/怪物/玩家），组件化实体，易扩展 |
| `mvvm/` | MVVM | UI 系统，`ViewModel` 绑定 `View` 与 `Model` |
| `mvc/` | MVC | 任务系统，快速实现小功能 |
| `skills/` | 混合 | ECS 组件 + MVVM 绑定 |

## 文件结构

```
lol/
├── main.py                   # 入口，组装所有模块
├── ecs/
│   ├── __init__.py
│   ├── world.py             # World：实体/组件管理，查询
│   ├── components.py        # 组件：HP/Attack/Exp/Respawn/Monster/Name
│   ├── systems.py           # 系统：combat/rest/respawn/level_up/reset
│   └── entities.py         # 实体工厂：create_player, create_monster
├── mvvm/
│   ├── __init__.py
│   ├── model.py            # GameModel：持有 World，提供游戏操作接口
│   ├── viewmodel.py        # GameViewModel：绑定属性 + 命令方法
│   └── view.py             # GameView：Tkinter UI，绑定 ViewModel
├── mvc/
│   ├── __init__.py
│   ├── model_task.py       # TaskModel：任务数据 + 进度管理
│   ├── controller_task.py  # TaskController：事件处理，奖励领取
│   └── view_task.py       # TaskView：任务列表 UI（嵌入主界面）
├── skills/
│   ├── __init__.py
│   ├── skill_components.py # ECS 组件：SkillSlot/Cooldown/SkillEffect
│   ├── skill_defs.py      # 技能定义（火焰斩/治疗术/闪电链）
│   └── skill_vm.py        # 技能 ViewModel（MVVM 绑定）
└── common/
    ├── __init__.py
    └── fonts.py            # cn_font() 中文字体工具
```

## 运行

```bash
cd <PATH>
python main.py
```

## 与原 demo.py 的差异

- 功能完全保留（攻击/暴击/闪避/死亡复活/升级/休息/经验池）
- 新增：任务系统（MVC，含 UI）
- 新增：技能系统（3 个示例技能，ECS+MVVM 混合）
- 架构清晰，各层职责明确，方便后续扩展
