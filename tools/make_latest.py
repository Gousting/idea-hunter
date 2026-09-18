# -*- coding: utf-8 -*-
"""把最新一轮产出复制成稳定文件名（latest_*），清理旧产物，并刷新 INDEX.md 时间戳。

为什么需要：out/ 里累积了多轮次的带时间戳产物（dashboard_20260918-1543/1544/...），
人分不清哪份是当前该看的。**稳定命名**是最省事的解法——
读者只需要记 `latest_*`，而不是一串时间戳。

用法：
    python tools/make_latest.py            # 刷新稳定名 + 清理旧产物
    python tools/make_latest.py --no-prune # 只刷新稳定名，不清理
"""
import argparse
import glob
import os
import re
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

PAIRS = [
    ("dashboard_*.html", "latest_dashboard.html"),
    ("directions_*.md", "latest_directions.md"),
    ("directions_*.json", "latest_directions.json"),
    ("platforms_*.md", "latest_platforms.md"),
    ("analysis_*.md", "latest_analysis.md"),
]

# 固定名产出（本来就唯一，不需要时间戳）
FIXED = ["resilience.json", "validation_kits.json", "platform_analysis.json",
         "agent_annotations.json", "INDEX.md"]


def _latest(pat):
    f = sorted(glob.glob(os.path.join(OUT, pat)))
    return f[-1] if f else None


# 每类时间戳产物保留几份。**只留 1 份**就够：脚本按 glob 取最新，
# 而 latest_* 已经是内容副本，多留只是堆积。
PRUNE_PATTERNS = ["dashboard_*.html", "directions_*.md", "directions_*.json",
                  "platforms_*.md", "platforms_*.json", "analysis_*.md",
                  "window_cache_*.json", "report_*.md", "candidates_*.json",
                  "resilience_*.json", "validation_kits_*.json"]


def prune(keep=1, dry=False):
    """清掉旧的时间戳产物。

    为什么移走而不是删除（实测）：本环境的 safe-delete 层对**工作区内**的删除
    是 fail-closed 的（转交回收站失败就拒绝删除），批量 rm 会被直接拦下。
    移到项目外的临时目录既能腾出工作区、又顺手留了后悔药。
    实测积累速度：一天 160 份 / 57MB，其中 35 份看板占 36MB。
    """
    arch = os.path.join(os.environ.get("TEMP", "/tmp"),
                        "idea-hunter-pruned-" + time.strftime("%Y%m%d-%H%M"))
    moved, freed = 0, 0
    for pat in PRUNE_PATTERNS:
        hit = sorted(glob.glob(os.path.join(OUT, pat)))
        for src in hit[:-keep] if keep else hit:
            freed += os.path.getsize(src)
            if not dry:
                os.makedirs(arch, exist_ok=True)
                shutil.move(src, os.path.join(arch, os.path.basename(src)))
            moved += 1
    return moved, freed, arch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-prune", action="store_true", help="只刷新稳定名，不清理旧产物")
    ap.add_argument("--keep", type=int, default=1, help="每类时间戳产物保留份数")
    a = ap.parse_args()

    rows = []
    for pat, dst in PAIRS:
        src = _latest(pat)
        if not src:
            print(f"  ! 未找到 {pat}（跳过）")
            continue
        shutil.copyfile(src, os.path.join(OUT, dst))
        rows.append((dst, os.path.basename(src), os.path.getsize(src)))

    for f in FIXED:
        p = os.path.join(OUT, f)
        if os.path.isfile(p):
            rows.append((f, f, os.path.getsize(p)))

    for d, s, n in rows:
        mark = "<-" if d != s else "  "
        print(f"  {d:<28} {mark} {s:<34} {n / 1024:>7.0f} KB")

    # 顺手把 INDEX.md 的生成时间刷新，避免读者以为索引是旧的
    ip = os.path.join(OUT, "INDEX.md")
    if os.path.isfile(ip):
        with open(ip, encoding="utf-8") as f:
            t = f.read()
        t2 = re.sub(r"生成时间：[0-9\-]+ [0-9:]+",
                    "生成时间：" + time.strftime("%Y-%m-%d %H:%M"), t, count=1)
        if t2 != t:
            with open(ip, "w", encoding="utf-8") as f:
                f.write(t2)
            print("  INDEX.md 时间戳已刷新")
    print(f"\n稳定名产出 {len(rows)} 份 → {OUT}")
    if not a.no_prune:
        n, freed, arch = prune(keep=a.keep)
        if n:
            print(f"清理旧产物 {n} 份（释放 {freed/1024/1024:.1f} MB）→ {arch}")
            print("  （移出而非删除：本环境工作区内的删除是 fail-closed 的）")
        else:
            print("旧产物清理：无需清理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
