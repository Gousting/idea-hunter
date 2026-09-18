#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 directions_*.json 渲染成可交互的可视化看板（单文件 HTML）。

为什么不用截图/静态图：看板要能悬停看数值、点图例过滤、切窗口对比，
ECharts 单文件 + 内联数据最合适；不用任何构建工具，Python 直接吐 HTML。

用法：
  python tools/render_dashboard.py                 # 取最新一份 directions_*.json
  python tools/render_dashboard.py --json <path>   # 指定报告

图表选择（对着"用户要回答的问题"设计，不为炫技）：
  1. 机会象限散点   —— "哪些方向热但拥挤、哪些稀疏但没人做"（x=热度 y=拥挤 log）
  2. 机会分条形     —— "综合排序到底谁先谁后"（含拥挤度着色，红海一眼可见）
  3. 平台支撑热力图 —— "这个方向是单平台噪音还是多平台共振"
  4. 平台占比环形   —— "本窗口的数据都是谁贡献的"（平台偏差提醒）
"""
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

PLATFORM_SHORT = {
    "github_trending": "GT·Trending", "github_search": "GS·Search",
    "github_issue": "GI·Issues", "hn": "HN", "reddit": "Reddit",
    "producthunt": "ProductHunt", "upwork": "Upwork", "browser": "浏览器",
    "stackoverflow": "StackOverflow", "lobsters": "Lobsters", "devto": "DEV.to",
    "lesswrong": "LessWrong", "indeed": "Indeed", "twitter": "X/Twitter",
    "zhihu": "知乎", "xiaohongshu": "小红书",
}
CROWD_COLOR = {"红海": "#d9534f", "拥挤": "#f0ad4e",
               "中等": "#4da3d9", "稀疏": "#5cb85c"}


def latest(pattern):
    c = sorted(glob.glob(os.path.join(OUT, pattern)))
    return c[-1] if c else None


def load_annotations():
    p = os.path.join(OUT, "agent_annotations.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build(json_path, cache_path, ann):
    with open(json_path, encoding="utf-8") as f:
        rep = json.load(f)
    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)
    sys.path.insert(0, ROOT)
    from hunter import directions as dr

    data = {"generated_at": rep.get("generated_at", ""),
            "windows": [], "health": rep.get("health", [])}
    for key, win in rep["windows"].items():
        kept = cache.get("windows", {}).get(key, {}).get("kept", [])
        # 与报告一致：应用 agent 标注 → 逐方向统计各平台条数
        plat_matrix = {}
        plat_total = {}
        n_ann_hit = 0
        for r in kept:
            a = ann.get((r.get("source_id") or "")[:44])
            if a:
                n_ann_hit += 1
                name = a[0] if a[0] != "无" else None
            else:
                name = None
            name = name or dr.classify_best(r)[0]
            if not name:
                continue
            src = r.get("source", "?")
            plat_matrix.setdefault(name, {})
            plat_matrix[name][src] = plat_matrix[name].get(src, 0) + 1
            plat_total[src] = plat_total.get(src, 0) + 1
        dirs = []
        for s in win["directions"]:
            dirs.append({
                "name": s["name"], "evidence": s.get("evidence", 0),
                "score": s.get("score", 0), "opp_score": s.get("opp_score"),
                "market": s.get("market_repos"), "crowd": s.get("crowd", "—"),
                "opp_tag": s.get("opp_tag", "—"),
                "wtp": s.get("wtp_total", s.get("wtp", 0)),
                "pain": s.get("pain", 0),
                "sources": s.get("sources", []),
                "plat": plat_matrix.get(s["name"], {}),
                "mature": s.get("mature", []),
                "evidence_links": s.get("evidence_links", []),
            })
        data["windows"].append({"key": key, "label": win["label"],
                                "raw": win.get("raw", 0), "kept": win.get("kept", 0),
                                "dirs": dirs, "plat_total": plat_total,
                                "ann_hits": n_ann_hit, "kept_n": len(kept)})
    return data


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>idea-hunter · 方向看板</title>
<script>__ECHARTS__</script>
<style>
  :root{--bg:#f6f8fa;--card:#fff;--ink:#24292f;--muted:#57606a;--line:#d8dee4;
        --red:#d9534f;--orange:#f0ad4e;--blue:#4da3d9;--green:#5cb85c}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
  .wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
  h1{font-size:22px;margin:6px 0 2px}
  .meta{color:var(--muted);font-size:12.5px;margin-bottom:14px}
  .tabs{display:flex;gap:8px;margin:14px 0}
  .tabs button{padding:7px 18px;border:1px solid var(--line);background:#fff;
       border-radius:20px;cursor:pointer;font-size:13.5px}
  .tabs button.on{background:#24292f;color:#fff;border-color:#24292f}
  .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;
        padding:12px 14px}
  .card b{display:block;font-size:22px}
  .card span{color:var(--muted);font-size:12px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:10px;
         padding:14px;margin-bottom:14px}
  .panel h3{margin:2px 0 6px;font-size:15px}
  .hint{color:var(--muted);font-size:12px;margin-bottom:4px}
  .chart{width:100%;height:380px}
  .chart-sm{width:100%;height:300px}
  table{border-collapse:collapse;width:100%;font-size:12.5px}
  th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
  th{color:var(--muted);font-weight:600}
  .tag{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11.5px;color:#fff}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:860px){.grid2{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}}
</style></head><body><div class="wrap">
<h1>idea-hunter · 方向看板</h1>
<div class="meta">生成时间：__GENERATED__　·　方向判定：__MODE__　·　
数据口径：证据数=窗口内独立候选条数；拥挤度=GitHub 同方向存量（红海≥1000/拥挤≥300/中等≥80/稀疏&lt;80）</div>
<div class="tabs" id="tabs"></div>
<div id="panels"></div>
<div class="panel"><h3>信源健康</h3><table id="health"></table></div>
</div>
<script>
const DATA = __DATA__;
const CROWD_COLOR = __CROWDCOLOR__;
const PLAT_SHORT = __PLATSHORT__;
const MODE_TEXT = __MODE__;
// 图表初始化加保护：ECharts 万一没加载成功，表格/卡片仍然完整可读，不整页白屏
function chart(id, opt){
  if(!window.echarts){ const el=document.getElementById(id);
    if(el) el.innerHTML='<div style="color:#8b949e;font-size:12px;padding:20px">图表组件未加载（本文件应已内嵌 ECharts，若见此提示说明文件被裁剪）</div>';
    return; }
  try{ echarts.init(document.getElementById(id)).setOption(opt); }catch(e){}
}
const fmt = n => n==null ? '—' : (n>=1000 ? n.toLocaleString('en-US') : n);
const tagColor = t => t.includes('★')?'#5cb85c':t.includes('已拥挤')?'#d9534f':t.includes('红海')?'#c9764a':'#8b949e';

// ---------- 标签页 ----------
const tabs=document.getElementById('tabs'), panels=document.getElementById('panels');
DATA.windows.forEach((w,i)=>{
  const b=document.createElement('button'); b.textContent=w.label;
  b.onclick=()=>show(i); tabs.appendChild(b);
  const d=document.createElement('div'); d.id='win'+i; panels.appendChild(d);
});
function show(i){
  [...tabs.children].forEach((b,j)=>b.classList.toggle('on',j===i));
  [...panels.children].forEach((p,j)=>p.style.display=j===i?'block':'none');
}

// ---------- 每个窗口 ----------
DATA.windows.forEach((w,i)=>{
  const el=document.getElementById('win'+i);
  const wtp=w.dirs.reduce((s,d)=>s+(d.wtp>0?1:0),0);
  el.innerHTML=`
  <div class="cards">
    <div class="card"><b>${w.raw}</b><span>原始采集</span></div>
    <div class="card"><b>${w.kept}</b><span>规则层留存</span></div>
    <div class="card"><b>${w.dirs.length}</b><span>候选方向</span></div>
    <div class="card"><b>${wtp}</b><span>带付费信号的方向</span></div>
  </div>
  <div class="panel"><h3>机会象限（热度 × 拥挤度）</h3>
    <div class="hint">右下=热但已挤满（红海）；左下=没人做但也没人要（待验证）；
      越靠左上越稀缺。气泡大小=综合评分，颜色=拥挤度。虚线：热度≥3、存量≥300。</div>
    <div class="chart" id="quad${i}"></div></div>
  <div class="grid2">
    <div class="panel"><h3>机会分排名</h3><div class="hint">机会分=热度分÷log(存量+10)，拥挤会稀释机会</div>
      <div class="chart-sm" id="bar${i}"></div></div>
    <div class="panel"><h3>平台 × 方向 支撑矩阵</h3>
      <div class="hint">同一方向被几个平台独立发现 = 信号更硬；只有一个平台的要先打折</div>
      <div class="chart-sm" id="heat${i}"></div></div>
  </div>
  <div class="panel"><h3>本窗口数据来源构成</h3>
    <div class="hint">GitHub 是供给侧（在做什么≠有人要），Reddit 才是需求侧原话</div>
    <div class="chart-sm" id="pie${i}"></div></div>
  <div class="panel"><h3>Top10 明细</h3><table>
    <tr><th>#</th><th>方向</th><th>机会</th><th>证据</th><th>平台</th><th>付费</th><th>存量</th><th>拥挤度</th><th>评分</th><th>机会分</th></tr>
    ${w.dirs.map((d,j)=>`<tr><td>${j+1}</td><td><b>${d.name}</b></td>
      <td><span class="tag" style="background:${tagColor(d.opp_tag)}">${d.opp_tag}</span></td>
      <td>${d.evidence}</td><td>${d.sources.map(s=>PLAT_SHORT[s]||s).join('、')}</td>
      <td>${d.wtp||'—'}</td><td>${fmt(d.market)}</td>
      <td><span class="tag" style="background:${CROWD_COLOR[d.crowd]||'#8b949e'}">${d.crowd}</span></td>
      <td>${d.score}</td><td>${d.opp_score??'—'}</td></tr>`).join('')}
  </table>
  <div style="margin-top:10px">
    ${w.dirs.map((d,j)=>`
      <div style="padding:6px 0;border-bottom:1px dashed var(--line)">
        <b>${j+1}. ${d.name}</b><br>
        <span style="color:var(--muted)">成熟项目：</span>
        ${(d.mature||[]).map(m=>`<a href="${m.url}" target="_blank" rel="noopener">${m.repo}</a>
           <span style="color:var(--muted)">★${fmt(m.stars)}·${m.updated||''}</span>`).join(' · ')||'—'}<br>
        <span style="color:var(--muted)">需求证据：</span>
        ${(d.evidence_links||[]).map(e=>`<a href="${e.url}" target="_blank" rel="noopener">${e.title.slice(0,42)}</a>`).join(' · ')||'—'}
      </div>`).join('')}
  </div></div>`;

  // 象限散点
  chart('quad'+i, {
    tooltip:{formatter:p=>`${p.data[3]}<br>证据 ${p.data[0]} · 存量 ${fmt(p.data[1])} · 评分 ${p.data[2]}<br>${p.data[4]}`},
    grid:{left:60,right:30,top:30,bottom:50},
    xAxis:{name:'证据数（热度）',type:'value',minInterval:1,nameLocation:'middle',nameGap:28},
    yAxis:{name:'存量项目（拥挤度）',type:'log',min:5,nameLocation:'middle',nameGap:34},
    series:[{type:'scatter',symbolSize:d=>8+Math.sqrt(d[2])*5,
      data:w.dirs.map(d=>[d.evidence,d.market||5,d.score,d.name,d.opp_tag]),
      itemStyle:{color:p=>CROWD_COLOR[p.data[4]]||'#4da3d9',opacity:.85},
      label:{show:true,formatter:p=>p.data[3],position:'top',fontSize:11}},
      {type:'line',markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed',color:'#bbb'},
        data:[{xAxis:3},{yAxis:300}]}},
      {type:'line',data:[]}]
  });
  // 机会分条形
  const bs=[...w.dirs].sort((a,b)=>(b.opp_score??0)-(a.opp_score??0)).slice(0,10).reverse();
  chart('bar'+i, {
    tooltip:{}, grid:{left:130,right:40,top:10,bottom:26},
    xAxis:{type:'value'}, yAxis:{type:'category',data:bs.map(d=>d.name)},
    series:[{type:'bar',data:bs.map(d=>({value:d.opp_score??d.score,
      itemStyle:{color:CROWD_COLOR[d.crowd]||'#4da3d9'}})),
      label:{show:true,position:'right',fontSize:11}}]
  });
  // 平台×方向 热力
  const dirs=[...w.dirs].slice(0,10);
  const platSet=new Set(); dirs.forEach(d=>Object.keys(d.plat).forEach(p=>platSet.add(p)));
  const plats=[...platSet];
  const hData=[]; dirs.forEach((d,y)=>plats.forEach((p,x)=>{
    if(d.plat[p]) hData.push([x,y,d.plat[p]]);}));
  chart('heat'+i, {
    tooltip:{formatter:p=>`${dirs[p.data[1]].name} × ${PLAT_SHORT[p.data[0]]||p.data[0]}：${p.data[2]} 条`},
    grid:{left:130,right:20,top:8,bottom:60},
    xAxis:{type:'category',data:plats.map(p=>PLAT_SHORT[p]||p),axisLabel:{rotate:30,fontSize:11}},
    yAxis:{type:'category',data:dirs.map(d=>d.name),inverse:true},
    visualMap:{show:false,min:0,max:6,inRange:{color:['#eef3f8','#2c7fb8']}},
    series:[{type:'heatmap',data:hData,label:{show:true,fontSize:11}}]
  });
  // 平台构成
  chart('pie'+i, {
    tooltip:{}, legend:{bottom:0,fontSize:11},
    series:[{type:'pie',radius:['38%','62%'],
      data:Object.entries(w.plat_total).map(([k,v])=>({name:PLAT_SHORT[k]||k,value:v})),
      label:{fontSize:11}}]
  });
});
show(0);

// ---------- 信源健康 ----------
const h=document.getElementById('health');
h.innerHTML='<tr><th>信源</th><th>条数</th><th>状态</th><th>备注</th></tr>'+
  DATA.health.map(x=>`<tr><td>${x.source}</td><td>${x.count}</td>
  <td>${x.ok?'✅':'❌'}</td><td>${(x.note||'').slice(0,80)}</td></tr>`).join('');
</script></body></html>
"""


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    jp = a.json or latest("directions_*.json")
    cp = latest("window_cache_*.json")
    if not jp or not cp:
        print("找不到 directions/window_cache 文件");  return 2
    ann = load_annotations()
    data = build(jp, cp, ann)
    # 判定方式按实际命中率标注，不虚标：标注文件只覆盖旧缓存时，新采集的
    # 记录大多走关键词签名，仍标"agent-语义分类"会误导（诚实性要求）。
    if not ann:
        mode = "关键词签名"
    else:
        hit = sum(w.get("ann_hits", 0) for w in data["windows"])
        kept_n = sum(w.get("kept_n", 0) for w in data["windows"])
        mode = ("agent-语义分类（Claude 直读原文）" if kept_n and hit >= kept_n * 0.5
                else "关键词签名（含部分 agent 语义标注）")
    data["mode"] = mode

    # ECharts 内嵌：看板必须离线可开。教训——之前走 CDN，预览环境加载不到就整页白屏
    # （页面 DOM 全由 JS 生成，echarts 未定义即抛异常，一行内容都出不来）。
    vendor = os.path.join(ROOT, "tools", "vendor", "echarts.min.js")
    ech = ""
    if os.path.isfile(vendor):
        with open(vendor, encoding="utf-8") as f:
            ech = f.read()
        if "</script>" in ech.lower()[:2000] or len(ech) < 100000:
            ech = ""  # 内容异常时不内嵌，退回 CDN + 占位提示
    echart_block = ech if ech else (
        "document.write('<scr'+'ipt src=\"https://cdn.jsdelivr.net/npm/echarts@5.5.0"
        "/dist/echarts.min.js\"><\\/scr'+'ipt>');")
    html = (HTML
            .replace("__ECHARTS__", echart_block)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__CROWDCOLOR__", json.dumps(CROWD_COLOR, ensure_ascii=False))
            .replace("__PLATSHORT__", json.dumps(PLATFORM_SHORT, ensure_ascii=False))
            .replace("__MODE__", json.dumps(mode, ensure_ascii=False))
            .replace("__GENERATED__", data["generated_at"]))
    ts = time.strftime("%Y%m%d-%H%M")
    out = os.path.join(OUT, f"dashboard_{ts}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("看板 ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
