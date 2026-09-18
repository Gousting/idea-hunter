# -*- coding: utf-8 -*-
"""判定方式的统一口径 —— 报告与看板必须共用这一份实现。

为什么单独成模块（2026-09-18 修复）：
"这份榜单是用什么方式分类出来的"这件事，此前被**写了两遍**：
  · run_windows.py           → 报告渲染器
  · tools/render_dashboard.py → 看板渲染器
两处一开始就不一致，直接导致同一次运行的两份产出互相矛盾：
    看板：关键词签名（含部分 agent 语义标注）
    报告：agent-语义分类（Claude 直读原文）
而实际覆盖率只有 12.8%（今日窗口）。读者拿到的那份（报告）恰好是夸大的那份。

修第一遍时我把逻辑从看板"搬"进了报告 —— 但那只是把两份合成两份，
边界条件很快又分叉了：报告修好了"零命中要说过期"，看板仍会在 0% 覆盖时
说"含部分语义标注"。**同一份数据有多个渲染器时，诚实性逻辑必须共享同一份代码，
而不是各写一份看起来一样的实现。**

本模块只做一件事：给 (是否有标注文件, 命中数, 留存数) 算出该说什么。
调用方负责把这三个数如实统计出来。
"""
SEMANTIC_MODES = ("llm-语义分类", "agent-语义分类")

MODE_KEYWORD = "关键词签名"
MODE_AGENT = "agent-语义分类（Claude 直读原文）"
MODE_PARTIAL = "关键词签名（含部分 agent 语义标注）"
MODE_STALE = "关键词签名（标注文件与本轮数据无交集，很可能已过期）"
MODE_NO_RECORDS = "关键词签名（本窗口无留存记录）"

# 覆盖率低于此值时，不得按"各方向语义等距"解读榜单
SEMANTIC_TRUST_THRESHOLD = 0.5


def is_semantic(mode):
    """判定方式是否属于（完整的）语义分类。

    注意不要用 `"llm" in mode` 做判断：MODE_AGENT 里不含 "llm"，
    那样会让报告同时输出"用了 agent 语义分类"和"关键词模式签名宽度不等"两句
    互相矛盾的话（实测踩过）。
    """
    return any(m in (mode or "") for m in SEMANTIC_MODES)


def classify_mode(ann_present, hit, kept_n):
    """按**实际命中率**给出判定方式。

    绝不只看"有没有传 --annotations"：传一个空的 {} 也会声称用了语义分类，
    而榜单实际 100% 来自关键词签名（实测过）。
    """
    if not ann_present:
        return MODE_KEYWORD
    if not kept_n:
        return MODE_NO_RECORDS
    if not hit:
        # 实测常态：标注按 source_id 绑定，重跑一次采集记录集就变了，
        # 旧标注立刻全部失效。这时必须说清"过期"，不能含糊成"含部分语义标注"。
        return MODE_STALE
    return MODE_AGENT if hit >= kept_n * SEMANTIC_TRUST_THRESHOLD else MODE_PARTIAL


def coverage_line(hit, kept_n, ann_used=True):
    """覆盖率披露行 —— 不披露覆盖率，"语义分类"就是一句无法核验的声明。

    ann_used=False（本轮根本没传标注文件）时返回空串：那种情况判定方式已经是
    纯"关键词签名"，再显示一行"语义标注覆盖 0/N"只会让人误以为语义分类跑过但失败了。
    """
    if not ann_used or not kept_n:
        return ""
    return (f"（语义标注实际覆盖 {hit} / {kept_n} 条 = **{hit / kept_n:.0%}**；"
            "未覆盖的记录回退关键词签名 —— 覆盖率 <50% 时不得按「语义等距」解读榜单）")
