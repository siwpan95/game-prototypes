---
主题: 同类产品与竞品扫描（平台化调研 03）
适用项目: text-adventure（Python + pygame 文字解谜，14 种谜题）
检索日期: 2026-10-16
检索方式: web_search（联网检索）；web_fetch 在本次会话中对若干站点返回 fetch failed，未取回正文
---

# 03 同类产品与竞品扫描

## 结论摘要

1. **头部平台的核心不是「谜题多」，而是「一天一道 + 记录 + 分享」的闭环。** NYT Games 的资源投入集中在每日节奏（Wordle/Connections/Strands/Spelling Bee/Sudoku 每日更新）、连续记录（streak）、无剧透分享卡片、以及订阅制档案库，而不是谜题种类的数量。参考：[NYT Games 订阅说明](https://help.nytimes.com/360011158491-New-York-Times-Games/360052272251-New-York-Times-Games-Subscription)、[NYT Games（维基）](https://en.wikipedia.org/wiki/The_New_York_Times_Games)。
2. **每日一题可以纯静态实现，不需要后端。** Wordle 的每日词是在客户端按「本地日期」从未打乱的固定列表里取的（重开浏览器不改结果、无需服务端）；共 2,315 个答案词 + 约 1 万可猜词。这是本项目最能低成本复制的一条工程结论。参考：[Wordle 词表说明（Reddit r/wordle）](https://www.reddit.com/r/wordle/comments/s4tcw8/a_note_on_wordles_word_list)、[Hacker News 讨论](https://news.ycombinator.com/item?id=30435522)、[Wordle（维基）](https://en.wikipedia.org/wiki/Wordle)。
3. **难度标定靠「人工分级 + 试玩打分」，不靠算法。** Connections 由专职编辑用表格组织题库、按黄绿蓝紫四级难度人工定级，并对每张盘做 1–5 分试玩评分（编辑本人强调「难度是主观的」）。这类机制可以复制「流程」，但复制不了编辑团队的判断力。参考：[NYU ITP 对 Wyna Liu 的访谈](https://tisch.nyu.edu/itp/news/fall-2024/connecting-with-the-editor-of-connections--wyna-liu--14)、[NYT Connections 技巧文](https://www.nytimes.com/2023/11/06/crosswords/connections-tips-and-tricks.html)。
4. **开源侧已经能拼出一条完整链路。** Simon Tatham 的 Portable Puzzle Collection（约 40 个逻辑谜题、MIT、同一后端多前端，含 JS/WASM 构建）就是「同一谜题多端渲染」的既成事实标准做法；Sudoku 有公有领域题库（Sudoku Exchange）、QQWing 生成器；填字有 ipuz 开放格式与 Python/JS 读写库；把 pygame 搬到浏览器有 pygbag。参考：[Portable Puzzle Collection](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/)、[sudoku-exchange-puzzle-bank](https://github.com/grantm/sudoku-exchange-puzzle-bank)、[ipuz 文档](https://ipuz.readthedocs.org/en/latest)、[pygbag](https://github.com/pygame-web/pygbag)。
5. **变现不是小团队的入口。** NYT 的 Games 是「订阅捆绑 + 免费引流」结构（Wordle/Connections 等免费，档案库、进阶工具与部分游戏置入订阅），Guardian/Apple 同样是订阅制；小团队更现实的是先做「每日习惯 + 可分享」，把变现留到有留存之后。参考：[NYT 家庭订阅新闻稿](https://www.nytco.com/press/familysubscription)、[Guardian Puzzles 上线报道](https://www.inpublishing.co.uk/articles/the-guardian-launches-puzzles-app-15159)、[Apple News+ Quartiles](https://www.apple.com/newsroom/2024/05/apple-news-plus-introduces-quartiles-a-new-game-and-offline-mode-for-subscribers)。
6. **本项目最大的差距不在玩法，而在「内容供给流水线」和「每日留存机制」**；跨端有低成本路径（pygbag），社交分享与可访问性是投入小、收益明确的补课项。详见「差距分析」。

> 说明：本报告不写任何未经来源支撑的用户量或收入数字；凡检索结果中出现但只有二手转述、无一手出处的数字，均在正文中标注「未找到可核查来源」或明确标为「二手转述」。

---

## 逐项扫描

### 1. NYT Games 的平台化路径

**产品矩阵与每日节奏。** NYT Games 的免费层包含 Wordle、Connections、Crossplay、Pips、Strands、Sudoku、Spelling Bee（限量）等；订阅层包含 Crossword/Midi/Mini、可回溯到 1993 年的 1 万多道填字档案、每月奖励谜题，以及 Wordle Bot / Cross Bot 等分析工具。官方帮助中心把「哪些免费、哪些订阅」列得很清楚，这个分层本身就是平台化设计的一部分。来源：[NYT Games 订阅帮助页](https://help.nytimes.com/360011158491-New-York-Times-Games/360052272251-New-York-Times-Games-Subscription)（检索 2026-10-16）。
**规模（有出处的部分）。** 维基百科条目引述：2024 年 NYT Games 全平台日活玩家超过 1,000 万、付费订阅者超过 100 万；2024 年谜题总游玩 111 亿次（Wordle 53 亿、Connections 33 亿、Strands 13 亿）；Games App 平均日活从 2022 年 10 月的 88.6 万增长到 2023 年超过 260 万。来源：[The New York Times Games（维基）](https://en.wikipedia.org/wiki/The_New_York_Times_Games)（检索 2026-10-16）。另有第三方站点给出「Wordle 2024 年日均约 1,450 万玩家」等数字，属二手转述，建议不作为决策依据。
**订阅与留存机制。** 2025 年 9 月 NYT 推出家庭订阅：All Access Family 30 美元/月（最多 4 人），Games Family 10 美元/月；单人 Games 订阅约 50 美元/年，家庭 Games 约 120 美元/年。每位成员有独立账号、独立战绩与 streak，并可在共享排行榜上互相竞争；官方称家庭计划早期测试显示留存更高（订阅增长负责人 Ben Cotton 语）。来源：[NYT 官方新闻稿](https://www.nytco.com/press/familysubscription)、[Nieman Lab 报道](https://www.niemanlab.org/2025/09/the-new-york-times-launches-a-family-subscription-with-separate-wordles-for-everyone)（检索 2026-10-16）。
**内容生产。** Connections 出自 NYT Games 内部年度 Game Jam，2023 年立项后由谜题编辑 Wyna Liu 负责出题；她用电子表格按黄/绿/蓝/紫四档难度组织题目，每张盘做 1–5 分试玩测试；紫档难在词间联系抽象，且刻意制造跨类干扰。来源：[NYU ITP 访谈](https://tisch.nyu.edu/itp/news/fall-2024/connecting-with-the-editor-of-connections--wyna-liu--14)、[NYT 官方技巧文](https://www.nytimes.com/2023/11/06/crosswords/connections-tips-and-tricks.html)（检索 2026-10-16）。
**难度标定（Wordle 侧）。** Wordle 的答案是人工筛选的 2,315 词表（Wardle 的伴侣 Palak Shah 把约 13,000 个五字母词按「认识 / 不认识 / 可能认识」分档筛出），按每天一题算够用约五年；猜词池则单独放行约一万词。来源：[Wordle（维基）](https://en.wikipedia.org/wiki/Wordle)、[Game Developer 对 Wardle 的回顾](https://www.gamedeveloper.com/marketing/josh-wardle-reflects-on-the-the-unconventional-road-to-wordle-s-success)、[词表说明帖](https://www.reddit.com/r/wordle/comments/s4tcw8/a_note_on_wordles_word_list)（检索 2026-10-16）。
**分享卡片。** 无剧透的彩色方块分享格式最初由玩家社群（新西兰一个群组）发明，Wardle 随后把它做进分享按钮；2022 年 1 月 1–13 日间 Twitter 上分享了 120 万条结果。来源：[BuzzFeed News 复盘](https://www.buzzfeednews.com/article/stefficao/how-wordle-went-viral-strategy)、[NYT 2022 年 1 月 31 日收购报道](https://www.nytimes.com/2022/01/31/crosswords/nyt-wordle-purchase.html)（检索 2026-10-16）。
**跨端与档案。** 2025 年 9 月 NYT 上线 Strands 档案（500+ 题），是 Games 组合里的第 6 个档案；订阅者可访问填字、Mini、Wordle、Connections、Spelling Bee、Strands 共 1 万多道题。来源：[NYT 官方 Strands Archive 新闻稿](https://www.nytco.com/press/introducing-the-strands-archive)（检索 2026-10-16）。维基条目还记载 2025 年 8 月起 Mini Crossword、Tiles、Letter Boxed 转为订阅专属，Spelling Bee 免费仅到「Good/Solid」等级，说明其免费层是**可调节的引流阀门**。来源：[维基条目](https://en.wikipedia.org/wiki/The_New_York_Times_Games)（检索 2026-10-16）。

**可复制 / 难复制。**
- 可复制：每日一题、streak、无剧透分享、档案补玩、免费层与订阅层分层。
- 难复制：专职谜题编辑团队与「Game Jam → 立项」的内容流水线；品牌带来的自然流量（NYT 收购 Wordle 时 Games 订阅约 98 万，2021 年 Q3 口径，来源：[CNBC 报道](https://www.cnbc.com/2022/01/31/the-new-york-times-is-buying-wordle.html)，检索 2026-10-16）；以及 Bot/分析工具这类需要长期数据积累的能力。

### 2. 其他每日谜题 / 解谜平台

**LinkedIn Games。** 五个每日游戏 Zip、Tango、Queens、Pinpoint、Crossclimb（官方页面口径），免费；每天太平洋时间午夜重置，每个游戏每天一局、无重玩；每个游戏**独立**记 streak，缺一天该游戏 streak 归零（其他游戏不受影响）；首次进入给教学局。单局时长设计目标在 5 分钟以内，定位是给职业资讯平台造「每日习惯」而不是长时游玩。来源：[LinkedIn Games 官方页](https://www.linkedin.com/games)、[第三方整理](https://cripsywire.com/linkedin-games-2026)（检索 2026-10-16）。第三方整理的细节（重置时区换算、教学局一次性）建议再核对，标记为中等可信。
**Guardian。** Guardian Puzzles App 覆盖 iOS/Android，含每周 15 道新填字与每日数独、可访问 1.5 万+ 档案；订阅为 1 周免费试用后 £3.49/月或 £32.99/年（省 20%）。更早的 Sudoku「联赛」产品是每周 £1.50 下载 3 包×6 题、含排行榜与免费新手包。来源：[InPublishing 报道](https://www.inpublishing.co.uk/articles/the-guardian-launches-puzzles-app-15159)、[GamesIndustry.biz 报道](https://www.gamesindustry.biz/guardian-unlimited-launches-sudoku-puzzle-league)（检索 2026-10-16）。Wordiply 是其每日单词游戏（给定起始串造最长单词、5 次机会），来源：[Wordiply 说明页](https://playlin.io/game/wordiply)（二手，检索 2026-10-16）。
**Apple News+。** News+ 订阅者可用每日与存档填字、填字 Mini、Quartiles、数独、Emoji Game；2024 年 5 月上线 Quartiles 与离线模式，并推出 Puzzles Scoreboard 展示每个谜题的解题率与最长 streak；2025 年 7 月上线 Emoji Game，支持 Game Center 排行榜，并可经 Messages/Mail/社交分享结果。来源：[Apple 新闻稿 Quartiles](https://www.apple.com/newsroom/2024/05/apple-news-plus-introduces-quartiles-a-new-game-and-offline-mode-for-subscribers)、[Apple 新闻稿 Emoji Game](https://www.apple.com/newsroom/2025/07/apple-news-plus-introduces-emoji-game)、[Apple 支持页](https://support.apple.com/guide/iphone/find-puzzles-in-apple-news-iph4883822da/ios)（检索 2026-10-16）。
**Puzzling Stack Exchange（社区投稿型）。** 走 Q&A 模式，谜题由社区提问投稿、投票排序，标签体系包括 riddle/knowledge/enigmatic-puzzle/wordplay/visual 等；社区内容被整理成《The Unofficial Stack Exchange Puzzle Book》（取站内历史最高分 100 题，CC BY-SA 3.0 授权，用 Stack Exchange Data Explorer + Python 导出）。来源：[Puzzling 站点](https://puzzling.stackexchange.com)、[Unofficial Puzzle Book 说明](https://consto.uk/2018/01/20/the-unofficial-stack-exchange-puzzle-book)（检索 2026-10-16）。**要点：社区投稿 + 许可证清晰的导出流水线，是「内容供给」的一条免费来源**；但 CC BY-SA 的传染性条款对商业闭源产品是约束，需法务确认。
**janko.at。** Angela 与 Otto Janko 维护的谜题站（版权标注 1999–2020），提供可嵌入自己网站/博客的谜题脚本（可直接引用其站点脚本或复制到本地，前者自动跟随更新但依赖其可用性）。来源：[janko.at 嵌入说明（检索片段）](https://www.janko.at/)、[ukpuzzles 论坛讨论帖](https://ww.ukpuzzles.org/forum/viewtopic.php?t=245)（检索 2026-10-16）。注意：本次未能取回站点正文，嵌入脚本的**具体许可证未找到可核查来源**，若要用需人工确认。
**Simon Tatham's Portable Puzzle Collection。** 约 40 个逻辑谜题，**MIT 许可**，全部后端用 C 编写并配「移植接口」，同一谜题后端可对接 Windows/Mac/GTK/Java applet/浏览器等不同前端（含 NestedVM 编译的 Java applet 与现在的 JS/WASM 网页版）。来源：[官方站点](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/)（检索 2026-10-16）。这是「**同一谜题、多端渲染**」最成熟的既有做法，也是本项目跨端架构可直接抄的作业。
**Microsoft Casual Games。** Minesweeper、Sudoku、Solitaire、Mahjong 等免费游戏，全部（Treasure Hunt 除外）可购买去广告的 Premium；Microsoft Sudoku 的商店页提到每日挑战、金币与徽章。来源：[Xbox 支持页](https://support.xbox.com/en-US/game/microsoft-casual-games/support/premium-game-pass/how-do-i-purchase-an-ad-free-premium-subscription)、[Microsoft Casual Games 购买说明](https://learn.microsoft.com/en-us/xandr/monetize/buying-microsoft-casual-games-windows-o-o-apps)（检索 2026-10-16）。**注意**：这印证了「免费 + 去广告订阅 + 每日挑战」是休闲谜题的通行结构；具体收入构成**未找到可核查来源**。

### 3. 开源实现与标准

**谜题引擎 / 生成器。**
- Sudoku：QQWing（C++，GPL，生成 + 求解 + 难度评估，支持 `--one-line` 81 字符、9 行、CSV 等输出），来源：[QQWing main.cpp 源码页](https://qqwing.com/main.cpp.html)（检索 2026-10-16）；Python 侧有 MIT 的 [python-sudoku-generator-solver](https://github.com/JoeKarlsson/python-sudoku-generator-solver)（4 档难度、暴力求解器、pytest 测试）；JS 侧有 [sudoku.js](https://github.com/robatron/sudoku.js)（生成 + 求解库）与 npm 上多个生成包（[npm 关键词检索](https://www.npmjs.com/search?q=keywords%3Asudoku)）；Go 侧 [eliben/go-sudoku](https://github.com/eliben/go-sudoku) 把「生成 + 难度评估 + 导出 SVG + 编译为 WASM 供网页使用」做成一条链路，来源：[作者博客](https://eli.thegreenplace.net/2022/sudoku-go-and-webassembly)（检索 2026-10-16）。
- 数独求解算法：Dancing Links（DLX）解精确覆盖问题，Knuth 的 Algorithm X 实现，被广泛用于数独/N 皇后等，来源：[Dancing links（维基）](https://en.wikipedia.org/wiki/Dancing_links)、[哥伦比亚大学 Exact Cover 课程报告](https://www.cs.columbia.edu/~sedwards/classes/2021/4995-fall/reports/Exact-Cover.pdf)（检索 2026-10-16）。
- 数织（Nonogram）：npm 有 `nonogram-solver`（Apache-2.0，求解/格式化/序列化，支持 griddler/picross/hanjie 等同义词），来源：[jsDelivr 包页](https://www.jsdelivr.com/package/npm/nonogram-solver)（检索 2026-10-16）；GitHub `nonogram` 话题下有「图片转 Picross / 支持自制彩色格式」的转换器，来源：[GitHub nonogram 话题](https://github.com/topics/nonogram)（检索 2026-10-16）。**未找到**公认的 `.non`/`.nono` 单文件标准规范（维基条目只描述玩法与命名沿革），来源：[Nonogram（维基）](https://en.wikipedia.org/wiki/Nonogram)（检索 2026-10-16）。
- 填字（Crossword）：[crosswords-js](https://github.com/dwmkerr/crosswords-js)（轻量 Web 填字控件，JSON 定义，支持可配置键位方案）、[crossword-api](https://github.com/michaelwehar/wordpress-blog) 的布局生成器（输入词表输出 JSON/文本、npm 包），来源：[作者博客](https://michaelwehar.wordpress.com/2022/03/11/crossword-layout-generator-open-source)（检索 2026-10-16）。
**谜题描述格式。**
- **ipuz**：开放规范（JSON 表达），可表示填字、数独、找词等多种谜题，是 Puzzazz 的商标；有官方 Python 读写/校验库，来源：[ipuz 文档](https://ipuz.readthedocs.org/en/latest)（检索 2026-10-16）。
- **.puz**：闭源格式但流行度高，NYT 等大报用其发布填字；`.ipuz` ↔ `.puz` 有开源 Python 转换器（基于 puzpy 与 ipuz 库），来源：[ipuz→puz 转换器说明](https://blatherberg.wordpress.com/2018/01/29/thing-i-made-ipuz-to-puz-converter)（检索 2026-10-16）。
- **数独文本格式**：每行 81 个 ASCII 字符、N 个数字加 81−N 个占位符的「单行一题」是事实标准，来源：[Sudopedia：Sudoku Clipboard and File Formats](https://sudopedia.sudocue.net/index.php/Sudoku_Clipboard_and_File_Formats)（检索 2026-10-16）。
- **开源题库**：[sudoku-exchange-puzzle-bank](https://github.com/grantm/sudoku-exchange-puzzle-bank) 提供数十万道 QQWing 随机生成的数独，**数据集声明为公有领域**，按难度分文件（easy < 1.5、medium < 2.5、hard < 5.0、diabolical ≥ 5.0），每行 100 字节＝12 字节 SHA1 + 81 位题库串 + 4 字节评分；站点补充说明其题「不受版权限制、可用于任何目的」，来源：[Sudoku Exchange 题库页](https://sudokuexchange.com/puzzle-bank)（检索 2026-10-16）。
- **词表**：[wordnik/wordlist](https://github.com/wordnik/wordlist)（约 18.5 万词、MIT，面向前述单词游戏；含释义/词性/频率/冒犯词标注的完整 JSON 数据集为付费一次性授权），来源同上；SCOWL 词表按 size level 分级、被 Firefox/LibreOffice/Debian 采用，可作为拼写与难度分层的上游，来源：[Linguabase 对比页](https://www.linguabase.org/vs-free.html)（二手汇总，检索 2026-10-16）。
**「同一谜题多端渲染」的既有做法。**
- Portable Puzzle Collection：C 后端 + 多前端（含 JS/WASM），MIT（见上）。
- Go + WASM：go-sudoku 用 `GOOS=js` 编译到 WebAssembly，配 GitHub Pages + Actions 部署（见上）。
- 通用思路：把「谜题数据 / 规则引擎 / 前端渲染」三层分开（JSON Forms 的 core + 多框架 renderer 是通用同构先例，但**不是**谜题领域的既有做法，仅供参考），来源：[JSON Forms 架构文档](https://jsonforms.io/docs/architecture)（检索 2026-10-16）。
**把现有 pygame 项目搬上浏览器。** [pygbag](https://github.com/pygame-web/pygbag) 把 Python + pygame-ce 打包为 WASM/CPython 预构建，在浏览器运行；本地用 `pygbag your.app.folder` 起测试服务器；限制包括：仅支持 pygame-ce、移动端 Safari 需 iOS 15.x 以上、首屏因 CDN 缓存建立较慢、需要避免用标准库做 GUI/IO 同步操作、音频用 OGG、避免 BMP 等大体积资源，来源：[pygbag 仓库](https://github.com/pygame-web/pygbag)、[pygame wasm wiki](https://pygame-web.github.io/wiki/pygbag)（检索 2026-10-16）。
**平台级开源先例。** 解谜活动（puzzle hunt）领域唯一较完整的开源代码基是 Puzzlehunt CMU 的 codebase（另有 galacticpuzzlehunt 的 Django 开源版），来源：[A Puzzlehunt Tech Checklist](https://www.alexirpan.com/2020/03/16/puzzlehunt-tech.html)、[galacticpuzzlehunt](https://github.com/galacticpuzzlehunt)（检索 2026-10-16）；通用自建谜题站有 [puzzlespring](https://github.com/dlareau/puzzlespring)（Django、MIT、正则判题、提示系统）。填字社区有 [Crosshare](https://crosshare.org)（免费、无广告、开源，支持 .puz/.ipuz 与自制 constructor、每日 Mini），来源：[Crosshare 站点](https://crosshare.org)（检索 2026-10-16；其 GitHub 仓库地址本次未取到，标记为未核实）。

### 4. 用户与商业模式（含坑）

**头部做法：免费引流 + 订阅捆绑 + 档案付费。** NYT Games 订阅 50 美元/年（个人）/10 美元/月（家庭），All Access Family 30 美元/月；Games 单订阅不含新闻、Cooking 等其他产品——即「单品订阅」与「全家桶」并行售卖，来源：[NYT 新闻稿](https://www.nytco.com/press/familysubscription)、[NYT Games 帮助页](https://help.nytimes.com/360011158491-New-York-Times-Games/360052272251-New-York-Times-Games-Subscription)（检索 2026-10-16）。行业分析把 Wordle 视为「钩子」，用免费游戏把人拉进 Games 生态再转化成订阅，来源：[Ivey HBA 案例分析](https://www.ivey.uwo.ca/hba/blog/2025/03/the-daily-puzzle-phenomenon-how-nyt-turned-games-into-a-subscription-goldmine)（二手分析，检索 2026-10-16）。
**中腰部做法：App 订阅 + 档案库。** Guardian Puzzles £3.49/月、£32.99/年，卖点是每日数独 + 1.5 万道档案（见上）；Apple 把谜题放进 News+（13 美元/月，来源：[Apple 支持页](https://support.apple.com/guide/iphone/find-puzzles-in-apple-news-iph4883822da/ios)）；微软系走「免费 + 去广告 Premium + 每日挑战/徽章」（见上）。第三方填字 App 的定价区间可参考 App Store 上的 Daily Crossword Challenge（周 9.99 / 月 25.99 / 年 99.99 美元、含免费试用与去广告），来源：[App Store 页面](https://apps.apple.com/us/app/daily-crossword-challenge/id1450607004)（检索 2026-10-16）。
**独立开发者的现实路径。** 一份行业向整理给出的路径是：内容型题库适合订阅制、模块化内容适合内购、广告只在日活与曝光量足够大时才划算，并建议成熟产品再叠加混合模式；其中引用的「个人开发者 3 万 DAU 约 7,000 美元/月」案例为第三方自述、**无法独立核查**，来源：[Anything 博客：如何选择变现模型](https://www.anything.com/blog/app-monetization-models-indie-builders)（检索 2026-10-16，可信度中等，勿据此做财务预测）。另一份游戏商业向综述同样指出「订阅适合持续产出内容的产品」，并提醒变现方式要与玩法预期一致，来源：[Game Business Guide](https://generalistprogrammer.com/game-business)（检索 2026-10-16，可信度中等）。
**广告的坑。** 上述两份来源一致认为广告收益需要较大日活/曝光量才「有意义」，小体量产品先上广告通常得不偿失（第三方观点，非一手数据）。**具体 ARPDAU、eCPM 区间未找到可核查来源。**
**内容平台的坑（可推演但需自证）。** 结合前面的平台事实可以列出：每日更新一旦开始就不能断（LinkedIn 每天午夜重置、断一天 streak 归零，见上）；授权内容（Puzzling SE 的 CC BY-SA、janko.at 脚本）在商用前必须确认许可；puzzle hunt 类平台的运维成本与被攻击面真实存在——有实践者记录维护期约 16 美元/月，并建议活动结束后转成纯静态站把成本压到接近零，来源：[A Puzzlehunt Tech Checklist](https://www.alexirpan.com/2020/03/16/puzzlehunt-tech.html)（检索 2026-10-16）。

### 5. 可访问性（作为独立扫描项）

- 文字型谜题天生适合屏幕阅读器：Wordle 的纯文本形态使盲人/低视力玩家可用屏幕阅读器游玩，来源：[Blind Ambition 介绍页](https://www.blindambition.co.uk/family-games-for-blind-parents-or-children-wordle-and-connections)（检索 2026-10-16）。NYT 玩家社区也在持续要求为「以图片为线索」的题目补充屏幕阅读器描述，来源：[r/NYTCrossword 讨论帖](https://www.reddit.com/r/NYTCrossword/comments/1wa8axy/im_a_totally_blind_nyt_games_player_who_posted)（玩家自述，可信度中等，检索 2026-10-16）。
- 游戏引擎的通用障碍：主流引擎把界面渲染成「一整块像素」，屏幕阅读器读不到系统 UI 元素，需要接 OS 级无障碍 API 或自发声；SDL 的屏幕阅读器支持仍是未完成的功能请求，现有第三方方案多为 Windows 专属且维护停滞，来源：[Game Accessibility Guidelines](https://gameaccessibilityguidelines.com/ensure-screenreader-support-including-menus-installers)、[SDL issue #7463](https://github.com/libsdl-org/SDL/issues/7463)（检索 2026-10-16）。
- 结论：**本项目现在这条路（pygame 桌面）在无障碍上是弱项，而 Web 层反而更容易做对**（浏览器原生提供无障碍树、键盘导航与屏幕阅读器支持）。

---

## 可复制机制清单（按性价比排序）

性价比 = 复制的留存/传播收益 ÷ 实现成本（以本仓库现有 `engine.py` / `domain.py` / `gameplay_pool/` 的改造量为口径）。

| 优先级 | 机制 | 为什么值得抄 | 落地要点 | 来源 |
|---|---|---|---|---|
| P0 | **每日一题（date-seeded）** | 制造稀缺与共同话题，是所有平台的地基 | 用本地日期做确定性索引，从**打乱过一次的固定题序**里取；纯客户端即可，无服务端也能全球同题 | [HN 讨论](https://news.ycombinator.com/item?id=30435522)、[Wordle 维基](https://en.wikipedia.org/wiki/Wordle) |
| P0 | **无剧透分享卡片** | 极低成本换取自然传播（Wordle 半月 120 万条分享） | 只输出「结构信息」（如方块/符号矩阵 + 题号），不输出答案文本 | [BuzzFeed 复盘](https://www.buzzfeednews.com/article/stefficao/how-wordle-went-viral-strategy) |
| P1 | **独立 streak + 本地持久化** | 损失厌恶驱动的次日回访；每个谜题独立计数可避免一次失手全盘放弃 | 每种谜题单独计数；先落本地存档，再考虑账号 | [LinkedIn 游戏整理](https://cripsywire.com/linkedin-games-2026)、[Duolingo streak 机制拆解](https://duolingo.deconstructoroffun.com/mechanics/streaks) |
| P1 | **补玩/档案模式** | 给「错过一天」的人出路，同时把历史内容变成资产 | 先做「按题号回放」，存档与订阅留到有服务器之后 | [NYT Strands Archive 新闻稿](https://www.nytco.com/press/introducing-the-strands-archive) |
| P1 | **难度显式分级 + 选关** | 用户可自选难度能显著降低首次流失；分级靠人工亦可 | 每个谜题内置 easy/normal/hard 档，题序按档维护 | [Connections 技巧文](https://www.nytimes.com/2023/11/06/crosswords/connections-tips-and-tricks.html)、[数独题库分档](https://github.com/grantm/sudoku-exchange-puzzle-bank) |
| P2 | **题库与引擎解耦（数据驱动出题）** | 让「加内容」不必改代码，是内容平台化的前提 | 已有 `gameplay_pool/` 的抽象基类可作切点：把内置常量抽成数据文件 | [Portable Puzzle Collection](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/)、[ipuz 规范](https://ipuz.readthedocs.org/en/latest) |
| P2 | **借力开源生成器补内容** | 用生成器把「题库」从手工升级为可按需生产 | 数独可直接采用公有领域题库；数织/单词类用生成器 + 人工抽检 | [Sudoku Exchange 题库](https://sudokuexchange.com/puzzle-bank)、[QQWing](https://qqwing.com/main.cpp.html)、[wordnik/wordlist](https://github.com/wordnik/wordlist) |
| P2 | **跨端共用渲染数据结构** | 同一份题面数据可以喂给桌面 UI 与 Web UI，避免双份实现 | 学「后端规则 + 多前端」的分层；Web 首选 pygbag 复用现有 pygame 渲染 | [Portable Puzzle Collection](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/)、[pygbag](https://github.com/pygame-web/pygbag) |
| P3 | **难度标定流程（表格 + 试玩打分）** | 让「难度」从感觉变成可维护的数据 | 每道题记录：标签、预估档位、内测 1–5 分、实际通过率 | [NYU ITP 访谈](https://tisch.nyu.edu/itp/news/fall-2024/connecting-with-the-editor-of-connections--wyna-liu--14) |
| P3 | **社区投稿通道** | 内容供给的最便宜来源，但需要规则与授权 | 投稿须带原创声明与授权条款；引用外部社区内容注意 CC BY-SA 传染性 | [Puzzling SE](https://puzzling.stackexchange.com)、[Unofficial Puzzle Book](https://consto.uk/2018/01/20/the-unofficial-stack-exchange-puzzle-book) |
| P3 | **无障碍：键盘导航 + 语音可读文本** | 文字谜题是低成本的「可访问性优等生」；Web 层比 pygame 好做 | 每个棋盘提供文本化状态输出；网页层用语义化 DOM/aria | [Game Accessibility Guidelines](https://gameaccessibilityguidelines.com/ensure-screenreader-support-including-menus-installers)、[SDL #7463](https://github.com/libsdl-org/SDL/issues/7463) |
| P4 | **订阅/去广告变现** | 头部与微软系都验证过结构，但门槛在留存之后 | 先证明每日回访，再谈档案订阅；广告需较大曝光量才成立 | [NYT 订阅页](https://www.nytco.com/press/familysubscription)、[Xbox 支持页](https://support.xbox.com/en-US/game/microsoft-casual-games/support/premium-game-pass/how-do-i-purchase-an-ad-free-premium-subscription) |

---

## 差距分析

对照对象：NYT Games（内容 + 每日 + 跨端 + 分享 + 无障碍的完整闭环）。

### 维度一：内容供给

- 现状：谜题由 `text_adventure/gameplay_pool/` 内各模块的 Python 代码产出（数学、谜语、填字、数独、猜数字、扫雷、数织、2048、记忆、单词阶梯、字母重排、图案规律、猜词、颜色序列），题目与实现耦合，双语版本各有一份并行实现。
- 差距：**没有独立的题库/内容层**，因此「增加内容」= 改代码；也没有难度分级数据、没有内容审核流程、没有外部内容来源。头部平台的内容供给是「编辑 + 题库 + 分级」三件套。
- 优先级评估：**高优先级、中等投入**。把所有谜题的数据抽成数据文件（JSON/ipuz 风格）+ 在 `base_puzzle.py` 之上加一层「题面加载器」，是内容平台化的第一步，也是后面每日一题、档案、难度分级的共同前置。

### 维度二：每日留存机制

- 现状：游戏内已有引擎、计分与事件总线（`engine.py`、`events.py`、`domain.py`），但均为单局会话模型，未见跨日期题序、streak、档案的痕迹。
- 差距：缺少「**同一时刻所有人拿到同一道题**」的每日节奏，缺少 streak 与补玩。
- 优先级评估：**最高优先级、最低投入**。确定性日期索引 + streak 计数 + 分享文本，三件都可以在纯本地完成，不需要服务端；这是投入产出比最高的一组改动。

### 维度三：跨端

- 现状：纯桌面 pygame（`main.py` + `ui.py`），依赖 `pygame-ce`，另有 `shared/ui_boot.py` 支持无头启动（说明渲染层与逻辑层已有一定切分）。
- 差距：没有可分享的 URL、没有手机可玩形态；但也不必从零重写——`ui_boot.py` 这类切分正好是「逻辑/渲染分层」的起点。
- 优先级评估：**中高优先级、投入可控**。最短路径是用 pygbag 把现有 pygame 应用编译为 WASM 上线（已知限制：仅支持 pygame-ce、移动端 Safari 需 iOS 15+、首屏较慢、资源需 OGG/PNG/WEBP）。中期再把题面数据与规则引擎抽成与渲染无关的层，为未来的 Web 原生渲染留口。

### 维度四：社交分享

- 现状：未找到任何分享/结果导出能力的痕迹（README 与目录结构均无）。
- 差距：缺少「无剧透结果卡片」这一最强的自然传播手段；也缺少排行榜、好友对比（NYT 家庭订阅的共享排行榜、Apple 的 Game Center 排行榜）。
- 优先级评估：**高优先级、极低投入**。先做纯文本分享卡片（复制到剪贴板即可，不需要任何账号体系），排行榜等需要服务端的能力往后排。

### 维度五：可访问性

- 现状：pygame 自绘界面 + 自备 CJK 字体解析（`shared/font_utils.py`），整体是「一整块像素」的渲染模型。
- 差距：屏幕阅读器无法读取自绘界面；SDL 的屏幕阅读器支持仍是未完成的功能请求；字号/对比度/键盘导航也没有独立设置。
- 优先级评估：**中优先级、Web 化后边际成本最低**。桌面端短期可做「文本模式输出」（把棋盘状态打印成可读文本，既服务无障碍也服务调试）；长期应把无障碍要求写进 Web 层。

### 优先级总排序（投入产出比）

1. **每日一题 + streak + 无剧透分享（P0）** —— 不需要服务端，直接复用现有引擎与计分；立刻产生「明天再来」与「分享出去」两个增长杠杆。
2. **题库/内容层解耦（P1）** —— 是 P0 之外的其余一切（难度分级、档案、社区投稿、生成器接入）的前置条件。
3. **跨端最小闭环（P1）** —— pygbag 上线一个可分享 URL 的版本，先验证「浏览器里能玩、能分享」，再谈重写。
4. **难度分级与补玩档案（P2）** —— 依赖第 2 项；补玩要谨慎：档案过强会削弱「每日一题」的稀缺性（NYT 自己也是把档案放在订阅层）。
5. **可访问性与变现（P3/P4）** —— 无障碍在 Web 化后顺手做；变现必须等到留存被证明，且内容平台化的收入结构在头部是「订阅捆绑」，小团队不应把变现当成近期目标。

---

## 来源清单（URL + 检索日期 + 支撑的结论）

所有条目检索日期均为 **2026-10-16**（本次会话联网检索日）。

**NYT Games**
1. https://help.nytimes.com/360011158491-New-York-Times-Games/360052272251-New-York-Times-Games-Subscription —— 免费层/订阅层分层、档案与 Bot 属订阅。
2. https://en.wikipedia.org/wiki/The_New_York_Times_Games —— 玩家/订阅规模（2024：>1000 万日活、>100 万付费）、111 亿次游玩、2025 年多款游戏转订阅。
3. https://www.nytco.com/press/familysubscription —— 家庭订阅价格与「独立战绩/streak + 共享排行榜」。
4. https://www.niemanlab.org/2025/09/the-new-york-times-launches-a-family-subscription-with-separate-wordles-for-everyone —— 价格与「家庭计划留存更高（Ben Cotton）」。
5. https://tisch.nyu.edu/itp/news/fall-2024/connecting-with-the-editor-of-connections--wyna-liu--14 —— Connections 出自 Game Jam；编辑按四色难度用表格组织题目。
6. https://www.nytimes.com/2023/11/06/crosswords/connections-tips-and-tricks.html —— 黄绿蓝紫四级难度定义与「紫档最抽象」。
7. https://en.wikipedia.org/wiki/Wordle —— 2,315 词答案表来源、每日一题带来的稀缺感、增长曲线。
8. https://www.gamedeveloper.com/marketing/josh-wardle-reflects-on-the-the-unconventional-road-to-wordle-s-success —— 每日一题的设计动机（受 NYT Crossword/Spelling Bee 启发）。
9. https://www.reddit.com/r/wordle/comments/s4tcw8/a_note_on_wordles_word_list —— 答案表 2,315 与可猜词表约 1 万的区分。
10. https://news.ycombinator.com/item?id=30435522 —— 客户端按本地日期从预打乱列表取词（无需服务端、重开不改题）。
11. https://www.buzzfeednews.com/article/stefficao/how-wordle-went-viral-strategy —— 分享格式由玩家社群发明、被 Wardle 做进按钮；半月 120 万条分享。
12. https://www.nytimes.com/2022/01/31/crosswords/nyt-wordle-purchase.html —— 无剧透分享卡片是传播主因之一。
13. https://www.nytco.com/press/introducing-the-strands-archive —— Strands 档案 500+ 题；6 个档案合计 1 万+ 题。
14. https://www.cnbc.com/2022/01/31/the-new-york-times-is-buying-wordle.html —— 收购时 Games 订阅约 98 万（2021 Q3）、Games 是订阅战略一环。
15. https://www.ivey.uwo.ca/hba/blog/2025/03/the-daily-puzzle-phenomenon-how-nyt-turned-games-into-a-subscription-goldmine —— 二手分析：「免费游戏作钩子 → 订阅转化」。

**其他平台**
16. https://www.linkedin.com/games —— LinkedIn 五个每日游戏（Zip/Tango/Queens/Pinpoint/Crossclimb）、免费。
17. https://cripsywire.com/linkedin-games-2026 —— 太平洋时间午夜重置、每日一局不可重玩、每游戏独立 streak、教学局一次性（第三方整理，中等可信）。
18. https://www.inpublishing.co.uk/articles/the-guardian-launches-puzzles-app-15159 —— Guardian Puzzles App：每周 15 道新填字、每日数独、1.5 万+ 档案、£3.49/月或 £32.99/年。
19. https://www.gamesindustry.biz/guardian-unlimited-launches-sudoku-puzzle-league —— Guardian 数独联赛：含排行榜与免费新手包的付费周包。
20. https://playlin.io/game/wordiply —— Wordiply 玩法（二手）。
21. https://www.apple.com/newsroom/2024/05/apple-news-plus-introduces-quartiles-a-new-game-and-offline-mode-for-subscribers —— News+ 每日题 + Puzzles Scoreboard（解题率、最长 streak）。
22. https://www.apple.com/newsroom/2025/07/apple-news-plus-introduces-emoji-game —— Emoji Game 每日/档案、Game Center 排行榜与分享。
23. https://support.apple.com/guide/iphone/find-puzzles-in-apple-news-iph4883822da/ios —— News+ 谜题集合（填字/Mini/Quartiles/数独/Emoji Game）。
24. https://puzzling.stackexchange.com —— 社区投稿 Q&A 模式与标签体系。
25. https://consto.uk/2018/01/20/the-unofficial-stack-exchange-puzzle-book —— 社区内容导出为书、CC BY-SA 3.0、Data Explorer + Python 流水线。
26. https://www.janko.at/ —— Janko 谜题站（可嵌入脚本，版权标注 1999–2020）；嵌入许可证未核实。
27. https://ww.ukpuzzles.org/forum/viewtopic.php?t=245 —— janko.at applet/嵌入的社区讨论（辅助）。
28. https://www.chiark.greenend.org.uk/~sgtatham/puzzles/ —— Portable Puzzle Collection：约 40 个谜题、MIT、C 后端 + 多前端（含 JS/WASM/Java applet）。
29. https://support.xbox.com/en-US/game/microsoft-casual-games/support/premium-game-pass/how-do-i-purchase-an-ad-free-premium-subscription —— 微软休闲游戏免费 + 去广告 Premium 结构。
30. https://learn.microsoft.com/en-us/xandr/monetize/buying-microsoft-casual-games-windows-o-o-apps —— 微软休闲游戏清单（辅助）。

**开源实现与标准**
31. https://qqwing.com/main.cpp.html —— QQWing：GPL、生成/求解/难度评估、`--one-line` 81 字符等输出。
32. https://github.com/JoeKarlsson/python-sudoku-generator-solver —— Python 数独生成器（4 档难度，MIT）。
33. https://github.com/robatron/sudoku.js —— JS 数独生成/求解库。
34. https://www.npmjs.com/search?q=keywords%3Asudoku —— npm 数独相关包集合。
35. https://github.com/eliben/go-sudoku + https://eli.thegreenplace.net/2022/sudoku-go-and-webassembly —— Go 库 + WASM 网页版 + SVG 导出（多端渲染链路）。
36. https://en.wikipedia.org/wiki/Dancing_links 与 https://www.cs.columbia.edu/~sedwards/classes/2021/4995-fall/reports/Exact-Cover.pdf —— DLX / Algorithm X 用于数独求解。
37. https://www.jsdelivr.com/package/npm/nonogram-solver —— npm 数织求解/序列化库（Apache-2.0）。
38. https://github.com/topics/nonogram —— 数织转换器/生成器集合（辅助）。
39. https://en.wikipedia.org/wiki/Nonogram —— 数织命名沿革与玩法；**未提供 .non/.nono 标准格式**。
40. https://ipuz.readthedocs.org/en/latest —— ipuz 开放格式规范与 Python 读写库（支持填字/数独/找词）。
41. https://blatherberg.wordpress.com/2018/01/29/thing-i-made-ipuz-to-puz-converter —— .puz 为闭源但主流（NYT 使用）、有 ipuz↔puz 转换器。
42. https://sudopedia.sudocue.net/index.php/Sudoku_Clipboard_and_File_Formats —— 数独单行 81 字符文本格式。
43. https://github.com/grantm/sudoku-exchange-puzzle-bank + https://sudokuexchange.com/puzzle-bank —— 公有领域数独题库与难度分档、每行记录格式。
44. https://github.com/wordnik/wordlist —— MIT 单词表（约 18.5 万词）；完整数据集付费。
45. https://www.linguabase.org/vs-free.html —— SCOWL/UKACD/EOWL 等词表的分级与许可证综述（二手）。
46. https://github.com/dwmkerr/crosswords-js —— Web 填字控件（JSON 定义、可配置键位）。
47. https://michaelwehar.wordpress.com/2022/03/11/crossword-layout-generator-open-source —— 开源填字布局生成器（输出 JSON/文本，有 npm 包）。
48. https://jsonforms.io/docs/architecture —— 「core + 多框架 renderer」的通用同构先例（非谜题领域）。
49. https://github.com/pygame-web/pygbag 与 https://pygame-web.github.io/wiki/pygbag —— pygame-ce → WASM；支持范围、iOS 15+、首屏延迟、资源格式要求。
50. https://www.alexirpan.com/2020/03/16/puzzlehunt-tech.html —— puzzle hunt 技术清单：开源代码基现状、维护成本约 16 美元/月、活动后转静态站降本。
51. https://github.com/galacticpuzzlehunt —— puzzlehunt 开源 Django 实现。
52. https://github.com/dlareau/puzzlespring —— 自建谜题站平台（Django、MIT、正则判题、提示系统）。
53. https://crosshare.org —— 开源、免费无广告的填字创作/分享/解题平台（.puz/.ipuz、每日 Mini）。

**商业模式与可访问性**
54. https://apps.apple.com/us/app/daily-crossword-challenge/id1450607004 —— 第三方填字 App 订阅定价（周/月/年 + 试用 + 去广告）。
55. https://www.anything.com/blog/app-monetization-models-indie-builders —— 变现模型选择（订阅/内购/广告的适用条件）；含无法核查的个人开发者案例数字。
56. https://generalistprogrammer.com/game-business —— 独立游戏变现综述（二手）。
57. https://duolingo.deconstructoroffun.com/mechanics/streaks 与 https://www.justanotherpm.com/blog/the-psychology-behind-duolingos-streak-feature —— streak 的机制拆解（习惯养成 + 损失厌恶 + streak freeze），跨产品参考。
58. https://www.blindambition.co.uk/family-games-for-blind-parents-or-children-wordle-and-connections —— 文字型谜题对屏幕阅读器友好。
59. https://www.reddit.com/r/NYTCrossword/comments/1wa8axy/im_a_totally_blind_nyt_games_player_who_posted —— 盲人玩家对图片线索无障碍描述的需求（玩家自述）。
60. https://gameaccessibilityguidelines.com/ensure-screenreader-support-including-menus-installers 与 https://github.com/libsdl-org/SDL/issues/7463 —— 引擎「整块像素」对屏幕阅读器的障碍、SDL 尚未支持。

**明确标注为证据不足的点**
- NYT Games 各游戏的 DAU、streak 使用率、分享带来的新增占比：**未找到可核查来源**（第三方站点数字为二手转述，已注明）。
- 广告 ARPDAU / eCPM 与独立解谜产品的真实收入结构：**未找到可核查来源**。
- janko.at 嵌入脚本的具体许可证、Crosshare 的 GitHub 仓库地址：**本次未取回正文，未核实**。
- 数织（Nonogram）的官方文件格式标准：**未找到可核查来源**（仅有 npm 库自定义序列化）。
