# game-prototypes

> **Tier ③ 收敛归档仓** — 薄游戏原型的收纳地，每个原仓保留完整 git 历史（`archive/<原仓>` 分支）与独立子目录副本。
> 原仓已冻结、不再开发；本仓只作**引擎演示素材库**，不追求可玩性完善。

## 内容

34 个薄游戏（`Idle` / `adventurelog` / `arcade` / `ashen-beacon` / … / `yuanbao`），逐个目录平铺在仓根。
收纳清单（原仓、原分支、历史分支对照）见 [ARCHIVE.md](ARCHIVE.md)。

## 使用

```bash
cd <游戏目录>          # 例如 cd arcade
python main.py         # 各游戏入口不同，见其 README
```

历史脚本以 `git log archive/<原仓>` 查看，或 `git checkout archive/<原仓>` 取回原仓完整工作树。

## 许可

MIT（见 [LICENSE](LICENSE)）。各收录项目的原作者与来源见 [ARCHIVE.md](ARCHIVE.md) 与各目录内 README。
