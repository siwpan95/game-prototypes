# Calculator ∞ Alchemia 解密终端 — 增强总结

基于机核文章 [《一篇我觉得有用的解密游戏〈Alchemia〉指南》](https://www.gcores.com/articles/130136) 全面增强。

将原本的 MVVM 计算器扩展为「计算器 + 古典密码学工具 + 解密游戏终端」三合一。

---

## 新增文件

| 文件 | 说明 |
|---|---|
| `alchemia.py` | Alchemia 解密引擎（约 600 行）— 所有古典密码算法、谜题数据、成就系统 |
| `ENHANCEMENT.md` | 本文档 |

## 修改文件

| 文件 | 改动 |
|---|---|
| `utils.py` | 转发 alchemia 算法到 `CryptoUtils` 类，新增 12 个静态方法 |
| `model.py` | 扩展 `SPECIAL_COMBOS`（40+ 彩蛋）；新增 12 个 `#` 模式；成就系统状态机 |
| `view.py` | 双主题（深色 / Alchemia 羊皮纸）；底部状态栏；多行显示；成就闪烁动画 |
| `viewmodel.py` | 新增 `crypto_mode` / `achievement` 可观察属性；`achievement` 副作用信号 |
| `main.py` | 注册 `achievement` 副作用处理器（弹窗显示成就） |

---

## 所有 # 模式（共 23 个）

### 经典密码
| 命令 | 用法示例 | 说明 |
|---|---|---|
| `#caesar` | `#caesar hello 3 =` | 凯撒密码（默认移位 3） |
| `#rot` | `#rot hello =` | ROT13 |
| `#atbash` | `#atbash hello =` | Atbash 倒序替换（古希伯来） |
| `#vig` | `#vig hello key =` | 维吉尼亚密码 |
| `#porta` | `#porta hello key =` | Porta 密码（对称） |
| `#trith` | `#trith hello =` | Trithemius（位置递增移位） |
| `#selenus` | `#selenus hello =` | Selenus（起始移位 1） |
| `#brute` | `#brute khoor =` | 凯撒爆破（26 种移位全列出） |

### 哈希 / 密钥
| 命令 | 用法示例 | 说明 |
|---|---|---|
| `#hash` | `#hash hello sha256 =` | 哈希计算 |
| `#key` | `#key 256 =` | 密钥生成（64-4096 位） |
| `#salt` | `#salt 16 =` | 盐值生成 |
| `#pwd` | `#pwd mypass =` | 密码哈希（PBKDF2） |
| `#xor` | `#xor hello:secret =` | XOR 加密 |
| `#b64` | `#b64 hello =` | Base64 编码 |

### Alchemia 高级解密
| 命令 | 用法示例 | 说明 | 对应文章 |
|---|---|---|---|
| `#alch` | `#alch` | 进入 Alchemia 模式（首次解锁成就） | 总入口 |
| `#page` | `#page 4 =` | 查询 7 页书某一页的提示 | 第 1-14 面 |
| `#golden` | `#golden AG BF =` | 黄金均值取中（A+G→D） | 第 4 面 ABSCONDITA EST INSIGNE |
| `#fib` | `#fib hello =` | 斐波那契移位（1,1,2,3,5,8...） | 第 9 面 NVMERO SANCTVM |
| `#sieve` | `#sieve 74 69 6 55 =` | 素数筛转换（74→AL） | 第 9 面 Eratosthenes |
| `#gem` | `#gem hello latin =` | Gematria 字母数字映射 | 第 5 面 LINGVA MATER |
| `#anti` | `#anti 2 =` | 古希腊 Corinthian 历法 | 第 7 面 SVPER STELLAE |
| `#mirror` | `#mirror hello =` | "As above, so below" 上下颠倒 | 第 8 面 HISTORIA |
| `#alchemy` | `#alchemy fire =` | 炼金符号查询（fire→🜂） | 第 6 面 CHYMISTRY |
| `#key2` | `#key2 PADEILSYMIELGEDIELVSIEL =` | 验证最终密钥 | 第 14 面 终页 |

---

## 彩蛋（直接输入即触发）

| 输入 | 输出 | 出处 |
|---|---|---|
| `1688` | `Mines Royal Act` | 文章第 6 面，Robert Boyle |
| `alchemia` | `7 页书` | 游戏本体 |
| `soyga` | `Book of Soyga` | 第 5 面 |
| `porta` / `trithemius` / `selenus` / `vigenere` | 对应密码名 | 第 5 面 |
| `faust` | `Johann Georg Faust` | 第 4 面 |
| `ripley` | `George Ripley` | 第 4 面 |
| `michelspacher` | `Stephan Michelspacher` | 第 4 面 |
| `boyle` | `Robert Boyle (Invisible College)` | 第 6 面 |
| `cleopatra` | `Cleopatra the Alchemist` | 第 8 面 |
| `zosimos` | `Zosimos of Panopolis` | 第 8 面 |
| `fibonacci` | `Liber Abaci` | 第 9 面 |
| `napier` | `Napier's bones` | 第 10 面 |
| `brahe` | `Tycho Brahe` | 第 7 面 |
| `eratosthenes` | `Sieve` | 第 9 面 |
| `atlantis` | `Phantom Island` | 第 10 面 |
| `babel` | `Tower of Babel` | 第 5 面 |
| `antikythera` | `ΚΡΑΝΕΙΟΣ` | 第 7 面 |
| `fire` / `water` / `air` / `earth` | 🜂 🜄 🜁 🜃 | 四元素 |
| `gold` / `silver` / `mercury` / `copper` / `iron` / `tin` / `lead` | ☉ ☽ ☿ ♀ ♂ ♃ ♄ | 七金属 |
| `salt` / `sulfur` | 🜔 🜍 | 三本原 |
| `goldenmean` | ⚖ | 第 4 面 |
| `130136` | `Alchemia Guide` | 文章编号 |
| `112358` | `Fibonacci` | 数列前几位 |
| `714` | `7 pages of Alchemia` | 7 页书 |
| `padeilsymielgedielvsiel` | `★ 终钥已开启 ★` | 第 14 面 最终密钥 |

---

## 成就系统（10 个）

| 成就 id | 名称 | 解锁条件 |
|---|---|---|
| `first_blood` | 初窥门径 | 第一次进入 `#alch` 模式 |
| `golden_mean` | 黄金均值 | 解开第 4 面 ABSCONDITA EST INSIGNE |
| `babel_tongue` | 巴别塔之舌 | 解开第 5 面 LINGVA MATER |
| `transmutation` | 点石成金 | 解开第 6 面 CHYMISTRY |
| `stargazer` | 观星者 | 解开第 7 面 SVPER STELLAE |
| `hermetic` | 赫尔墨斯 | 解开第 8 面 HISTORIA |
| `sieve_master` | 筛法大师 | 解开第 9 面 NVMERO SANCTVM |
| `cartographer` | 幻岛制图师 | 解开第 10 面 MAPPVS MUNDI |
| `final_key` | 终钥持有者 | 输入最终密钥 PADEILSYMIELGEDIELVSIEL |
| `completionist` | 炼金术大师 | 全部解锁 |

> 解锁成就时会弹出系统对话框，状态栏闪烁金色 6 次，并显示 `成就: N/10`。

---

## 算法对应表（文章 → 实现）

| 文章解密机制 | 实现位置 | 验证 |
|---|---|---|
| 第 4 面：Golden Mean 取中 | `alchemia.golden_mean` | `AG → d` ✓ |
| 第 5 面：四种古典密码 | `porta / trithemius / selenus / vigenere` | 全部实现 ✓ |
| 第 5 面：SOYGA → The Book of Soyga | `SPECIAL_COMBOS["soyga"]` | ✓ |
| 第 6 面：Invisible College + Barlet's key | `SPECIAL_COMBOS["boyle"]` + 炼金符号 | ✓ |
| 第 7 面：Antikythera + Corinthian 历 | `alchemia.antikythera_month` | `月2 → ΚΡΑΝΕΙΟΣ` ✓ |
| 第 7 面：凯撒爆破（fifth month = July = Caesar） | `CryptoUtils.caesar_bruteforce` | 26 种移位全列出 ✓ |
| 第 8 面：As above, so below 镜像 | `alchemia.mirror_text` | `hello → ollǝɥ` ✓ |
| 第 9 面：埃拉托色尼筛 + 数字转字母 | `alchemia.sieve_convert` | `74 → AL` ✓ |
| 第 9 面：斐波那契首位数字移位 | `alchemia.fibonacci_shift` | `hello → ifnot` ✓ |
| 第 9 面：74 69 6 55 → ALBIABCEIR → Liber Abaci | `alchemia.sieve_batch([74,69,6,55,1403])` | `ALBIABCEIR` ✓（文章中重排得到 Liber Abaci） |
| 第 10 面：五个传说地点 | `alchemia.PHANTOM_ISLANDS` | ✓ |
| 第 12 面：元素单词 + 符号对应 | `alchemia.ELEMENTS_TABLE` | 13 种符号 ✓ |
| 第 14 面：加点字提取 → PADEILSYMIELGEDIELVSIEL | `alchemia.FINAL_KEY` + `verify_final_key` | ✓ |

---

## 视觉增强

### 双主题
- **默认深色主题**（原计算器配色）
- **Alchemia 羊皮纸主题**（进入 `#alch` 后激活）：深棕背景 + 金色等号 + 朱砂退格 + 羊皮纸色文字

### 底部状态栏
显示当前模式 + 成就进度，例：
- `普通模式 | 成就: 0/10`
- `🔐 凯撒密码 | 成就: 1/10`
- `🔮 Alchemia 解密模式 | 成就: 2/10`

### 多行显示
`#brute`（26 行）、`#page`（多行提示）等结果支持多行显示，自动切换小字号。

### 成就闪烁
解锁成就时状态栏金色闪烁 6 次 + 系统弹窗。

---

## 启动方式

```bash
cd <PATH>
python main.py
```

或使用本地 Python（推荐，tkinter 完整支持）：
```bash
"C:/Users/13122/AppData/Local/Programs/Python/Python314/python.exe" main.py
```

---

## 快速上手建议

1. 启动后先输入 `#alch` 进入 Alchemia 模式（解锁首个成就）
2. 输入 `#page 4 =` 查看第 4 面的解密提示
3. 试试 `#golden AG BF =`（黄金均值取中）
4. 试试 `#sieve 74 69 6 55 =`（素数筛，会得到 ALBIABCEIR）
5. 试试 `#brute khoor =`（凯撒爆破，找到 hello 对应的移位 3）
6. 试试 `#mirror hello =`（上下颠倒）
7. 试试 `#alchemy fire =`（炼金符号）
8. 最终输入 `#key2 PADEILSYMIELGEDIELVSIEL =` 解锁终钥成就
9. 也可直接输入 `padeilsymielgedielvsiel =` 触发终钥

---

## 架构说明（未破坏 MVVM）

```
main.py  ──── 装配三层 + 注册副作用（quit / shuffle / achievement）
   │
   ├─ model.py ────── 业务逻辑（状态机 + SPECIAL_COMBOS + # 模式 + 成就）
   │     │
   │     └─ utils.py ────── CryptoUtils 静态方法（转发）
   │           │
   │           └─ alchemia.py ────── 所有 Alchemia 算法实现 + 谜题数据
   │
   ├─ viewmodel.py ─ Observable 属性 + 副作用信号
   │
   └─ view.py ────── UI（双主题 + 状态栏 + 多行显示 + 闪烁）
```

所有新增功能都遵循 MVVM 分层：
- `alchemia.py` 是纯算法模块，无 GUI 依赖
- `utils.py` 转发，保持原 `CryptoUtils` API 兼容
- `model.py` 持有状态，通过 observer 通知
- `viewmodel.py` 映射状态为 Observable
- `view.py` 只看 ViewModel，不引用 Model
- `main.py` 是唯一知道所有三层的入口
