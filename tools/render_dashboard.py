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


def load_analysis():
    """热榜付费潜力分析（agent 判断层）。没有就返回 None。"""
    p = os.path.join(OUT, "platform_analysis_dashboard.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_platforms():
    """平台优先轨道的 JSON（run_platforms.py 产出）。没有就返回 None。"""
    p = latest("platforms_*.json")
    if not p:
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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
    from hunter import paths as ph

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
                "heat": s.get("heat", 0),
                "mature_products": s.get("mature_products"),
                "pain": s.get("pain", 0),
                "sources": s.get("sources", []),
                "hot": s.get("hot", 0),
                "resonance": s.get("resonance", 0),
                "native_sources": s.get("native_sources", []),
                "keyword_sources": s.get("keyword_sources", []),
                "plat": plat_matrix.get(s["name"], {}),
                "mature": s.get("mature", []),
                "evidence_links": s.get("evidence_links", []),
                "advice": s.get("advice", ""),
                "advice_level": s.get("advice_level", 0),
                "advice_action": s.get("advice_action", ""),
                "advice_reasons": s.get("advice_reasons", []),
                "trend_level": s.get("trend_level", ""),
                "trend_score": s.get("trend_score", 0),
                "trend_reasons": s.get("trend_reasons", []),
            })
        # 贡献率直接从缓存算，不依赖上游 JSON 是否导出该字段
        n_nat, n_kw, rate = ph.counts(kept)
        data["windows"].append({"key": key, "label": win["label"],
                                "path_stats": [n_nat, n_kw, rate],
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
<div id="analysis"></div>
<div class="tabs" id="tabs"></div>
<div id="panels"></div>
<div id="platforms"></div>
<div class="panel"><h3>信源健康</h3><table id="health"></table></div>
</div>
<script>window.__PLATFORMS__ = __PLATFORMS_JSON__;
window.__ANALYSIS__ = __ANALYSIS_JSON__;</script>
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
const ADVICE_COLOR = {4:'#5cb85c',3:'#7cb342',2:'#f0ad4e',1:'#d9534f',0:'#8b949e'};
const TREND_COLOR = {'高':'#d9534f','中':'#f0ad4e','低':'#8b949e','':'#8b949e'};
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
  const ps=w.path_stats&&w.path_stats.length===3?w.path_stats:null;
  const natRate=ps?(ps[2]*100).toFixed(0)+'%':'—';
  const natOk=ps&&ps[2]>=0.4;
  el.innerHTML=`
  <div class="cards">
    <div class="card"><b>${w.raw}</b><span>原始采集</span></div>
    <div class="card"><b>${w.kept}</b><span>规则层留存</span></div>
    <div class="card"><b>${natRate}</b><span>原生榜贡献率${natOk?'（达标 ≥40%）':'（未达标 <40%）'}</span></div>
    <div class="card"><b>${wtp}</b><span>带付费信号的方向</span></div>
  </div>
  <div class="panel"><h3>证据通道说明</h3>
    <div class="hint">需求证据＝过痛点/付费构式门槛；平台热点证据＝原生榜且热度达标（不走门槛）。
      <b>共振只统计原生榜</b>（排序由平台决定＝独立发现）；关键词检索命中是同一个查询在多个平台的回声，
      <b>不计入共振</b>——这正是"假共振"的修复点。</div></div>
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
    <tr><th>#</th><th>方向</th><th>机会</th><th>需求</th><th>热点</th><th>共振(原生/检索)</th><th>讨论热度</th><th>付费</th><th>存量</th><th>成型产品</th><th>拥挤度</th><th>评分</th><th>机会分</th></tr>
    ${w.dirs.map((d,j)=>`<tr><td>${j+1}</td><td><b>${d.name}</b></td>
      <td><span class="tag" style="background:${tagColor(d.opp_tag)}">${d.opp_tag}</span></td>
      <td>${d.evidence}</td><td>${d.hot||0}</td>
      <td>${d.resonance||0}
        <span style="color:var(--muted);font-size:11.5px">
        （${(d.native_sources||[]).map(s=>PLAT_SHORT[s]||s).join('、')||'—'} /
         ${(d.keyword_sources||[]).map(s=>PLAT_SHORT[s]||s).join('、')||'—'}）</span></td>
      <td>${d.heat||'—'}</td>
      <td>${d.wtp||'—'}</td><td>${fmt(d.market)}</td>
      <td>${d.mature_products==null?'—':(d.mature_products===0?'<b style="color:#5cb85c">0</b>':d.mature_products)}</td>
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
        ${d.advice?`<div style="margin-top:4px">
          <span class="tag" style="background:${ADVICE_COLOR[d.advice_level]||'#8b949e'}">${d.advice}</span>
          <span class="tag" style="background:${TREND_COLOR[d.trend_level]||'#8b949e'};margin-left:4px">趋势 ${d.trend_level}·${d.trend_score}</span>
          <span style="color:var(--muted);font-size:11.5px"> · ${[...(d.advice_reasons||[]),...(d.trend_reasons||[])].join('；')}</span>
          ${d.advice_action?`<div style="color:var(--muted);font-size:11.5px">建议动作：${d.advice_action}</div>`:''}
        </div>`:''}
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

// ---------- 热榜付费潜力分析（judgment 层，放最前）----------
const AN = window.__ANALYSIS__;
const md = x => (x||'').replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>');
if (AN && AN.items) {
  const TIER = {A:{l:'A 级 · 付费路径明确', c:'#5cb85c'},
                B:{l:'B 级 · 有可能需验证', c:'#f0ad4e'},
                C:{l:'C 级 · 无付费路径', c:'#8b949e'}};
  const card = it => `
    <div class="panel" style="margin-bottom:10px">
      <h3>${it.title}
        <span class="tag" style="background:${TIER[it.tier].c};margin-left:6px">
          ${TIER[it.tier].l}　付费潜力 ${it.pay}/5</span></h3>
      <table style="font-size:12.5px">
        <tr><td style="width:96px;color:var(--muted)">谁付钱</td><td>${md(it.who_pays)||'—'}</td></tr>
        <tr><td style="color:var(--muted)">付费触发点</td><td>${md(it.trigger)||'—'}</td></tr>
        <tr><td style="color:var(--muted)">现有供给</td><td>${md(it.supply)||'—'}</td></tr>
        <tr><td style="color:var(--muted)">结论</td><td><b>${md(it.verdict)||'—'}</b></td></tr>
        <tr><td style="color:var(--muted)">建议动作</td><td>${md(it.action)||'—'}</td></tr>
      </table>
      ${(it.urls&&it.urls.length)?`<div style="margin-top:4px;font-size:12px">
        ${it.urls.map(u=>`<a href="${u}" target="_blank" rel="noopener">原帖</a>`).join(' · ')}</div>`:''}
    </div>`;
  const el = document.getElementById('analysis');
  const ab = AN.items.filter(i=>i.tier!=='C'), cc = AN.items.filter(i=>i.tier==='C');
  el.innerHTML = `
    <div class="panel">
      <h3>热榜内容的付费潜力分析</h3>
      <div class="hint">${(AN.note||'').replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>')}</div>
      <div class="hint">四个必答问题：谁付钱（具体角色）· 付费触发点（新增支出还是旧预算搬家）·
        现有供给（有没有人做成）· 能否 2-4 周做出 MVP。</div>
    </div>
    ${ab.map(card).join('')}
    <div class="panel">
      <h3>C 级 · 无付费路径（明确排除，省时间）</h3>
      <table><tr><th>条目</th><th>为什么排除</th></tr>
      ${cc.map(i=>`<tr><td><b>${i.title}</b></td><td>${md(i.verdict)}</td></tr>`).join('')}
      </table>
    </div>`;
}

// ---------- 平台热榜（平台优先轨道）----------
const PF = window.__PLATFORMS__;
if (PF) {
  const el = document.getElementById('platforms');
  const terms = {};
  (PF.terms ? Object.entries(PF.terms) : []).forEach(([k,v])=>terms[k]=v);
  el.innerHTML = `
    <div class="panel" style="margin-top:16px">
      <h3>平台热榜（平台优先轨道）</h3>
      <div class="hint">不做需求门槛、不做方向归类，按各平台原生热度排序。
        各站量纲不同（知乎是平台热度、HN 是点数、PH 是排名代理），<b>只比排名不比数值</b>。</div>
      <div class="chart-sm" id="pfbar"></div>
    </div>
    <div class="panel"><h3>跨平台主题</h3>
      <div class="hint">同一关键词出现在 ≥2 个平台。<b>关键词法有上限</b>：同义不同词不合并、中文用 n-gram 会切出碎片。</div>
      ${(PF.topics&&PF.topics.length)?`<table>
        <tr><th>主题</th><th>平台数</th><th>出现平台</th><th>热度合计</th></tr>
        ${PF.topics.map(t=>`<tr><td><b>${t.topic}</b></td><td>${t.n_platforms}</td>
          <td>${t.platforms.map(x=>PLAT_SHORT[x]||x).join('、')}</td><td>${t.heat}</td></tr>`).join('')}
      </table>`:'<div class="hint">本轮无词汇交叉（热榜标题过短、样本不足）</div>'}
    </div>
    ${PF.platforms.map((p,i)=>`
      <div class="panel">
        <h3>${PLAT_SHORT[p.source]||p.source}　<span style="color:var(--muted);font-weight:400">${p.items.length} 条</span></h3>
        ${terms[p.source]?`<div class="hint">平台高频词：${terms[p.source].map(x=>x.t+'('+x.n+')').join('、')}</div>`:''}
        <table>
          <tr><th>#</th><th>标题</th><th>平台热度</th><th>链接</th></tr>
          ${p.items.map((it,j)=>`<tr><td>${j+1}</td><td>${it.title.slice(0,72)}</td>
            <td>${it.heat}</td><td><a href="${it.url}" target="_blank" rel="noopener">打开</a></td></tr>`).join('')}
        </table>
      </div>`).join('')}`;
  chart('pfbar', {
    tooltip:{formatter:p=>`${p.name}<br>头部热度 ${p.value}`},
    grid:{left:120,right:60,top:10,bottom:26},
    xAxis:{type:'value'},
    yAxis:{type:'category',data:PF.platforms.map(p=>PLAT_SHORT[p.source]||p.source)},
    series:[{type:'bar',data:PF.platforms.map(p=>({value:p.items[0]?p.items[0].heat:0,
      itemStyle:{color:'#4da3d9'}})),label:{show:true,position:'right',fontSize:11}}]
  });
}

// ---------- 信源健康 ----------
const h=document.getElementById('health');
h.innerHTML='<tr><th>信源</th><th>条数</th><th>状态</th><th>备注</th></tr>'+
  DATA.health.map(x=>`<tr><td>${x.source}</td><td>${x.count}</td>
  <td>${x.ok?'✅':'❌'}</td><td>${(x.note||'').slice(0,80)}</td></tr>`).join('');
</script>
</body></html>
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
            .replace("__GENERATED__", data["generated_at"])
            .replace("__PLATFORMS_JSON__", json.dumps(load_platforms(), ensure_ascii=False))
            .replace("__ANALYSIS_JSON__", json.dumps(load_analysis(), ensure_ascii=False)))
    ts = time.strftime("%Y%m%d-%H%M")
    out = os.path.join(OUT, f"dashboard_{ts}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("看板 ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
