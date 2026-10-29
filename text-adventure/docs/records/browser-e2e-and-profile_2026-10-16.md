# 浏览器端到端验证 + 进度/分享 + label 键（M4 收尾）

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** 补上「浏览器没人验证过」这个窟窿、完成 M4 剩余部分、修掉 label 的临时处置
> **证据** 全部为当轮实测；复现命令见文末

## 一、浏览器验证：能做，而且已经做了

之前浏览器端只做到「HTTP 正确、SSE 正确、客户端语法与 DOM 绑定正确」，**没有真正在浏览器里跑过**，
路线图里如实登记为未验证项。现在用 Playwright 补上了：

- 本机 `%LOCALAPPDATA%\ms-playwright` 里**已有** Chromium（build 1243），
  但安装的 playwright-core 期望 1248，且默认无头模式还要一个单独的 `headless-shell` 包。
  `chromium.launch({ channel: 'chromium' })` 会改用完整浏览器二进制，于是**一个字节都不用下载**。
- `src/browser.mjs` 按「默认 → channel=chromium → 显式指向缓存构建」的顺序尝试，
  换台机器（没有任何缓存）时第一种就能用；失败时把每种尝试的原因一起报出来，而不是只说一句"启动失败"。
- `src/browser_e2e.mjs` 真开浏览器跑 16 项检查，已进入 `npm test`。

它当场抓到三个真实缺陷（都不是小事）：

| # | 现象 | 根因 | 处置 |
| --- | --- | --- | --- |
| 1 | 每次打开页面控制台都有一条 404 | 浏览器自动请求 `/favicon.ico`，而站点没有图标 | 用内联 SVG data URI 提供图标，从根上消掉；这类噪音会把真错误淹掉 |
| 2 | 右键插旗「没反应」 | 我点的是**已翻开**的格子，而翻开的格子按设计是惰性的 | 测试改为先找未翻开的格子；**产品行为正确，是测试选错了目标** |
| 3 | 键盘操作「没反应」 | 上一条已经把那格插过旗了，我又断言"旗数变多" | 调整用例顺序并改为比较前后差值；随后用探针确认 `page.keyboard.press('f')` 真能插旗（before=0 → after=1） |

第 2、3 条值得记下来：**两次都不是产品缺陷，是断言写错了**。如果不先弄清楚就"修真问题"，
就会把正确的行为改坏——这也是为什么每次都要先探针、再改代码。

## 二、进度与分享（M4 剩余部分）

- `puzzle_service/profile.py`：每天一条记录（日期、种类、是否完成、得分、尝试次数、用时），
  **不存谜底、不存题目内容**——存档可以被人看、被分享、甚至被提交，都不会泄题。
- **连续天数是从记录推导的，不是计数器**：跨过缺口自动归零，改存档也编不出没有证据的连续记录。
  今天还没玩时，昨天结束的连续记录仍然有效（否则每天零点会误报断签）。
- 存档写入是**原子的**（临时文件 + `os.replace`），中途崩溃不会截断既有进度；
  存档损坏时**在 stderr 说明原因并按空档案继续**，不阻断开局，也不悄悄删档。
- 重玩同一天：保留最好成绩、累加尝试次数、不会把"已完成"变回"未完成"。
- **分享卡片不含谜底**，并且卡片自己就写着「不含谜底，可安全分享」——这条性质是给读卡片的人看的。
- 浏览器端新增「每日一题」「分享卡片」两个按钮与进度行；CLI 新增 `profile`、`share` 两个命令。
- CLI 里 `;` 分隔多命令的写法在**真实 PowerShell 下会被当成语句分隔符**，
  所以用 shell 时请分次调用（此前记录里的示例只适用于直接传 argv 的场景）。

## 三、`field.label` 的临时处置改成了正式契约

原来服务端把 `label` 写死成英文（`"Answer"`），而服务端并不知道谁在渲染，
于是中文界面里出现英文标签，我只能先在客户端做字符串翻译——那是**临时处置，不是设计**。

现在：视图模型发 **label 键**（`label_key`，如 `answer` / `word` / `next_word`），
外加一份英文默认文本兜底；**文案由客户端决定**，因为只有客户端知道用户读什么语言。
三个客户端各自持有自己的表，服务端只维护「有哪些键」这一份契约
（`puzzle_service/views.py` 的 `LABEL_KEYS`），并有测试要求每个 field 节点都带键。

## 四、验证

```
.venv/Scripts/python.exe -m pytest tests -q                    -> 143 passed
npm test                                                        -> CLIENT CHECK / SMOKE / BROWSER E2E 全过（16 项）
.venv/Scripts/python.exe scripts/check_build_consistency.py      -> BUILD CONSISTENCY PASSED
.venv/Scripts/python.exe scripts/smoke_headless.py               -> SMOKE PASSED（两版 × 14 种画面）
.venv/Scripts/python.exe scripts/build_content_pack.py --check   -> up to date（6 文件 / 154 条）
```

浏览器实测覆盖：页面加载与控制台零错误、SSE 连接、14 种可在选择器里列出、
开局渲染中文标签、错答反馈、提示、**点格子翻开**、**键盘 `f` 插旗**、**右键插旗**、
**方向键操作 2048**、纯颜色玩法给符号与文字、答题结果、每日一题、分享卡片、进度显示。

## 五、复现

```
npm run e2e:browser            # 无头；加 --headful 可留 60 秒人工观察
npm run e2e:browser -- --headful --verbose
.venv/Scripts/python.exe -m pytest tests/test_profile.py -q
$env:TEXT_ADVENTURE_PROFILE = "$env:TEMP\ta-profile.json"   # 用临时档案，不动本机进度
```

## 六、未做

- 按题号**回放历史每日题**（`daily <日期>` 已经能取回任意一天的题并保持可复现，
  但没有"列出过去 N 天"的入口）。
- 分享卡片的**图形化**版本（当前是文本，保证任何地方粘贴都不走形）。
- 浏览器侧的**可访问性自动审计**（axe 之类）：调研阶段就没找到可核查的选型结论，
  目前只有手写断言（键盘通路、aria-label、颜色不单独承载信息）。
