# M2 补齐：内容包投稿 / 审核 / 签名，以及运行时强制

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 内容流水线的社区侧（M2 剩余两项）
> **面向投稿者的说明** [`content-submission.md`](../content-submission.md) ｜ **证据** 40 项测试 + 端到端命令实录

## 一、M2 之前缺的是什么

M2 已交付内容包格式、双包（zh/en）与校验。缺的两块是**社区侧**与**信任侧**：

| 缺口 | 之前的状态 | 现在 |
| --- | --- | --- |
| 投稿 | "把补丁发给维护者" | `pack-cli new/validate/sign/submit`，`submission.json` 记投稿人与许可证 |
| 审核 | 无 | `pack-cli review`：校验 + 签名 + **与已发布内容逐项对比**（+/-/未变） |
| 收录 | 无 | `pack-cli accept`：写入 `provenance.json`（谁投的、谁收的、哪把钥匙签的、摘要） |
| 信任 | 无 | 签名 + 钥匙环 + 五态结论；`--require-signature` 在服务与协议服务两层强制 |

## 二、三个设计决定，以及为什么

### 1. 签名覆盖**语义**，不是文件字节

第一版直觉是"对目录里所有文件做哈希"。那会让**任何格式化**（改缩进、重排对象键）都变成"篡改"，
于是签名立刻变成噪音——而噪音会被忽略，被忽略的签名等于没有签名。

所以摘要取的是规范化语义：manifest 的语义字段 + 每个 kind 的条目（对象键排序、JSON 紧凑序列化）。
**条目顺序算数**（顺序会影响某次随机抽取抽到哪条，是可观测量）；格式不算数。

实测：把 `riddles.json` 重排为 8 空格缩进 + 键排序后，摘要不变、签名仍 `valid`；而增删一条或改一个
`answer` 立即失效。两种摘要都保留了：`--bytes` 查文件字节，默认查语义。

### 2. `unsigned`、`digest-match`、`valid`、`untrusted-key`、`invalid` 必须分开

"没有签名"和"签名不对"是完全不同的事。混为一谈的两种失败方式都是坏的：

- 把"没有签名"当失败 → 仓库自带内容包（维护者自己写的、未签名）直接起不来；
- 把"有签名"当可信 → 任何人自己签一个就能进。

于是：默认策略只宽容"还没签名"（**附警告**），而 `untrusted-key`（签名者的钥匙不在钥匙环里）
和 `invalid`（内容与签名不符）**在任何策略下都拒绝**。

还有一条：**没有钥匙时不做密码学验证**，此时结论是 `digest-match` 并显式附言
"signature not cryptographically verified (no key supplied)"——不谎称已验证。

### 3. 加密原语的选择：HMAC 而不是自己实现 Ed25519

Python 3.14 标准库没有 Ed25519（`crypto` 是 3.15 才有），本项目零第三方依赖。选项只有两个：
自己实现一条曲线，或用经过审计的原语做 HMAC。**自己实现 Ed25519 是错误的那种聪明**——那是细微、
静默、与安全相关的 bug 最喜欢藏身的地方。HMAC 契合真实威胁模型：维护者与投稿者能带外交换钥匙，
审核者必须能发现"签名之后包被改过"。签名文件带 `algorithm` 字段，将来换非对称签名不会让老包失效。

这条选择连同理由写进了模块 docstring，而不是留在提交信息里。

## 三、端到端实测（全部真跑，不是推演）

```
keygen → new → validate → digest → sign → verify（带钥匙）= valid
                                      verify（不带钥匙）= digest-match + 显式说明未验证
篡改后再 verify                                        = invalid（退出码 1，指出前后摘要）
钥匙环里换成别人的钥匙                                  = untrusted-key（退出码 1）
未签名 + --require-signature                           = missing-required（退出码 1）
未签名 + 默认策略                                       = unsigned（退出码 0，附警告）
重排缩进后 digest                                      = 不变；签名仍 valid
accept → provenance.json（投稿人/许可证/签名者/摘要/收录人/时间）
第二次提交（+1 条）review                              = delta: riddles 1 -> 2 (+1, -0) + second-riddle
```

运行时强制（两种模式都实测）：

```
python/rpc_server.py --require-signature   -> 退出码 4，stderr: refusing to serve untrusted content
python/rpc_server.py                       -> 正常服务
PuzzleService(...).content_summary()['trust'] -> 'unsigned'（默认）/ 'digest-match'（严格且签名正确）
```

## 四、写测试时抓到的两个真实缺陷

都是**报告层**的缺陷，而不是校验层的：

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | 严格策略下未签名包的报告里，`signature.status` 仍是 `unsigned` | 策略判断放在 `verify_signature` 里抛出，报告层只把原因写进 `problems`，状态字段却留在"没签名"——**读起来像没问题** | 报告层显式转成 `missing-required`，并把"缺签名"与"钥匙不可信"两条路径分开 |
| 2 | 未签名包被报成 `untrusted-key` | 钥匙环检查对空 `key_id`（`''`）也生效，于是"没签名"被误判成"钥匙不认识" | 先要求签名文件存在且**指明钥匙**，再判断信任；签名缺 `key_id` 现在是签名错误而非信任错误 |

第 2 条只有在我把"未知钥匙"用例写成测试时才暴露——**对抗性用例写下来才会真的跑**。

还有一个测试自身的缺陷值得记：我最初在**同进程**里断言"严格模式加载的是这份投稿包"，
结果进程里先前的测试已经把 `zh` 的 kind 注册绑在自带包上，服务跳过发现、验证的是投稿包、
玩的却是自带内容。测试**通过不了**才发现这一点；现在该用例在子进程里跑，并断言"抽到的谜面
必须就是投稿包里那一条"——如果只断言 `trust` 字段，这个错误会溜过去。

## 五、验证

```
.venv/Scripts/python.exe -m pytest tests -q                    -> 200 passed（新增 40 项投稿/签名测试）
.venv/Scripts/python.exe scripts/client_screens.py --language zh/en -> MATCH THE BASELINE
.venv/Scripts/python.exe scripts/smoke_headless.py             -> SMOKE PASSED
.venv/Scripts/python.exe scripts/check_build_consistency.py    -> CLIENT CONSISTENCY PASSED
npm test                                                       -> CLIENT CHECK / SMOKE / BROWSER E2E
```

对抗性用例覆盖：篡改后验证、篡改后收录、未知钥匙、缺签名（严格/默认）、缺 `key_id`、
不支持的算法、损坏的 provenance（**不覆盖而是报错**）、`--force` 收录问题包仍如实记录、
重复收录同一包不产生重复或损坏。

## 六、复现

```
python pack_cli.py keygen --out author.key --label "Ada <ada@example.com>"
python pack_cli.py new --out drafts/my-pack --name my-pack --language zh --submitter ada --license CC-BY-4.0
python pack_cli.py validate drafts/my-pack
python pack_cli.py sign drafts/my-pack --key author.key --signer ada
python pack_cli.py verify drafts/my-pack --key author.key --require-signature
python pack_cli.py review drafts/my-pack --target content/packs
python pack_cli.py accept drafts/my-pack --target content/packs --actor maintainer
.venv/Scripts/python.exe -m pytest tests/test_submission.py -q
```

## 七、未做（边界如实说明）

- **自带内容包未签名**：签名要私钥，私钥不进仓库。要跑严格模式，先用维护者钥匙签 `content/packs/core-*`。
- **没有在线投稿服务**：投稿走目录/PR。在线服务要账号体系与存储，是独立工程。
- **没有吊销名单**：钥匙泄露只能换钥匙并重新签名；`provenance.json` 记录了每个包由哪把钥匙签的，便于追查。
- **非对称签名**：等 Python 3.15 的 `crypto`（或引入依赖）再换，签名文件的 `algorithm` 字段已为此留好位置。
