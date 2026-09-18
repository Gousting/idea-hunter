# -*- coding: utf-8 -*-
"""
采集层：只负责"把原始信息拿回来"，不做任何判断。
三个信源全部零鉴权可用；GitHub 深度字段需要 token，缺失时自动降级。
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "idea-hunter/0.1 (+local research script)"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# ---------------------------------------------------------------- 本地代理
# Reddit 的实测结论（2026-09）：
#   · 未登录用户走机房/代理 IP 访问 HTML 页面 → 403 "Blocked"（网络策略拦截）。
#     实测 14 个节点全部失败、返回体长度完全一致 → 封的是整个 ASN 段而非单个 IP，
#     换节点没有用；但换到 RSS 端点就通了（见 reddit_rss）。
#   · RSS 端点 200 可用，速率限制很紧：连续几次请求即 429，约 45–90 秒后恢复。
#   · 国内直连不可达（Reddit 在国内网络本身不通），必须走本地代理。
PROXY_CANDIDATES = [
    os.environ.get("HUNTER_PROXY", ""),
    "http://127.0.0.1:7897",   # Clash Verge 混合端口
    "http://127.0.0.1:7890",   # Clash 经典端口
    "http://127.0.0.1:10809",  # v2rayN
    "http://127.0.0.1:1080",   # 通用
]
_PROXY_CACHE = {"v": "__unset__"}


def detect_proxy(probe_url="https://www.reddit.com/r/SaaS/.rss"):
    """探测本地可用代理。返回 proxy url；None 表示直连可用。"""
    if _PROXY_CACHE["v"] != "__unset__":
        return _PROXY_CACHE["v"]
    for cand in PROXY_CANDIDATES:
        if not cand:
            continue
        try:
            op = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": cand, "https": cand}))
            req = urllib.request.Request(probe_url, headers={"User-Agent": UA})
            with op.open(req, timeout=12) as r:
                if r.status == 200:
                    _PROXY_CACHE["v"] = cand
                    return cand
        except Exception:
            continue
    _PROXY_CACHE["v"] = None
    return None


def _get_proxied(url, timeout=25, retries=2, backoff=60):
    """走本地代理的 GET，带 429 退避。Reddit RSS 的限流恢复窗口约 45–90 秒。"""
    proxy = detect_proxy()
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    op = urllib.request.build_opener(*handlers)
    last = ""
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with op.open(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace"), r.status
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 403, 503) and i < retries:
                time.sleep(backoff * (i + 1))
                continue
            return "", e.code
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(3)
    return "", last



# ---------------------------------------------------------------- GitHub 查询缓存
# 为什么必须落盘（P0-3 实测教训）：GitHub 搜索 API 未认证限流约 **10 次/分钟**，
# 而一轮三窗口要发 ~35 次查询（拥挤度×方向 + 成型数 + 案例 + 仓库搜索 + 赏金），
# 实测 7d/30d 的仓库搜索直接被打成"请求失败"——**整个"开源供给"能力因此单点失效**，
# 连带把原生榜贡献率从 55% 拖到 19%（看起来像方法学退化，其实是上游限流）。
# 对策一：按 URL 落盘缓存，跨窗口/跨轮次复用（进程内 crowd_cache 出了进程就没了）。
# 对策二：限流时若有过期旧值，**用旧值而不是留空**（宁可陈旧也不能凭空缺数据），
#         并在返回值里带 stale 标记，让上层能如实报告"这条是旧数据"。
_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", ".gh_cache.json")
_CACHE_TTL = 6 * 3600          # 新鲜期 6 小时（同一天内重跑直接复用）
_CACHE_STALE_MAX = 7 * 86400   # 限流兜底：最多接受 7 天前的旧值
_cache = None


def _cache_load():
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _cache_save():
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except Exception:
        pass


def cache_stats():
    """缓存规模与新鲜度 —— 报告里如实展示"有多少答案来自缓存"。"""
    c = _cache_load()
    now = time.time()
    fresh = sum(1 for v in c.values() if now - v.get("t", 0) <= _CACHE_TTL)
    return {"entries": len(c), "fresh": fresh, "stale": len(c) - fresh,
            "file": _CACHE_FILE}


def _get(url, headers=None, retries=3, timeout=25, use_cache=True):
    """带退避 + 磁盘缓存的 GET（GitHub API）。

    返回 (body, headers)。body 为空字符串表示彻底失败（上层负责识别）。
    """
    hdrs = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if TOKEN:
        hdrs["Authorization"] = f"Bearer {TOKEN}"
    if headers:
        hdrs.update(headers)

    now = time.time()
    if use_cache:
        hit = _cache_load().get(url)
        if hit and now - hit.get("t", 0) <= _CACHE_TTL:
            return hit.get("body", ""), dict(hit.get("h") or {}, _cached="fresh")

    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
                if use_cache and body:
                    _cache_load()[url] = {"t": time.time(), "body": body,
                                          "h": dict(r.headers)}
                    _cache_save()
                return body, dict(r.headers)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            last = f"HTTP {e.code} {body[:120]}"
            if e.code in (403, 429):
                # 限流：先按 Retry-After / X-RateLimit-Reset 等，但不等超过 20s
                # （一轮里还有几十个查询要跑，把整轮拖死更糟）。多试几次不成，
                # 就走下面的"旧值兜底"。
                wait = 2 ** i * 5
                try:
                    ra = e.headers.get("Retry-After")
                    if ra:
                        wait = min(int(float(ra)), 20)
                    else:
                        rst = float(e.headers.get("X-RateLimit-Reset") or 0)
                        if rst:
                            wait = min(max(rst - time.time(), 1), 20)
                except Exception:
                    pass
                if i < retries - 1:
                    time.sleep(wait)
                    continue
            else:
                raise RuntimeError(last)
        except Exception as e:  # 网络类错误
            last = f"{type(e).__name__}: {e}"
            time.sleep(1.5 ** i)

    # 兜底：限流/网络失败但有旧值 → 用旧值（标记 stale），不静默留空
    if use_cache:
        hit = _cache_load().get(url)
        if hit and now - hit.get("t", 0) <= _CACHE_STALE_MAX:
            age_h = (now - hit["t"]) / 3600
            return hit.get("body", ""), {"X-IdeaHunter-Stale": f"{age_h:.1f}h"}
    raise RuntimeError(f"请求失败 {url} :: {last}")


# ---------------------------------------------------------------- GitHub Trending
# GitHub 官方没有任何 trending API（已核实），只能解析页面 HTML。
# 这是全链路最脆弱的一环：GitHub 改版即失效，所以必须做"解析结果自检"。
_BLOCK = re.compile(r'<article class="Box-row">(.*?)</article>', re.S)
_REPO = re.compile(r'<h2[^>]*>\s*<a[^>]*href="/([^"?]+)"', re.S)
_DESC = re.compile(r'<p class="col-9 color-fg-muted my-1 pr-4">(.*?)</p>', re.S)
_TOTAL_STAR = re.compile(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', re.S)
_FORK = re.compile(r'href="/[^"]+/forks"[^>]*>(.*?)</a>', re.S)
_LANG = re.compile(r'itemprop="programmingLanguage">(.*?)<', re.S)
_PERIOD = re.compile(r'([\d,]+)\s+stars\s+(?:today|this week|this month)')


def _num(s):
    if not s:
        return 0
    s = re.sub(r"<[^>]+>", "", s).strip().replace(",", "")
    m = re.match(r"^([\d.]+)k$", s, re.I)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.match(r"^([\d.]+)$", s)
    return int(m.group(1)) if m else 0


def github_trending(since="weekly", language="", expect_min=10):
    """抓 Trending 榜。返回 (repos, health)。health.min_count 不达标 → 说明页面结构变了。"""
    url = "https://github.com/trending"
    if language:
        url += "/" + urllib.parse.quote(language)
    url += f"?since={since}"
    html, _ = _get(url, headers={"Accept": "text/html"})
    out = []
    for blk in _BLOCK.findall(html):
        m = _REPO.search(blk)
        if not m:
            continue
        full = m.group(1).strip().strip("/")
        if full.count("/") != 1:
            continue
        t = _TOTAL_STAR.search(blk)
        f = _FORK.search(blk)
        p = _PERIOD.search(blk)
        d = _DESC.search(blk)
        lg = _LANG.search(blk)
        out.append({
            "source": "github_trending",
            "source_id": f"trending:{since}:{full}",
            "repo": full,
            "url": f"https://github.com/{full}",
            "title": full,
            "text": re.sub(r"<[^>]+>", " ", d.group(1)).strip() if d else "",
            "language": re.sub(r"<[^>]+>", "", lg.group(1)).strip() if lg else "",
            "stars_total": _num(t.group(1)) if t else 0,
            "forks": _num(f.group(1)) if f else 0,
            "stars_window": _num(p.group(1)) if p else 0,
            "window": since,
            "collected_at": int(time.time()),
        })
    # 自检：抓到 0 条或明显偏少，说明选择器失效，必须报警而不是静默返回空
    health = {"source": "github_trending", "count": len(out),
              "ok": len(out) >= expect_min,
              "note": "" if len(out) >= expect_min else f"仅解析到 {len(out)} 条，疑页面结构变更"}
    return out, health


# ---------------------------------------------------------------- GitHub Issues
# 方法论的核心环节："开源内核很强、但门槛极高"的机会点藏在 Issues 的吐槽里。
# 只取有讨论度的 issue（评论数为门控），因为零评论的 issue 往往是随手提的。
ISSUE_SIGNAL = re.compile(
    r"(how (do|can) i|is there (a|any) way|no way to|only (works?|available) "
    r"(in|on|via|through)|command[- ]?line|cli only|no gui|no (web )?ui|"
    r"too (complex|heavy|slow|hard)|confus(ing|ed)|documentation is|docs are|"
    r"would (love|like) to|please add|feature request|support for|"
    r"docker|kubernetes|deploy|install(ation)? (fail|error|problem)|"
    r"windows support|local (run|llm|mode)|self[- ]host)", re.I)


def github_issues(repo, limit=15, min_comments=2):
    """抓仓库里讨论热度最高的 issue —— 真实用户的抱怨集中地。
    走 search API：未认证 10 req/min，认证 30 req/min。只对 Top N 仓库调用。

    两级降级：先用评论数门槛过滤（过滤随手提的 issue），若返回空则放宽，
    因为"新项目 issue 少"是常态，不能因此把整个仓库判为无价值。
    """
    for mc in (min_comments, 0):
        q = f"repo:{repo} is:issue" + (f" comments:>{mc}" if mc else "")
        url = ("https://api.github.com/search/issues?q=" + urllib.parse.quote(q)
               + f"&sort=comments&order=desc&per_page={limit}")
        try:
            raw, _ = _get(url)
            data = json.loads(raw)
        except Exception as e:
            return [], f"issue 抓取失败 {e}"
        items = data.get("items", [])
        if items:
            break
    out = []
    for it in items:
        body = (it.get("body") or "")[:900]
        blob = f"{it.get('title', '')} {body}"
        hits = sorted(set(m.group(0).lower() for m in ISSUE_SIGNAL.finditer(blob)))
        # 正则只是降噪器，不是闸门：高讨论度的 issue 即便不命中关键词也放行，
        # 交由 LLM 判定。把闸门设成"必须命中正则"会让召回塌成 0（实测踩过）。
        if not hits and (it.get("comments") or 0) < 5:
            continue
        out.append({
            "source": "github_issue",
            "source_id": f"issue:{repo}#{it['number']}",
            "repo": repo,
            "url": it["html_url"],
            "title": it["title"][:180],
            "text": " ".join(blob.split()),
            "comments": it.get("comments", 0),
            "issue_state": it.get("state"),
            "issue_created": it.get("created_at", ""),
            "issue_updated": it.get("updated_at", ""),
            "signal_hits": hits,
            "collected_at": int(time.time()),
        })
    return out, ""


# ---------------------------------------------------------------- GitHub Search
def github_search_new_rising(days=21, min_stars=80, per_page=50, pages=1):
    """Search API 是 trending 的官方替代：找"刚创建就起量"的仓库。
    未认证 10 req/min，认证 30 req/min。"""
    since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
    out = []
    for pg in range(1, pages + 1):
        q = f"created:>{since} stars:>{min_stars}"
        url = ("https://api.github.com/search/repositories?q="
               + urllib.parse.quote(q)
               + f"&sort=stars&order=desc&per_page={per_page}&page={pg}")
        raw, _ = _get(url)
        data = json.loads(raw)
        for i in data.get("items", []):
            out.append({
                "source": "github_search",
                "source_id": f"search:{i['full_name']}",
                "repo": i["full_name"],
                "url": i["html_url"],
                "title": i["full_name"],
                "text": i.get("description") or "",
                "language": i.get("language") or "",
                "stars_total": i.get("stargazers_count", 0),
                "forks": i.get("forks_count", 0),
                "watchers": i.get("subscribers_count", 0),
                "open_issues": i.get("open_issues_count", 0),
                "created_at": i.get("created_at", ""),
                "pushed_at": i.get("pushed_at", ""),
                "license": (i.get("license") or {}).get("spdx_id"),
                "topics": i.get("topics", []),
                "stars_window": i.get("stargazers_count", 0),  # 全生命周期即窗口
                "window": f"created<={days}d",
                "collected_at": int(time.time()),
            })
        time.sleep(6.5)  # 未认证 Search 10/min，留余量
    note = ("" if out else
            f"0 条：created:>{since} 且 stars>{min_stars}。"
            "GitHub 的 created 是日期粒度且索引有延迟，窗口过短必然为空（实测 1 天=0 条，2 天=31 条）")
    return out, {"source": "github_search", "count": len(out), "ok": len(out) > 0,
                 "note": note}


# ---------------------------------------------------------------- Hacker News
def hn_search(term, days=365, tags="(story,comment)", per_page=20):
    """交叉验证：某个技术方向/项目在 HN 上被讨论过多少、口径如何。
    对应方法论里的"GitHub 看到上升项目 → 去社区搜吐槽"这一步。"""
    cut = int(time.time()) - days * 86400
    url = ("https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote(term)
           + f"&tags={urllib.parse.quote(tags)}&hitsPerPage={per_page}"
           + f"&numericFilters=created_at_i>{cut}")
    try:
        raw, _ = _get(url)
        d = json.loads(raw)
    except Exception as e:
        return {"term": term, "count": 0, "sample": [], "error": str(e)}
    sample = []
    for h in d.get("hits", [])[:5]:
        txt = re.sub(r"<[^>]+>", " ", (h.get("comment_text") or h.get("title") or ""))
        sample.append({"date": (h.get("created_at") or "")[:10],
                       "text": " ".join(txt.split())[:200],
                       "url": f"https://news.ycombinator.com/item?id={h.get('objectID')}"})
    return {"term": term, "count": d.get("nbHits", 0), "sample": sample}


# ---------------------------------------------------------------- Reddit (RSS)
# 关键：不要用 HTML 页面。未登录访问 www.reddit.com/r/xxx/ 会 403 Blocked
# （网络策略，换节点无效）；而 /r/xxx/.rss 返回 200。
# 局限：每个子版块最多 25 条、只有帖子正文没有评论、限流很紧（见 _get_proxied）。
# 合规定位：RSS 是 Reddit 官方公开订阅端点，仅用于个人研究判断，不做批量分发或产品化。
REDDIT_SUBS = ["SaaS", "microsaas", "SideProject", "selfhosted", "Entrepreneur"]
_ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
_X = {
    "title": re.compile(r"<title>(.*?)</title>", re.S),
    "link": re.compile(r'<link href="([^"]+)"'),
    "author": re.compile(r"<name>(.*?)</name>", re.S),
    "updated": re.compile(r"<updated>(.*?)</updated>", re.S),
    "content": re.compile(r"<content[^>]*>(.*?)</content>", re.S),
    "id": re.compile(r"<id>(.*?)</id>", re.S),
}


def _strip_html(s):
    import html as _h
    s = _h.unescape(_h.unescape(s or ""))
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</p>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"submitted by.*$", "", s, flags=re.S)  # 去掉 RSS 附带的样板尾巴
    return " ".join(s.split())


def reddit_rss(subs=None, sort="", window="", spacing=22):
    """抓子版块 RSS。spacing 是请求间隔秒数，默认 22s —— 限流很紧，别调小。"""
    subs = subs or REDDIT_SUBS
    out, errs = [], []
    for i, sub in enumerate(subs):
        if sort and window:
            url = f"https://www.reddit.com/r/{sub}/{sort}/.rss?t={window}"
        elif sort:
            url = f"https://www.reddit.com/r/{sub}/{sort}/.rss"
        else:
            url = f"https://www.reddit.com/r/{sub}/.rss"
        body, status = _get_proxied(url)
        if status != 200 or not body:
            errs.append(f"{sub}: {status}")
        else:
            for e in _ENTRY.findall(body):
                g = lambda k: (_X[k].search(e).group(1).strip()
                               if _X[k].search(e) else "")
                title = _strip_html(g("title"))
                # Reddit 的标题往往就是痛点本身（"How do I get my first paying
                # customer?"），所以把标题并入正文一起参与信号判断，否则会漏。
                text = f"{title}. {_strip_html(g('content'))}"
                out.append({
                    "source": "reddit",
                    "source_id": f"reddit:{g('id') or g('link')}",
                    "repo": "",
                    "url": g("link"),
                    "title": title[:200],
                    "text": text[:2000],
                    "author": g("author"),
                    "subreddit": sub,
                    "created_at": g("updated"),
                    "collected_at": int(time.time()),
                })
        if i < len(subs) - 1:
            time.sleep(spacing)  # 限流很紧，必须间隔
    note = "；".join(errs) if errs else ""
    return out, {"source": "reddit", "count": len(out),
                 "ok": len(out) > 0,
                 "note": (note or f"{len(subs)} 个子版块")}


def github_bounties(label="bounty", per_page=40, min_amount_note=True):
    """GitHub 赏金 Issue —— **Upwork 的免登录等效源**。

    为什么它能替代 Upwork：赏金 issue 是"有人出钱请人做这件事"的直接证据，
    且 money 就写在标题/正文里（实测有 $3000 这类明确金额），不需要任何登录态、
    不依赖第三方平台的商业 API（Upwork 通道 100% 失败、Reddit 2026-05 开始封未认证访问）。

    两个必须踩对的口径（都实测踩过）：
      · source 必须独立成 "github_bounty"，**不能复用 "github_search"**——
        后者属于 REPO_SOURCES，会走仓库通道，而 issue 没有星标 → 全部被
        "星标低于门槛"丢掉（实测 5/5 全丢，等效源形同虚设）。
      · 标签由我选（label:bounty），所以它不是"平台热榜"意义上的独立发现，
        path 记为 keyword：它提供的是**付费证据**，不是共振证据。
    """
    q = f"label:{label} state:open"
    url = ("https://api.github.com/search/issues?q=" + urllib.parse.quote(q)
           + f"&sort=created&order=desc&per_page={per_page}")
    try:
        raw, _ = _get(url)
        items = (json.loads(raw).get("items") or [])[:per_page]
    except Exception as e:
        return [], {"source": f"opencli:github_bounties[{label}]", "count": 0,
                    "ok": False, "note": str(e)[:100]}
    out = []
    for it in items:
        title = (it.get("title") or "")[:180]
        body = " ".join((it.get("body") or "").split())[:600]
        repo = (it.get("repository_url") or "").replace("https://api.github.com/repos/", "")
        out.append({
            "source": "github_bounty", "source_id": f"github_bounty:{it.get('id')}",
            "repo": repo, "url": it.get("html_url", ""),
            "title": title,
            "text": f"{title}. {body}"[:2000],
            "topic_text": f"{title} {body[:200]}"[:600],
            "site": f"github:bounty:{label}", "path": "keyword",
            "heat": {"score": int(it.get("comments") or 0) * 5, "comments": int(it.get("comments") or 0)},
            "stars_total": 0, "created_at": (it.get("created_at") or "")[:10],
            "collected_at": int(time.time()),
        })
    return out, {"source": f"opencli:github_bounties[{label}]", "count": len(out),
                 "ok": len(out) > 0,
                 "note": f"开放赏金 {len(out)} 条（免登录，付费证据/非独立发现）"}


def bluesky_trending(limit=20):
    """Bluesky 热门话题（public，免登录）—— Twitter 认证失败时的**弱等效**。

    诚实定位：它只提供"热门话题"，**不能按关键词搜帖**（该适配器 search 只搜用户）。
    所以它能对冲"完全没信号"，但覆盖不了"创始人原话"这块。
    """
    import subprocess
    try:
        from hunter import opencli as _oc
        d, m = _run_bluesky(limit)
        rows = _oc._rows(d)
    except Exception as e:
        return [], {"source": "opencli:bluesky:trending", "count": 0, "ok": False,
                    "note": str(e)[:100]}
    # 注意两处坑（实测）：
    # ① 字段名是 topic/link/rank（不是 title/url），按 _norm 的候选键取会拿到空标题；
    # ② 必须给一个**显式热度**——该接口只有 rank，没有点数/票数，
    #    而下游热点通道要靠热度阈值放行，heat=0 会导致「采到了但一条都进不去」
    #    （等效源声称覆盖但实际零贡献，这是最隐蔽的一种假覆盖）。
    #    所以把 rank 转成代理热度（与 Product Hunt 同一处理），并在报告口径里标注。
    out = []
    for r in rows:
        topic = r.get("topic") or ""
        if not topic:
            continue
        rank = int(r.get("rank") or 0)
        out.append(_norm_generic("bluesky", {
            "title": topic, "url": ("https://bsky.app" + r["link"]) if r.get("link") else "",
            "id": r.get("link") or topic[:40], "rank": rank,
            "score": max(1, 26 - rank) * 5 if rank else 0},
            "bluesky:trending", path="platform"))
    return out, {"source": "opencli:bluesky:trending", "count": len(out),
                 "ok": len(out) > 0,
                 "note": "免登录弱等效（仅热门话题，不可按关键词搜；内容偏新闻，价值低）"}


def _norm_generic(src, d, site="", path="platform"):
    """轻量归一化（给字段名特殊的站点用）。"""
    from hunter import opencli as _oc
    return _oc._norm(src, d, site, path=path)


def _run_bluesky(limit=20):
    from hunter import opencli as _oc
    return _oc.run(["bluesky", "trending", "--limit", str(limit)])


def github_count(keywords, min_stars=50):
    """查某关键词组合下 GitHub 的存量项目数 —— 拥挤度的供给侧指标。

    注意口径：GitHub 搜索是多词 AND，且这里过滤 stars:>N（只算"真项目"）。
    所以这个数字强烈依赖关键词的选择，只能作相对比较的粗代理，
    不能当绝对市场规模读。阈值按实测分布定（见 directions.CROWD_LEVELS）。
    """
    q = f"{keywords} stars:>{min_stars}"
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + "&per_page=1")
    try:
        raw, hdr = _get(url)
        note = ""
        if hdr.get("X-IdeaHunter-Stale"):
            note = f"（限流兜底：用了 {hdr['X-IdeaHunter-Stale']} 前的旧值）"
        return int(json.loads(raw).get("total_count", 0)), note
    except Exception as e:
        return None, str(e)[:100]


def github_mature_count(keywords, min_stars=1000):
    """某方向「已成型产品」的存量数 —— 判断"有没有人已经做成"。

    口径说明（必须披露）：只看**开源**项目。闭源商业 SaaS（大多数赚钱的产品）
    这里看不到，所以 0 不等于"市场空白"，只等于"开源侧没人做成"。
    """
    q = f"{keywords} stars:>{min_stars}"
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + "&per_page=1")
    try:
        raw, hdr = _get(url)
        note = ""
        if hdr.get("X-IdeaHunter-Stale"):
            note = f"（限流兜底：用了 {hdr['X-IdeaHunter-Stale']} 前的旧值）"
        return int(json.loads(raw).get("total_count", 0)), note
    except Exception as e:
        return None, str(e)[:100]


def github_mature(keywords, min_stars=300, per_page=3):
    """查某方向「成熟/高关注」的真实项目 —— 按星标全量排序，不看时间窗。

    为什么需要：Trending/Search 只抓"新增"，用户看到方向后需要能点开
    已经做大做熟的项目来验证赛道成色（有没有人做成过、做成了什么样）。
    返回 [{repo, url, stars, desc, updated}]；失败返回 (None, err)。
    """
    q = f"{keywords} stars:>{min_stars}"
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q)
           + f"&sort=stars&order=desc&per_page={per_page}")
    try:
        raw, _ = _get(url)
        items = (json.loads(raw).get("items") or [])[:per_page]
        return [{"repo": it.get("full_name", ""),
                 "url": it.get("html_url", ""),
                 "stars": it.get("stargazers_count", 0),
                 "desc": (it.get("description") or "")[:110],
                 "updated": (it.get("pushed_at") or "")[:10]}
                for it in items], ""
    except Exception as e:
        return None, str(e)[:100]


def hn_pain_points(queries, days=120, per_page=40):
    """HN Algolia 免费、无需鉴权、可按时间过滤。
    注意：Algolia 是全文倒排匹配，召回很脏（实测 "willing to pay" 命中 265 条里大量无关），
    这一层刻意只做召回、不做判断——脏活交给后面的规则+LLM。"""
    cut = int(time.time()) - days * 86400
    out = []
    for q in queries:
        url = ("https://hn.algolia.com/api/v1/search?query="
               + urllib.parse.quote(q)
               + f"&tags=comment&hitsPerPage={per_page}"
               + f"&numericFilters=created_at_i>{cut}")
        try:
            raw, _ = _get(url)
        except Exception as e:
            out.append({"source": "hn", "source_id": f"hn:ERR:{q}", "error": str(e)})
            continue
        data = json.loads(raw)
        for h in data.get("hits", []):
            txt = re.sub(r"<[^>]+>", " ", h.get("comment_text") or "")
            txt = urllib.parse.unquote(txt)
            txt = " ".join(txt.split())
            if len(txt) < 60:
                continue
            oid = h.get("objectID")
            out.append({
                "source": "hn",
                "source_id": f"hn:{oid}",
                "path": "keyword",
                "repo": "",
                "url": f"https://news.ycombinator.com/item?id={oid}",
                "title": (h.get("story_title") or "")[:160],
                "text": txt[:1600],
                "author": h.get("author"),
                "points": h.get("points"),
                # 讨论热度统一成 heat（HN 的 Algolia 命中里 points/num_comments
                # 经常为空，取不到就留 0，别假装有）
                "heat": {"score": h.get("points") or 0,
                         "comments": h.get("num_comments") or 0},
                "created_at": h.get("created_at", ""),
                "query": q,
                "collected_at": int(time.time()),
            })
        time.sleep(0.7)
    return out, {"source": "hn", "count": len(out), "ok": len(out) > 0, "note": ""}
