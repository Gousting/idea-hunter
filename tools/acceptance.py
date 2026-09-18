# -*- coding: utf-8 -*-
"""P0 验收总检：一条命令把三项 P0 的验收标准全部实测出来。

为什么单独做一个脚本：验收标准散在三个模块里（原生榜贡献率在 paths、
北极星在 validate、能力覆盖在 resilience），逐条手敲四个脚本既慢又容易漏。
这里统一从**最新产物**反算，并明确打印"口径"和"达标判定"——
不达标就打印 ❌，不做任何粉饰。

用法：
    python tools/acceptance.py                  # 用最新产出验收
    python tools/acceptance.py <cache.json>     # 指定缓存文件
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
sys.path.insert(0, ROOT)

from hunter import paths as ph        # noqa: E402
from hunter import resilience as rz   # noqa: E402
from hunter import sources as S       # noqa: E402


def latest(pat):
    f = sorted(glob.glob(os.path.join(OUT, pat)))
    return f[-1] if f else None


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    cache_p = sys.argv[1] if len(sys.argv) > 1 else latest("window_cache_*.json")
    dir_p = latest("directions_*.json")
    if not cache_p or not dir_p:
        print("缺少产出文件（window_cache_*.json / directions_*.json）")
        return 2
    cache, dirs = jload(cache_p), jload(dir_p)

    print("=" * 74)
    print(f"P0 验收总检　缓存={os.path.basename(cache_p)}　报告={os.path.basename(dir_p)}")
    print("=" * 74)

    fails = []

    # ---------- P0-1 假共振修复 ----------
    print("\n【P0-1】假共振修复　验收标准：原生榜贡献率 ≥40%")
    print("  口径：原生榜=排序由平台决定（真独立发现）；关键词检索=我的查询词回声（不计共振）")
    tot_nat = tot_all = 0
    for k, v in cache["windows"].items():
        kept = v.get("kept", [])
        n_nat, n_kw, rate = ph.counts(kept)
        tot_nat += n_nat
        tot_all += len(kept)
        ok = rate >= 0.40
        if not ok:
            fails.append(f"P0-1 {v.get('label')} 原生率 {rate:.0%} < 40%")
        nf = v.get("native_fail") or []
        warn = f"　⚠ 原生源失败 {len(nf)} 个（读数需结合，非口径退化）" if nf else ""
        print(f"  {'✅' if ok else '❌'} {v.get('label'):<4} 原生 {n_nat:>3} / "
              f"关键词 {n_kw:>3} = {rate:>5.0%}　留存 {len(kept):>3}{warn}")
    rate_all = tot_nat / tot_all if tot_all else 0
    ok = rate_all >= 0.40
    if not ok:
        fails.append(f"P0-1 合计原生率 {rate_all:.0%} < 40%")
    print(f"  {'✅' if ok else '❌'} 合计　原生 {tot_nat} / 全部 {tot_all} = {rate_all:.0%}")

    # ---------- P0-2 验证闭环 ----------
    print("\n【P0-2】验证闭环　验收标准：北极星（近 7 天验证通过方向数）≥1")
    print("  口径：通过 = ≥2 个独立受访者已在为此付费或给出明确预算；表达「有意思」不算")
    vp = os.path.join(OUT, "validation_kits.json")
    if os.path.isfile(vp):
        v = jload(vp)
        st = v["stats"]
        ok = st["north_star"] >= st["target"]
        if not ok:
            fails.append(f"P0-2 北极星 {st['north_star']} < {st['target']}")
        print(f"  {'✅' if ok else '❌'} 北极星 {st['north_star']} / 目标 ≥{st['target']}"
              f"　（待续 {len(st['pending'])} · 否决 {len(st['rejected'])} · "
              f"误杀复活 {len(st['resurrected'])} · 台账 {st['total_records']} 条）")
        print(f"  待验证队列 {len(v.get('queue') or [])} 个方向"
              + ("：" + "、".join(q["direction"] for q in v["queue"]) if v.get("queue") else ""))
    else:
        fails.append("P0-2 validation_kits.json 不存在")
        print("  ❌ 缺 validation_kits.json")

    # ---------- P0-3 平台依赖对冲 ----------
    print("\n【P0-3】平台依赖对冲　验收标准：能力缺口 <20% 且 硬失败率 <10%")
    print("  口径：按**能力**统计（唯一提供某能力的源挂了才算缺口）；"
          "已知不可用源跳过不计失败")
    res = rz.assess(dirs.get("health", []))
    ok_gap, ok_fail = res["gap_rate"] < 0.20, res["fail_rate"] < 0.10
    if not ok_gap:
        fails.append(f"P0-3 能力缺口 {res['gap_rate']:.0%} ≥ 20%")
    if not ok_fail:
        fails.append(f"P0-3 硬失败率 {res['fail_rate']:.0%} ≥ 10%")
    print(f"  {'✅' if ok_gap else '❌'} 能力缺口 {res['gap_rate']:.0%}（{res['lost']}/{res['n_capabilities']} 项）")
    print(f"  {'✅' if ok_fail else '❌'} 硬失败率 {res['fail_rate']:.0%}")
    # 把"谁在失败"直接列出来 —— 只有一个百分数无法行动，必须能一眼看到元凶
    fc, fd = {}, {}
    for h in dirs.get("health", []):
        if h.get("skipped") or h.get("ok") or h.get("count"):
            continue
        b = (h.get("source") or "").split("[")[0]
        fc[b] = fc.get(b, 0) + 1
        fd.setdefault(b, (h.get("note") or "")[:56])
    if fc:
        print(f"  失败明细（合计 {sum(fc.values())} 源次）：")
        for b, n in sorted(fc.items(), key=lambda kv: -kv[1]):
            print(f"      {b} × {n}　{fd[b]}")
    print(f"  跳过（不计失败）{len(res['skipped'])} 个：{list(res['skipped'])}"
          "　← 「失败率低」必须与「跳过几个」一起读")
    for r in res["rows"]:
        mark = {"covered": "✅", "degraded": "⚠️", "lost": "❌"}[r["state"]]
        print(f"    {mark} {r['capability']:<22} 主源 {r['primary_ok'] or '—'}"
              f"　等效 {r['equivalent_ok'] or '—'}")
    # 失败回填：缓存状态
    cs = S.cache_stats()
    print(f"  失败回填：GitHub 查询缓存 {cs['entries']} 条（新鲜 {cs['fresh']} / "
          f"过期 {cs['stale']}）——限流时过期旧值会被兜底使用并标记 stale")

    # ---------- P0-3b 等效源的边际贡献 ----------
    # 为什么要单独查这一项：能力矩阵只看"采集健康"（count>0）就判 covered，
    # 但**采到了 ≠ 用上了**。实测踩过：四个等效源采集全部成功，
    # 却因为源名/门槛/字段名不匹配，进入规则层的记录数是 **0**——
    # 矩阵显示"已覆盖"，实际等于没接。这是最隐蔽的一种假覆盖。
    print("\n【P0-3b】等效源边际贡献　验收标准：每个等效源至少有 1 条进入规则层")
    all_kept = [r for v in cache["windows"].values() for r in v.get("kept", [])]

    def matcher(name):
        if name == "reddit:forhire":
            return lambda r: (r.get("source") == "reddit"
                              and "forhire" in ((r.get("subreddit") or "")
                                                + " " + (r.get("site") or "")))
        if name == "github_bounty":
            return lambda r: r.get("source") == "github_bounty"
        if name == "bluesky:trending":
            return lambda r: r.get("source") == "bluesky"
        if name == "juejin:hot":
            return lambda r: r.get("source") == "juejin"
        b = name.split(":")[0]
        return lambda r: r.get("source") == b

    for r in res["rows"]:
        claims = list(r["equivalent_ok"])
        if not claims:
            continue
        for claim in claims:
            base = claim.replace("(弱)", "")
            m = matcher(base)
            n = sum(1 for x in all_kept if m(x))
            if base in rz.EXCLUDED_BY_DESIGN:
                # 主动排除 ≠ 假覆盖：一个是决策，一个是 bug。必须区分，
                # 否则"主动不接"会被误报成失败，久了就没人看这两个数字。
                print(f"  ➖ {r['capability']:<20} ← {claim:<18} 主动排除"
                      f"（{rz.EXCLUDED_BY_DESIGN[base][:34]}…）")
                continue
            ok1 = n > 0
            if not ok1:
                fails.append(f"P0-3b 等效源 {claim} 采集成功但 0 条进入规则层（假覆盖）")
            print(f"  {'✅' if ok1 else '❌'} {r['capability']:<20} ← {claim:<18} "
                  f"边际贡献 {n} 条")

    # ---------- 汇总 ----------
    print("\n" + "=" * 74)
    if fails:
        print(f"验收结果：❌ 未通过（{len(fails)} 项不达标）")
        for f in fails:
            print("  -", f)
    else:
        print("验收结果：✅ 三项 P0 全部达标")
    print("=" * 74)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
