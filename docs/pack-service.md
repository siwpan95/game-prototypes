# 在线内容包服务

> **类** 规范（面向部署者与投稿者） ｜ **实现** [`puzzle_service/pack_server.py`](../puzzle_service/pack_server.py)、[`pack_client.py`](../puzzle_service/pack_client.py)、[`pack_registry.py`](../puzzle_service/pack_registry.py)
> **前置** 先读 [`content-submission.md`](content-submission.md)（投稿工具与签名策略）

## 一、它解决什么

`pack-cli` 把投稿变成「发一个目录」，这在维护者必须在场时就停止了。这个服务把同一条
审核/发布路径搬到 HTTP 上：投稿者随时提交，维护者事后审核。它**不是**内容分发 CDN，
也不替代离线投稿——离线路径仍然完整可用。

## 二、三个状态，别搞混

| 位置 | 谁能看到 | 怎么进去 | 怎么出来 |
| --- | --- | --- | --- |
| `quarantine/` | **只有维护者** | `POST /submit` | `accept` 或 `reject` |
| `published/` | 所有客户端 | `accept`（**唯一**入口） | 手工删除 |
| 客户端本地 `content/packs/` | 本机玩家 | 客户端 `install` | 手工删除 |

关键性质：**没有任何请求能让内容自己上线**。投稿请求带 `status: accepted` 也没用——
服务端只读它需要的字段，其余一律忽略（有测试守着）。

## 三、跑起来（维护者）

```powershell
# 目录：published 对外可见，quarantine 是隔离区
.\.venv\Scripts\python.exe -m puzzle_service.pack_server `
    --published content/published `
    --quarantine content/quarantine `
    --key-file maintainer.key `
    --keyring keys.json `
    --host 127.0.0.1 --port 8765
```

- `--key-file`（或环境变量 `PACK_SERVICE_KEY`）：服务端签名钥匙，用来签**目录**，
  并在 `accept` 时用它对发布内容重新签名。没给就发不签名目录（客户端会被拒绝）。
- `--keyring`：受信任的**投稿者**钥匙。给了就只收这些钥匙签的投稿。
- `--allow-unsigned`：**仅开发用**。允许无签名投稿——等于任何人都能往隔离区塞东西。

默认只绑回环地址。绑定公网前请先读第七节。

## 四、HTTP 面

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/healthz` | 存活探测 |
| GET | `/registry.json` | **已签名**的包目录（客户端就靠它） |
| GET | `/packs/<name>.json` | 一个包的 bundle（base64 文件 + 签名） |
| GET | `/submissions` | 隔离区列表（**不含文件体**，所以拿不到未审核内容） |
| GET | `/submissions/<name>` | 单个投稿的状态（pending/accepted/rejected） |
| POST | `/submit` | 提交一个包 → 落隔离区 |
| POST | `/accept/<name>` | 发布（维护者动作） |
| POST | `/reject` | 拒绝并记录原因 |

`POST /submit` 的 body：

```json
{
  "name": "my-pack",
  "submitter": "ada",
  "notes": "12 条新谜语",
  "files": { "bundle.json": "<base64>", "riddles.json": "<base64>", "signature.json": "<base64>" }
}
```

`bundle.json` 就是包的 `manifest.json`（换个名字，这样下载到本地的东西不会被误当成已安装的包）。
服务端会**在收下之前**完整加载并校验它：格式版本、每条内容、以及签名（默认要求）。
一个装不上的包在这里就被拒绝，投稿人还在场，能读到原因。

## 五、客户端怎么用它

```python
from puzzle_service.pack_client import PackClient
from puzzle_service.submission import key_id, load_keyring

client = PackClient(
    base_url="http://127.0.0.1:8765",
    install_root=Path("content/packs"),
    registry_keyring={"k-…": "maintainer"},   # 信任的目录签名钥匙
    pack_keyring={"k-…": "maintainer"},       # 信任的内容签名钥匙
    require_signature=True,                   # 下载是远程输入，默认要求签名
)
for row in client.available():        # 先看有什么（含 installed/current）
    print(row)
client.update_all()                   # 装缺失或过期的包
```

顺序是刻意的，也是整个设计里最容易写错的地方：

```
取目录 → 验目录签名 → 挑包 → 下载 → 验内容签名 + 逐文件哈希 → 装
```

**先验后装**：下载先写到临时目录，在那里验完才挪到 `content/packs/`。
「先装后验」会在两者之间留一个窗口，窗口期内未验证的内容就躺在游戏会读取的位置上。
安装本身是**目录改名**，所以崩溃只会留下旧包或新包，不会留半个包。

客户端拒绝的五种情况：目录签名不对/不可信、内容与目录哈希不符、内容签名无效、
索引里有但包里没有的文件、以及体积超限。

## 六、边界与限制（有意为之）

- **body 上限 4 MiB，单文件 2 MiB**：内容包是词库，不是二进制分发。
- **限流**：默认每客户端 10 次突发、约 6 秒回填一次；超限返回 429。
  校验一个包比发一个包贵，没有限流的公开端点等于请人做拒绝服务。
- **超限时先把请求读完再回 413**：不读完就断开，客户端看到的是连接中断而不是状态码，
  而状态码才是有用的那部分。
- **投稿重名不许覆盖**：可能正在审核中，覆盖会静默丢掉它。换个名字，或让维护者清掉。
- **路径穿越**：包名受正则约束（不含分隔符、不以点或横线开头），且只在名字通过后才拼路径；
  `GET /packs/../…` 一律 404。
- **`GET /submissions` 不含文件体**：隔离区的东西拿不到，哪怕知道名字。

## 七、绑到公网之前必须补的

如实说明——这些**没有**做：

1. **没有认证与权限**：`/accept` 与 `/reject` 目前谁都能调。`--host 0.0.0.0` 之前必须加
   token/账号与权限分级，或把它们放到反向代理的鉴权后面。
2. **没有持久化配额与磁盘上限**：限流是按请求数，不是按占用空间。
3. **没有审核界面**：维护者用 `/submissions` 列 + `/accept` 发布，没有浏览器界面。
4. **没有吊销**：钥匙泄露只能换钥匙并重新签名。
5. **没有 TLS**：请放在反向代理后面终止 TLS。

## 八、验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pack_service.py -q     # 36 项
.\.venv\Scripts\python.exe -m pytest tests/test_submission.py -q      # 40 项
```

测试全部跑在**真实 socket** 上（`ThreadingHTTPServer` + 端口 0），不是 mock：
最可能写错的地方（body 上限、路径处理、验签与安装的先后）恰好是 mock 会替掉的部分。
对抗性用例覆盖：篡改的 bundle、被改过的目录、无签名投稿、陌生钥匙、超大 body、
畸形 JSON、路径穿越、限流、以及「投稿不能自我发布」。
