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


class TestLeadExtraction(unittest.TestCase):
    """tools/leads.py：把线索保留为「个体」，回答"现在能接哪个活"。

    样本用的是**实测抓到的真实原文**（知乎搜索"有偿找人做脚本"），不是构造的。
    这批真实数据里第 2 条就是供给方 —— 正好验证过滤器有没有用。
    """

    # (source, title, text, 期望 verdict, 期望 supply_side)
    CASES = [
        ("zhihu", "有偿寻找一个代写游戏脚本的程序员",
         "有偿寻找一个代写游戏脚本的程序员 预算 3000 元左右，需要能写按键精灵或者 python 脚本，有意者私信",
         "值得联系", False),
        ("zhihu", "个人纯手工接单，脚本定制，不成功不收费！！",
         "个人纯手工接单，脚本定制，不成功不收费！！本人多年经验，专业代做各类脚本，价格优惠，欢迎咨询",
         "跳过（供给方）", True),
        ("reddit", "[Hiring] Need a Python automation script for invoice sync",
         "[Hiring] Need a Python automation script for invoice sync. Budget $800. Looking to hire someone.",
         "值得联系", False),
        ("reddit", "[For Hire] The Last Google Ads Guy You'll Ever Hire",
         "[For Hire] For over 8 years I have worked with brands managing Ad Budgets. "
         "My rates are $20/h, dm me",
         "跳过（供给方）", True),
        ("zhihu", "什么时候你突然发现挣钱是件很容易的事情？",
         "什么时候你突然发现挣钱是件很容易的事情？聊聊你的经历吧",
         "跳过", False),
    ]

    def _lead(self, i):
        import leads
        src, title, text, _, _ = self.CASES[i]
        return leads.to_lead({"title": title, "text": text, "url": "u", "author": "a"}, src)

    def test_verdicts_match_expectation(self):
        for i, (_, title, _, exp_v, exp_s) in enumerate(self.CASES):
            L = self._lead(i)
            self.assertEqual(L["verdict"], exp_v, f"{title[:30]!r} 的判定不符")
            self.assertEqual(L["supply_side"], exp_s, f"{title[:30]!r} 的供给方判定不符")

    def test_supply_side_is_never_marked_worth_contacting(self):
        """供给方可能同时命中金额词（"我的报价 $20/h"），打分不低但方向是反的。
        必须在这一层就压成"跳过"，否则调用方一旦忘记过滤就会把它当客户。"""
        import leads
        L = leads.to_lead({"title": "[For Hire] dev available",
                           "text": "For Hire. My rates are $50/h, 8 years of experience, dm me",
                           "url": "u"}, "reddit")
        self.assertTrue(L["supply_side"])
        self.assertIn("跳过", L["verdict"])
        self.assertNotEqual(L["verdict"], "值得联系")

    def test_money_score_prefers_explicit_amount(self):
        import leads
        self.assertEqual(leads._money_score("预算 3000 元"), 3)
        self.assertEqual(leads._money_score("Budget $800"), 3)
        self.assertEqual(leads._money_score("有偿 付费 报酬"), 2)   # 多个裸词
        self.assertEqual(leads._money_score("有偿"), 1)             # 单个裸词
        self.assertEqual(leads._money_score("今天天气不错"), 0)

    def test_money_score_uses_magnitude_not_just_presence(self):
        """踩过的坑：原实现只看"有没有金额"，于是 $50/week 的营销零工和 $3000 的悬赏
        拿同样的 money=3、并排在最前面 —— 实测榜单前 12 条里 4 条是低价值零工。

        三种计价方式用三把尺子：一次性 / 时薪 / 周期价。
        """
        import leads
        # 一次性：≥500 → 3
        self.assertEqual(leads._money_score("Budget $3000 bounty"), 3)
        self.assertEqual(leads._money_score("Bounty $1,500 for the fix"), 3)
        self.assertEqual(leads._money_score("预算 5000 元"), 3)
        self.assertEqual(leads._money_score("报酬 200 元"), 2)
        self.assertEqual(leads._money_score("报酬 50 元"), 1)
        # 时薪：≥50 → 3
        self.assertEqual(leads._money_score("$60/hour"), 3)
        self.assertEqual(leads._money_score("$20/h"), 2)
        self.assertEqual(leads._money_score("$18/h"), 1)
        # 周期价：$50/week ≈ 200/月 → 1
        self.assertEqual(leads._money_score("$50 Weekly"), 1)
        self.assertEqual(leads._money_score("月薪 30K"), 3)

    def test_amount_info_reports_period(self):
        import leads
        self.assertEqual(leads.amount_info("$60/hour"), (60.0, "hour"))
        self.assertEqual(leads.amount_info("$50 Weekly"), (50.0, "month"))
        self.assertEqual(leads.amount_info("Budget $800"), (800.0, "total"))
        self.assertEqual(leads.amount_info("没有金额"), (None, ""))

    def test_plausible_amount_rejects_ids_and_dates(self):
        """实测踩过：GitHub bounty 的 issue 里出现 `$239398281948585883`（18 位，是 id 不是钱），
        原实现判 money=3，结果 26 条垃圾把 top30 挤满、国内通道一条都进不来。"""
        import leads
        bad = ["$239398281948585883* bounty", "第 20260920123456 号", "编号 12345678",
               "需要 3 天时间", "版本 2 已发布"]
        for t in bad:
            self.assertFalse(leads.has_plausible_amount(t), f"{t!r} 不该被当成金额")
        good = ["Budget $800", "预算 3000 元左右", "$20/h", "价格 500",
                "报酬 5000 元", "rate: $60/hour"]
        for t in good:
            self.assertTrue(leads.has_plausible_amount(t), f"{t!r} 应被当成金额")

    def test_quota_select_prevents_noise_source_taking_over(self):
        """配额是项目在 P0-3 学到的教训：「只要采集层允许噪音源海量进入，
        再好的下游过滤也救不回来。信源配额是防止『劣币驱逐良币』的必要机制。」
        实测：不加配额时 GitHub bounty 靠 40 条量把 top30 全占了。"""
        import leads
        import collections
        pool = [{"source": "github_bounty", "score": 9.5 - i * 0.1, "verdict": "待看"}
                for i in range(26)]
        pool += [{"source": "zhihu", "score": 6.0 - i * 0.1, "verdict": "待看"}
                 for i in range(4)]
        pool += [{"source": "v2ex", "score": 5.5 - i * 0.1, "verdict": "待看"}
                 for i in range(3)]
        naive = collections.Counter(
            x["source"] for x in sorted(pool, key=lambda x: -x["score"])[:12])
        self.assertEqual(len(naive), 1, "不配额时应当只有一个信源霸榜（前提校验）")
        sel = leads.quota_select(pool, 12)
        self.assertEqual(len(set(x["source"] for x in sel)), 3,
                         "配额后所有信源都应出现在榜单里")
        self.assertLessEqual(len(sel), 12)

    def test_title_quality_rejects_placeholder_issues(self):
        """GitHub bounty 里混着占位/刷量 issue —— 实测抓到「[Bounty] Bounty」
        「[Bounty] EKEODKDE9DKE9DO BOUNTY」，标题没有信息但正文凑得出金额，会拿满分。"""
        import leads
        bad = ["[Bounty] Bounty", "[Bounty] EKEODKDE9DKE9DO BOUNTY", "bounty",
               "$$$", "12345678", "[BOUNTY] IMPLEMENT FOO"]
        for t in bad:
            self.assertFalse(leads.title_quality(t), f"{t!r} 应被判为无信息标题")
        good = ["[Bounty] [Bounty $1,500] SFPLOADMACRO produces wrong output",
                "[Hiring] Hiring Marketers | $50 Weekly",
                "有偿寻找一个代写游戏脚本的程序员",
                "[Hiring] Full Stack Engineer (Python): In Person, Austin TX"]
        for t in good:
            self.assertTrue(leads.title_quality(t), f"{t!r} 不该被判为无信息标题")

    def test_cap_per_repo_stops_single_repo_flooding(self):
        """实测：github_bounty 里 `zhangjiayang6835-cyber/bounty-plaza` 一个仓库贡献 6+ 条。
        信源配额防跨源霸榜，这一层防同源内刷量 —— 两道缺一不可。"""
        import leads
        import collections
        pool = [{"group": "gh:spam/repo", "score": 9.0, "verdict": "待看"} for _ in range(6)]
        pool += [{"group": "gh:real/proj", "score": 8.0, "verdict": "待看"} for _ in range(3)]
        capped = leads.cap_per_repo(pool, max_per_repo=2)
        c = collections.Counter(x["group"] for x in capped)
        self.assertLessEqual(max(c.values()), 2)
        self.assertEqual(len(c), 2, "不同主体都应保留")
        self.assertEqual(len(capped), 4)

    def test_repo_of_groups_by_owner_repo(self):
        import leads
        self.assertEqual(leads.repo_of("https://github.com/a/b/issues/3"), "gh:a/b")
        self.assertEqual(leads.repo_of("https://github.com/a/b/issues/9"), "gh:a/b")
        self.assertNotEqual(leads.repo_of("https://github.com/a/b/issues/1"),
                            leads.repo_of("https://github.com/a/c/issues/1"))
        self.assertTrue(leads.repo_of("https://www.reddit.com/r/forhire/comments/x/y/"))

    def test_md_text_escapes_brackets_in_link_text(self):
        """标题常以 [Bounty]/[Hiring] 开头，直接塞进 [标题](url) 会变成
        [[Bounty] [Bounty $1,500] …](url) —— 嵌套方括号让 Markdown 解析失败、链接点不动。"""
        import leads
        out = leads.md_text("[Bounty] [Bounty $1,500] fix it | now")
        self.assertNotIn("[Bounty]", out)
        self.assertIn("\\[Bounty\\]", out)
        self.assertNotIn("|", out)          # 竖线会撑破表格
        # 端到端：渲染出的表格里不应出现嵌套方括号
        import re
        md = leads.render([self._lead(0)], [], 0, "t")
        self.assertEqual(len(re.findall(r"\[\[[^\]]*\]\s*\[", md)), 0)

    def test_inquiry_lead_money_is_capped(self):
        """询价帖**不是委托**：对方还在问"大概多少钱"，没有决定要做。

        实测踩过：一条「请人做小程序大概多少钱？」因为深读后的正文里有人报了价
        （2 万到 20 万），money 拿到 3 分、排进前三 —— 但那条帖子里没有人要雇人。
        """
        import leads
        inq = leads.to_lead({"title": "请人做一个微信小程序一般费用大概需要多少钱？",
                             "text": "请人做一个微信小程序一般费用大概需要多少钱？"
                                     "有人报价 2 万到 20 万，看功能复杂度",
                             "url": "u"}, "zhihu")
        self.assertEqual(leads.lead_kind(inq), "inquiry")
        self.assertLessEqual(inq["money"], 2)
        self.assertNotEqual(inq["verdict"], "值得联系")
        self.assertIn("封顶", inq.get("kind_note", ""))
        # 真委托不受影响
        real = leads.to_lead({"title": "需要人做一个小程序，预算 3 万，功能不复杂",
                              "text": "需要人做一个小程序，预算 3 万，功能不复杂，"
                                      "希望两周内交付",
                              "url": "u2"}, "zhihu")
        self.assertEqual(real["money"], 3)
        self.assertEqual(real["verdict"], "值得联系")

    def test_kind_prefers_title_over_body(self):
        """踩过的坑：深读后的正文是一整段讨论，里面什么词都有 ——
        一条「请人做小程序大概多少钱？」因为正文里有人提到「月薪」，
        被误判成招聘帖，于是询价的钱分封顶失效、又排回了前三。

        与 tech_tags 同一个教训：**类型判断必须优先看标题**。
        """
        import leads
        L = {"title": "请人做一个微信小程序一般费用大概需要多少钱？",
             "text": "请人做一个微信小程序一般费用大概需要多少钱？ 有人报价 2 万到 20 万，"
                     "如果找人做，月薪大概是多少，薪资怎么算",
             "url": "u", "source": "zhihu"}
        self.assertEqual(leads.lead_kind(L), "inquiry")
        # 标题判不出类型时才退回全文
        L2 = {"title": "帮个忙", "text": "某公司诚聘后端工程师，月薪 30K", "url": "u"}
        self.assertEqual(leads.lead_kind(L2), "hiring")

    def test_single_char_xin_is_not_a_hiring_marker(self):
        """单字「薪」会被"薪资/薪酬/加薪"等各种语境命中 —— 必须用完整的词。"""
        import leads
        L = {"title": "讨论一下薪资水平", "text": "讨论一下薪资水平", "url": "u"}
        self.assertNotEqual(leads.lead_kind(L), "hiring")

    def test_verdicts_are_discriminating(self):
        """实测原阈值下 30/30 全判「值得联系」，等于没有筛选能力。"""
        import leads
        L = [self._lead(i) for i in range(len(self.CASES))]
        verdicts = {x["verdict"] for x in L}
        self.assertGreater(len(verdicts), 1, "判定结果必须有区分度，不能全是同一档")

    def test_spec_score_requires_concrete_object(self):
        import leads
        vague = leads._spec_score("求推荐工具")
        concrete = leads._spec_score(
            "需要人做一个 python 爬虫脚本，定时抓取某网站数据并导出 csv，"
            "已经试过 selenium 但被反爬拦了，希望能绕过")
        self.assertLess(vague, concrete)
        self.assertEqual(leads._spec_score(""), 0)

    def test_age_parsing_chinese_relative(self):
        import leads
        self.assertAlmostEqual(leads._age_days({"text": "3 天前发布"}), 3.0)
        self.assertAlmostEqual(leads._age_days({"text": "2 小时前"}), 2 / 24)
        self.assertAlmostEqual(leads._age_days({"text": "1 周前"}), 7.0)
        self.assertIsNone(leads._age_days({"text": "没有时间信息"}))
        # 时间戳
        import time
        ts = time.time() - 5 * 86400
        self.assertAlmostEqual(leads._age_days({"created_at": int(ts)}), 5.0, places=1)

    def test_render_discloses_supply_filter_count(self):
        import leads
        md = leads.render([self._lead(0)], [], 7, "测试")
        self.assertIn("供给方已过滤 7 条", md)
        self.assertIn("值得联系", md)
        self.assertIn("合规提醒", md)

    def test_render_handles_empty(self):
        import leads
        md = leads.render([], [], 0, "测试")
        self.assertIn("本轮没有抽到线索", md)

    def test_from_cache_only_takes_hiring_and_bounty(self):
        """离线模式必须只取 record_type in (hiring, bounty) ——
        这两类已由 hunter/filter.py 做过供需过滤，是现成的高质量线索池。"""
        import leads
        blob = {"windows": {"day": {"kept": [
            {"record_type": "hiring", "title": "a", "text": "有偿 找人做脚本 预算 3000"},
            {"record_type": "demand", "title": "b", "text": "随便一条需求证据"},
            {"record_type": "supply", "title": "c", "text": "一个仓库"},
        ]}}}
        import io
        import json as _json
        import os as _os
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            _json.dump(blob, f)
            p = f.name
        try:
            recs, health = leads.from_cache(p)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["record_type"], "hiring")
            self.assertTrue(health[0]["ok"])
        finally:
            _os.remove(p)


class TestDeepRead(unittest.TestCase):
    """二段式深读：标题粗排（便宜）→ 头部深读正文后重打分（贵）。

    为什么需要：知乎/小红书的**搜索结果不含正文**，只有标题 ——
    于是「钱」和「具体」两列对国内线索系统性偏低，而国内线索恰恰最需要。
    深读的真实价值（实测）：一条标题看着像需求的知乎回答，正文是
    「简单点，淘宝直接搜脚本编辑」—— 不是需求，是建议。只有读了正文才知道。
    """

    def test_flatten_text_collects_nested_strings(self):
        import leads
        obj = [{"id": "1", "content": "这是一个足够长的正文片段用于测试",
                "nested": {"deep": "嵌套里的字符串也要被收集到"}},
               {"short": "x"}]
        t = leads._flatten_text(obj)
        self.assertIn("足够长的正文片段", t)
        self.assertIn("嵌套里的字符串", t)
        self.assertNotIn("x", t.split())        # 过短的丢弃

    def test_find_time_picks_created_at(self):
        import leads
        self.assertEqual(
            leads._find_time([{"created_at": "2025-10-17T09:45:12.000Z"}]),
            "2025-10-17T09:45:12.000Z")
        self.assertEqual(
            leads._find_time({"a": {"b": [{"published_at": "2026-01-01"}]}}),
            "2026-01-01")
        self.assertIsNone(leads._find_time({"no": "time"}))

    def test_unsupported_source_returns_empty_with_reason(self):
        """不支持深读的来源必须返回空串 + 说明，不能假装读到了。"""
        import leads
        for src, url in [("xiaohongshu", "https://www.xiaohongshu.com/explore/abc?xsec_token=x"),
                         ("zhihu", "https://zhuanlan.zhihu.com/p/123456"),
                         ("github_bounty", "https://github.com/a/b/issues/1")]:
            txt, ts, note = leads.deep_read({"source": src, "url": url})
            self.assertEqual(txt, "")
            self.assertIsNone(ts)
            self.assertTrue(note, f"{src} 应给出不支持的原因")

    def test_deep_read_top_skips_unsupported(self):
        """只读支持的来源；不支持的计为 skipped，不报错。"""
        import leads
        pool = [{"source": "github_bounty", "url": "https://github.com/a/b/issues/1",
                 "title": "t", "text": "x", "score": 5.0, "verdict": "待看"},
                {"source": "xiaohongshu", "url": "https://x.com/e/1", "title": "t",
                 "text": "x", "score": 4.0, "verdict": "待看"}]
        done, skipped = leads.deep_read_top(pool, n=2, timeout=1)
        self.assertEqual(done, 0)
        self.assertEqual(skipped, 2, "两种来源都不支持深读时都应计为 skipped")

    def test_deep_supported_list_is_explicit(self):
        import leads
        self.assertEqual(set(leads.DEEP_SUPPORTED), {"v2ex", "zhihu"})


class TestApplyScript(unittest.TestCase):
    """应征话术：线索表解决"有没有活"，但真正让人卡住的是"打开对话框不知道写什么"。

    对不擅长主动推销的人，这个门槛比找不到活更高。
    """

    def _mk(self, **kw):
        # 字段与 to_lead() 的产出一致，否则 render() 会 KeyError
        base = {"title": "t", "text": "t", "url": "u", "source": "v2ex",
                "money": 0, "spec": 1, "fresh": 1, "score": 5.0,
                "verdict": "值得联系", "age_days": 1.0, "author": "a"}
        base.update(kw)
        return base

    def test_four_kinds_are_distinguished(self):
        """四类线索语气与问题完全不同 —— 类型判错的话术还不如不写。

        实测踩过：第一版只有一套"项目式"模板，对一条「量化策略研究员」招聘帖
        写「这个我可以做」、还问它「跑在什么环境」—— 错位得非常明显。
        """
        import leads
        cases = [
            ("github_bounty", "[Bounty $500] Fix the parser crash", "bounty"),
            ("v2ex", "某公司诚聘 后端工程师 月薪 30K", "hiring"),
            ("zhihu", "找人写个爬虫大概多少钱？", "inquiry"),
            ("v2ex", "需要人做一个数据采集脚本，预算 5000", "outsourcing"),
        ]
        for src, title, want in cases:
            got = leads.lead_kind(self._mk(source=src, title=title, text=title))
            self.assertEqual(got, want, f"{title[:30]!r} 应判为 {want}")

    def test_hiring_does_not_use_project_template(self):
        """招聘帖绝不能出现「这个我可以做」「跑在什么环境」。"""
        import leads
        L = self._mk(source="v2ex", title="Crypto CEX 诚聘 量化策略研究员 薪水 30K-50K RMB",
                     text="Crypto CEX 诚聘 量化策略研究员 薪水 30K-50K RMB 纯远程办公")
        s = leads.apply_script(L)
        self.assertEqual(s["kind"], "hiring")
        self.assertNotIn("这个我可以做", s["message"])
        self.assertNotIn("跑在什么环境", s["message"])
        self.assertIn("远程", s["message"])

    def test_language_follows_content_not_source(self):
        """踩过的坑：第一版用 `cjk == 0` 判断，正文里有一个中文字就翻成中文，
        于是一条全英文的 GitHub 悬赏被套上了中文话术。"""
        import leads
        en = self._mk(source="github_bounty",
                      title="[Bounty $500] Fix the parser crash on large inputs",
                      text="[Bounty $500] Fix the parser crash on large inputs. "
                           "The parser throws on inputs larger than 2GB.")
        self.assertEqual(leads._lang_of(en), "en")
        s = leads.apply_script(en)
        self.assertIn("Hi — I saw your bounty", s["message"])
        self.assertNotIn("你好", s["message"])
        # 中文帖即便来自同一来源也应是中文
        zh = self._mk(source="v2ex", title="找人做个小程序，预算 3 万",
                      text="找人做个小程序，预算 3 万，功能不复杂")
        self.assertEqual(leads._lang_of(zh), "zh")

    def test_tech_question_is_bilingual(self):
        """技术问题必须跟着语言走 —— 否则英文信里夹一句中文，像机翻。"""
        import leads
        self.assertIn("anti-scraping", leads._specific_question("写个爬虫", "en"))
        self.assertIn("反爬", leads._specific_question("写个爬虫", "zh"))
        self.assertIn("reproducible", leads._specific_question("fix this bug", "en"))

    def test_restate_skips_title_duplicate(self):
        """踩过的坑：record.text 是「标题 + 正文」，第一句往往就是标题，
        于是话术出现「看到你发的「X」。你提到：X」的重复。"""
        import leads
        L = self._mk(source="v2ex", title="需要人做一个数据采集脚本",
                     text="需要人做一个数据采集脚本 目标站点有反爬，数据量大概每天一万条，"
                          "希望导出成 csv")
        s = leads.apply_script(L)
        self.assertNotIn("你提到：需要人做一个数据采集脚本", s["message"])
        self.assertIn("反爬", s["message"])       # 复述的应是正文那句

    def test_title_markers_are_stripped(self):
        """[Bounty] [Bounty $1,500] … 这种重复嵌进话术像机器拼的。"""
        import leads
        self.assertEqual(leads._clean_title("[Bounty] [Bounty $1,500] fix it"), "fix it")
        self.assertEqual(leads._clean_title("[Hiring] Hiring Marketers"), "Hiring Marketers")
        self.assertEqual(leads._clean_title("无标记标题"), "无标记标题")
        # 全是标记时不能返回空
        self.assertTrue(leads._clean_title("[Bounty]"))

    def test_amount_and_age_produce_targeted_tips(self):
        import leads
        rich = leads.apply_script(self._mk(money=3, age_days=1.0))
        self.assertTrue(any("不要主动压价" in t for t in rich["tips"]))
        poor = leads.apply_script(self._mk(money=0, age_days=1.0))
        self.assertTrue(any("别先报价" in t for t in poor["tips"]))
        old = leads.apply_script(self._mk(money=0, age_days=30.0))
        self.assertTrue(any("已被接走" in t for t in old["tips"]))

    def test_undeepped_supported_source_warns_to_open_link(self):
        """没读到正文的线索要提醒先点开看 —— 否则容易问出对方已写明的问题。"""
        import leads
        L = self._mk(source="zhihu", deep=False, title="找人做个小程序，预算 3 万",
                     text="找人做个小程序，预算 3 万")
        s = leads.apply_script(L)
        self.assertTrue(any("没读到正文" in t for t in s["tips"]))

    def test_render_includes_scripts_section(self):
        import leads
        L = self._mk(source="v2ex", title="找人做一个数据采集脚本，预算 5000",
                     text="找人做一个数据采集脚本，目标站点有反爬，预算 5000")
        md = leads.render([L], [], 0, "t", n_scripts=1)
        self.assertIn("应征话术", md)
        self.assertIn("发之前请自己读一遍", md)
        self.assertIn("这个我可以做", md)


class TestAbilityProfile(unittest.TestCase):
    """能力画像：用户的核心困境是「我也不知道我能做什么」——这是自我认知问题，
    工具无法替他回答。但工具能提供证据：对线索做快速标注，累积起来就是一份
    **基于真实市场供给**的可服务范围画像，而不是自我感觉。
    """

    def setUp(self):
        import leads
        import tempfile
        self.leads = leads
        self._orig = leads.LEDGER
        fd, self.tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.tmp)              # 让 load_ledger 走"文件不存在"分支
        leads.LEDGER = self.tmp

    def tearDown(self):
        self.leads.LEDGER = self._orig
        if os.path.isfile(self.tmp):
            os.remove(self.tmp)

    def _mk(self, title, source="v2ex", **kw):
        d = {"title": title, "text": title, "url": "u/" + title[:20],
             "source": source, "money": 0, "spec": 1, "fresh": 1,
             "score": 5.0, "verdict": "值得联系", "age_days": 1.0, "author": "a"}
        d.update(kw)
        d["tech"] = self.leads.tech_tags(d)
        return d

    def test_tech_tags_prefer_title_and_are_capped(self):
        """踩过的坑：第一版对整个 text 匹配，而 text 是「标题 + 正文」，
        正文会东拉西扯 —— 一条「量化策略研究员」招聘同时命中 6 个标签，画像失去区分度。"""
        import leads
        # 标题只说明是爬虫，正文却提到一堆别的 —— 应以标题为准
        L = {"title": "写个爬虫抓数据",
             "text": "写个爬虫抓数据。顺便也要做前端页面、后端接口、部署运维、"
                     "数据报表、模型训练、Bug 修复、UI 设计"}
        self.assertEqual(leads.tech_tags(L), ["爬虫/数据采集"])
        # 标题给不出标签时才退回正文
        L2 = {"title": "帮个忙", "text": "需要写个爬虫抓数据"}
        self.assertEqual(leads.tech_tags(L2), ["爬虫/数据采集"])
        # 限量
        L3 = {"title": "爬虫 + 小程序 + 插件 + 脚本 + API 都要做"}
        self.assertLessEqual(len(leads.tech_tags(L3)), 3)

    def test_ledger_name_does_not_collide_with_output_glob(self):
        """踩过的坑：台账原叫 leads_log.json，也匹配 `leads_*.json` 这个 glob，
        而它在字符串排序里排在 `leads_20260920-1029.json` **之后** ——
        于是"取最新一轮产出"会读到台账本身，--mark 的序号全部错位（静默出错）。

        注意用 self._orig（原始常量）断言 —— setUp 会把 LEDGER 换成临时文件。
        """
        import glob as _glob
        name = os.path.basename(self._orig)
        self.assertFalse(_glob.fnmatch.fnmatch(name, "leads_[0-9]*.json"),
                         f"台账名 {name} 不能匹配取产出用的 glob")
        self.assertEqual(name, "lead_marks.json")

    def test_mark_records_and_accumulates(self):
        import leads
        ls = [self._mk("写个爬虫抓数据"), self._mk("修个 Bug"), self._mk("做个小程序")]
        done, bad = leads.mark_leads(ls, [(1, "yes"), (2, "no")])
        self.assertEqual((done, bad), (2, []))
        self.assertEqual(len(leads.load_ledger()), 2)
        # 第二轮再标第三条，应累积而不是覆盖
        done2, _ = leads.mark_leads(ls, [(3, "maybe")])
        self.assertEqual(done2, 1)
        self.assertEqual(len(leads.load_ledger()), 3)

    def test_mark_rejects_bad_input(self):
        import leads
        ls = [self._mk("写个爬虫抓数据")]
        done, bad = leads.mark_leads(ls, [(1, "maybe-ok"), (99, "yes")])
        self.assertEqual(done, 0)
        self.assertEqual(len(bad), 2)

    def test_profile_shows_net_signal_and_sample_warning(self):
        """同一类目常在两边都出现（多标签），所以必须给净差 ——
        否则读者看到「能做里有脚本、不能做里也有脚本」只会觉得结论糊。"""
        import leads
        ls = [self._mk(f"写个爬虫抓数据 {i}") for i in range(3)]
        ls += [self._mk(f"修个 Bug {i}") for i in range(3)]
        leads.mark_leads(ls, [(1, "yes"), (2, "yes"), (3, "yes"),
                              (4, "no"), (5, "no"), (6, "no")])
        md = "\n".join(leads.profile_md(min_sample=5))
        self.assertIn("净信号", md)
        self.assertIn("爬虫/数据采集", md)
        self.assertIn("明显不能做", md)
        self.assertIn("样本量偏小", md)          # 各 3 条 < 5
        self.assertIn("别拿现在的结论去改简历", md)

    def test_profile_weights_sign(self):
        """权重只做加减分，不做硬过滤 —— 硬过滤会形成信息茧房：
        今天标「不能做」的类目，可能正是三个月后该做的那一类。"""
        import leads
        ls = [self._mk(f"写个爬虫抓数据 {i}") for i in range(2)]
        ls += [self._mk(f"修个 Bug {i}") for i in range(2)]
        leads.mark_leads(ls, [(1, "yes"), (2, "yes"), (3, "no"), (4, "no")])
        w = leads.profile_weights()
        self.assertGreater(w.get("爬虫/数据采集", 0), 0)
        self.assertLess(w.get("Bug 修复", 0), 0)

    def test_empty_ledger_is_handled(self):
        import leads
        md = "\n".join(leads.profile_md())
        self.assertIn("台账是空的", md)
        self.assertEqual(leads.profile_weights(), {})


    def test_render_marks_already_marked_leads(self):
        """推荐的工作流是「每周跑一次、标 20 条」。如果每次重跑都把标过的
        重新摆在最前面，就得反复重读同样的东西 —— 那不是省时间的工具，
        是每周浪费半小时的仪式。"""
        import leads
        fresh = self._mk("写个爬虫抓数据", url="u/new")
        old = self._mk("修个 Bug", url="u/old", prev_mark="no", already_marked=True)
        md = leads.render([fresh, old], [], 0, "t", n_scripts=0, n_prev=1)
        self.assertIn("其中 1 条你已标注过", md)
        self.assertIn("--new-only", md)
        self.assertIn("| 上次 |", md)              # 表头有这一列
        # 已标过的显示上次标记的短标签
        line = [l for l in md.splitlines() if "u/old" in l][0]
        self.assertIn("| 不能 |", line)
        line_new = [l for l in md.splitlines() if "u/new" in l][0]
        self.assertIn("| — |", line_new)


if __name__ == "__main__":
    unittest.main(verbosity=2)
