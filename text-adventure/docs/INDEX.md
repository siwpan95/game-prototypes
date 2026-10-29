# INDEX — 文档枢纽总目录

> **时点** 2026-10-16 ｜ **覆盖** 枢纽 3 + 规范 1 + 事实源 1 + 记录 6 = **11 份**
> （`枢纽` 计入枢纽门面、总目录与规范类索引——索引类的存在只为让枢纽可用，与枢纽件同槽计数。
> 记录口径按**入口文档**计：`records/README.md` + 2 份记录 + `records/platform-research-2026-10/README.md`，
> 后者索引下辖 4 份报告，报告不单独在此登记以免重复计数。）
> **范围** `docs/` 下全部受管文档。四分类判据见 [`README.md`](README.md)。
> **登记是硬要求**：没登记进本文件的文档等于不存在。

登记行的格式：`ID · 标题 · 路径 · 状态 · 时点 · 一句话摘要`。

## 枢纽 · Hub

| ID | 标题 | 路径 | 状态 | 时点 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| HUB-01 | 文档枢纽门面 | [README.md](README.md) | 生效 | 2026-10-16 | 四分类判据、怎么加文档、与治理门禁的关系 |
| HUB-02 | 本总目录 | [INDEX.md](INDEX.md) | 生效 | 2026-10-16 | 全量登记；新增文档必须登记于此 |
| HUB-03 | 规范类索引 | [spec/README.md](spec/README.md) | 生效 | 2026-10-16 | 效力等级、引用格式、规范清单、规范必须带的头部字段 |

## 规范 · Specifications

未来有人必须照着做的东西。文件名不带日期（效力与修订日期写在头部）。

| ID | 标题 | 路径 | 状态 | 时点 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| SPEC-101 | 平台化路线图（谜题即插件 → 内容平台） | [spec/SPEC-101-platform-roadmap.md](spec/SPEC-101-platform-roadmap.md) | 生效 | 2026-10-16 | 三层架构（渲染/编排/领域）、M0–M5 分阶段路线、六条红线；判断均带实测或联网来源 |
| SPEC-102 | 内容包投稿与审核（面向投稿者与维护者） | [content-submission.md](content-submission.md) | 生效 | 2026-10-16 | 包格式、投稿命令、签名覆盖范围（语义而非字节）、五态签名结论与各策略下的取舍 |
| SPEC-103 | 在线内容包服务（部署者与投稿者） | [pack-service.md](pack-service.md) | 生效 | 2026-10-16 | 隔离区/发布区/客户端三级可见性、HTTP 面、客户端**先验后装**、限流与上限、**绑公网前必须补的鉴权** |

## 事实源 · Facts

当前状态的权威台账，须带时点、观测命令与过期条件。**本卷当前为空**：
本仓还没有「被多处引用的状态值」，README 的「测试状态」与 `docs/records/` 承担此职，
等出现第二处引用再建台账（理由见索引件）。

| ID | 标题 | 路径 | 状态 | 时点 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| FACT-AU-01 | 事实源类的准入与现状 | [facts/README.md](facts/README.md) | 生效 | 2026-10-16 | 什么算事实源、必须带的三样东西、为什么现在是空的 |

## 记录 · Records

一次性发生的证据，只追加。文件名带日期或月份卷。

| ID | 标题 | 路径 | 状态 | 时点 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| REC-AU-01 | 记录类的准入与命名 | [records/README.md](records/README.md) | 生效 | 2026-10-16 | 什么算记录、命名规则、只追加纪律 |
| REC-01 | 启动崩溃修复与改造起点 | [records/text-adventure-boot-crash-fix_2026-10-16.md](records/text-adventure-boot-crash-fix_2026-10-16.md) | 生效 | 2026-10-16 | 三个缺陷的实测证据（缺失字体模块、死掉的 .venv、同名模块遮蔽）、14 种谜题的输入健壮性表 |
| REC-02 | Cordis 化与 Web 层落地 | [records/text-adventure-cordis-web_2026-10-16.md](records/text-adventure-cordis-web_2026-10-16.md) | 生效 | 2026-10-16 | 三层架构的实测验证（58 条 pytest + 11 项宿主冒烟）、构建过程中被实测抓到的问题 |
| REC-03 | 内容包落地与两个实测缺陷 | [records/content-pack-m2_2026-10-16.md](records/content-pack-m2_2026-10-16.md) | 生效 | 2026-10-16 | M2 内容包（154 条，由模块派生）、4 字母池混入 5 字母词的脏数据、英文填字界面的 UnboundLocalError |
| REC-04 | 命令行客户端 | [records/cli-client_2026-10-16.md](records/cli-client_2026-10-16.md) | 生效 | 2026-10-16 | 终端客户端作为当前主力交互面；开发中被测试抓到的 6 个真实缺陷（缺 `__main__` 守卫、用文本当控制信号、跨进程状态、未接住查找失败、英文 label、夹具污染） |
| REC-05 | 每日一题（种子驱动的确定性选题） | [records/daily-puzzle_2026-10-16.md](records/daily-puzzle_2026-10-16.md) | 生效 | 2026-10-16 | M4 第一步；三个让「确定性」名存实亡的陷阱（`hash()` 加盐、污染全局 random、静态方法读不到种子）与两版 base 类漂移 |
| REC-06 | 浏览器端到端验证、进度/分享、label 键 | [records/browser-e2e-and-profile_2026-10-16.md](records/browser-e2e-and-profile_2026-10-16.md) | 生效 | 2026-10-16 | 用 Playwright 补上「浏览器没人验证过」；M4 收尾（推导式连续天数、原子存档、无剧透分享卡）；`field.label` 由临时翻译改为 label 键契约；含两次「断言写错而非产品有缺陷」的记录 |
| REC-07 | 收尾：历史回看、图形卡片、可访问性审计 | [records/share-card-and-a11y_2026-10-16.md](records/share-card-and-a11y_2026-10-16.md) | 生效 | 2026-10-16 | 三个边角；axe-core 审计抓到真实的对比度违规（3.96 < 4.5）；SVG 卡片的 `aria-label` 未转义导致标记注入（测试先写、再修代码） |
| REC-08 | M5：两套并行实现收敛为「一份实现 + 语言资源」 | [records/m5-unification_2026-10-16.md](records/m5-unification_2026-10-16.md) | 生效 | 2026-10-16 | 17 对文件合并成 `gameplay_pool/` + `messages.py`；注册表改按 (语言, 种类) 建键；新增 en 内容包；删除两份重复池（含功能面×接任者对照）；行为等价性逐项比对（两版各 0 problem），含四处「探针/断言自身的缺陷」 |
| REC-09 | M5 第二步：两个 pygame 客户端合并为一份 | [records/m5-client-merge_2026-10-16.md](records/m5-client-merge_2026-10-16.md) | 生效 | 2026-10-16 | 客户端合并，以**像素级等价**为判据（两语言各 44/44 画面一致，基线已固化进测试）；抓到三处人眼难发现的真实差异（卡片顺序、英文大小写、英文界面字体）；含两处按语言保留的行为差异与三处自查出的工具链错误 |
| REC-10 | M2 补齐：内容包投稿/审核/签名 + 运行时强制 | [records/content-submission_2026-10-16.md](records/content-submission_2026-10-16.md) | 生效 | 2026-10-16 | `pack-cli` 全流程（new/validate/sign/review/accept）；签名覆盖**语义**而非字节（格式化不失效、改内容必失效）；五态签名结论（unsigned ≠ invalid，签名 ≠ 可信）；`--require-signature` 在服务与协议服务两层强制；40 项测试含篡改、未知钥匙、缺密钥等对抗场景 |
| REC-11 | 桌面版接入每日一题与进度 · 在线投稿服务 | [records/desktop-daily-and-pack-service_2026-10-16.md](records/desktop-daily-and-pack-service_2026-10-16.md) | 生效 | 2026-10-16 | 每日一题抽成共用模块并**逐日核对三客户端同题**（含「桌面端根本没注册 kind」这一静默退回）；进度与练习分开、同题只记一次；字体字形检查自带负向对照，抓出 `✓` 豆腐块与分享卡片两个缺字；在线服务把目录也签名、客户端**先验后装**（原子改名），隔离区不可见、投稿不能自我发布；含 5 处自查错误与 4 处实测撞出的形状不一致 |
| REC-AU-02 | 平台化调研卷（2026-10） | [records/platform-research-2026-10/README.md](records/platform-research-2026-10/README.md) | 生效 | 2026-10-16 | 四份联网调研报告的索引入口：内核选型 / 平台化架构 / 竞品扫描 / Web 平台形态 |
