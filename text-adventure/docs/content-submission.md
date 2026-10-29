# 内容包投稿与审核

> **类** 规范（面向投稿者） ｜ **实现** [`puzzle_service/submission.py`](../puzzle_service/submission.py)、[`pack_cli.py`](../pack_cli.py)
> **读者** 想投内容的人（第一节起）与维护者（第四节起）

## 一、内容包是什么

一个目录，里面是 JSON 数据，**没有可执行代码**：

```
my-pack/
  manifest.json      包名、版本、格式版本、最低引擎版本、语言、包含哪些内容
  riddles.json       谜语
  hangman_words.json 猜词词库
  anagram_words.json 拼字词库
  word_ladders.json  单词梯
  crosswords.json    填字
  submission.json    投稿人、许可证、备注（投稿才有）
  signature.json     签名（签名后才有）
```

只有被 `manifest.json` 声明的内容文件会被读取；多出来的文件会在审核时被**列出来**且不会被复制。

## 二、投稿（作者视角）

```bash
# 1. 生成骨架（生成即是合法的，先跑 validate 看到"干净"再开始写）
python pack_cli.py new --out drafts/my-pack --name my-pack --language zh \
    --submitter ada --license CC-BY-4.0

# 2. 编辑 JSON。每加一条内容就跑一次：
python pack_cli.py validate drafts/my-pack

# 3. 签名（需要先有钥匙，见下）
python pack_cli.py keygen --out author.key --label "Ada <ada@example.com>"
python pack_cli.py sign drafts/my-pack --key author.key --signer ada

# 4. 自检：把维护者会看到的报告先看一遍
python pack_cli.py review drafts/my-pack --key author.key
```

`author.key` **不要提交、不要外发**：谁拿到它就能以你的名义签名。`key id`（形如
`k-c8f8a79321138036`）是可以公开的，它就是给别人核对用的名字。

投稿内容要求：

- `submission.json` 必须写 `license`；不写许可证的投稿会被审核**拒绝**（不是警告）。
- 谜语/填字等内容不要抄别人的题库；`license` 要如实反映你的权利。
- 每条内容都会被校验：谜语的 `answer` 必须落在 `options` 范围内、填字的每个格子必须被词覆盖或被 `blocks` 标为障碍、单词梯的每个词长度必须一致，等等。错误信息会指出**文件与条目下标**（例如 `riddles.json[7]: 'answer' index 9 is outside the 4 options`），不必自己数。

## 三、签名覆盖的是什么

签名覆盖的是**内容的语义**，不是文件的字节：

- 对 `manifest.json` 的语义字段（包名、格式版本、语言、每个 kind 的条目）做规范化 JSON 哈希；
- 条目**顺序**算数（顺序会影响某次随机抽取抽到哪条，所以它是可观测量）；
- 对象内部的键顺序、缩进、换行**不算数**——所以格式化、重排键都不会弄坏签名。

因此：改了任何一条内容、增删任何一条、调换顺序，签名都会失效并**明确报错**（"content does not
match the signature — the pack changed after it was signed"，并给出前后摘要）。

算法当前是 `hmac-sha256`（共享密钥）。原因写在模块文档里：Python 3.14 标准库没有 Ed25519
（`crypto` 是 3.15 才有），本项目不引第三方依赖，于是选择"用经过审计的原语做 HMAC"而不是"自己实现一条曲线"。
签名文件里带 `algorithm` 字段，将来换成非对称签名不会让老包失效。

## 四、审核与收录（维护者视角）

```bash
# 1. 审核：校验 + 签名 + 与已发布内容逐项对比
python pack_cli.py review drafts/my-pack \
    --target content/packs --keyring keys.json --key author.key --require-signature

# 2. 收录（会写 content/packs/provenance.json）
python pack_cli.py accept drafts/my-pack \
    --target content/packs --keyring keys.json --key author.key --require-signature \
    --actor maintainer
```

`review` 会**一次列出全部问题**，而不是遇到第一个就停下——审核者要的是清单，不是往返。

三种状态必须分得清，代码里也是分开的：

| 状态 | 含义 | 默认策略 | `--require-signature` |
| --- | --- | --- | --- |
| `unsigned` | 没有 `signature.json` | 通过（附警告） | 拒绝：`missing-required` |
| `digest-match` | 有签名、内容一致，但**没提供钥匙**，未做密码学验证 | 通过（明确说明未验证） | 通过（明确说明未验证） |
| `valid` | 有签名、内容一致、钥匙对得上 | 通过 | 通过 |
| `untrusted-key` | 签名有效，但签名者不在 `keys.json` 里 | **拒绝** | **拒绝** |
| `invalid` | 签名与内容不符（被改过） | **拒绝** | **拒绝** |

要点：**"没有签名"和"签名不对"是两件事**，而**"有签名"不等于"可信"**。
`untrusted-key` 与 `invalid` 在任何策略下都拒绝——默认策略宽容的是"还没签名"，不是"签错了"。

`--force` 是给"已经读过问题、仍然要收"的维护者用的；它不会隐藏问题，报告仍会写进 provenance。

## 五、运行时强制

```bash
# 服务第三方内容时：启动即拒绝未签名/被篡改的内容（退出码 4）
python python/rpc_server.py --require-signature --keyring keys.json
```

默认**不**要求签名：仓库自带的内容包是维护者自己写的、没有签名，为了满足一条没人要求的策略而
让游戏起不来是本末倒置。`--require-signature` 是给"要分发第三方内容"的部署用的。

无论策略如何，**被篡改**（内容与签名不符）一律拒绝启动：一个内容与签名不匹配的包，已经不是那个包了。

`content.info` 会回报 `trust` 字段，所以客户端也能看到当前内容被验证到什么程度。

## 六、当前边界（如实说明）

- 自带内容包未签名：签名需要私钥，私钥不该进仓库。要跑严格模式，先用维护者钥匙给 `content/packs/core-*` 签名。
- 没有在线投稿服务：投稿走目录/PR，`pack-cli` 是本地工具。做在线服务要有账号体系与存储，不在本轮范围。
- 没有吊销名单：钥匙泄露只能靠换钥匙 + 重新签名；`provenance.json` 记录了每个包由哪把钥匙签的，便于追查。
