# 值得看的方向 Top10 · 按时效性分层

生成时间：2026-09-18 15:55

**判定口径**：把散点候选聚合成「方向」后按证据强度排序。
方向判定方式：**agent-语义分类（Claude 直读原文）**。关键词模式下签名宽度不等（AI 方向最宽），跨方向证据数不可直接比热度。

证据数 = 该方向在本时间窗内的独立候选条数（同一候选只计入一个方向，避免重复计数）。

（GitHub 查询缓存：136 条已缓存 / 136 条新鲜——限流时过期旧值会被兜底使用并标记）

**两条证据通道**：需求证据（过痛点/付费构式门槛）与平台热点证据（原生榜+热度达标，不走门槛）。**共振只统计原生榜**——关键词检索命中是同一个查询在多个平台的回声，不等于独立发现。

**评分** = 证据数×1.0 + 信源多样性×0.8 + 付费信号×1.2 + 仓库热度×1.5 + 仓库数×0.4

**强度**：≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。弱信号不等于没价值，但只有一条独立证据时不足以支撑判断 —— 它需要在下个窗口复现才算成立。

**口径警告（读榜单前必读）**：

1. **各方向的关键词签名宽度不等**，「AI 代理与自动化」的签名最宽（agent/llm/prompt/mcp/rag/automation…近 10 组高频词），而「支付与账单」等方向命中面窄。**宽签名天然抓得多，跨方向的证据数不能直接当热度比较**——头部方向的领先幅度要看折扣。
2. **绝对证据数很小**。本周榜第一的「8 条证据」实际 = 4 条 HN 评论 + 2 个 GitHub 仓库 + 1 个 Trending + 1 个 Reddit 帖，排名对一两 条记录的波动敏感，别把「第一」读成「优势巨大」。
3. **各平台采集相互独立**（HN/Reddit/Upwork 的查询都是写死的常量，不存在用 GitHub 结果去搜其他平台的循环），但 Reddit 样本量小（规则层拦截后每周仅个位数），其"投票权"有限。

---

## 今日

### 今日 Top 10 方向

（本窗口采集 476 条，归类出 17 个候选方向）

**原生榜贡献率 74%**（原生 139 / 关键词 49｜目标 ≥40%：达标）　—— 原生榜=排序由平台决定（真独立发现）；关键词检索=排序由我的查询决定（同一查询的回声，不计入共振）。

⚠ **注意**：本窗口有 1 个原生源采集失败（opencli:stackoverflow#api）——原生率会被上游故障直接压低，读数时必须结合失败情况判断，不能当作口径退化。

| # | 方向 | 机会 | 强度 | 需求证据 | 热点 | 共振(原生/检索) | 讨论热度 | 付费 | 存量 | 成型 | 拥挤度 | 评分 | 机会分 |
|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|
| 1 | **AI 代理与自动化** | 已拥挤：需差异化切入 | 强 | 25 | 4 | 6（GS、GT、HN、JJ、PH、RD / B$、HN、IN） | 376 | 0 | 3303 | 621 | 红海 | 36.03 | 10.24 |
| 2 | **报表与可视化** | ★ 值得看 | 强 | 4 | 1 | 3（GS、HN、RD / —） | 37 | 0 | 89 | 13 | 中等 | 11.13 | 5.58 |
| 3 | **视频与音频处理** | 已拥挤：需差异化切入 | 强 | 8 | 1 | 3（DT、GT、RD / B$） | 72 | 0 | 763 | 101 | 拥挤 | 10.8 | 3.74 |
| 4 | **数据采集与解析** | ★ 值得看 | 强 | 5 | 1 | 2（GS、LB / B$、IN） | 360 | 0 | 49 | 6 | 稀疏 | 9.18 | 5.18 |
| 5 | **文档与知识库** | 红海 | 中 | 2 | 1 | 3（GS、JJ、RD / —） | 646 | 0 | 1327 | 107 | 红海 | 7.91 | 2.53 |
| 6 | **内容创作与分发** | 待验证 | 偏弱 | 2 | 0 | 1（GS / B$） | 288 | 0 | 35 | 4 | 稀疏 | 6.57 | 3.97 |
| 7 | **终端与开发者效率** | 待验证 | 偏弱 | 2 | 0 | 1（GS / HN） | 0 | 0 | 62 | 12 | 稀疏 | 5.64 | 3.04 |
| 8 | **支付与账单** | ★ 值得看 | 中 | 3 | 0 | 1（RD / HN） | 693 | 1 | 37 | 6 | 稀疏 | 5.0 | 2.99 |
| 9 | **集成与 API 网关** | 红海 | 弱（单条证据） | 1 | 0 | 1（GS / —） | 0 | 0 | 710 | 56 | 拥挤 | 4.86 | 1.7 |
| 10 | **获客与 SEO** | ★ 值得看 | 中 | 3 | 0 | 1（RD / —） | 0 | 0 | 22 | 3 | 稀疏 | 3.8 | 2.52 |

> **机会象限**：热度（证据数≥3 视为高）× 拥挤度（存量项目≥300 视为拥挤）。「★ 值得看」= 高热度 + 低拥挤；「已拥挤」= 高热度 + 红海，需差异化切入。拥挤度阈值（红海≥1000 / 拥挤≥300 / 中等≥80 / 稀疏<80）来自实测分布，且 GitHub 存量数受关键词选择影响，只作相对比较。

> 强度口径：需求证据+热点合计 ≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。「弱」不代表没价值，只代表本期只有一条独立证据 —— 需要下期复现才算成立。

#### 建议与趋势

**建议结论**看当下值不值得投入（热度 × 拥挤度 × 付费信号）；**趋势评级**看变化速率（头部仓库涨星速度 × 平台共振 × 窗口加速）。两者可能背离 —— 很热但停滞、或证据少却在加速，都真实存在。

| 方向 | 建议结论 | 趋势 | 支撑理由 | 建议动作 |
|---|---|---|---|---|
| **AI 代理与自动化** | 已拥挤，不建议正面进入 | 高（8） | 25 条证据显示需求真实；但 GitHub 存量 3303 个（红海）；头部仓库日均涨星 231（极快）；6 个平台原生榜独立出现（真共振）；今日 25 条 ≥ 本周 22 条（当下密集） | 除非有明确差异化切口（细分人群 / 现有产品的具体差评），否则跳过 |
| **报表与可视化** | ★ 建议优先验证 | 高（8） | 4 条证据 · 3 个平台；存量仅 89 个（稀疏）；1 条出钱证据（招聘/赏金：有人已在为这类活付费）；头部仓库日均涨星 104（较快）；3 个平台原生榜独立出现（真共振）；今日 4 条 ≥ 本周 3 条（当下密集）；仅近期窗口出现（新近冒头） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **视频与音频处理** | 需求真实但供给密集，需差异化 | 高（5） | 8 条证据 · 4 个平台；存量 763 个，已有多家在解；3 个平台原生榜独立出现（真共振）；今日 8 条 / 本周 10 条（正在加速） | 先扒 3-5 个现有产品的差评与退款理由，找未被满足的细分场景 |
| **数据采集与解析** | ★ 建议优先验证 | 中（4） | 5 条证据 · 4 个平台；存量仅 49 个（稀疏）；4 条出钱证据（招聘/赏金：有人已在为这类活付费）；2 个平台原生榜独立出现（真共振）；仅近期窗口出现（新近冒头） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **文档与知识库** | 待观察，证据偏弱 | 高（8） | 3 个平台各 1 条，尚未形成共振；头部仓库日均涨星 117（较快）；3 个平台原生榜独立出现（真共振）；今日 2 条 ≥ 本周 2 条（当下密集）；仅近期窗口出现（新近冒头） | 记进观察名单，看下个窗口能否复现 |
| **内容创作与分发** | 待观察，证据偏弱 | 高（6） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 176（较快）；1 个平台原生榜出现；今日 2 条 ≥ 本周 2 条（当下密集） | 记进观察名单，看下个窗口能否复现 |
| **终端与开发者效率** | 待观察，证据偏弱 | 中（4） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 41；1 个平台原生榜出现；今日 2 条 / 本周 3 条（正在加速） | 记进观察名单，看下个窗口能否复现 |
| **支付与账单** | ★ 建议优先验证 | 中（4） | 3 条证据 · 2 个平台；存量仅 37 个（稀疏）；已出现付费信号；1 个平台原生榜出现；出现付费信号；仅近期窗口出现（新近冒头） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **集成与 API 网关** | 信号不足，暂不判断 | 中（3） | 单条证据支撑不了结论；头部仓库日均涨星 58；1 个平台原生榜出现；仅近期窗口出现（新近冒头） | 不下结论；若趋势评级高可提前留意 |
| **获客与 SEO** | ★ 建议优先验证 | 中（3） | 3 条证据 · 1 个平台；存量仅 22 个（稀疏）；3 条出钱证据（招聘/赏金：有人已在为这类活付费）；1 个平台原生榜出现；仅近期窗口出现（新近冒头） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |

**早期加速信号**（趋势高但证据还少 —— 提前占位候选，失败风险也高）：

- **文档与知识库**：头部仓库日均涨星 117（较快）；3 个平台原生榜独立出现（真共振）；今日 2 条 ≥ 本周 2 条（当下密集）；仅近期窗口出现（新近冒头）
- **内容创作与分发**：头部仓库日均涨星 176（较快）；1 个平台原生榜出现；今日 2 条 ≥ 本周 2 条（当下密集）

#### 今日 主要方向的证据原文

**AI 代理与自动化**　证据 25 条　信源 github_bounty, github_search, github_trending, hn, indeed, juejin, producthunt, reddit
- [kuhnhomeuk-cell/procedural-film](https://github.com/kuhnhomeuk-cell/procedural-film)
  > Agent skill: turn a topic into a 30s vertical film drawn and scored entirely in JavaScript. Reference film: the life of a monarch butterfly.
- [vlad-terin/jev-browser](https://github.com/vlad-terin/jev-browser)
  > Jev-powered element selection for your agent’s existing computer-use tools
- [jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)
  > One AI trade decision every Monad block. Jev on Kuru MON-USDC.
- 相关仓库：[jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)（★611，日均+230.8）、[fhshaik/typesafe-mario](https://github.com/fhshaik/typesafe-mario)（★237，日均+89.5）、[kitze/skillbox](https://github.com/kitze/skillbox)（★119，日均+72.3）

**报表与可视化**　证据 4 条　信源 github_search, hn, reddit
- [Marcos66236/github-stars-history](https://github.com/Marcos66236/github-stars-history)
  > Track and visualize the stars history of any GitHub repository. Open-source growth analytics and velocity tracking.
- [devagrawal09/jev-review](https://github.com/devagrawal09/jev-review)
  > A staged code-review workflow and local dashboard built with TypeSafe Jev.
- [[FOR HIRE] The Last Google Ads Guy You'll Ever Hire](https://www.reddit.com/r/forhire/comments/1wj8p84/for_hire_the_last_google_ads_guy_youll_ever_hire/)
  > [FOR HIRE] The Last Google Ads Guy You'll Ever Hire. For over 8 years, I’ve worked with brands managing Ad Budgets up to $500K/month, generating consistent profits of $90K+ weekly for my Cli
- 相关仓库：[Marcos66236/github-stars-history](https://github.com/Marcos66236/github-stars-history)（★276，日均+104.3）、[devagrawal09/jev-review](https://github.com/devagrawal09/jev-review)（★191，日均+72.2）、[mirkovicdev/HFTENGINE](https://github.com/mirkovicdev/HFTENGINE)（★127，日均+48）

**视频与音频处理**　证据 8 条　信源 devto, github_bounty, github_trending, reddit
- [​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground P](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/)
  > ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project. ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project ($40/mo + Growth Up
- [[FOR HIRE] Graphic Design, Motion Graphics, Branding, Social Content & Video E](https://www.reddit.com/r/forhire/comments/1wjiif2/for_hire_graphic_design_motion_graphics_branding/)
  > [FOR HIRE] Graphic Design, Motion Graphics, Branding, Social Content & Video Edits - $20+. Hey, I'm a freelance designer/editor with 4+ years in graphic design and 2+ years in video editing.
- [[For Hire] Affordable Photo & Video Editing - High Quality Results !](https://www.reddit.com/r/forhire/comments/1wjg795/for_hire_affordable_photo_video_editing_high/)
  > [For Hire] Affordable Photo & Video Editing - High Quality Results !. Hi ! I’m a photo and video editor with 7 years of experience turning ordinary visuals into eye-catching content. I help 
- 相关仓库：[jamiepine/voicebox](https://github.com/jamiepine/voicebox)（★54952，日均+0）

#### 真实案例速查

成熟项目=GitHub 全量按星标 top3（验证赛道成色）；需求证据帖=本窗口抓到的原链（验证需求真实性）。

**1. AI 代理与自动化**
- 成熟/高关注项目：[affaan-m/ECC](https://github.com/affaan-m/ECC）（★261358，更新 2026-09-17） · [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent）（★246639，更新 2026-09-18） · [langgenius/dify](https://github.com/langgenius/dify）（★156226，更新 2026-09-18）
- 需求证据帖：[kuhnhomeuk-cell/procedural-film](https://github.com/kuhnhomeuk-cell/procedural-film) · [vlad-terin/jev-browser](https://github.com/vlad-terin/jev-browser) · [jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)

**2. 报表与可视化**
- 成熟/高关注项目：[metabase/metabase](https://github.com/metabase/metabase）（★49324，更新 2026-09-18） · [briefercloud/briefer](https://github.com/briefercloud/briefer）（★4325，更新 2025-08-07） · [StructuredLabs/preswald](https://github.com/StructuredLabs/preswald）（★4270，更新 2026-06-11）
- 需求证据帖：[Marcos66236/github-stars-history](https://github.com/Marcos66236/github-stars-history) · [devagrawal09/jev-review](https://github.com/devagrawal09/jev-review) · [[FOR HIRE] The Last Google Ads Guy You'll Ev](https://www.reddit.com/r/forhire/comments/1wj8p84/for_hire_the_last_google_ads_guy_youll_ever_hire/)

**3. 视频与音频处理**
- 成熟/高关注项目：[harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo）（★124487，更新 2026-09-18） · [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg）（★64317，更新 2026-09-17） · [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage）（★59813，更新 2026-09-06）
- 需求证据帖：[​[Hiring] Visual Director & Short-Form Video](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/) · [[FOR HIRE] Graphic Design, Motion Graphics, ](https://www.reddit.com/r/forhire/comments/1wjiif2/for_hire_graphic_design_motion_graphics_branding/) · [[For Hire] Affordable Photo & Video Editing ](https://www.reddit.com/r/forhire/comments/1wjg795/for_hire_affordable_photo_video_editing_high/)

**4. 数据采集与解析**
- 成熟/高关注项目：[cheeriojs/cheerio](https://github.com/cheeriojs/cheerio）（★30491，更新 2026-09-18） · [rust-scraper/scraper](https://github.com/rust-scraper/scraper）（★2420，更新 2026-09-14） · [oxylabs/how-to-scrape-google-images](https://github.com/oxylabs/how-to-scrape-google-images）（★2117，更新 2026-06-19）
- 需求证据帖：[justoneapi-labs/xiaohongshu-api](https://github.com/justoneapi-labs/xiaohongshu-api) · [Bartlett Distribution Services LLC 招聘：data s](https://www.indeed.com/viewjob?jk=c6dd8c024ade7f41) · [INTERNATIONAL HIGHLIGHT LLC 招聘：data scraping](https://www.indeed.com/viewjob?jk=6417d71cb37e683c)

**5. 文档与知识库**
- 成熟/高关注项目：[freeCodeCamp/devdocs](https://github.com/freeCodeCamp/devdocs）（★39463，更新 2026-09-15） · [inkonchain/docs](https://github.com/inkonchain/docs）（★36505，更新 2026-09-15） · [docsifyjs/docsify](https://github.com/docsifyjs/docsify）（★31513，更新 2026-09-17）
- 需求证据帖：[nMaas8388/github-ranking-audit](https://github.com/nMaas8388/github-ranking-audit) · [[FOR HIRE] CAD Draftsman / Architectural Dra](https://www.reddit.com/r/forhire/comments/1wjh261/for_hire_cad_draftsman_architectural_drafter/) · [为什么越来越多人用OpenWiki？](https://juejin.cn/post/7685591822258585626)

**6. 内容创作与分发**
- 成熟/高关注项目：[TryGhost/Ghost](https://github.com/TryGhost/Ghost）（★55347，更新 2026-09-18） · [yaojingang/GEOFlow](https://github.com/yaojingang/GEOFlow）（★3652，更新 2026-09-18） · [blogifierdotnet/Blogifier](https://github.com/blogifierdotnet/Blogifier）（★1295，更新 2026-03-16）
- 需求证据帖：[korcarc/text-humanizer](https://github.com/korcarc/text-humanizer) · [Reverse bounty](https://github.com/OmniBlocks/monorepo/issues/795)

**7. 终端与开发者效率**
- 成熟/高关注项目：[apollographql/apollo-client](https://github.com/apollographql/apollo-client）（★19801，更新 2026-09-17） · [guarinogabriel/Mac-CLI](https://github.com/guarinogabriel/Mac-CLI）（★9121，更新 2026-02-28） · [donnemartin/dev-setup](https://github.com/donnemartin/dev-setup）（★6267，更新 2023-02-27）
- 需求证据帖：[kdbhalala/avdslim](https://github.com/kdbhalala/avdslim) · [Cpak – OCI application package format for Li](https://news.ycombinator.com/item?id=49709877)

**8. 支付与账单**
- 成熟/高关注项目：[OpenByteInc/QuantDinger](https://github.com/OpenByteInc/QuantDinger）（★11712，更新 2026-09-18） · [getlago/lago](https://github.com/getlago/lago）（★10572，更新 2026-09-17） · [killbill/killbill](https://github.com/killbill/killbill）（★5737，更新 2026-09-14）
- 需求证据帖：[Show HN: The bottom 50% of U.S. households a](https://news.ycombinator.com/item?id=49743608) · [First Monthly Subscription I am legit shakin](https://www.reddit.com/comments/1wi88io) · [[FOR HIRE] Designer and illustrator - mascot](https://www.reddit.com/r/forhire/comments/1wj22qz/for_hire_designer_and_illustrator_mascots_logos/)

**9. 集成与 API 网关**
- 成熟/高关注项目：[appsmithorg/appsmith](https://github.com/appsmithorg/appsmith）（★40898，更新 2026-09-18） · [The-Vibe-Company/quivr](https://github.com/The-Vibe-Company/quivr）（★39532，更新 2026-08-31） · [deepseek-ai/awesome-deepseek-integration](https://github.com/deepseek-ai/awesome-deepseek-integration）（★39165，更新 2026-02-23）
- 需求证据帖：[dofastted/vm2api](https://github.com/dofastted/vm2api)

**10. 获客与 SEO**
- 成熟/高关注项目：[coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills）（★50754，更新 2026-09-05） · [nextacular/nextacular](https://github.com/nextacular/nextacular）（★1388，更新 2026-05-30） · [ALwrity/ALwrity](https://github.com/ALwrity/ALwrity）（★1164，更新 2026-09-15）
- 需求证据帖：[[Hiring] Mid/Senior Ad Campaign Manager (Use](https://www.reddit.com/r/forhire/comments/1wjdnj7/hiring_midsenior_ad_campaign_manager_user/) · [[FOR HIRE] Digital Marketing Support | Virtu](https://www.reddit.com/r/forhire/comments/1wj5ohv/for_hire_digital_marketing_support_virtual/) · [[For Hire] Reliable Copywriter That Won't Br](https://www.reddit.com/r/forhire/comments/1wj3135/for_hire_reliable_copywriter_that_wont_break_the/)


#### 各平台视角

> 平台偏差不同，混看会被平均：GitHub 是供给侧（大家在做什么≠有人要），Reddit 才是需求侧原话，Product Hunt 是竞品情报。**同一方向出现在多个平台 = 信号更硬**。

**GitHub 赏金 Issue（有人挂钱求做）**　34 条
- 方向：AI 代理与自动化（3 条 / 平台内 9%）、视频与音频处理（1 条 / 平台内 3%）、数据采集与解析（1 条 / 平台内 3%）、代码质量与 CI（1 条 / 平台内 3%）
- 代表证据：[[bounty] 真机对照测量：装了 MisakaNet 的 agent 是否真的更少重复犯错（要原始日志）](https://github.com/Ikalus1988/MisakaNet/issues/1819)
  > [bounty] 真机对照测量：装了 MisakaNet 的 agent 是否真的更少重复犯错（要原始日志）. > 这是本轮评估（`docs/maintainer/strategic-assessment-2026-09-18.md`）得出的**唯一一个**能改变结论的缺口： > 仓库里所有"装了 

**Reddit（创始人社区·需求侧）**　26 条
- 方向：招聘与 HR（7 条 / 平台内 27%）、视频与音频处理（4 条 / 平台内 15%）、获客与 SEO（3 条 / 平台内 12%）、支付与账单（2 条 / 平台内 8%）
- 代表证据：[​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Under](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/)
  > ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project. ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap

**GitHub Search（供给侧·新增）**　25 条
- 方向：AI 代理与自动化（8 条 / 平台内 32%）、报表与可视化（3 条 / 平台内 12%）、内容创作与分发（1 条 / 平台内 4%）、文档与知识库（1 条 / 平台内 4%）
- 代表证据：[kuhnhomeuk-cell/procedural-film](https://github.com/kuhnhomeuk-cell/procedural-film)
  > Agent skill: turn a topic into a 30s vertical film drawn and scored entirely in JavaScript. Reference film: the life of a monarch butterfly.

**Hacker News（技术讨论）**　24 条
- 方向：AI 代理与自动化（4 条 / 平台内 17%）、支付与账单（1 条 / 平台内 4%）、电商与跨境（1 条 / 平台内 4%）、终端与开发者效率（1 条 / 平台内 4%）
- 代表证据：[Introducing System One Models and Jev](https://news.ycombinator.com/item?id=49720601)
  > …ou really have to do a lot of hand holding here, and map out your problem space manually, and very carefully, to get any sort of accuracy. For exampl

**掘金（中文技术热榜，弱等效）**　20 条
- 方向：文档与知识库（1 条 / 平台内 5%）、AI 代理与自动化（1 条 / 平台内 5%）
- 代表证据：[为什么越来越多人用OpenWiki？](https://juejin.cn/post/7685591822258585626)
  > 为什么越来越多人用OpenWiki？. comments=3 author=苏三说技术

**GitHub Trending（供给侧·热度）**　13 条
- 方向：AI 代理与自动化（5 条 / 平台内 38%）、安全与合规（1 条 / 平台内 8%）、视频与音频处理（1 条 / 平台内 8%）、协作与项目管理（1 条 / 平台内 8%）
- 代表证据：[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
  > 

**Lobsters（技术讨论）**　11 条
- 方向：数据采集与解析（1 条 / 平台内 9%）、自托管与部署（1 条 / 平台内 9%）
- 代表证据：[Creepy crawlies](https://lobste.rs/s/nbjo0i/creepy_crawlies)
  > Creepy crawlies. score=140 comments=60 author=gmem

**Bluesky（热门话题，弱等效）**　10 条
- 无可归类方向（供给型记录或未覆盖话题）

**Indeed（招聘=企业付费）**　7 条
- 方向：AI 代理与自动化（4 条 / 平台内 57%）、数据采集与解析（3 条 / 平台内 43%）
- 代表证据：[Johns Hopkins University 招聘：automation（Hybrid work in Baltimore, MD 21](https://www.indeed.com/viewjob?jk=fcb56cc3453612c1)
  > Johns Hopkins University 招聘：automation（Hybrid work in Baltimore, MD 21218）. 薪资 薪资面议；类型 。企业正在出钱招人做「automation」相关任务——该任务已被验证值得花钱。

**Product Hunt（新发布·竞品情报）**　7 条
- 方向：AI 代理与自动化（2 条 / 平台内 29%）、财务与记账（1 条 / 平台内 14%）、本地化与翻译（1 条 / 平台内 14%）
- 代表证据：[M9R](https://www.producthunt.com/products/m9r)
  > M9R. Multiplayer space for your AI coding agents and teams author=Ayaan Ali

**DEV.to（开发者文章）**　4 条
- 方向：视频与音频处理（1 条 / 平台内 25%）
- 代表证据：[Build real-time voice applications with Gemini 3.8 Live and 3.5 Transc](https://dev.to/googleai/build-real-time-voice-applications-with-gemini-38-live-and-35-transcribe-4nb5)
  > Build real-time voice applications with Gemini 3.8 Live and 3.5 Transcribe. comments=8 author=thorwebdev

**LessWrong（理性社区）**　4 条
- 无可归类方向（供给型记录或未覆盖话题）

**Stack Overflow（提问=未满足需求）**　3 条
- 方向：自托管与部署（1 条 / 平台内 33%）
- 代表证据：[Getting forbidden error on selenium chrome I am working on a Python Se](https://stackoverflow.com/questions/80003603/getting-forbidden-error-on-selenium-chrome)
  > Getting forbidden error on selenium chrome I am working on a Python Selenium application that monitors an exam registration website. I am getting a 40


---

## 本周

### 本周 Top 10 方向

（本窗口采集 322 条，归类出 17 个候选方向）

**原生榜贡献率 57%**（原生 69 / 关键词 53｜目标 ≥40%：达标）　—— 原生榜=排序由平台决定（真独立发现）；关键词检索=排序由我的查询决定（同一查询的回声，不计入共振）。

⚠ **注意**：本窗口有 1 个原生源采集失败（opencli:stackoverflow#api）——原生率会被上游故障直接压低，读数时必须结合失败情况判断，不能当作口径退化。

| # | 方向 | 机会 | 强度 | 需求证据 | 热点 | 共振(原生/检索) | 讨论热度 | 付费 | 存量 | 成型 | 拥挤度 | 评分 | 机会分 |
|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|
| 1 | **AI 代理与自动化** | 已拥挤：需差异化切入 | 强 | 22 | 0 | 3（GS、GT、RD / B$、HN、IN） | 1744 | 1 | 3303 | 621 | 红海 | 31.66 | 8.99 |
| 2 | **视频与音频处理** | 已拥挤：需差异化切入 | 强 | 10 | 0 | 2（GS、RD / B$、HN） | 48 | 0 | 763 | 101 | 拥挤 | 15.69 | 5.43 |
| 3 | **自托管与部署** | ★ 值得看 | 中 | 4 | 0 | 2（GS、GT / —） | 0 | 0 | 182 | 39 | 中等 | 10.6 | 4.64 |
| 4 | **报表与可视化** | ★ 值得看 | 中 | 3 | 0 | 2（GS、RD / —） | 0 | 0 | 89 | 13 | 中等 | 8.77 | 4.39 |
| 5 | **安全与合规** | ★ 值得看 | 中 | 3 | 0 | 1（GS / —） | 0 | 0 | 198 | 38 | 中等 | 8.4 | 3.62 |
| 6 | **代码质量与 CI** | ★ 值得看 | 中 | 3 | 0 | 1（GS / B$） | 224 | 0 | 17 | 3 | 稀疏 | 7.85 | 5.48 |
| 7 | **文档与知识库** | 红海 | 偏弱 | 2 | 0 | 2（GS、RD / —） | 0 | 0 | 1327 | 107 | 红海 | 7.11 | 2.27 |
| 8 | **终端与开发者效率** | ★ 值得看 | 中 | 3 | 0 | 1（GS / HN） | 0 | 0 | 62 | 12 | 稀疏 | 6.75 | 3.63 |
| 9 | **内容创作与分发** | 待验证 | 偏弱 | 2 | 0 | 1（GS / B$） | 288 | 0 | 35 | 4 | 稀疏 | 6.57 | 3.97 |
| 10 | **育儿与生活服务** | 待验证 | 弱（单条证据） | 1 | 0 | 1（GS / —） | 0 | 0 | 0 | 0 | 稀疏 | 5.65 | 5.65 |

> **机会象限**：热度（证据数≥3 视为高）× 拥挤度（存量项目≥300 视为拥挤）。「★ 值得看」= 高热度 + 低拥挤；「已拥挤」= 高热度 + 红海，需差异化切入。拥挤度阈值（红海≥1000 / 拥挤≥300 / 中等≥80 / 稀疏<80）来自实测分布，且 GitHub 存量数受关键词选择影响，只作相对比较。

> 强度口径：需求证据+热点合计 ≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。「弱」不代表没价值，只代表本期只有一条独立证据 —— 需要下期复现才算成立。

#### 建议与趋势

**建议结论**看当下值不值得投入（热度 × 拥挤度 × 付费信号）；**趋势评级**看变化速率（头部仓库涨星速度 × 平台共振 × 窗口加速）。两者可能背离 —— 很热但停滞、或证据少却在加速，都真实存在。

| 方向 | 建议结论 | 趋势 | 支撑理由 | 建议动作 |
|---|---|---|---|---|
| **AI 代理与自动化** | 已拥挤，不建议正面进入 | 高（8） | 25 条证据显示需求真实；但 GitHub 存量 3303 个（红海）；头部仓库日均涨星 231（极快）；6 个平台原生榜独立出现（真共振）；今日 25 条 ≥ 本周 22 条（当下密集） | 除非有明确差异化切口（细分人群 / 现有产品的具体差评），否则跳过 |
| **视频与音频处理** | 需求真实但供给密集，需差异化 | 高（5） | 8 条证据 · 4 个平台；存量 763 个，已有多家在解；3 个平台原生榜独立出现（真共振）；今日 8 条 / 本周 10 条（正在加速） | 先扒 3-5 个现有产品的差评与退款理由，找未被满足的细分场景 |
| **自托管与部署** | ★ 值得看，但需补付费证据 | 高（5） | 4 条证据 · 2 个平台；存量仅 182 个，供给少；头部仓库日均涨星 114（较快）；2 个平台原生榜独立出现（真共振）；本周 4 / 本月 3（升温） | 先验证有没有人愿意为此掏钱（找原帖作者 / 招聘帖 / 付费竞品） |
| **报表与可视化** | ★ 建议优先验证 | 高（8） | 4 条证据 · 3 个平台；存量仅 89 个（稀疏）；1 条出钱证据（招聘/赏金：有人已在为这类活付费）；头部仓库日均涨星 104（较快）；3 个平台原生榜独立出现（真共振）；今日 4 条 ≥ 本周 3 条（当下密集）；仅近期窗口出现（新近冒头） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **安全与合规** | ★ 值得看，但需补付费证据 | 中（4） | 3 条证据 · 1 个平台；存量仅 198 个，供给少；头部仓库日均涨星 95（较快）；1 个平台原生榜出现；本周 3 / 本月 2（升温） | 先验证有没有人愿意为此掏钱（找原帖作者 / 招聘帖 / 付费竞品） |
| **代码质量与 CI** | ★ 建议优先验证 | 高（5） | 3 条证据 · 2 个平台；存量仅 17 个（稀疏）；1 条出钱证据（招聘/赏金：有人已在为这类活付费）；头部仓库日均涨星 87（较快）；1 个平台原生榜出现；本周 3 / 本月 3（升温） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **文档与知识库** | 待观察，证据偏弱 | 高（8） | 3 个平台各 1 条，尚未形成共振；头部仓库日均涨星 117（较快）；3 个平台原生榜独立出现（真共振）；今日 2 条 ≥ 本周 2 条（当下密集）；仅近期窗口出现（新近冒头） | 记进观察名单，看下个窗口能否复现 |
| **终端与开发者效率** | 待观察，证据偏弱 | 中（4） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 41；1 个平台原生榜出现；今日 2 条 / 本周 3 条（正在加速） | 记进观察名单，看下个窗口能否复现 |
| **内容创作与分发** | 待观察，证据偏弱 | 高（6） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 176（较快）；1 个平台原生榜出现；今日 2 条 ≥ 本周 2 条（当下密集） | 记进观察名单，看下个窗口能否复现 |
| **育儿与生活服务** | 信号不足，暂不判断 | 中（3） | 单条证据支撑不了结论；头部仓库日均涨星 199（较快）；1 个平台原生榜出现 | 不下结论；若趋势评级高可提前留意 |

**早期加速信号**（趋势高但证据还少 —— 提前占位候选，失败风险也高）：

- **文档与知识库**：头部仓库日均涨星 117（较快）；3 个平台原生榜独立出现（真共振）；今日 2 条 ≥ 本周 2 条（当下密集）；仅近期窗口出现（新近冒头）
- **内容创作与分发**：头部仓库日均涨星 176（较快）；1 个平台原生榜出现；今日 2 条 ≥ 本周 2 条（当下密集）

#### 本周 主要方向的证据原文

**AI 代理与自动化**　证据 22 条　信源 github_bounty, github_search, github_trending, hn, indeed, reddit
- [AetherLabsAI/RSIAgent](https://github.com/AetherLabsAI/RSIAgent)
  > A training-free multi-agent framework for recursive self-improvement in new environments through broad-then-deep autonomous exploration and reusable memory.
- [Rant: Stop building useless apps and products This sub and few adjacent are fu](https://www.reddit.com/comments/1wgxzx9)
  > …all in. Do you have a teamspeak server I can join? > I'm sold. Just shut up and take my money > > ![gif](giphy|TdwziQPhbNAzK) \- pomodoro timer \- fasting timer \- habit tracker \- ADHD rem
- [jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)
  > One AI trade decision every Monad block. Jev on Kuru MON-USDC.
- 相关仓库：[jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)（★614，日均+231.5）、[fhshaik/typesafe-mario](https://github.com/fhshaik/typesafe-mario)（★238，日均+89.8）、[mcncarl/jianying-headless](https://github.com/mcncarl/jianying-headless)（★301，日均+82.4）

**视频与音频处理**　证据 10 条　信源 github_bounty, github_search, hn, reddit
- [letorig/video-generator-client](https://github.com/letorig/video-generator-client)
  > Async Python wrapper for Seedance, Kling, MiniMax and Wan video generation. Supports CLI and a local web UI
- [groundboxerrespect/Dlls5-auto](https://github.com/groundboxerrespect/Dlls5-auto)
  > 🎮 Self-hosted neural rendering & AI image enhancement service inspired by DLSS 5. Turn any photo, screenshot or game capture into a photoreal cinematic render — bloom, filmic tone mapping, 6
- [​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground P](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/)
  > ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project. ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project ($40/mo + Growth Up
- 相关仓库：[letorig/video-generator-client](https://github.com/letorig/video-generator-client)（★533，日均+114.6）、[groundboxerrespect/Dlls5-auto](https://github.com/groundboxerrespect/Dlls5-auto)（★274，日均+41.2）

**自托管与部署**　证据 4 条　信源 github_search, github_trending
- [danieldeer/seriousdb](https://github.com/danieldeer/seriousdb)
  > A simple, yet effective persistent key-value database.
- [agentverse-os/AgentVerse-OS](https://github.com/agentverse-os/AgentVerse-OS)
  > Personal cloud OS for a developer and their AI agents on a single server. One-command install on Ubuntu, then everything in the browser: a windowed desktop, isolated workspaces with VS Code,
- [MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks)
  > DeepSeek v4.1 Flash EXL3 2.9 bpw for 2x DGX Sparks
- 相关仓库：[agentverse-os/AgentVerse-OS](https://github.com/agentverse-os/AgentVerse-OS)（★757，日均+113.8）、[MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks)（★213，日均+37.7）、[danieldeer/seriousdb](https://github.com/danieldeer/seriousdb)（★208，日均+31.3）

#### 真实案例速查

成熟项目=GitHub 全量按星标 top3（验证赛道成色）；需求证据帖=本窗口抓到的原链（验证需求真实性）。

**1. AI 代理与自动化**
- 成熟/高关注项目：[affaan-m/ECC](https://github.com/affaan-m/ECC）（★261358，更新 2026-09-17） · [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent）（★246639，更新 2026-09-18） · [langgenius/dify](https://github.com/langgenius/dify）（★156226，更新 2026-09-18）
- 需求证据帖：[AetherLabsAI/RSIAgent](https://github.com/AetherLabsAI/RSIAgent) · [Rant: Stop building useless apps and product](https://www.reddit.com/comments/1wgxzx9) · [jarrodwatts/jev-trader](https://github.com/jarrodwatts/jev-trader)

**2. 视频与音频处理**
- 成熟/高关注项目：[harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo）（★124487，更新 2026-09-18） · [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg）（★64317，更新 2026-09-17） · [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage）（★59813，更新 2026-09-06）
- 需求证据帖：[letorig/video-generator-client](https://github.com/letorig/video-generator-client) · [groundboxerrespect/Dlls5-auto](https://github.com/groundboxerrespect/Dlls5-auto) · [​[Hiring] Visual Director & Short-Form Video](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/)

**3. 自托管与部署**
- 成熟/高关注项目：[langgenius/dify](https://github.com/langgenius/dify）（★156226，更新 2026-09-18） · [coollabsio/coolify](https://github.com/coollabsio/coolify）（★61968，更新 2026-09-17） · [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw）（★35070，更新 2026-09-18）
- 需求证据帖：[danieldeer/seriousdb](https://github.com/danieldeer/seriousdb) · [agentverse-os/AgentVerse-OS](https://github.com/agentverse-os/AgentVerse-OS) · [MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sp](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks)

**4. 报表与可视化**
- 成熟/高关注项目：[metabase/metabase](https://github.com/metabase/metabase）（★49324，更新 2026-09-18） · [briefercloud/briefer](https://github.com/briefercloud/briefer）（★4325，更新 2025-08-07） · [StructuredLabs/preswald](https://github.com/StructuredLabs/preswald）（★4270，更新 2026-06-11）
- 需求证据帖：[Marcos66236/github-stars-history](https://github.com/Marcos66236/github-stars-history) · [devagrawal09/jev-review](https://github.com/devagrawal09/jev-review) · [[FOR HIRE] The Last Google Ads Guy You'll Ev](https://www.reddit.com/r/forhire/comments/1wj8p84/for_hire_the_last_google_ads_guy_youll_ever_hire/)

**5. 安全与合规**
- 成熟/高关注项目：[wazuh/wazuh](https://github.com/wazuh/wazuh）（★16924，更新 2026-09-18） · [CISOfy/lynis](https://github.com/CISOfy/lynis）（★16356，更新 2026-09-16） · [prowler-cloud/prowler](https://github.com/prowler-cloud/prowler）（★14831，更新 2026-09-17）
- 需求证据帖：[KazamaDono/taoxd](https://github.com/KazamaDono/taoxd) · [KillaBoi/BrokenPipe](https://github.com/KillaBoi/BrokenPipe) · [shinthink/blitzstrike](https://github.com/shinthink/blitzstrike)

**6. 代码质量与 CI**
- 成熟/高关注项目：[cinder/Cinder](https://github.com/cinder/Cinder）（★5539，更新 2026-03-20） · [cirosantilli/china-dictatorship](https://github.com/cirosantilli/china-dictatorship）（★3211，更新 2026-02-05） · [gege-circle/.github](https://github.com/gege-circle/.github）（★2009，更新 2025-10-04）
- 需求证据帖：[apple/xcode-project-format](https://github.com/apple/xcode-project-format) · [Qiuner/birdview](https://github.com/Qiuner/birdview) · [Bounty](https://github.com/OmniBlocks/Boxy-gh/issues/143)

**7. 文档与知识库**
- 成熟/高关注项目：[freeCodeCamp/devdocs](https://github.com/freeCodeCamp/devdocs）（★39463，更新 2026-09-15） · [inkonchain/docs](https://github.com/inkonchain/docs）（★36505，更新 2026-09-15） · [docsifyjs/docsify](https://github.com/docsifyjs/docsify）（★31513，更新 2026-09-17）
- 需求证据帖：[nMaas8388/github-ranking-audit](https://github.com/nMaas8388/github-ranking-audit) · [[FOR HIRE] CAD Draftsman / Architectural Dra](https://www.reddit.com/r/forhire/comments/1wjh261/for_hire_cad_draftsman_architectural_drafter/)

**8. 终端与开发者效率**
- 成熟/高关注项目：[apollographql/apollo-client](https://github.com/apollographql/apollo-client）（★19801，更新 2026-09-17） · [guarinogabriel/Mac-CLI](https://github.com/guarinogabriel/Mac-CLI）（★9121，更新 2026-02-28） · [donnemartin/dev-setup](https://github.com/donnemartin/dev-setup）（★6267，更新 2023-02-27）
- 需求证据帖：[lingyired/status-trio](https://github.com/lingyired/status-trio) · [Working with Git Worktrees in Magit](https://news.ycombinator.com/item?id=49655548) · [Cpak – OCI application package format for Li](https://news.ycombinator.com/item?id=49709877)

**9. 内容创作与分发**
- 成熟/高关注项目：[TryGhost/Ghost](https://github.com/TryGhost/Ghost）（★55347，更新 2026-09-18） · [yaojingang/GEOFlow](https://github.com/yaojingang/GEOFlow）（★3652，更新 2026-09-18） · [blogifierdotnet/Blogifier](https://github.com/blogifierdotnet/Blogifier）（★1295，更新 2026-03-16）
- 需求证据帖：[korcarc/text-humanizer](https://github.com/korcarc/text-humanizer) · [Reverse bounty](https://github.com/OmniBlocks/monorepo/issues/795)

**10. 育儿与生活服务**
- 本窗口新增仓库：[Chuloo/mural](https://github.com/Chuloo/mural）（★1325）
- 需求证据帖：[Chuloo/mural](https://github.com/Chuloo/mural)


#### 各平台视角

> 平台偏差不同，混看会被平均：GitHub 是供给侧（大家在做什么≠有人要），Reddit 才是需求侧原话，Product Hunt 是竞品情报。**同一方向出现在多个平台 = 信号更硬**。

**GitHub 赏金 Issue（有人挂钱求做）**　34 条
- 方向：AI 代理与自动化（3 条 / 平台内 9%）、视频与音频处理（1 条 / 平台内 3%）、数据采集与解析（1 条 / 平台内 3%）、代码质量与 CI（1 条 / 平台内 3%）
- 代表证据：[[bounty] 真机对照测量：装了 MisakaNet 的 agent 是否真的更少重复犯错（要原始日志）](https://github.com/Ikalus1988/MisakaNet/issues/1819)
  > [bounty] 真机对照测量：装了 MisakaNet 的 agent 是否真的更少重复犯错（要原始日志）. > 这是本轮评估（`docs/maintainer/strategic-assessment-2026-09-18.md`）得出的**唯一一个**能改变结论的缺口： > 仓库里所有"装了 

**GitHub Search（供给侧·新增）**　32 条
- 方向：AI 代理与自动化（5 条 / 平台内 16%）、自托管与部署（3 条 / 平台内 9%）、安全与合规（3 条 / 平台内 9%）、视频与音频处理（2 条 / 平台内 6%）
- 代表证据：[AetherLabsAI/RSIAgent](https://github.com/AetherLabsAI/RSIAgent)
  > A training-free multi-agent framework for recursive self-improvement in new environments through broad-then-deep autonomous exploration and reusable m

**Reddit（创始人社区·需求侧）**　26 条
- 方向：招聘与 HR（7 条 / 平台内 27%）、视频与音频处理（4 条 / 平台内 15%）、获客与 SEO（3 条 / 平台内 12%）、AI 代理与自动化（2 条 / 平台内 8%）
- 代表证据：[​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Under](https://www.reddit.com/r/forhire/comments/1wjhyjt/hiring_visual_director_shortform_video_editor_for/)
  > ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap/Underground Project. ​[Hiring] Visual Director & Short-Form Video Editor for Emo-Trap

**Hacker News（技术讨论）**　13 条
- 方向：AI 代理与自动化（4 条 / 平台内 31%）、终端与开发者效率（2 条 / 平台内 15%）、数据采集与解析（1 条 / 平台内 8%）、文件与存储同步（1 条 / 平台内 8%）
- 代表证据：[Anthropic boss Dario Amodei calls for AI development to slow down](https://news.ycombinator.com/item?id=49675132)
  > …g crazy. And when it works, that&#x27;s worth _something_ but probably our team would pay for that ability at a different price point than the models

**GitHub Trending（供给侧·热度）**　11 条
- 方向：AI 代理与自动化（3 条 / 平台内 27%）、自托管与部署（1 条 / 平台内 9%）
- 代表证据：[openai/plugins](https://github.com/openai/plugins)
  > 

**Indeed（招聘=企业付费）**　6 条
- 方向：AI 代理与自动化（4 条 / 平台内 67%）、数据采集与解析（2 条 / 平台内 33%）
- 代表证据：[Johns Hopkins University 招聘：automation（Hybrid work in Baltimore, MD 21](https://www.indeed.com/viewjob?jk=fcb56cc3453612c1)
  > Johns Hopkins University 招聘：automation（Hybrid work in Baltimore, MD 21218）. 薪资 薪资面议；类型 。企业正在出钱招人做「automation」相关任务——该任务已被验证值得花钱。


---

## 本月

### 本月 Top 10 方向

（本窗口采集 252 条，归类出 15 个候选方向）

**原生榜贡献率 55%**（原生 36 / 关键词 29｜目标 ≥40%：达标）　—— 原生榜=排序由平台决定（真独立发现）；关键词检索=排序由我的查询决定（同一查询的回声，不计入共振）。

⚠ **注意**：本窗口有 1 个原生源采集失败（opencli:stackoverflow#api）——原生率会被上游故障直接压低，读数时必须结合失败情况判断，不能当作口径退化。

| # | 方向 | 机会 | 强度 | 需求证据 | 热点 | 共振(原生/检索) | 讨论热度 | 付费 | 存量 | 成型 | 拥挤度 | 评分 | 机会分 |
|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|
| 1 | **AI 代理与自动化** | 已拥挤：需差异化切入 | 强 | 25 | 0 | 3（GS、GT、RD / HN） | 1625 | 1 | 3303 | 621 | 红海 | 35.34 | 10.04 |
| 2 | **内容创作与分发** | ★ 值得看 | 强 | 5 | 0 | 1（GS / —） | 0 | 0 | 35 | 4 | 稀疏 | 11.93 | 7.22 |
| 3 | **终端与开发者效率** | ★ 值得看 | 强 | 5 | 0 | 2（GS、GT / HN） | 0 | 0 | 62 | 12 | 稀疏 | 10.66 | 5.74 |
| 4 | **监控与可观测** | ★ 值得看 | 中 | 3 | 0 | 1（GS / HN） | 0 | 1 | 277 | 62 | 中等 | 8.63 | 3.51 |
| 5 | **代码质量与 CI** | ★ 值得看 | 中 | 3 | 0 | 1（GS / HN） | 0 | 0 | 17 | 3 | 稀疏 | 8.08 | 5.64 |
| 6 | **视频与音频处理** | 红海 | 偏弱 | 2 | 0 | 1（GS / —） | 0 | 0 | 763 | 101 | 拥挤 | 7.09 | 2.45 |
| 7 | **自托管与部署** | ★ 值得看 | 中 | 3 | 0 | 1（GS / HN） | 0 | 0 | 182 | 39 | 中等 | 6.94 | 3.04 |
| 8 | **安全与合规** | 待验证 | 偏弱 | 2 | 0 | 1（GS / HN） | 0 | 0 | 198 | 38 | 中等 | 5.88 | 2.54 |
| 9 | **电商与跨境** | 待验证 | 弱（单条证据） | 1 | 0 | 1（GS / —） | 0 | 0 | 16 | 1 | 稀疏 | 5.54 | 3.92 |
| 10 | **文件与存储同步** | 待验证 | 偏弱 | 2 | 0 | 0（— / HN） | 0 | 0 | 12 | 1 | 稀疏 | 2.0 | 1.49 |

> **机会象限**：热度（证据数≥3 视为高）× 拥挤度（存量项目≥300 视为拥挤）。「★ 值得看」= 高热度 + 低拥挤；「已拥挤」= 高热度 + 红海，需差异化切入。拥挤度阈值（红海≥1000 / 拥挤≥300 / 中等≥80 / 稀疏<80）来自实测分布，且 GitHub 存量数受关键词选择影响，只作相对比较。

> 强度口径：需求证据+热点合计 ≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。「弱」不代表没价值，只代表本期只有一条独立证据 —— 需要下期复现才算成立。

#### 建议与趋势

**建议结论**看当下值不值得投入（热度 × 拥挤度 × 付费信号）；**趋势评级**看变化速率（头部仓库涨星速度 × 平台共振 × 窗口加速）。两者可能背离 —— 很热但停滞、或证据少却在加速，都真实存在。

| 方向 | 建议结论 | 趋势 | 支撑理由 | 建议动作 |
|---|---|---|---|---|
| **AI 代理与自动化** | 已拥挤，不建议正面进入 | 高（8） | 25 条证据显示需求真实；但 GitHub 存量 3303 个（红海）；头部仓库日均涨星 231（极快）；6 个平台原生榜独立出现（真共振）；今日 25 条 ≥ 本周 22 条（当下密集） | 除非有明确差异化切口（细分人群 / 现有产品的具体差评），否则跳过 |
| **内容创作与分发** | 待观察，证据偏弱 | 高（6） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 176（较快）；1 个平台原生榜出现；今日 2 条 ≥ 本周 2 条（当下密集） | 记进观察名单，看下个窗口能否复现 |
| **终端与开发者效率** | 待观察，证据偏弱 | 中（4） | 2 个平台各 1 条，尚未形成共振；头部仓库日均涨星 41；1 个平台原生榜出现；今日 2 条 / 本周 3 条（正在加速） | 记进观察名单，看下个窗口能否复现 |
| **监控与可观测** | ★ 建议优先验证 | 中（4） | 3 条证据 · 2 个平台；存量仅 277 个（稀疏）；已出现付费信号；头部仓库日均涨星 142（较快）；1 个平台原生榜出现；出现付费信号 | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **代码质量与 CI** | ★ 建议优先验证 | 高（5） | 3 条证据 · 2 个平台；存量仅 17 个（稀疏）；1 条出钱证据（招聘/赏金：有人已在为这类活付费）；头部仓库日均涨星 87（较快）；1 个平台原生榜出现；本周 3 / 本月 3（升温） | 本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品 |
| **视频与音频处理** | 需求真实但供给密集，需差异化 | 高（5） | 8 条证据 · 4 个平台；存量 763 个，已有多家在解；3 个平台原生榜独立出现（真共振）；今日 8 条 / 本周 10 条（正在加速） | 先扒 3-5 个现有产品的差评与退款理由，找未被满足的细分场景 |
| **自托管与部署** | ★ 值得看，但需补付费证据 | 高（5） | 4 条证据 · 2 个平台；存量仅 182 个，供给少；头部仓库日均涨星 114（较快）；2 个平台原生榜独立出现（真共振）；本周 4 / 本月 3（升温） | 先验证有没有人愿意为此掏钱（找原帖作者 / 招聘帖 / 付费竞品） |
| **安全与合规** | ★ 值得看，但需补付费证据 | 中（4） | 3 条证据 · 1 个平台；存量仅 198 个，供给少；头部仓库日均涨星 95（较快）；1 个平台原生榜出现；本周 3 / 本月 2（升温） | 先验证有没有人愿意为此掏钱（找原帖作者 / 招聘帖 / 付费竞品） |
| **电商与跨境** | 信号不足，暂不判断 | 中（3） | 单条证据支撑不了结论；头部仓库日均涨星 168（较快）；1 个平台原生榜出现 | 不下结论；若趋势评级高可提前留意 |
| **文件与存储同步** | 待观察，证据偏弱 | 低（0） | 1 个平台各 1 条，尚未形成共振；⚠ 另有 1 个平台仅关键词检索命中（非独立发现，不计共振） | 记进观察名单，看下个窗口能否复现 |

**早期加速信号**（趋势高但证据还少 —— 提前占位候选，失败风险也高）：

- **视频与音频处理**：3 个平台原生榜独立出现（真共振）；今日 8 条 / 本周 10 条（正在加速）

#### 本月 主要方向的证据原文

**AI 代理与自动化**　证据 25 条　信源 github_search, github_trending, hn, reddit
- [totec448-spec/chat-on-steroids](https://github.com/totec448-spec/chat-on-steroids)
  > Cross-platform local MCP capabilities for ChatGPT with Chrome integration, Goal, Compact & Resume, and durable multi-agent workflows.
- [nateherkai/scroll-craft](https://github.com/nateherkai/scroll-craft)
  > An agent skill for building premium, immersive, scroll-driven websites. Works with Codex, Claude Code, and other coding agents. Also available as a Claude Code plugin.
- [achimala/dream-loop](https://github.com/achimala/dream-loop)
  > Agent skill for impressive 3D visuals using Blender + image gen + subagent critic
- 相关仓库：[lnkiai/m3e-canvas](https://github.com/lnkiai/m3e-canvas)（★7351，日均+441.4）、[NVlabs/SoL-Pi](https://github.com/NVlabs/SoL-Pi)（★2208，日均+132.6）、[b-nnett/grok-bot-0.18-reconstructed](https://github.com/b-nnett/grok-bot-0.18-reconstructed)（★3508，日均+131.6）

**内容创作与分发**　证据 5 条　信源 github_search
- [Nanako0129/sepia](https://github.com/Nanako0129/sepia)
  > De-AI writing skill for any Agent Skills-compatible agent (77+ via the Skills CLI), with native plugins for Claude Code, Codex, Grok Build, and Antigravity. Narrative-architecture repair for
- [sebbbi/NoGraphicsAPI](https://github.com/sebbbi/NoGraphicsAPI)
  > Minimal graphics API. Built on top of latest Vulkan extensions. As close as possibly to my "No Graphics API" blog post and the SIGGRAPH talk.
- [yang0/handraw-style](https://github.com/yang0/handraw-style)
  > 手绘风格编号画廊与双语提示词 Skill
- 相关仓库：[yang0/handraw-style](https://github.com/yang0/handraw-style)（★2246，日均+164.5）、[EverettFish/holo-card-studio](https://github.com/EverettFish/holo-card-studio)（★1633，日均+140.1）、[Nanako0129/sepia](https://github.com/Nanako0129/sepia)（★2674，日均+123.5）

**终端与开发者效率**　证据 5 条　信源 github_search, github_trending, hn
- [omacom/try-omarchy](https://github.com/omacom/try-omarchy)
  > Run Omarchy on MacOS without any setup.
- [omacom/omarchy](https://github.com/omacom/omarchy)
  > 
- [Lakr233/vphone-cli](https://github.com/Lakr233/vphone-cli)
  > 
- 相关仓库：[omacom/try-omarchy](https://github.com/omacom/try-omarchy)（★2134，日均+80.1）、[omacom/omarchy](https://github.com/omacom/omarchy)（★41773，日均+0）、[Lakr233/vphone-cli](https://github.com/Lakr233/vphone-cli)（★13820，日均+0）

#### 真实案例速查

成熟项目=GitHub 全量按星标 top3（验证赛道成色）；需求证据帖=本窗口抓到的原链（验证需求真实性）。

**1. AI 代理与自动化**
- 成熟/高关注项目：[affaan-m/ECC](https://github.com/affaan-m/ECC）（★261358，更新 2026-09-17） · [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent）（★246639，更新 2026-09-18） · [langgenius/dify](https://github.com/langgenius/dify）（★156226，更新 2026-09-18）
- 需求证据帖：[totec448-spec/chat-on-steroids](https://github.com/totec448-spec/chat-on-steroids) · [nateherkai/scroll-craft](https://github.com/nateherkai/scroll-craft) · [achimala/dream-loop](https://github.com/achimala/dream-loop)

**2. 内容创作与分发**
- 成熟/高关注项目：[TryGhost/Ghost](https://github.com/TryGhost/Ghost）（★55347，更新 2026-09-18） · [yaojingang/GEOFlow](https://github.com/yaojingang/GEOFlow）（★3652，更新 2026-09-18） · [blogifierdotnet/Blogifier](https://github.com/blogifierdotnet/Blogifier）（★1295，更新 2026-03-16）
- 需求证据帖：[Nanako0129/sepia](https://github.com/Nanako0129/sepia) · [sebbbi/NoGraphicsAPI](https://github.com/sebbbi/NoGraphicsAPI) · [yang0/handraw-style](https://github.com/yang0/handraw-style)

**3. 终端与开发者效率**
- 成熟/高关注项目：[apollographql/apollo-client](https://github.com/apollographql/apollo-client）（★19801，更新 2026-09-17） · [guarinogabriel/Mac-CLI](https://github.com/guarinogabriel/Mac-CLI）（★9121，更新 2026-02-28） · [donnemartin/dev-setup](https://github.com/donnemartin/dev-setup）（★6267，更新 2023-02-27）
- 需求证据帖：[omacom/try-omarchy](https://github.com/omacom/try-omarchy) · [omacom/omarchy](https://github.com/omacom/omarchy) · [Lakr233/vphone-cli](https://github.com/Lakr233/vphone-cli)

**4. 监控与可观测**
- 成熟/高关注项目：[netdata/netdata](https://github.com/netdata/netdata）（★80566，更新 2026-09-18） · [grafana/grafana](https://github.com/grafana/grafana）（★76795，更新 2026-09-18） · [langfuse/langfuse](https://github.com/langfuse/langfuse）（★34755，更新 2026-09-17）
- 需求证据帖：[vinzdg/codenotch](https://github.com/vinzdg/codenotch) · [One resignation turned the embers of AI fear](https://news.ycombinator.com/item?id=49647380) · [Show HN: Watches user sessions, finds bugs t](https://news.ycombinator.com/item?id=49479539)

**5. 代码质量与 CI**
- 成熟/高关注项目：[cinder/Cinder](https://github.com/cinder/Cinder）（★5539，更新 2026-03-20） · [cirosantilli/china-dictatorship](https://github.com/cirosantilli/china-dictatorship）（★3211，更新 2026-02-05） · [gege-circle/.github](https://github.com/gege-circle/.github）（★2009，更新 2025-10-04）
- 需求证据帖：[shadcn-ui/lint](https://github.com/shadcn-ui/lint) · [shadcn-ui/cn](https://github.com/shadcn-ui/cn) · [How well do agents use test/verification tec](https://news.ycombinator.com/item?id=49640663)

**6. 视频与音频处理**
- 成熟/高关注项目：[harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo）（★124487，更新 2026-09-18） · [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg）（★64317，更新 2026-09-17） · [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage）（★59813，更新 2026-09-06）
- 需求证据帖：[FireRedTeam/FireRedAudio](https://github.com/FireRedTeam/FireRedAudio) · [Vincentwei1021/anything2explainer](https://github.com/Vincentwei1021/anything2explainer)

**7. 自托管与部署**
- 成熟/高关注项目：[langgenius/dify](https://github.com/langgenius/dify）（★156226，更新 2026-09-18） · [coollabsio/coolify](https://github.com/coollabsio/coolify）（★61968，更新 2026-09-17） · [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw）（★35070，更新 2026-09-18）
- 需求证据帖：[Git-Agni/prod-FARM-IOS-Core](https://github.com/Git-Agni/prod-FARM-IOS-Core) · [Keep Our Servers Running](https://news.ycombinator.com/item?id=49638934) · [Why your local LLM feels dumber than it is](https://news.ycombinator.com/item?id=49407702)

**8. 安全与合规**
- 成熟/高关注项目：[wazuh/wazuh](https://github.com/wazuh/wazuh）（★16924，更新 2026-09-18） · [CISOfy/lynis](https://github.com/CISOfy/lynis）（★16356，更新 2026-09-16） · [prowler-cloud/prowler](https://github.com/prowler-cloud/prowler）（★14831，更新 2026-09-17）
- 需求证据帖：[N4darae/anti-mage](https://github.com/N4darae/anti-mage) · [Actively exploited sandbox RCE in all Chromi](https://news.ycombinator.com/item?id=49575163)

**9. 电商与跨境**
- 成熟/高关注项目：[ever-co/ever-demand](https://github.com/ever-co/ever-demand）（★1858，更新 2026-08-05）
- 需求证据帖：[anthropics/commerce-agents](https://github.com/anthropics/commerce-agents)

**10. 文件与存储同步**
- 成熟/高关注项目：[sebastianfeldmann/phpbu](https://github.com/sebastianfeldmann/phpbu）（★1305，更新 2026-07-03） · [stefankueng/CryptSync](https://github.com/stefankueng/CryptSync）（★443，更新 2026-07-28） · [VikasSukhija/Downloads](https://github.com/VikasSukhija/Downloads）（★424，更新 2025-02-16）
- 需求证据帖：[Show HN: Syq – copy files between machines f](https://news.ycombinator.com/item?id=49661996) · [Creating Backup Storage Sucks](https://news.ycombinator.com/item?id=49546160)


#### 各平台视角

> 平台偏差不同，混看会被平均：GitHub 是供给侧（大家在做什么≠有人要），Reddit 才是需求侧原话，Product Hunt 是竞品情报。**同一方向出现在多个平台 = 信号更硬**。

**Hacker News（技术讨论）**　29 条
- 方向：AI 代理与自动化（11 条 / 平台内 38%）、监控与可观测（2 条 / 平台内 7%）、自托管与部署（2 条 / 平台内 7%）、终端与开发者效率（2 条 / 平台内 7%）
- 代表证据：[Proposal to prohibit vibe coded projects from being hosted on Sourcehu](https://news.ycombinator.com/item?id=49362340)
  > … code review model for that. Coding is just going to be asking for a result and manually testing it, no real thought about what code has been generat

**GitHub Search（供给侧·新增）**　27 条
- 方向：AI 代理与自动化（10 条 / 平台内 37%）、内容创作与分发（5 条 / 平台内 19%）、代码质量与 CI（2 条 / 平台内 7%）、视频与音频处理（2 条 / 平台内 7%）
- 代表证据：[totec448-spec/chat-on-steroids](https://github.com/totec448-spec/chat-on-steroids)
  > Cross-platform local MCP capabilities for ChatGPT with Chrome integration, Goal, Compact & Resume, and durable multi-agent workflows.

**GitHub Trending（供给侧·热度）**　7 条
- 方向：AI 代理与自动化（3 条 / 平台内 43%）、终端与开发者效率（2 条 / 平台内 29%）
- 代表证据：[jingyaogong/minimind](https://github.com/jingyaogong/minimind)
  > 

**Reddit（创始人社区·需求侧）**　2 条
- 方向：AI 代理与自动化（1 条 / 平台内 50%）
- 代表证据：[Rant: Stop building useless apps and products This sub and few adjacen](https://www.reddit.com/comments/1wgxzx9)
  > …all in. Do you have a teamspeak server I can join? > I'm sold. Just shut up and take my money > > ![gif](giphy|TdwziQPhbNAzK) \- pomodoro timer \- fa


---

## 跨窗口观察

**三个窗口都出现（持续需求，优先看）**：AI 代理与自动化、内容创作与分发、终端与开发者效率、视频与音频处理

- 今日：10 个方向 —— AI 代理与自动化、内容创作与分发、报表与可视化、支付与账单、数据采集与解析、文档与知识库、终端与开发者效率、获客与 SEO、视频与音频处理、集成与 API 网关
- 本周：10 个方向 —— AI 代理与自动化、代码质量与 CI、内容创作与分发、安全与合规、报表与可视化、文档与知识库、终端与开发者效率、育儿与生活服务、自托管与部署、视频与音频处理
- 本月：10 个方向 —— AI 代理与自动化、代码质量与 CI、内容创作与分发、安全与合规、文件与存储同步、电商与跨境、监控与可观测、终端与开发者效率、自托管与部署、视频与音频处理

> 只在单一窗口出现的，多是短期热点或话题波动；跨窗口反复出现的，才更接近可持续的需求。

## 机会象限汇总

以下方向在对应窗口同时满足「高热度 + 低拥挤」，是当前最值得先看的一批：

- **终端与开发者效率**　证据 8 条　存量项目 62　出现于 本周、本月
- **报表与可视化**　证据 7 条　存量项目 89　出现于 今日、本周
- **自托管与部署**　证据 7 条　存量项目 182　出现于 本周、本月
- **代码质量与 CI**　证据 6 条　存量项目 17　出现于 本周、本月
- **数据采集与解析**　证据 5 条　存量项目 49　出现于 今日
- **内容创作与分发**　证据 5 条　存量项目 35　出现于 本月
- **支付与账单**　证据 3 条　存量项目 37　出现于 今日
- **获客与 SEO**　证据 3 条　存量项目 22　出现于 今日
- **安全与合规**　证据 3 条　存量项目 198　出现于 本周
- **监控与可观测**　证据 3 条　存量项目 277　出现于 本月

> 注意：这只说明「当前信号下相对不拥挤」，不代表验证过需求。下一步仍是落地页/预售/冷启动外联的真实付费验证。

## 源健康与依赖对冲（P0-3）

**能力覆盖缺口 0%**（目标 <20%：✅ 达标）　·　**硬失败率 11%**（目标 <10%：❌ 未达标）

（能力 6 项：covered 5 · degraded 1 · lost 0｜**跳过 2 个已知不可用源**，跳过不计失败——所以「失败率低」必须与「跳过几个」一起读，单看失败率是粉饰）

> 口径：按**能力**而不是按源统计。一个源失败不等于能力缺失；唯一提供某能力的源挂了才是缺口。已知不可用的源（upwork/twitter）**跳过而不计入失败**——否则失败率被永久污染，真实退化会被掩盖。

| 能力 | 状态 | 主源可用 | 主源失败 | 等效源撑着 | 已知跳过 | 说明 |
|---|---|---|---|---|---|---|
| **开源供给（在做什么）** | ✅ 正常 | github_trending、github_search | — | — | — | 官方 API + 公开页面，无登录依赖 |
| **技术讨论与痛点原话** | ✅ 正常 | hn、lobsters、lesswrong | — | — | — | 全部免登录（HN Algolia 公开搜索 / Lobsters / DEV.to / LessWrong） |
| **付费需求（有人出钱做事）** | ✅ 正常 | indeed | — | github_bounty、reddit:forhire | upwork | 主源都要登录态且 upwork 100% 失败；等效源免登录且金额可核（赏金写在 issue 里） |
| **创始人原话与发声** | ✅ 正常 | reddit | — | bluesky:trending(弱) | twitter | reddit 有官方 RSS；twitter 需登录。bluesky 仅弱等效且实测内容是新闻榜（不能替代创始人原话），本条能力实际仍降级 |
| **中文需求信号** | ⚠️ 降级（仅等效源） | — | — | juejin:hot | — | xhs 需登录且常超时；juejin 免登录但偏技术（弱等效）；zhihu 主动排除（新闻榜零价值，见 EXCLUDED_BY_DESIGN） |
| **新发布产品（竞品情报）** | ✅ 正常 | producthunt | — | — | — | 仅有公开页面通道；无等效源（潜在单点） |

### 采集机制与合规登记

| 源 | 采集机制 | 合规风险 |
|---|---|---|
| github_trending | 官方公开页面 | 低 |
| github_search | 官方 API（未认证，有速率限制） | 低 |
| github_bounty | 官方 API 搜索（label:bounty，付费证据/非独立发现） | 低 |
| hn | Algolia 公开搜索 API / 官方页面 | 低 |
| lobsters | 公开页面 / 公开 API | 低 |
| devto | 公开 API | 低 |
| lesswrong | 公开 API | 低 |
| stackoverflow | 公开页面 | 低 |
| juejin:hot | 公开页面 | 低-中 |
| bluesky:trending | 公开 API（AT Protocol） | 低 |
| reddit | 官方 RSS（/r/x/.rss，个人研究用）+ 登录态读帖 | 中 |
| producthunt | 公开页面（登录态交互） | 中 |
| indeed | 浏览器登录态 + 页面渲染 | 中-高 |
| upwork | 浏览器登录态 | 中-高 |
| twitter | 浏览器登录态 | 中-高 |
| xiaohongshu | 浏览器登录态 | 中-高 |
| zhihu | 浏览器登录态 | 中-高 |

> 风险判读：官方 API/RSS = 低；登录态自动化 = 中-高（可能违反站点自动化条款，且有账号风险）。**GummySearch 的前车之鉴**：它是在盈利状态（$35K MRR）下被Reddit API 政策逼停的，说明「业务健康」保护不了「依赖单一平台」这一结构性风险。

> 已跳过（待恢复）：upwork——4；twitter——2


## 验证闭环（P0-2）

**北极星：近 7 天验证通过方向数 0 / 目标 ≥1　❌ 未达标**

（待续 0 个 · 否决 0 个 · 误杀复活 0 个 · 误杀率 —）

> 判定标准：**通过 = ≥2 个独立受访者已在为此付费或给出明确预算**。表达"有意思"不算证据。

> 记录方式：`python tools/validation.py log "<方向>" --result pass --intents 3 --note "..."`；待验证队列：`python tools/validation.py queue`。

### 验证包（可直接执行：去哪问 / 问什么 / 怎么判定 / 可复制脚本）

### 今日 待验证方向（4 个）

**报表与可视化**　建议档位：★ 建议优先验证　趋势：高

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）；reddit → 从证据帖反查它所在的 subreddit，再到该 sub 发帖；另看 r/SaaS 每周"what are you working on" 帖
- 先读这些原帖（含具体抱怨）：[Marcos66236/github-stars-history](https://github.com/Marcos66236/github-stars-history) · [devagrawal09/jev-review](https://github.com/devagrawal09/jev-review) · [[FOR HIRE] The Last Google Ads Guy Y](https://www.reddit.com/r/forhire/comments/1wj8p84/for_hire_the_last_google_ads_guy_youll_ever_hire/)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about Marcos66236/github-stars-history (https://github.com/Marcos66236/github-stars-history).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle Marcos66236/github-stars-history today?

I keep running into the same problem: Track and visualize the stars history of any GitHub repository. Open-source growth analytics and velocity tracking.

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于报表与可视化的帖子（https://github.com/Marcos66236/github-stars-history）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

**数据采集与解析**　建议档位：★ 建议优先验证　趋势：中

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）；lobsters → 该讨论帖的评论区（Lobsters 评论质量高，适合问技术细节）
- 先读这些原帖（含具体抱怨）：[justoneapi-labs/xiaohongshu-api](https://github.com/justoneapi-labs/xiaohongshu-api) · [Bartlett Distribution Services LLC 招](https://www.indeed.com/viewjob?jk=c6dd8c024ade7f41) · [INTERNATIONAL HIGHLIGHT LLC 招聘：data ](https://www.indeed.com/viewjob?jk=6417d71cb37e683c)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about justoneapi-labs/xiaohongshu-api (https://github.com/justoneapi-labs/xiaohongshu-api).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle justoneapi-labs/xiaohongshu-api today?

I keep running into the same problem: Frantic bounty #131: Run Ausca Document OCR end to end and report the process. Frantic bounty #131 Run Ausca Document OCR end to end and report the process Worker price: 

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于数据采集与解析的帖子（https://github.com/justoneapi-labs/xiaohongshu-api）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

**支付与账单**　建议档位：★ 建议优先验证　趋势：中

- **验证目标**：见建议结论中的付费方
- **去哪问**：reddit → 从证据帖反查它所在的 subreddit，再到该 sub 发帖；另看 r/SaaS 每周"what are you working on" 帖
- 先读这些原帖（含具体抱怨）：[Show HN: The bottom 50% of U.S. hous](https://news.ycombinator.com/item?id=49743608) · [First Monthly Subscription I am legi](https://www.reddit.com/comments/1wi88io) · [[FOR HIRE] Designer and illustrator ](https://www.reddit.com/r/forhire/comments/1wj22qz/for_hire_designer_and_illustrator_mascots_logos/)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about Show HN: The bottom 50% of U.S. households are short after essentials (BLS data) (https://news.ycombinator.com/item?id=49743608).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle Show HN: The bottom 50% of U.S. households are short after essentials (BLS data) today?

I keep running into the same problem: Fully agree he should not pay less tax % than his secretary, however I also would contend he should not pay more either. that is if his secretary is paying 20% so should 

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于支付与账单的帖子（https://news.ycombinator.com/item?id=49743608）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

**获客与 SEO**　建议档位：★ 建议优先验证　趋势：中

- **验证目标**：见建议结论中的付费方
- **去哪问**：reddit → 从证据帖反查它所在的 subreddit，再到该 sub 发帖；另看 r/SaaS 每周"what are you working on" 帖
- 先读这些原帖（含具体抱怨）：[[Hiring] Mid/Senior Ad Campaign Mana](https://www.reddit.com/r/forhire/comments/1wjdnj7/hiring_midsenior_ad_campaign_manager_user/) · [[FOR HIRE] Digital Marketing Support](https://www.reddit.com/r/forhire/comments/1wj5ohv/for_hire_digital_marketing_support_virtual/) · [[For Hire] Reliable Copywriter That ](https://www.reddit.com/r/forhire/comments/1wj3135/for_hire_reliable_copywriter_that_wont_break_the/)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about [Hiring] Mid/Senior Ad Campaign Manager (User Acquisition) - Remote (Brazil Market Focus) (https://www.reddit.com/r/forhire/comments/1wjdnj7/hiring_midsenior_ad_campaign_manager_user/).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle [Hiring] Mid/Senior Ad Campaign Manager (User Acquisition) - Remote (Brazil Market Focus) today?

I keep running into the same problem: [Hiring] Mid/Senior Ad Campaign Manager (User Acquisition) - Remote (Brazil Market Focus). We are looking for a Mid to Senior Ad Campaign / UA Manager to drive our growth

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于获客与 SEO的帖子（https://www.reddit.com/r/forhire/comments/1wjdnj7/hiring_midsenior_ad_campaign_manager_user/）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

### 本周 待验证方向（3 个）

**自托管与部署**　建议档位：★ 值得看，但需补付费证据　趋势：高

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）；github_trending → 相关仓库的 Issues / Discussions（找 workaround 与抱怨）
- 先读这些原帖（含具体抱怨）：[danieldeer/seriousdb](https://github.com/danieldeer/seriousdb) · [agentverse-os/AgentVerse-OS](https://github.com/agentverse-os/AgentVerse-OS) · [MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about danieldeer/seriousdb (https://github.com/danieldeer/seriousdb).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle danieldeer/seriousdb today?

I keep running into the same problem: A simple, yet effective persistent key-value database.

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于自托管与部署的帖子（https://github.com/danieldeer/seriousdb）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

**安全与合规**　建议档位：★ 值得看，但需补付费证据　趋势：中

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）
- 先读这些原帖（含具体抱怨）：[KazamaDono/taoxd](https://github.com/KazamaDono/taoxd) · [KillaBoi/BrokenPipe](https://github.com/KillaBoi/BrokenPipe) · [shinthink/blitzstrike](https://github.com/shinthink/blitzstrike)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about KazamaDono/taoxd (https://github.com/KazamaDono/taoxd).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle KazamaDono/taoxd today?

I keep running into the same problem: The Art of Exploit Development companion code.

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于安全与合规的帖子（https://github.com/KazamaDono/taoxd）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

**代码质量与 CI**　建议档位：★ 建议优先验证　趋势：高

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）
- 先读这些原帖（含具体抱怨）：[apple/xcode-project-format](https://github.com/apple/xcode-project-format) · [Qiuner/birdview](https://github.com/Qiuner/birdview) · [Bounty](https://github.com/OmniBlocks/Boxy-gh/issues/143)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about apple/xcode-project-format (https://github.com/apple/xcode-project-format).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle apple/xcode-project-format today?

I keep running into the same problem: A Swift library for reading, writing, and manipulating Xcode's JSON-based project.xcproj format.

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于代码质量与 CI的帖子（https://github.com/apple/xcode-project-format）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

### 本月 待验证方向（1 个）

**监控与可观测**　建议档位：★ 建议优先验证　趋势：中

- **验证目标**：见建议结论中的付费方
- **去哪问**：github_search → 同类项目的 Issues（尤其 labeled bug/feature-request）
- 先读这些原帖（含具体抱怨）：[vinzdg/codenotch](https://github.com/vinzdg/codenotch) · [One resignation turned the embers of](https://news.ycombinator.com/item?id=49647380) · [Show HN: Watches user sessions, find](https://news.ycombinator.com/item?id=49479539)
- **问什么**（五问，按顺序问，别跳）：
  1. [现状] 你们现在怎么处理这件事？用什么工具、还是纯手工？
  2. [痛感] 上一次因为它出问题是什么时候？造成什么后果？
  3. [已付费行为] 有没有为它花过钱（工具/外包/人力）？大概多少？
  4. [WTP] 如果有个东西能解决它，你愿意每月付多少？
  5. [决策链] 这类支出谁拍板？走什么流程？
- **怎么判定**：
  - 通过 = ≥2 个独立受访者已在为此付费，或给出明确预算
  - 待续 = 1 个受访者符合上述标准
  - 否决 = 0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）
- **样本与时间盒**：5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）

<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>

```text
Hi <对方名字> — I saw your post about vinzdg/codenotch (https://github.com/vinzdg/codenotch).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!
```

```text
Ask HN: How do you handle vinzdg/codenotch today?

I keep running into the same problem: A macOS app that pins usage limits from Claude Code, Cursor, Codex, and Antigravity to a screen edge.

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread.
```

```text
你好，我看到你关于监控与可观测的帖子（https://github.com/vinzdg/codenotch）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！
```

</details>

## 信源健康

| 信源 | 条数 | 状态 | 备注 |
|---|---:|---|---|
| github_trending:daily | 20 | ✅ |  |
| github_search:3d | 50 | ✅ |  |
| hn:3d | 133 | ✅ |  |
| opencli:upwork[automation scrip] | 0 | ⏭ 跳过 | 适配器侧故障（多次 exitCode 1，与站点改版有关）→ 已由 github_bounty + r/forhire 覆盖 |
| opencli:upwork[web scraping too] | 0 | ⏭ 跳过 | 适配器侧故障（多次 exitCode 1，与站点改版有关）→ 已由 github_bounty + r/forhire 覆盖 |
| opencli:twitter["is there a tool" la] | 0 | ⏭ 跳过 | 需在 Chrome 登录 X 后可用 → 登录即恢复，当前由 bluesky:trending 弱覆盖 |
| opencli:reddit:deep:r/SaaS | 3 | ✅ | r/SaaS: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/microsaas | 3 | ✅ | r/microsaas: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/SideProject | 3 | ✅ | r/SideProject: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:github_bounties[bounty] | 40 | ✅ | 开放赏金 40 条（免登录，付费证据/非独立发现） |
| reddit:forhire | 25 | ✅ | 1 个子版块 |
| opencli:juejin:hot | 20 | ✅ | 免登录弱等效（中文技术热榜，非消费社区） |
| opencli:bluesky:trending | 10 | ✅ | 免登录弱等效（仅热门话题，不可按关键词搜；内容偏新闻，价值低） |
| opencli:producthunt | 20 | ✅ |  |
| opencli:hn:show | 25 | ✅ |  |
| opencli:hn:ask | 15 | ✅ |  |
| opencli:stackoverflow#api | 0 | ❌ | 返回空结果 |
| opencli:stackoverflow#automation | 2 | ✅ |  |
| opencli:lobsters#ai | 15 | ✅ |  |
| opencli:lobsters#devops | 15 | ✅ |  |
| opencli:devto#webdev | 15 | ✅ |  |
| opencli:devto#ai | 15 | ✅ |  |
| opencli:lesswrong | 10 | ✅ |  |
| opencli:hn:deep:show | 2 | ✅ | hn/show: 列表 25 条 → 深读 2 帖 |
| opencli:lobsters:deep | 2 | ✅ | 热帖 25 条 → 深读 2 帖 |
| opencli:stackoverflow:deep:#automation | 2 | ✅ | #automation 2 条 → 深读 2 帖 |
| opencli:indeed[automation] | 15 | ✅ |  |
| opencli:indeed[data scraping] | 15 | ✅ |  |
| opencli:xhs[效率工具] | 0 | ❌ |   exitCode: 75 |
| opencli:xhs[自动化办公] | 0 | ❌ |   exitCode: 75 |
| opencli:zhihu | 15 | ✅ |  |
| github_trending:weekly | 21 | ✅ |  |
| github_search:7d | 50 | ✅ |  |
| hn:7d | 142 | ✅ |  |
| opencli:upwork[automation scrip] | 0 | ⏭ 跳过 | 适配器侧故障（多次 exitCode 1，与站点改版有关）→ 已由 github_bounty + r/forhire 覆盖 |
| opencli:upwork[web scraping too] | 0 | ⏭ 跳过 | 适配器侧故障（多次 exitCode 1，与站点改版有关）→ 已由 github_bounty + r/forhire 覆盖 |
| opencli:twitter["is there a tool" la] | 0 | ⏭ 跳过 | 需在 Chrome 登录 X 后可用 → 登录即恢复，当前由 bluesky:trending 弱覆盖 |
| opencli:reddit:deep:r/SaaS | 3 | ✅ | r/SaaS: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/microsaas | 3 | ✅ | r/microsaas: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/SideProject | 3 | ✅ | r/SideProject: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:github_bounties[bounty] | 40 | ✅ | 开放赏金 40 条（免登录，付费证据/非独立发现） |
| reddit:forhire | 25 | ✅ | 1 个子版块 |
| opencli:indeed[automation] | 15 | ✅ |  |
| opencli:indeed[data scraping] | 15 | ✅ |  |
| opencli:xhs[效率工具] | 0 | ❌ |   exitCode: 75 |
| opencli:xhs[自动化办公] | 0 | ❌ |   exitCode: 75 |
| opencli:zhihu | 15 | ✅ |  |
| github_trending:monthly | 22 | ✅ |  |
| github_search:30d | 50 | ✅ |  |
| hn:30d | 172 | ✅ |  |
| opencli:reddit:deep:r/SaaS | 3 | ✅ | r/SaaS: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/microsaas | 3 | ✅ | r/microsaas: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
| opencli:reddit:deep:r/SideProject | 3 | ✅ | r/SideProject: 列表 25 条 → 深读 3 帖（评论门槛 ≥5） |
