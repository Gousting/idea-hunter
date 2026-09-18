# 产出索引（idea-hunter）

> 找不到产出时先看这里。`out/` 里累积了多轮次的带时间戳文件，
> **要看当前结果请用 `latest_*`**（每次跑完流水线会自动刷新）。

生成时间：2026-09-18 16:13　·　数据窗口：今日 / 本周 / 本月

---

## 一、先看这三份（按优先级）

| 文件 | 是什么 | 回答什么问题 |
|---|---|---|
| **`out/latest_dashboard.html`** | 可视化看板（单文件，1.1MB，**双击可离线打开**） | 一眼看全部：判断层 → 验证闭环 → 系统健康 → 方向榜单 → 平台热榜 |
| **`out/latest_directions.md`** | 方向报告（三窗口 Top10 + 建议 + 真实案例 + 验证包） | 该看哪个方向、为什么、去哪验证 |
| **`out/latest_analysis.md`** | 热榜付费潜力判断（16 条，A/B/C 分级） | 这些热点里有没有值得做的 |

### 看板的分区顺序（就是阅读顺序）

1. **热榜内容的付费潜力分析** —— 判断层，最高优先（A 级展开四问，C 级折叠成排除清单）
2. **验证闭环** —— 北极星指标 + 待验证队列 + 可执行验证包
3. **源健康与依赖对冲** —— 能力覆盖矩阵 + 合规登记
4. **方向榜单** —— 今日 / 本周 / 本月三个页签
5. **平台热榜** —— 12 个平台各自的热榜（不做门槛、不归类）

---

## 二、按用途查

| 我想… | 看这个 |
|---|---|
| 快速扫一眼今天值不值得关注 | `out/latest_dashboard.html`（首屏就是判断层） |
| 看某个方向的证据、存量、拥挤度、真实项目链接 | `out/latest_directions.md` → 对应窗口的 Top10 表 |
| 知道下一步该做什么验证 | `out/latest_directions.md` → 「验证闭环」章节；或 `python tools/validation.py queue` |
| 看各平台自己在热什么 | `out/latest_platforms.md` |
| 复核系统本身健不健康 | `out/resilience.json`；或 `python tools/acceptance.py` |
| 接入更多数据后要看原始记录 | `out/window_cache_<时间>.json`（规则层留存记录全量） |

---

## 三、机器可读的数据（给脚本/后续处理用）

| 文件 | 内容 |
|---|---|
| `out/latest_directions.json` | 三窗口方向统计（证据/热点/共振原生成分/存量/成型数/建议/趋势/案例链接） |
| `out/platform_analysis.json` | 判断层 16 条（含四问与结论） |
| `out/resilience.json` | 能力覆盖矩阵、失败率、跳过清单、合规登记 |
| `out/validation_kits.json` | 验证包（去哪问/问什么/怎么判定/脚本）+ 北极星 + 待验证队列 |
| `out/agent_annotations.json` | agent 语义分类标注（source_id → 方向/付费强度/痛点） |
| `out/window_cache_<时间>.json` | 规则层留存记录（含 path=原生榜/关键词、record_type、heat） |
| `out/.gh_cache.json` | GitHub 查询缓存（限流兜底用，**不要提交到 git**） |

---

## 四、怎么重新生成

```bash
cd idea-hunter

# 需求轨道（14 源 + GitHub，约 15-17 分钟）
python run_windows.py --opencli --windows day,week,month

# 平台轨道（12 平台热榜，约 50 秒）
python run_platforms.py --limit 15

# 看板
python tools/render_dashboard.py

# 判断层（agent 直读热榜后写判断；改完判断内容要跑这两步）
python tools/write_platform_analysis.py && python tools/render_analysis.py

# 验收总检（P0-1/P0-2/P0-3/P0-3b 一次全查，不达标直接 ❌）
python tools/acceptance.py
```

刷新 `latest_*` 稳定命名：跑完上面后执行一次 `python tools/make_latest.py`

---

## 五、当前验收状态（`tools/acceptance.py` 实测）

| 项 | 标准 | 实测 | |
|---|---|---|---|
| P0-1 原生榜贡献率 | ≥40% | 今日 74% / 本周 57% / 本月 55% | 达标 |
| P0-2 北极星（近 7 天验证通过方向数） | ≥1 | **0** | **未达标（需人工访谈）** |
| P0-3 能力覆盖缺口 | <20% | 0% | 达标 |
| P0-3 硬失败率 | <10% | **11%** | **未达标（xhs 超时 ×4）** |
| P0-3b 等效源边际贡献 | ≥1 条 | 4/4 | 达标 |

---

## 六、口径与已知局限（读结论前必须知道）

1. **证据分两条通道**：需求证据（过痛点/付费构式门槛）、平台热点证据（原生榜 + 热度达标）。
   **共振只统计原生榜**——关键词检索命中是同一个查询在多个平台的回声，不算独立发现。
2. **热度不可跨平台比较**。各站量纲不同（知乎是平台热度、HN 是点数、Product Hunt 与 Bluesky 是排名代理），
   **只比排名不比数值**。
3. **成型产品数只看开源**（GitHub stars>1000）。闭源商业 SaaS 看不到，
   所以 `0` 只等于「开源侧没人做成」，不等于「市场空白」。
4. **方向归类漏检**：关键词签名漏约 46%，叠加 agent 语义标注后仍漏约 25%；
   剩下的缺口主要是**分类表覆盖不足**（新品类不在 28 类里）。
5. **中文热榜（知乎）已主动排除**：实测是新闻/社会话题榜，对软件选品零价值。
   Bluesky 同理（新闻榜）。要中文**技术**信号看掘金，要中文**消费**需求需用搜索类通道。
6. **`record_type=hiring/bounty` 的记录是「有人出钱」的付费证据**，
   不代表对应方向的软件需求（招聘帖不得归入「招聘与 HR」，已在代码里强制）。
