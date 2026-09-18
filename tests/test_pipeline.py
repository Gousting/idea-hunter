# -*- coding: utf-8 -*-
"""离线单元测试 —— 纯标准库，不联网、不依赖上一轮产物。

为什么必须有（P1-7）：
原仓库没有任何 tests/，也没有 CI。tools/acceptance.py 依赖上一轮产出
（全新 clone 后直接跑会打印"缺少产出文件"），tools/eval_gates.py 依赖网络。
结果是**只有跑起来才会暴露的 bug** 全靠人肉发现 —— 而本仓库已经出过好几起这类
（"等效源采到了但一条没用上"、"假共振"、以及本次修的 forhire 供需倒置）。

每条测试都对应一次真实修复，注释里写明"不修会怎样"，避免以后被人当成冗余删掉。

用法：
    python -m unittest discover -s tests -v
    python tests/test_pipeline.py
"""
import os
import re
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from hunter import filter as flt            # noqa: E402
from hunter import paths as ph              # noqa: E402
import run_windows as rw                    # noqa: E402

CFG = {"min_stars": 60, "min_text_len": 120}


def _forhire(sid, title, body_extra=""):
    """构造一条 r/forhire 记录（source/subreddit 与 sources.reddit_rss 产出一致）。"""
    return {"source": "reddit", "source_id": sid, "repo": "", "url": "https://x/" + sid,
            "title": title, "text": f"{title}. {body_extra}" + "x" * 160,
            "subreddit": "forhire", "created_at": "2026-09-18"}


class TestForhireDemandVsSupply(unittest.TestCase):
    """P0-1：r/forhire 的 [Hiring]（需求方）与 [For Hire]（供给方）必须分开判。

    不修会怎样：供给方广告被记为 record_type="hiring" → 计入"付费证据" →
    触发 advice.verdict_of 的「★ 建议优先验证」档。已发布报告里 9 条 forhire 帖
    有 7 条是自由职业者自我推销，把「报表与可视化」「视频与音频处理」推上了推荐位。
    """

    def test_hiring_is_kept_as_paid_evidence(self):
        r = _forhire("reddit:t3_a", "[Hiring] Need a Python automation script")
        kept, _ = flt.rule_filter([r], CFG)
        self.assertEqual(len(kept), 1, "雇主招人帖是真需求，不应被丢")
        self.assertEqual(kept[0]["record_type"], "hiring")

    def test_for_hire_ad_is_dropped_as_supply(self):
        r = _forhire("reddit:t3_b", "[For Hire] The Last Google Ads Guy You'll Ever Hire",
                     "For over 8 years I have worked with brands managing Ad Budgets.")
        kept, dropped = flt.rule_filter([r], CFG)
        self.assertEqual(kept, [], "自由职业者自我推销是供给方，必须丢弃")
        self.assertEqual(len(dropped), 1)
        self.assertIn("供给方广告", dropped[0]["drop_reason"])

    def test_for_hire_variants(self):
        """大小写与常见变体都要挡住。"""
        for title in ("[FOR HIRE] Video editor available",
                      "[For Hire] Affordable Photo & Video Editing",
                      "[Available] Copywriter for SaaS"):
            kept, _ = flt.rule_filter([_forhire("reddit:x", title,
                                                "my rates are $20/h, dm me")], CFG)
            self.assertEqual(kept, [], f"{title!r} 应被判为供给方广告")

    def test_supply_ad_does_not_inflate_paid_evidence(self):
        """端到端：供给方广告不得进入 aggregate 的 hiring 计数。"""
        from hunter import directions as dr
        kept, _ = flt.rule_filter([
            _forhire("reddit:t3_a", "[Hiring] Need a Python automation script"),
            _forhire("reddit:t3_b", "[For Hire] The Last Google Ads Guy You'll Ever Hire"),
        ], CFG)
        stat = dr.aggregate(kept)
        hiring = sum(s["hiring"] for s in stat.values())
        self.assertEqual(hiring, 1, "两条里只有 [Hiring] 那一条算出钱证据")


class TestPathsConservativeDefault(unittest.TestCase):
    """P0-2：paths.infer 的兜底必须取保守侧。

    不修会怎样：兜底是 PLATFORM（原生榜=真独立发现），任何新接入、忘了写 path
    的信源都白拿"原生"身份，直接抬高「原生榜贡献率 ≥40%」这个头条验收指标 ——
    指标可以自证达标。
    """

    def test_unknown_source_is_keyword(self):
        self.assertEqual(ph.infer({"source": "brand_new_platform"}), ph.KEYWORD)
        self.assertFalse(ph.is_native({"source": "brand_new_platform"}))

    def test_explicit_path_wins(self):
        self.assertEqual(
            ph.infer({"source": "brand_new_platform", "path": ph.PLATFORM}),
            ph.PLATFORM)

    def test_registry_is_respected(self):
        self.assertEqual(ph.infer({"source": "github_trending"}), ph.PLATFORM)
        self.assertEqual(ph.infer({"source": "github_issue"}), ph.KEYWORD)

    def test_hn_query_vs_hotlist(self):
        self.assertEqual(ph.infer({"source": "hn", "query": "willing to pay"}), ph.KEYWORD)
        self.assertEqual(ph.infer({"source": "hn"}), ph.PLATFORM)

    def test_weak_native_is_flagged(self):
        """弱原生（门槛由作者设定）必须能被单独标出来，否则原生率会被读得过硬。"""
        for src in ("github_search", "reddit", "browser"):
            self.assertTrue(ph.is_weak_native({"source": src}), src)
        self.assertFalse(ph.is_weak_native({"source": "github_trending"}))

    def test_undeclared_is_reported(self):
        recs = [{"source": "brand_new_platform"}, {"source": "brand_new_platform"},
                {"source": "github_trending"}]
        self.assertEqual(ph.undeclared(recs), {"brand_new_platform": 2})

    def test_breakdown_sums_to_total(self):
        recs = [{"source": "github_search"}, {"source": "github_trending"},
                {"source": "hn", "query": "x"}]
        b = ph.breakdown(recs)
        self.assertEqual(sum(x["native"] + x["keyword"] for x in b), len(recs))
        n, k, rate = ph.counts(recs)
        self.assertAlmostEqual(rate, n / (n + k))


class TestClassifyModeHonesty(unittest.TestCase):
    """P0-4：判定方式必须按**实际命中率**标注。

    不修会怎样：classify_mode 只看"有没有传 --annotations"，传一个空的 {} 也会
    声称"agent-语义分类（Claude 直读原文）"，而榜单实际 100% 来自关键词签名。
    已实测：同一次运行的看板写"关键词签名（含部分 agent 语义标注）"，
    报告写"agent-语义分类" —— 两份产出互相矛盾。
    """

    def test_no_annotations_means_keyword(self):
        self.assertEqual(rw._classify_mode({}, 0, 100), "关键词签名")

    def test_low_hit_rate_is_partial(self):
        self.assertEqual(rw._classify_mode({"k": 1}, 24, 188), rw.MODE_PARTIAL)

    def test_high_hit_rate_is_agent(self):
        self.assertEqual(rw._classify_mode({"k": 1}, 60, 100), rw.MODE_AGENT)

    def test_zero_kept_is_not_overclaimed(self):
        self.assertNotEqual(rw._classify_mode({"k": 1}, 0, 0), rw.MODE_AGENT)

    def test_zero_hit_rate_is_labelled_stale(self):
        """传了标注文件但零命中（实测常态：标注按 source_id 绑定，重跑一次采集
        记录集就变了）—— 必须说清是"过期"，不能含糊成"含部分语义标注"。"""
        mode = rw._classify_mode({"k": 1}, 0, 53)
        self.assertIn("过期", mode)
        self.assertNotEqual(mode, rw.MODE_PARTIAL)

    def test_semantic_branch_recognises_agent_mode(self):
        """回归：原实现用 `if "llm" in classify_mode` 判断，而 MODE_AGENT 不含 "llm"，
        于是报告会同时输出"用了 agent 语义分类"和"关键词模式签名宽度不等"两句
        互相矛盾的话。"""
        self.assertTrue(rw._is_semantic(rw.MODE_AGENT))
        self.assertTrue(rw._is_semantic("llm-语义分类"))
        self.assertFalse(rw._is_semantic(rw.MODE_PARTIAL))
        self.assertFalse(rw._is_semantic("关键词签名"))

    def test_coverage_line_discloses_ratio(self):
        line = rw._coverage_line(22, 54)
        self.assertIn("41%", line)
        self.assertIn("22 / 54", line)
        self.assertEqual(rw._coverage_line(0, 0), "")

    def test_coverage_line_hidden_when_annotations_not_used(self):
        """没传 --annotations 时不该显示"语义标注覆盖 0/N" —— 那会让人误以为
        语义分类跑过但失败了。"""
        self.assertEqual(rw._coverage_line(0, 53, ann_used=False), "")
        self.assertNotEqual(rw._coverage_line(0, 53, ann_used=True), "")


class TestReportIsDataDriven(unittest.TestCase):
    """P0-3 / P1-4：报告里的声明必须由数据生成，链接必须可点击。"""

    def _results(self):
        rec = {"source": "hn", "title": "t", "text": "x" * 200, "url": "https://a",
               "strong_wtp_hits": [], "pain_hits": []}
        row = {"name": "测试方向", "evidence": 3, "hot": 1, "score": 4.0,
               "sources": ["hn"], "native_sources": [], "keyword_sources": ["hn"],
               "resonance": 0, "heat": 0, "wtp_total": 0, "items": [rec],
               "repos": [], "velocity": 0.0,
               "evidence_links": [{"title": "证据帖", "url": "https://b", "source": "hn"}],
               "mature": [{"repo": "o/r", "url": "https://github.com/o/r",
                           "stars": 123, "updated": "2026-09-18"}]}
        return {"day": {"label": "今日", "raw": 100, "kept": 3, "stat": {"测试方向": row},
                        "rows": [row], "records": [rec], "path_stats": (2, 1, 0.667),
                        "native_breakdown": [{"source": "hn", "native": 2,
                                              "keyword": 1, "weak": 0}],
                        "undeclared": {}, "native_fail": []}}

    def _render(self, **kw):
        vstats = {"window_days": 7, "north_star": 0, "target": 1, "pending": [],
                  "rejected": [], "resurrected": [], "mistake_rate": None}
        return rw.render(self._results(), [], types.SimpleNamespace(),
                         kw.pop("classify_mode", "关键词签名"),
                         vstats=vstats, **kw)

    def test_no_stale_hardcoded_caliber_warning(self):
        """原实现硬编码了"本周榜第一的 8 条证据 = 4 条 HN + 2 个 GitHub 仓库…"，
        跑今日窗口时也照样输出 —— 与本轮数据无关。"""
        out = self._render()
        self.assertNotIn("本周榜第一的", out)
        self.assertIn("本窗口榜第一的", out)

    def test_evidence_composition_is_computed(self):
        comp = rw._evidence_composition(self._results()["day"]["rows"])
        self.assertEqual(comp["name"], "测试方向")
        self.assertEqual(comp["evidence"], 3)
        self.assertIn("hn", comp["parts"])
        self.assertIsNone(rw._evidence_composition([]))

    def test_north_star_is_above_the_ranking(self):
        """北极星是全局最重要的状态，必须在报告开头而不是藏在末尾章节。"""
        out = self._render()
        self.assertLess(out.index("北极星"), out.index("判定口径"))

    def test_case_links_are_ascii_closed(self):
        """原实现用全角 `）` 收尾，Markdown 不认 → 报告里 30 处"成熟/高关注项目"
        链接全部不可点击，而那正是"真实案例速查"章节存在的唯一理由。"""
        from hunter import directions as dr
        lines = dr.render_cases(self._results()["day"]["rows"][0], 1)
        joined = "\n".join(lines)
        self.assertNotIn("）（", joined)
        self.assertIn("](https://github.com/o/r)", joined)
        self.assertRegex(joined, r"\]\(https://github\.com/o/r\)")

    def test_coverage_and_breakdown_are_disclosed(self):
        out = self._render(ann_hit=22, kept_total=54, ann_used=True)
        self.assertIn("22 / 54", out)
        self.assertIn("原生率的信源明细", out)

    def test_no_coverage_line_without_annotations(self):
        out = self._render()
        self.assertNotIn("语义标注实际覆盖", out)


class TestSupplyRisk(unittest.TestCase):
    """L2 反刷星阈值（判断层现在也复用这套判据，见 P0-5）。"""

    def _rec(self, **kw):
        base = {"source": "github_search", "stars_total": 1000, "forks": 200,
                "stars_window": 1000, "created_at": "2026-09-01", "license": "MIT",
                "open_issues": 10}
        base.update(kw)
        return base

    def test_healthy_repo_has_no_flags(self):
        lvl, flags = flt.supply_risk(self._rec())
        self.assertEqual(lvl, "low")
        self.assertEqual(flags, [])

    def test_low_fork_ratio_is_flagged(self):
        _, flags = flt.supply_risk(self._rec(forks=40))
        self.assertTrue(any("低于 0.05" in f for f in flags))

    def test_star_velocity_is_flagged(self):
        _, flags = flt.supply_risk(self._rec(stars_total=3000,
                                             created_at="2026-09-16"))
        self.assertTrue(any("日均涨星" in f for f in flags))

    def test_two_flags_means_high_and_gets_dropped(self):
        """≥2 个 flag 判 high → rule_filter 直接丢弃。判断层必须用同一判据。"""
        rec = self._rec(stars_total=3564, forks=214, created_at="2026-09-16")
        lvl, flags = flt.supply_risk(rec)
        self.assertEqual(lvl, "high")
        self.assertGreaterEqual(len(flags), 2)

    def test_gpl_license_is_flagged(self):
        _, flags = flt.supply_risk(self._rec(license="AGPL-3.0"))
        self.assertTrue(any("强传染" in f for f in flags))


class TestAnalysisRiskGuard(unittest.TestCase):
    """P0-5：判断层必须复用 L2 判据，不能绕过。"""

    def test_github_url_parsing(self):
        import write_platform_analysis as wpa
        got = wpa._gh_repos([
            "https://github.com/browser-use/jev-ultrafast",
            "https://github.com/o/r/issues/3",
            "https://github.com/browser-use/jev-ultrafast",   # 重复
            "https://www.reddit.com/r/SaaS/comments/x/y/",     # 非 GitHub
        ])
        self.assertEqual(got, ["browser-use/jev-ultrafast", "o/r"])

    def test_attach_risks_marks_high_risk(self):
        import write_platform_analysis as wpa
        orig = wpa.repo_risks
        try:
            wpa.repo_risks = lambda urls: [
                {"repo": "o/r", "level": "high", "flags": ["日均涨星 1314"],
                 "stars": 3564, "created_at": "2026-09-16"}]
            items = [{"title": "最强爆发信号", "urls": ["https://github.com/o/r"]}]
            high, unknown = wpa.attach_risks(items)
            self.assertEqual(len(high), 1)
            self.assertEqual(unknown, 0)
            self.assertIn("repo_risks", items[0])
        finally:
            wpa.repo_risks = orig

    def test_attach_risks_silent_when_clean(self):
        import write_platform_analysis as wpa
        orig = wpa.repo_risks
        try:
            wpa.repo_risks = lambda urls: [{"repo": "o/r", "level": "low", "flags": []}]
            items = [{"title": "t", "urls": ["https://github.com/o/r"]}]
            high, _ = wpa.attach_risks(items)
            self.assertEqual(high, [])
        finally:
            wpa.repo_risks = orig


class TestEvalGatesQueries(unittest.TestCase):
    """实验脚本自己的查询必须符合它自己写下的教训（短词扇出，不要长句）。

    真正的判据是**实测召回**（联网才能验），这里做的是离线能做的部分：
    ① 不得再用已实测归零的那几条长句；② 词数控制在短查询范围。
    实测对照（2026-09-18，365 天窗口 / 100 条上限，"可用条数"= 去 HTML 后 ≥120 字符）：
        "invoice reconciliation tool too manual"   → 命中 0   可用 0
        "self-hosted monitoring setup too complex" → 命中 0   可用 0
        "no web interface command line only"       → 命中 6   可用 6
        "reconciliation manual"                    → 命中 34  可用 34
        "self-hosted complex"                      → 命中 141 可用 98
        "command line only"                        → 命中 827 可用 100
        "too complex to set up"                    → 命中 306 可用 100
    """

    # 已实测召回归零/接近归零的查询 —— 不得再出现在实验里
    DEAD_QUERIES = {
        "invoice reconciliation tool too manual",
        "self-hosted monitoring setup too complex",
    }

    def test_no_dead_queries(self):
        import eval_gates as eg
        for q in eg.QUERIES_GENERIC + eg.QUERIES_VERTICAL:
            self.assertNotIn(q, self.DEAD_QUERIES,
                             f"{q!r} 已实测命中 0 条，用它等于让这一臂失效")

    def test_queries_are_short(self):
        import eval_gates as eg
        for q in eg.QUERIES_VERTICAL:
            self.assertLessEqual(len(q.split()), 5,
                                 f"{q!r} 词数过多 —— HN Algolia 多词是 AND 语义，"
                                 "长句召回会塌成 0（实测已踩过）")

    def test_both_arms_non_empty(self):
        import eval_gates as eg
        self.assertTrue(eg.QUERIES_GENERIC)
        self.assertTrue(eg.QUERIES_VERTICAL)


class TestModeModuleShared(unittest.TestCase):
    """判定方式的口径必须**只有一份实现**（hunter/mode.py）。

    不修会怎样：这份逻辑曾在 run_windows.py 与 tools/render_dashboard.py 各写一份，
    直接导致同一次运行的两份产出互相矛盾（看板说"含部分 agent 语义标注"、
    报告说"agent-语义分类"）。第一次修复时我把逻辑从看板**搬**进报告 ——
    那仍然是一式两份，边界很快又分叉：报告修好了"零命中要说过期"，
    看板仍在 0% 覆盖时说"含部分语义标注"。
    正确做法是**抽出来共享**，而不是各写一份看起来一样的实现。
    """

    def test_report_uses_the_shared_module(self):
        from hunter import mode as md
        self.assertIs(rw._classify_mode, md.classify_mode)
        self.assertIs(rw._is_semantic, md.is_semantic)
        self.assertIs(rw._coverage_line, md.coverage_line)

    def test_dashboard_does_not_reimplement_threshold(self):
        """看板必须 import 共享模块，不得再内联一套阈值判断。"""
        with open(os.path.join(ROOT, "tools", "render_dashboard.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("hunter import mode", src)
        self.assertNotIn("kept_n * 0.5", src)

    def test_all_modes_distinct(self):
        from hunter import mode as md
        modes = {md.MODE_KEYWORD, md.MODE_AGENT, md.MODE_PARTIAL,
                 md.MODE_STALE, md.MODE_NO_RECORDS}
        self.assertEqual(len(modes), 5)
        self.assertFalse(md.is_semantic(md.MODE_STALE))
        self.assertFalse(md.is_semantic(md.MODE_KEYWORD))

    def test_report_json_records_classify(self):
        """报告 JSON 必须落盘判定方式 —— 否则看板只能自己猜，两份产出必然可能不一致。"""
        with open(os.path.join(ROOT, "run_windows.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"classify"', src)
        self.assertIn('"ann_used"', src)

    def test_dashboard_trusts_recorded_mode(self):
        """看板要"描述这次运行"，不是"重新决定"：优先读 JSON 里的 classify。"""
        with open(os.path.join(ROOT, "tools", "render_dashboard.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('rep_meta.get("mode")', src)


class TestPrivacyMinimalCollection(unittest.TestCase):
    """登录态复制只取维持登录所需的最小文件集。"""

    def test_login_data_is_not_copied(self):
        """原先还复制 `Default\\Login Data`（保存的密码库）。维持会话登录**不需要**它
        —— 登录态在 Cookies 里。多复制一个凭据库没有收益、只有风险。"""
        from hunter import browser
        joined = " ".join(browser.LOGIN_FILES).lower()
        self.assertNotIn("login data", joined)
        self.assertIn("cookies", joined)
        self.assertIn("local state", joined)

    def test_cookies_path_is_chrome96_plus(self):
        from hunter import browser
        joined = " ".join(browser.LOGIN_FILES)
        self.assertIn(r"Network\Cookies", joined)


class TestVerdictWordingMatchesCriteria(unittest.TestCase):
    """结论标签不得超出判据能支撑的范围。"""

    def _row(self, **kw):
        row = {"name": "x", "evidence": 3, "market_repos": 50, "crowd": "稀疏",
               "wtp_total": 0, "hiring": 0, "sources": ["hn", "reddit"],
               "heat": 500, "mature_products": 0}
        row.update(kw)
        return row

    def test_verdict_does_not_say_market_blank(self):
        """`mature_products == 0` 来自 github_mature_count（只统计 GitHub stars>1000 的
        **开源**项目），闭源商业 SaaS 不在视野内，且该数字还受关键词选择影响。
        把 0 读成"市场空白"是双重过度解读 —— 标签必须跟着判据走。

        断言用**行为**而不是源码文本：源码注释里会引用旧措辞做说明，
        按文本断言会把解释性注释也判成违规（已踩过）。
        """
        from hunter import advice
        verdict, level, _, _ = advice.verdict_of(self._row())
        self.assertNotIn("市场空白", verdict)
        self.assertIn("开源", verdict)
        self.assertEqual(level, 5, "档位不变，只是措辞改准确")

    def test_limitation_is_disclosed_inline(self):
        """局限必须写在**理由**里，不能只留在文档里 —— 读者看的是理由。"""
        from hunter import advice
        _, _, reasons, action = advice.verdict_of(self._row())
        self.assertTrue(any("只看开源" in r or "闭源" in r for r in reasons))
        self.assertIn("闭源", action)


class TestDashboardRendersModeHonestly(unittest.TestCase):
    """看板是 INDEX.md 里的第 1 优先级产出，判定方式与覆盖率必须在它上面也看得到。

    不修会怎样：我把 mode_coverage 放进了看板数据，但模板里只有 __MODE__、
    没有渲染覆盖率 —— 于是"披露覆盖率"这件事只在报告里成立，看板上仍然是
    一个没有覆盖率的判定方式声明。
    """

    def _tpl(self):
        with open(os.path.join(ROOT, "tools", "dashboard_template.html"),
                  encoding="utf-8") as f:
            return f.read()

    def _renderer(self):
        with open(os.path.join(ROOT, "tools", "render_dashboard.py"),
                  encoding="utf-8") as f:
            return f.read()

    def test_template_shows_coverage(self):
        tpl = self._tpl()
        self.assertIn('id="modecov"', tpl)
        self.assertIn("DATA.mode_coverage", tpl)

    def test_mode_is_injected_as_text_not_json(self):
        """__MODE__ 是**文本**注入。原实现用 json.dumps，页面上会多渲染一对字面引号：
        方向判定："关键词签名（…）"。"""
        src = self._renderer()
        self.assertIn('html.escape(data["mode"])', src)
        self.assertNotIn('__MODE__", json.dumps', src)

    def test_no_local_shadowing_of_html_module(self):
        """踩过的坑：render_dashboard 里用局部变量 `html` 存页面内容，遮蔽了模块级
        `import html`，导致 html.escape 抛 UnboundLocalError。局部变量已改名 page。"""
        src = self._renderer()
        self.assertNotIn("    html = (load_template()", src)
        self.assertIn("page = (load_template()", src)

    def test_template_discloses_that_it_does_not_re_decide(self):
        """看板必须说明它只显示上游落盘的判定方式，不自行判定。"""
        self.assertIn("不重新判定", self._tpl())


class TestDualCaliberIsLabelled(unittest.TestCase):
    """「强度」与「机会」用的基数不同，报告必须写明，否则同一行的组合看起来自相矛盾。"""

    def test_both_calibers_are_stated_explicitly(self):
        with open(os.path.join(ROOT, "hunter", "directions.py"),
                  encoding="utf-8") as f:
            src = f.read()
        self.assertIn("仅需求证据", src, "机会象限要写明它不含热点")
        self.assertIn("需求证据+热点合计", src, "强度列要写明它的基数")
        self.assertIn("不是矛盾", src, "要说明两列基数不同属口径差异")


if __name__ == "__main__":
    unittest.main(verbosity=2)
