# -*- coding: utf-8 -*-
"""
OpenCLI 通道：用「你已登录的 Chrome」直接读站点。

与前面几条通道的区别（这是它值得单独存在的理由）：
  · 官方 API  → 有条款与限额（Reddit 商用被合同锁死）
  · RSS      → 通，但只有帖子正文，**没有评论**
  · 浏览器裸读 → 免验证站点可以，但 Reddit 等被网络策略拦（403 Blocked）
  · OpenCLI  → 走「扩展 + 本地守护进程」，复用你正在用的 Chrome 登录态，
               因此 **Reddit 的帖子+评论、Upwork 的付费需求** 都能拿到

实测要点（2026-09）：
  1. CLI 本体：`@jackwener/opencli`（npm），扩展已装且 ID 与官方商店一致。
  2. **需要本地代理**：CLI 的 Node 进程不走系统代理，不加 HTTP_PROXY 会连
     Google 的地址超时（实测 34.120.x.x:443 timeout）。
  3. `[public]` 适配器无需浏览器；`[cookie]` 适配器**必须 Chrome 开着**，
     否则返回 exitCode 69 / BROWSER_CONNECT。
  4. 不要为了让 cookie 可读而关闭 Chrome —— 这条路本来就不需要复制 cookie。
"""
import json
import os
import re
import socket
import subprocess
import time

WORKSPACE = os.path.expanduser(
    r"~\.workbuddy\binaries\node\workspace\node_modules\.bin\opencli.cmd")
NODE = r"C:\nvm4w\nodejs\node.exe"
NPX = r"C:\nvm4w\nodejs\npx.cmd"

# 本地代理探测：只做 TCP 连通性检查，不发请求（比探针请求快且无副作用）
PROXY_PORTS = ["7897", "7890", "10809", "10808", "1080", "20171"]


def _port_open(port, host="127.0.0.1", timeout=0.6):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def proxy_url():
    env = os.environ.get("HUNTER_PROXY")
    if env:
        return env
    for p in PROXY_PORTS:
        if _port_open(p):
            return f"http://127.0.0.1:{p}"
    return ""


def cli_argv():
    if os.path.isfile(WORKSPACE):
        return [WORKSPACE]
    return [NPX, "-y", "@jackwener/opencli@latest"]


def run(args, timeout=150, fmt="json"):
    """调用 opencli。返回 (数据, 元信息)。

    退出码遵循 sysexits：0 成功 / 66 空结果 / 69 浏览器未连接 /
    75 超时 / 77 需认证 / 78 配置错误。
    """
    argv = cli_argv() + list(args) + ["-f", fmt]
    env = dict(os.environ)
    px = proxy_url()
    if px:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, {"ok": False, "code": 75, "note": f"超时 {timeout}s"}
    out, err = (p.stdout or ""), (p.stderr or "")
    code = p.returncode
    if code != 0:
        blob = err + out
        hint = ""
        if code == 69 or "BROWSER_CONNECT" in blob:
            hint = "需 Chrome 处于打开状态且 OpenCLI 扩展已启用"
        elif code == 77 or "AUTH_REQUIRED" in blob:
            hint = "该适配器需要登录：请在 Chrome 里登录目标站点（cookie 过期也要重登）"
        elif "Navigation rejected" in blob:
            hint = "站点拒绝导航，多为未登录或站点改版；可先用 <site> whoami 验证登录态"
        elif code == 66:
            hint = "返回空结果"
        tail = (err or out).strip()
        detail = tail.splitlines()[-1][:160] if tail else f"exit {code}"
        return None, {"ok": False, "code": code, "note": hint or detail}
    try:
        return json.loads(out), {"ok": True, "code": 0, "note": ""}
    except Exception:
        # 个别适配器输出非 JSON，退回按行解析
        try:
            return json.loads("[" + out.strip().rstrip(",") + "]"), {"ok": True, "code": 0,
                                                                    "note": "非标准 JSON，已容错"}
        except Exception as e:
            return None, {"ok": False, "code": 0,
                          "note": f"输出无法解析：{type(e).__name__}"}


def doctor():
    """连通性诊断。返回 (可用适配器类型, 说明)。"""
    argv = cli_argv() + ["doctor"]
    env = dict(os.environ)
    px = proxy_url()
    if px:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90, env=env)
        txt = (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return {"daemon": False, "extension": False, "note": str(e)[:120]}
    return {
        "daemon": "[OK] Daemon" in txt,
        "extension": "[MISSING] Extension" not in txt and "not connected" not in txt.lower(),
        "proxy": px,
        "note": " ".join(t for t in txt.splitlines() if t.startswith("[")).replace("[", " ["),
    }


# ---------------------------------------------------------------- 规整化
def _pick(d, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _i(v):
    """宽松取整：'683' / '1,234' / 683 都能转，失败返回 0。"""
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def _cn_num(v):
    """解析中文数量串：'1160 万热度' → 11600000，'1.2 亿' → 120000000。

    知乎等站的热度是中文单位字符串，直接 int() 会失败并静默变成 0（实测踩过：
    知乎整榜热度全是 0，因为 '1160 万热度' 转不动）。
    """
    t = str(v or "").replace(",", "")
    m = re.search(r"([\d.]+)\s*(亿|万|千)?", t)
    if not m:
        return 0
    try:
        n = float(m.group(1))
    except Exception:
        return 0
    unit = m.group(2)
    return int(n * {"亿": 1e8, "万": 1e4, "千": 1e3}.get(unit, 1))


def _norm(src, d, site=""):
    """把各适配器不同的字段名统一成流水线的记录结构。
    适配器字段名不统一（name/title、tagline/selftext、permalink/url），
    所以这里用"多候选键名"的方式容错，而不是为每个站点写死字段。"""
    title = str(_pick(d, "title", "name", "jobTitle", "headline"))
    body = str(_pick(d, "selftext", "tagline", "description", "text", "body",
                     "content", "summary"))
    url = str(_pick(d, "url", "permalink", "link", "href"))
    if url.startswith("/"):
        url = "https://www.reddit.com" + url
    sid = _pick(d, "id", "uuid", "slug", default=url) or f"{title[:40]}"
    # 结构化的讨论热度（别再塞进文本里 —— 塞了就没法参与计算，实测踩过）
    heat = {"score": max(_i(d.get(k)) for k in ("score", "ups", "votesCount", "votes", "points")),
            "comments": max(_i(d.get(k)) for k in ("comments", "num_comments", "commentCount", "descendants")),
            # 各站原生热度字段（量纲不同，由 platforms.heat_of 按站取用）
            "answers": _i(d.get("answers")), "views": _i(d.get("views")),
            "votes": _i(d.get("votesCount") or d.get("votes")),
            "rank": _i(d.get("rank")),
            "heat_num": _cn_num(d.get("heat"))}
    extra = []
    for k, label in (("score", "score"), ("comments", "comments"),
                     ("ups", "ups"), ("num_comments", "num_comments"),
                     ("budget", "budget"), ("hourly", "hourly"),
                     ("jobType", "jobType"), ("subreddit", "subreddit"),
                     ("votesCount", "votes"), ("author", "author")):
        if d.get(k) not in (None, "", []):
            extra.append(f"{label}={d[k]}")
    return {
        "source": src,
        "source_id": f"{src}:{site}:{sid}",
        "repo": "",
        "heat": heat,
        "url": url,
        "title": title[:200],
        "text": " ".join(f"{title}. {body} {' '.join(extra)}".split())[:2200],
        "site": site,
        "raw": {k: v for k, v in d.items() if not isinstance(v, (dict, list))},
        "collected_at": int(time.time()),
    }


def _rows(data):
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    for k in ("items", "results", "posts", "data", "jobs", "comments", "products", "rows"):
        v = data.get(k)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    if isinstance(data, dict):
        return [data]
    return []


# ---------------------------------------------------------------- 适配器封装
def reddit_subreddit(name, limit=25, sort="hot", time_filter=""):
    """子版块帖子。--time 支持 hour/day/week/month/year/all，
    所以三个时间窗都能直接表达（不需要退回 RSS）。"""
    args = ["reddit", "subreddit", name, "--limit", str(limit), "--sort", sort]
    if time_filter:
        args += ["--time", time_filter]
    d, m = run(args)
    rows = _rows(d)
    return [_norm("reddit", r, f"r/{name}") for r in rows], \
        {"source": f"opencli:reddit:r/{name}[{sort}{'/' + time_filter if time_filter else ''}]",
         "count": len(rows), "ok": m["ok"], "note": m["note"]}


def reddit_search(query, limit=25, subreddit="", sort="relevance", time_filter=""):
    args = ["reddit", "search", query, "--limit", str(limit), "--sort", sort]
    if subreddit:
        args += ["--subreddit", subreddit]
    if time_filter:
        args += ["--time", time_filter]
    d, m = run(args)
    rows = _rows(d)
    return [_norm("reddit", r, "search") for r in rows], \
        {"source": f"opencli:reddit:search[{query[:16]}]", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def reddit_read(post_id, limit=25, depth=2, max_length=800, expand=False):
    """帖子 + 评论。这是 RSS 拿不到的部分，也是抱怨最集中处。

    实测输出结构（别按直觉写成嵌套）：
      返回的是**平铺数组**，第一项 type=POST 是原帖，其余 type=L0/L1… 是各级评论，
      每项各自带 author/score/text。所以要把它们合并成一条证据记录，
      而不是去找某个 comments 嵌套字段（首版就是这么写错的，会拿到空评论）。
    """
    args = ["reddit", "read", str(post_id), "--limit", str(limit),
            "--depth", str(depth), "--max-length", str(max_length)]
    if expand:
        args += ["--expand-more", "true"]
    d, m = run(args, timeout=180)
    rows = _rows(d)
    if not rows:
        return [], {"source": "opencli:reddit:read", "count": 0, "ok": m["ok"],
                    "note": m["note"] or "无返回"}

    post = next((r for r in rows if str(r.get("type", "")).upper() == "POST"), rows[0])
    comments = [r for r in rows
                if str(r.get("type", "")).upper().startswith("L")
                and r is not post]

    # 过滤 "[+3 more replies]" 这类占位行与图片直链
    def _clean(t):
        t = " ".join(str(t or "").split())
        if not t or re.match(r"^\[\+\d+ more repl", t):
            return ""
        if re.match(r"^https?://\S+$", t):
            return ""
        return t

    post_text = _clean(_pick(post, "text", "selftext", "body"))
    title = post_text.split("\n")[0][:180] if post_text else str(_pick(post, "title"))
    bodies, total_score = [], 0
    for c in comments:
        b = _clean(_pick(c, "text", "body"))
        if len(b) >= 25:
            bodies.append(b)
        try:
            total_score += int(c.get("score") or 0)
        except Exception:
            pass

    rec = {
        "source": "reddit",
        "source_id": f"reddit:read:{post.get('id') or post_id}",
        "repo": "",
        "url": str(_pick(post, "url", "permalink",
                         default=f"https://www.reddit.com/comments/{post_id}")),
        "title": title,
        "text": " ".join(f"{title}. {post_text} {' '.join(bodies)}".split())[:4000],
        # 归类只依据「帖子主题」，不能用合并后的长评论文本 ——
        # 评论区会跑题（实测一条讲"评论被当垃圾删掉"的评论把整个帖带偏到"报表与可视化"）。
        # 但信号检测（痛点/付费构式）仍要用全部文本，因为抱怨常在评论区。
        "topic_text": f"{title}. {post_text}"[:600],
        "site": "reddit:post",
        "comment_count": len(bodies),
        "comment_score_sum": total_score,
        # 讨论热度：评论区赞同合计是最贴近"社区认同这个抱怨"的量
        "heat": {"score": _i(post.get("score")), "comments": len(bodies),
                 "comment_score": total_score},
        "collected_at": int(time.time()),
    }
    health = {"source": "opencli:reddit:read", "count": 1, "ok": True,
              "note": f"{len(bodies)} 条评论，评论赞同数合计 {total_score}"}
    return [rec], health


def reddit_deep(subreddit, top_n=3, sort="top", time_filter="week",
                min_comments=5, comment_limit=25):
    """列表页 → 挑评论最多的若干帖 → 深读评论。

    为什么按"评论数"挑而不是按赞数：赞多的常是梗图和情绪帖（实测 r/SaaS 榜首是
    一张配图帖），而**评论多的帖子才是有真实讨论、有具体抱怨的地方**。
    """
    listing, h1 = reddit_subreddit(subreddit, 25, sort=sort, time_filter=time_filter)
    if not listing:
        return [], h1
    cands = []
    for r in listing:
        try:
            c = int(r.get("raw", {}).get("comments") or 0)
        except Exception:
            c = 0
        if c >= min_comments:
            cands.append((c, r))
    cands.sort(key=lambda x: -x[0])
    picked = cands[:top_n]

    out = []
    for c, r in picked:
        rs, h = reddit_read(r["raw"].get("id") or r["url"], limit=comment_limit,
                            depth=2, max_length=800)
        out += rs
    note = (f"r/{subreddit}: 列表 {len(listing)} 条 → 深读 {len(picked)} 帖"
            f"（评论门槛 ≥{min_comments}）"
            + (f"；{h1['note']}" if h1.get("note") else ""))
    return out, {"source": f"opencli:reddit:deep:r/{subreddit}", "count": len(out),
                 "ok": len(out) > 0, "note": note}




def _merge_thread(src, rows, sid, url, site, limit_chars=800):
    """把平铺的线程输出合并成一条记录：首项是主帖，其余是各级评论。

    为什么抽出来：Reddit / Hacker News / Lobsters / Stack Overflow 的 read
    返回结构**完全一致**（POST + L0/L1/L2，SO 用 Q-COMMENT），各写一遍是重复。
    评论正文与**评论赞同数**都要留——后者是"有多少人认同这个抱怨"的量化。
    """
    def _clean(t):
        t = " ".join(str(t or "").split())
        if not t or re.match(r"^\[\+\d+ more repl", t):
            return ""
        if re.match(r"^https?://\S+$", t):
            return ""
        return t

    post = next((r for r in rows if str(r.get("type", "")).upper() == "POST"), rows[0])
    comments = [r for r in rows if r is not post]
    post_text = _clean(_pick(post, "text", "selftext", "body"))
    title = post_text.split("\n")[0][:180] if post_text else str(_pick(post, "title"))
    bodies, total_score = [], 0
    for c in comments:
        b = _clean(_pick(c, "text", "body"))
        if len(b) >= 25:
            bodies.append(b)
        try:
            total_score += int(c.get("score") or 0)
        except Exception:
            pass
    return {
        "source": src,
        "source_id": f"{src}:read:{sid}",
        "repo": "",
        "url": url,
        "title": title,
        "text": " ".join(f"{title}. {post_text} {' '.join(bodies)}".split())[:4000],
        # 归类只用帖子主题（评论区会跑题），信号检测才用全文
        "topic_text": f"{title}. {post_text}"[:600],
        "site": site,
        "comment_count": len(bodies),
        "comment_score_sum": total_score,
        "heat": {"score": _i(post.get("score")), "comments": len(bodies),
                 "comment_score": total_score},
        "collected_at": int(time.time()),
    }


def hackernews_deep(feed="show", top_n=2, comment_limit=30):
    """深读 HN 讨论区 —— 按评论数挑帖（评论多才有真实讨论）。全 public。"""
    listing, h1 = hackernews(feed, 25)
    cands = sorted(listing, key=lambda r: -(r.get("heat", {}).get("comments") or 0))
    out = []
    for r in cands[:top_n]:
        hid = (r.get("raw") or {}).get("id") or r.get("url")
        d, m = run(["hackernews", "read", str(hid)], timeout=120)
        rows = _rows(d)
        if rows:
            out.append(_merge_thread("hn", rows, hid, r.get("url", ""), f"hn:{feed}"))
    note = (f"hn/{feed}: 列表 {len(listing)} 条 → 深读 {len(out)} 帖"
            + (f"；{h1['note']}" if h1.get("note") else ""))
    return out, {"source": f"opencli:hn:deep:{feed}", "count": len(out),
                 "ok": len(out) > 0, "note": note}


def lobsters_deep(top_n=2, comment_limit=30):
    """深读 Lobsters 讨论区。全 public。"""
    d0, m0 = run(["lobsters", "hot", "--limit", "25"])
    listing = [_norm("lobsters", x, "hot") for x in _rows(d0)]
    cands = sorted(listing, key=lambda r: -((r.get("heat", {}).get("comments") or 0)
                                            + (r.get("heat", {}).get("score") or 0)))
    out = []
    for r in cands[:top_n]:
        sid = (r.get("raw") or {}).get("id") or r.get("url")
        d, m = run(["lobsters", "read", str(sid)], timeout=120)
        rows = _rows(d)
        if rows:
            out.append(_merge_thread("lobsters", rows, sid, r.get("url", ""), "lobsters"))
    return out, {"source": "opencli:lobsters:deep", "count": len(out),
                 "ok": len(out) > 0, "note": f"热帖 {len(listing)} 条 → 深读 {len(out)} 帖"}


def stackoverflow_deep(tag="automation", top_n=2):
    """深读 SO 提问的评论与回答。全 public。"""
    d0, m0 = run(["stackoverflow", "tag", tag, "--sort", "hot", "--limit", "25"])
    listing = [_norm("stackoverflow", x, f"#{tag}") for x in _rows(d0)]
    cands = sorted(listing, key=lambda r: -((r.get("heat", {}).get("score") or 0)))
    out = []
    for r in cands[:top_n]:
        sid = (r.get("raw") or {}).get("id") or r.get("url")
        d, m = run(["stackoverflow", "read", str(sid)], timeout=120)
        rows = _rows(d)
        if rows:
            out.append(_merge_thread("stackoverflow", rows, sid, r.get("url", ""),
                                     f"so:{tag}"))
    return out, {"source": f"opencli:stackoverflow:deep:#{tag}", "count": len(out),
                 "ok": len(out) > 0, "note": f"#{tag} {len(listing)} 条 → 深读 {len(out)} 帖"}


def producthunt_today():
    d, m = run(["producthunt", "today"])
    return [_norm("producthunt", r, "today") for r in _rows(d)], \
        {"source": "opencli:producthunt", "count": len(_rows(d)), "ok": m["ok"],
         "note": m["note"]}


def upwork_search(query, per_page=30, sort="recency", location=""):
    """Upwork = 有人正在付钱找人做事。这是信噪比最高的付费需求证据。

    注意：该适配器**没有 --limit**，用的是 --per_page（10–50，且只支持单页）；
    传错参数会直接报 unknown option（实测踩过）。
    """
    args = ["upwork", "search", query, "--per_page", str(min(max(per_page, 10), 50)),
            "--sort", sort]
    if location:
        args += ["--location", location]
    d, m = run(args, timeout=180)
    rows = _rows(d)
    return [_norm("upwork", r, "search") for r in rows], \
        {"source": f"opencli:upwork[{query[:16]}]", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def hackernews(mode="show", limit=20):
    d, m = run(["hackernews", mode, "--limit", str(limit)])
    return [_norm("hn", r, mode) for r in _rows(d)], \
        {"source": f"opencli:hn:{mode}", "count": len(_rows(d)), "ok": m["ok"],
         "note": m["note"]}


if __name__ == "__main__":
    import sys
    print("代理:", proxy_url() or "未检测到")
    print("CLI:", cli_argv()[0])
    info = doctor()
    print("doctor:", json.dumps(info, ensure_ascii=False))
    tests = {
        "hn_show": lambda: hackernews("show", 3),
        "producthunt": lambda: producthunt_today(),
    }
    if len(sys.argv) > 1 and sys.argv[1] == "--with-browser":
        tests["reddit"] = lambda: reddit_subreddit("SaaS", 3)
    for name, fn in tests.items():
        rs, h = fn()
        print(f"\n[{name}] {json.dumps(h, ensure_ascii=False)}")
        for r in rs[:2]:
            print("   -", r["title"][:80])
            print("     ", r["text"][:140])


# ---------------------------------------------------------------- 第二批适配器
# 接入原则：能 public 的不登录；需要登录的（indeed/twitter/zhihu/xhs）未登录时
# 适配器会返回明确的 AUTH_REQUIRED，health 里可见，不静默吞掉。
# 采集频率刻意压低（每站每天几页），社交平台对自动化访问敏感。

def stackoverflow_tag(tag, limit=20, sort="hot"):
    """SO 某标签下的热门问题——"怎么才能做到 X"就是未满足需求。全 public。"""
    d, m = run(["stackoverflow", "tag", tag, "--sort", sort, "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("stackoverflow", r, f"#{tag}") for r in rows], \
        {"source": f"opencli:stackoverflow#{tag}", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def lobsters_tag(tag, limit=15):
    d, m = run(["lobsters", "tag", tag, "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("lobsters", r, f"#{tag}") for r in rows], \
        {"source": f"opencli:lobsters#{tag}", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def devto_tag(tag, limit=15):
    d, m = run(["devto", "tag", tag, "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("devto", r, f"#{tag}") for r in rows], \
        {"source": f"opencli:devto#{tag}", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def lesswrong_top(limit=10):
    d, m = run(["lesswrong", "top-week", "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("lesswrong", r, "top-week") for r in rows], \
        {"source": "opencli:lesswrong", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def indeed_search(query):
    """招聘搜索 = 企业在出钱招人做的事。注意该命令**没有 --limit**。

    实测返回结构只有元数据：{rank,id,title:"",company,location,salary,tags,url}——
    没有职位名和正文，所以必须用 company/salary/tags 自己拼 text，
    通用 _norm 拼出来是空的（首版踩坑：15 条全因"噪音/过短"被拦）。
    """
    d, m = run(["indeed", "search", query], timeout=180)
    rows = _rows(d)
    out = []
    for r in rows:
        comp = r.get("company") or "未知公司"
        sal = r.get("salary") or "薪资面议"
        loc = r.get("location") or ""
        tags = r.get("tags") or ""
        url = r.get("url", "")
        title = f"{comp} 招聘：{query}（{loc}）"
        text = (f"{title}. 薪资 {sal}；类型 {tags}。"
                f"企业正在出钱招人做「{query}」相关任务——该任务已被验证值得花钱。")
        out.append({
            "source": "indeed",
            "source_id": f"indeed:{r.get('id') or url}",
            "url": url,
            "title": title[:150],
            "text": text[:400],
            "site": "indeed:search",
            "salary": sal,
            "raw": {k: v for k, v in r.items() if not isinstance(v, (dict, list))},
            "collected_at": int(time.time()),
        })
    return out, {"source": f"opencli:indeed[{query[:14]}]", "count": len(out),
                 "ok": m["ok"], "note": m["note"]}


def zhihu_hot(limit=15):
    d, m = run(["zhihu", "hot", "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("zhihu", r, "hot") for r in rows], \
        {"source": "opencli:zhihu", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def twitter_search(query):
    """X 搜索透传原始操作符（lang:en / since: / -filter:replies 可用）。无 --limit。"""
    d, m = run(["twitter", "search", query], timeout=180)
    rows = _rows(d)
    return [_norm("twitter", r, "search") for r in rows], \
        {"source": f"opencli:twitter[{query[:20]}]", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}


def xhs_search(query, limit=15):
    d, m = run(["xiaohongshu", "search", query, "--limit", str(limit)])
    rows = _rows(d)
    return [_norm("xiaohongshu", r, "search") for r in rows], \
        {"source": f"opencli:xhs[{query[:12]}]", "count": len(rows),
         "ok": m["ok"], "note": m["note"]}
