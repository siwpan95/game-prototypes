# 收尾：历史回看、图形化分享卡片、可访问性自动审计

> **时点** 2026-10-16 ｜ **类** 记录 ｜ **范围** SPEC-101 里挂着的三个「待做」边角
> **证据** 全部为当轮实测；复现命令见文末

## 一、历史回看（按题号回看过去的每日题）

`Profile.history(limit, day)` 返回最近若干天的记录（新在前，且**不显示锚点日之后的记录**——
回看旧日子不应该剧透后面几天）。入口：RPC `profile.history`、`GET /api/history?limit=&day=`、
CLI `history [天数] [日期]`、网页「历史」按钮。

关键性质有测试守着：**过去某一天能被重新取回，并且取回的题目与当天记录一致**
（`daily <日期>` 本来就确定性可复现，现在能从列表里知道该输哪个日期）。

## 二、图形化分享卡片

`share_card_svg()` 输出独立 SVG（480×260）。选 SVG 而不是位图有两个理由：
生成它不需要任何依赖、也不需要浏览器；而且**文字仍是 `<text>`**，
所以屏幕阅读器读得到、测试也断言得了——导成 PNG 会把这两样一起丢掉。

- 状态用「圆点 + 符号 + 文字」三重表达（✔/✘ 与"已完成/未完成"），不靠颜色单独承载信息。
- 卡片自带 `aria-label`，把日期、结果、得分、连续天数与"不含谜底"念出来。
- 想看位图：`node scripts/render-share-card.mjs <card.svg> <out.png>`（复用端到端测试同一套浏览器）。
- 入口：`profile.share.svg`、`GET /api/share.svg`（`image/svg+xml`）、CLI `card [日期] [路径]`、
  网页「卡片图」链接。

**本轮实际输出的卡片**（已渲染核对，不是"应该能看"）：

```
文字解谜 · 每日一题
2026-10-16
● ✔ 已完成 · guess_number
得分 19 · 用时 33s · 尝试 4 次
连续 2 天（最佳 2 天）
本卡片不含谜底，可安全分享
```

### 这里抓到一个真缺陷
`aria-label` 里直接拼了调用方传来的日期字符串，**未转义**——一个带引号的日期能闭合属性、
把标记注入文档。测试先写、再改代码：现在所有插值都过 `_svg_escape()`，
并且有一条用例专门用 `"><script>…` 作为日期来验证注入被挡住、文档仍能解析。

## 三、可访问性自动审计（调研阶段没找到可核查选型的那一项）

用 **axe-core 4.14.0** 注入真实页面运行（`npm test` 的浏览器用例内），
只把 **serious/critical** 当失败——minor 是风格意见，混进来会让这条检查变成噪音，
而噪音迟早被人忽略。

审计**当场抓到一个真违规**：

```
color-contrast (serious) — #status
  对比度 3.96（前景 #8964ea / 背景 #1e1e2e，16px 常规字重），AA 要求 ≥ 4.5
```

这个紫色本来只用于边框与强调（UI 组件 3:1 就够），被拿来当正文颜色就不达标。
处置：拆成两个 token——`--accent`（画边框）与 `--accent-text`（写字，`#a78bfa`，实测 6.03）。
四个画面（菜单 / 网格谜题 / 颜色谜题 / 输入谜题）现在都是 **0 violations**。

## 四、验证

```
.venv/Scripts/python.exe -m pytest tests -q                  -> 156 passed
npm test                                                     -> CLIENT CHECK / SMOKE / BROWSER E2E（18 项）全过
.venv/Scripts/python.exe scripts/check_build_consistency.py   -> BUILD CONSISTENCY PASSED
.venv/Scripts/python.exe scripts/smoke_headless.py            -> SMOKE PASSED
.venv/Scripts/python.exe scripts/build_content_pack.py --check -> up to date（6 文件 / 154 条）
```

浏览器用例新增三项：图形卡片以 `image/svg+xml` 提供且声明不含谜底、历史按新在前返回、
**axe 审计四个画面零 serious/critical**。

## 五、复现

```
.venv/Scripts/python.exe -m puzzle_service.cli history
.venv/Scripts/python.exe -m puzzle_service.cli card 2026-10-16 out.svg
node scripts/render-share-card.mjs out.svg out.png
npm test
```

## 六、仍然没做的（如实登记）

- 卡片只支持中文文案（与服务端目前只有 zh 内容包一致）；英文客户端要看英文卡片需要
  一张按语言分的文案表，与 label 键是同一类问题，见 SPEC-101 §阶段 M5。
- 没有做"分享到某个平台"的集成（调研结论：文本/图片 + 剪贴板已经覆盖绝大多数场景，
  平台集成会把外部 API 的易变性引进来）。
