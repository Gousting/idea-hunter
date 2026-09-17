# -*- coding: utf-8 -*-
"""
浏览器通道（替代性采集方式）

【为什么需要这一层】
官方 API 覆盖不到两种站点：① 根本没有 API 的（Indie Hackers 等社区）；
② API 有严格商用条款的（Product Hunt 等）。浏览器通道用"读页面"的方式补上。

【实测结论，别抱错期望】
- 能读到：Indie Hackers、GitHub、HN 等免验证站点 —— 这是本层的主要价值。
- 读不到：Cloudflare 保护站点（Product Hunt / V2EX 等）会返回安全验证页；
  Reddit 在部分网络下直接返回 Blocked（且国内网络本身不通）。
  这两类都必须**明确报错**，绝不能静默返回空内容当作"没有数据"。
- 本层无法突破网络层封锁（如 Reddit 的 IP 级拦截），只能靠代理，不要在这上面浪费时间。

【实现说明】
本机可用的是 browser-use CLI 3.0：从 stdin 读 Python 片段，在常驻会话里执行，
通过 CDP 附着到浏览器。若安装了 opencli（把网站映射成子命令的同类工具），
可用 SITE_MAP 里同名的命令替换 —— 两者定位一致，选一个即可。
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

CDP_PORT = int(os.environ.get("BU_CDP_PORT", "9222"))
CDP_URL = os.environ.get("BU_CDP_URL", f"http://127.0.0.1:{CDP_PORT}")
PROFILE_DIR = os.environ.get(
    "BU_PROFILE_DIR", os.path.expanduser(r"~\.config\browser-harness\cdp-profile"))

# 反爬验证页识别：命中即判定为"被拦截"，不是"页面为空"
CHALLENGE_MARKERS = (
    "安全验证", "请稍候", "Just a moment", "Attention Required",
    "Checking your browser", "cf-browser-verification", "Blocked",
    "Enable JavaScript and cookies to continue", "正在确认您是真人",
)


def cdp_alive(timeout=4):
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=timeout) as r:
            return "webSocketDebuggerUrl" in r.read().decode("utf-8", "replace")
    except Exception:
        return False


def launch_cdp_chrome():
    """起一个带调试端口的独立 Chrome 实例（独立 profile，不影响用户正在用的窗口）。"""
    candidates = [
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    exe = next((c for c in candidates if os.path.isfile(c)), None)
    if not exe:
        raise RuntimeError("未找到 Chrome/Edge，请手动启动带 --remote-debugging-port 的实例")
    os.makedirs(PROFILE_DIR, exist_ok=True)
    flags = [exe, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
             f"--user-data-dir={PROFILE_DIR}", "--no-first-run",
             "--no-default-browser-check", "--disable-gpu", "about:blank"]
    creation = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(flags, creationflags=creation,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(1)
        if cdp_alive():
            return True
    raise RuntimeError("Chrome 调试端口未就绪，检查端口是否被占用")


def ensure_cdp(auto_launch=True):
    if cdp_alive():
        return "已有实例"
    if not auto_launch:
        raise RuntimeError(
            f"CDP 不可用（{CDP_URL}）。请启动 Chrome 时加 --remote-debugging-port={CDP_PORT}，"
            "或设置 BU_CDP_URL / BU_CDP_WS 指向已有浏览器")
    launch_cdp_chrome()
    return "已自动启动"


def _cli():
    exe = shutil.which("browser-use")
    if not exe:
        raise RuntimeError("未找到 browser-use CLI。安装：pip install browser-use")
    return exe


def _run_script(body, timeout=180):
    """把 Python 片段喂给 browser-use CLI，返回它打印的 JSON 行。"""
    env = dict(os.environ, BU_CDP_URL=CDP_URL)
    p = subprocess.run([_cli()], input=body, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    out = []
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out, (p.stderr or "")[-500:]


READ_SCRIPT = r'''
import json, time, sys
urls = json.loads({urls_json!r})
for u in urls:
    rec = {{"url": u, "ok": False}}
    for attempt in (1, 2):
        try:
            new_tab(u)
            wait_for_load()
            time.sleep({wait})
            rec["title"] = js("document.title") or ""
            rec["text"] = js("document.body ? document.body.innerText : ''") or ""
            rec["links"] = js(
                "Array.from(document.querySelectorAll('a[href]'))"
                ".map(a => [a.href, (a.innerText||'').trim().slice(0,160)])"
                ".filter(p => p[1].length > 12).slice(0, {max_links})") or []
            rec["ok"] = True
            break
        except Exception as e:
            rec["error"] = f"{{type(e).__name__}}: {{e}}"
            time.sleep(1)
    print(json.dumps(rec, ensure_ascii=False))
'''


def _clean_title(s):
    """浏览器工具会在 document.title 前注入一个标记字符，入库前清掉。"""
    s = (s or "").strip()
    return s.lstrip("🐴").strip()


def read_pages(urls, wait=3, max_links=60, timeout=300):
    """读取若干页面，返回 [{url,title,text,links,ok,blocked,error}]。"""
    script = READ_SCRIPT.format(urls_json=json.dumps(urls), wait=wait,
                               max_links=max_links)
    recs, err = _run_script(script, timeout=timeout)
    by_url = {r.get("url"): r for r in recs}
    out = []
    for u in urls:
        r = by_url.get(u) or {"url": u, "ok": False, "error": err or "无返回"}
        txt = r.get("text") or ""
        r["title"] = _clean_title(r.get("title"))
        blob = f"{r.get('title','')} {txt[:300]}"
        # 关键：被反爬拦截必须显式标记，不能和"页面确实没内容"混为一谈
        hit = next((m for m in CHALLENGE_MARKERS if m.lower() in blob.lower()), None)
        r["blocked"] = bool(hit)
        r["block_reason"] = hit or ""
        if r["blocked"]:
            r["ok"] = False
        out.append(r)
    return out


# ---------------------------------------------------------------- 站点配置
# selector: 从列表页里挑出值得深读的详情页链接
SITES = {
    "indiehackers": {
        "list_url": "https://www.indiehackers.com/",
        "match": ("/post/",),
        "note": "独立开发者社区：讨论'做不出增长/找不到需求'的原话最多",
    },
    "hn_ask": {
        "list_url": "https://news.ycombinator.com/ask",
        "match": ("item?id=",),
        "note": "Ask HN：提问里常直接暴露未满足需求",
    },
    "reddit_html": {
        # 这条通道**必须带登录态**：未登录访问 HTML 会被网络策略拦截（403 Blocked），
        # RSS 能拿到帖子正文但拿不到评论，而评论才是抱怨最集中的地方。
        "list_url": "https://www.reddit.com/r/SaaS/hot/",
        "match": ("/comments/",),
        "note": "Reddit HTML + 评论（需登录态，见 prepare_logged_in_profile）",
    },
}


# ---------------------------------------------------------------- 登录态复用
# 背景：Chrome 136+ 出于防 cookie 窃取，禁止在默认 user-data-dir 上开远程调试，
# 且 Chrome 运行期间会**独占锁定** cookie 数据库（实测 PermissionError）。
# 所以复用登录态的唯一可靠路径是：先完全退出 Chrome → 复制最小文件集到独立目录
# → 用该目录启动带调试端口的实例。
REAL_PROFILE = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
LOGIN_FILES = [
    "Local State",                          # cookie 加密密钥（DPAPI 绑定当前用户）
    r"Default\Network\Cookies",             # 实际 cookie（Chrome 96+ 路径）
    r"Default\Preferences",
    r"Default\Login Data",
]


def prepare_logged_in_profile(dst_dir=None):
    """把真实 Chrome 的登录态复制到独立调试目录。返回 (ok, 说明)。

    只复制维持登录所需的最小文件集，不复制书签/历史/扩展数据。
    若 Chrome 仍在运行，cookie 库被独占锁定 → 会明确报错要求先退出 Chrome。
    """
    dst_dir = dst_dir or PROFILE_DIR
    copied, skipped = [], []
    for rel in LOGIN_FILES:
        src = os.path.join(REAL_PROFILE, rel)
        if not os.path.isfile(src):
            skipped.append(rel)
            continue
        dst = os.path.join(dst_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copy2(src, dst)
            copied.append(rel)
        except PermissionError:
            return False, ("无法读取 cookie 数据库：Chrome 正在运行并独占锁定该文件。"
                           "请先**完全退出 Chrome**（含后台进程），再重试。")
        except Exception as e:
            return False, f"复制失败 {rel}: {type(e).__name__} {e}"
    if not copied:
        return False, "未找到可复制的登录态文件，请确认 Chrome 已登录过目标站点"
    return True, f"已复制 {len(copied)} 个文件：{', '.join(copied)}" + \
                 (f"（缺失 {len(skipped)} 个，非致命）" if skipped else "")


def login_domains(dst_dir=None):
    """列出（独立目录中）已登录的域名 —— 只读 host_key 与条数，不解密任何值。"""
    dst_dir = dst_dir or PROFILE_DIR
    db = os.path.join(dst_dir, r"Default\Network\Cookies")
    if not os.path.isfile(db):
        return {}
    tmp = os.path.join(os.environ.get("TEMP", "."), "bu_ck_probe.db")
    try:
        shutil.copy(db, tmp)
        import sqlite3
        c = sqlite3.connect(tmp)
        rows = c.execute("SELECT host_key, COUNT(*) FROM cookies GROUP BY host_key").fetchall()
        c.close()
        return {h: n for h, n in rows}
    except Exception:
        return {}
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def login_report(domains=("reddit.com", "producthunt.com", "g2.com", "v2ex.com")):
    d = login_domains()
    out = []
    for dom in domains:
        n = sum(cnt for h, cnt in d.items() if h.endswith(dom))
        out.append({"domain": dom, "cookies": n, "logged_in": n > 0})
    return out


def collect_reddit_html(sub="SaaS", max_detail=5):
    """带登录态读 Reddit 帖子页（含评论）。未登录时会明确报 403，不会静默返回空。"""
    cfg = SITES["reddit_html"]
    try:
        ensure_cdp()
    except Exception as e:
        return [], {"source": "browser:reddit", "count": 0, "ok": False, "note": str(e)}
    listing = read_pages([f"https://www.reddit.com/r/{sub}/hot/"], max_links=60)[0]
    if not listing.get("ok"):
        reason = listing.get("block_reason") or listing.get("error")
        hint = "（需登录态：先执行 prepare_logged_in_profile 并重启调试实例）" \
            if listing.get("blocked") else ""
        return [], {"source": "browser:reddit", "count": 0, "ok": False,
                    "note": f"列表页失败：{reason}{hint}"}
    seen, picked = set(), []
    for href, txt in (listing.get("links") or []):
        if "/comments/" not in href or href in seen:
            continue
        seen.add(href)
        picked.append(href)
        if len(picked) >= max_detail:
            break
    out = []
    if picked:
        for pg in read_pages(picked, wait=2, max_links=5):
            body = pg.get("text") or ""
            if not pg.get("ok") or len(body) < 300:
                continue
            out.append({
                "source": "browser",
                "source_id": f"browser:reddit:{pg['url']}",
                "repo": "",
                "url": pg["url"],
                "title": (pg.get("title") or "")[:180],
                "text": " ".join(body.split())[:2500],
                "site": f"reddit:{sub}",
                "collected_at": int(time.time()),
            })
    return out, {"source": "browser:reddit", "count": len(out), "ok": len(out) > 0,
                 "note": f"r/{sub} 深读 {len(picked)} 篇（含评论）"}


def collect_site(site_key, max_detail=6, max_links=60):
    """抓一个站点：列表页 → 挑详情页 → 深读。返回 (记录列表, 健康信息)。"""
    cfg = SITES[site_key]
    try:
        ensure_cdp()
    except Exception as e:
        return [], {"source": f"browser:{site_key}", "count": 0, "ok": False,
                    "note": f"浏览器不可用 {e}"}

    listing = read_pages([cfg["list_url"]], max_links=max_links)[0]
    if not listing.get("ok"):
        return [], {"source": f"browser:{site_key}", "count": 0, "ok": False,
                    "note": f"列表页失败：{listing.get('block_reason') or listing.get('error')}"}

    cand = [(href, txt) for href, txt in (listing.get("links") or [])
            if any(m in href for m in cfg["match"])]
    seen, picked = set(), []
    for href, txt in cand:
        if href in seen:
            continue
        seen.add(href)
        picked.append((href, txt))
        if len(picked) >= max_detail:
            break

    out = []
    if picked:
        pages = read_pages([h for h, _ in picked], wait=2, max_links=10)
        for (href, txt), pg in zip(picked, pages):
            body = pg.get("text") or ""
            if not pg.get("ok") or len(body) < 200:
                continue
            out.append({
                "source": "browser",
                "source_id": f"browser:{site_key}:{href}",
                "repo": "",
                "url": href,
                "title": (pg.get("title") or txt)[:180],
                "text": " ".join(body.split())[:2000],
                "site": site_key,
                "collected_at": int(time.time()),
            })
    health = {"source": f"browser:{site_key}", "count": len(out),
              "ok": len(out) > 0,
              "note": f"列表页 {len(listing.get('links') or [])} 链接 / 深读 {len(picked)}" }
    return out, health


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="浏览器通道工具")
    ap.add_argument("cmd", choices=["collect", "login-setup", "login-check", "reddit"],
                    help="collect=抓站点；login-setup=复制登录态；"
                         "login-check=检查登录态；reddit=读 Reddit HTML+评论")
    ap.add_argument("--site", default="indiehackers")
    ap.add_argument("--sub", default="SaaS")
    a = ap.parse_args()

    if a.cmd == "login-setup":
        ok, msg = prepare_logged_in_profile()
        print(("OK  " if ok else "FAIL ") + msg)
        if ok:
            for r in login_report():
                print(f"  {r['domain']:<22} cookies={r['cookies']:<4} "
                      f"{'已登录' if r['logged_in'] else '未登录'}")
    elif a.cmd == "login-check":
        for r in login_report():
            print(f"  {r['domain']:<22} cookies={r['cookies']:<4} "
                  f"{'已登录' if r['logged_in'] else '未登录'}")
    elif a.cmd == "reddit":
        rs, h = collect_reddit_html(a.sub)
        print(json.dumps(h, ensure_ascii=False))
        for r in rs[:3]:
            print("-", r["title"][:90])
            print("   ", r["text"][:200])
    else:
        rs, h = collect_site(a.site)
        print(json.dumps(h, ensure_ascii=False))
        for r in rs[:3]:
            print("-", r["title"][:90])
            print("   ", r["text"][:160])
