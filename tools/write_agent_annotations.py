# -*- coding: utf-8 -*-
"""把 agent（Claude）直读原文后的语义分类结果写成标注文件。

与 llm.classify_batch 的产出对齐：direction / llm_wtp / llm_pain。
key = source_id 截断到 44 字符（与工作表一致），应用时按前缀匹配。

标注纪律：
- 只依据记录文本判断；trending 仓库正文为空时，按仓库本名的公认用途分类（agent 有
  世界知识，这是相对 LLM-API 纯文本模式的偏离，已披露）。
- 真正的空白（描述与名称都无信息）一律"无"，不硬猜。
- wtp（付费意愿 0-5）：口语化表达也算（would pay for that / take my money /
  已有收入 / 正在付费）。
"""
import json
import os

A = {}  # key -> [direction, wtp, pain]


def a(key, d, wtp=0, pain=0):
    A[key] = [d, wtp, pain]


AI = "AI 代理与自动化"
# ---------------- day ----------------
a("search:Marcos66236/github-stars-history", "报表与可视化")
a("search:korcarc/text-humanizer", "内容创作与分发")
a("search:anmolkapil/plexo", "文件与存储同步")
a("search:jarrodwatts/jev-trader", AI)
a("search:YongshengWin/VpsCT", "自托管与部署")
a("search:dofastted/vm2api", "集成与 API 网关")
a("search:SpikeCalls/FlyDrones", "无")
a("search:davidmokos/expo-gpt-live", AI)
a("reddit:read:1wi88io", "支付与账单", 2, 3)          # Stripe fees were insane
a("search:vinnylarouge/jevlike", "无")
a("search:awlevin/typesafe-computer-use", AI)
a("search:apple/xcode-project-format", "代码质量与 CI")
a("search:TheoLeeCJ/openjev", "自托管与部署")
a("search:ForrestKnight/omarchy-key-promoter", "终端与开发者效率")
a("search:justoneapi-labs/xiaohongshu-api", "数据采集与解析")
a("search:dmtrKovalenko/bashka", "代码质量与 CI")
a("search:greentfrapp/panel", "无")
a("search:kdbhalala/avdslim", "终端与开发者效率")
a("hn:49736767", "无")                                # Pangram AI 检测讨论
a("reddit:read:1u0z4vz", "无")
a("reddit:read:1whypao", "无")
a("trending:daily:JustVugg/colibri", "无")
a("trending:daily:jamiepine/voicebox", "视频与音频处理")
a("trending:daily:Lakr233/vphone-cli", "终端与开发者效率")
a("trending:daily:anthropics/knowledge-work-plu", AI)
a("trending:daily:ever-co/ever-gauzy", "协作与项目管理")
a("trending:daily:ankitects/anki", "育儿与生活服务")
a("trending:daily:NationalSecurityAgency/ghidra", "安全与合规")
a("trending:daily:anthropics/claude-code", AI)
a("trending:daily:supabase/supabase", "自托管与部署")
a("trending:daily:Tencent/WeKnora", AI)
a("trending:daily:SnailSploit/Claude-Red", "安全与合规")
a("trending:daily:multimodal-art-projection/YuE", "视频与音频处理")
a("trending:daily:addyosmani/agent-skills", AI)
a("trending:daily:cline/cline", AI)
a("trending:daily:affaan-m/ECC", "无")
a("search:ctdal/cve-2026-41940-PoC", "安全与合规")
a("search:hirakujira/NEIN", "无")
a("search:FLModel/flm", "无")
a("hn:49729128", AI, 0, 1)
a("hn:49717564", "无", 0, 2)                          # 缺参数化 STEP 生成（分类表外）
a("hn:49720601", "无")
a("hn:49734338", "无")
a("hn:49700199", "终端与开发者效率", 0, 2)
a("hn:49720589", "无")
a("hn:49720373", "无")
a("hn:49717758", "无")
a("hn:49709877", "终端与开发者效率")
# ---------------- week ----------------
a("search:linguo2625469/workbuddy2api-panel", "集成与 API 网关")
a("search:danieldeer/seriousdb", "自托管与部署")
a("search:Chuloo/mural", "育儿与生活服务")
a("search:kruzovic7/ai-data-extractor", "数据采集与解析")
a("search:eternityspring/reelbench-skills", "视频与音频处理")
a("search:letorig/video-generator-client", "视频与音频处理")
a("search:browser-use/life-recorder", "无")
a("search:AetherLabsAI/RSIAgent", AI)
a("search:lingyired/status-trio", "终端与开发者效率")
a("search:KazamaDono/taoxd", "安全与合规")
a("search:FLModel/flybook", AI)
a("search:modelscope/ms-cookbook", AI)
a("search:opencoredev/bg0", "无")
a("search:KillaBoi/BrokenPipe", "安全与合规")
a("search:Matthew0822/ToolReplay", AI)
a("search:0xjohnnydev/airlift", "安全与合规")
a("reddit:read:1wgxzx9", "无")
a("search:agentverse-os/AgentVerse-OS", "自托管与部署")
a("search:atria-asi/Atria-Dawn-Preview", "无")
a("search:anonymous-report-421/GPT-as-Policy", "无")
a("search:DefiLeoo/YOINK", "无")
a("search:Qiuner/birdview", "代码质量与 CI", 0, 2)
a("search:groundboxerrespect/Dlls5-auto", "视频与音频处理")
a("search:arikchakma/gpu-time", "无")
a("search:mpociot/claude-siri-ai", AI)
a("search:pliablepixels/gap-trap", "代码质量与 CI", 0, 2)
a("hn:49647380", "无")
a("hn:49662003", "无")
a("search:MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x", "自托管与部署")
a("reddit:read:1weymt7", "无", 4, 2)                  # $600 收入 = 有人在付钱
a("trending:weekly:bilawalsidhu/gods-eye-view", "无")
a("trending:weekly:openai/plugins", AI)
a("trending:weekly:kunchenguid/firstmate", "无")
a("trending:weekly:home-assistant/core", "自托管与部署")
a("trending:weekly:THU-MAIC/OpenMAIC", "无")
a("trending:weekly:danny-avila/LibreChat", AI)
a("trending:weekly:TauricResearch/TradingAgents", AI)
a("search:nhovongoc0-max/meme-radar", "价格与竞品情报")
a("search:shilapi/xcertplay", "无")
a("search:max99x/wutw-public", "无")
a("search:ithtelab/workbuddy-manager", "集成与 API 网关")
a("hn:49675132", AI, 3, 2)                            # would pay for that ability
a("hn:49671945", "数据采集与解析", 0, 2)              # 反爬升级伤及采集生态
a("hn:49655548", "终端与开发者效率")
a("hn:49640663", "代码质量与 CI")
a("hn:49661996", "文件与存储同步")
# ---------------- month ----------------
a("search:totec448-spec/chat-on-steroids", AI)
a("search:nateherkai/scroll-craft", AI)
a("search:vinzdg/codenotch", "监控与可观测")          # AI 工具用量限额监控
a("search:lnkiai/m3e-canvas", AI)
a("search:ashemag/human-atlas", "无")
a("search:ApodexAI/FrontierAgent", AI)
a("search:yanliudesign/mono-color-skill", "内容创作与分发")
a("search:anthropics/commerce-agents", "电商与跨境")
a("search:Nanako0129/sepia", "内容创作与分发")
a("search:tobi/walgit", "无")
a("search:NVlabs/SoL-Pi", AI)
a("search:omacom/try-omarchy", "终端与开发者效率")
a("search:duty1g/x64dbg-mcp-server", AI)
a("search:shadcn-ui/lint", "代码质量与 CI")
a("search:FireRedTeam/FireRedAudio", "视频与音频处理")
a("search:cbrock84/headcount", AI)
a("search:shadcn-ui/cn", "代码质量与 CI")
a("search:Git-Agni/prod-FARM-IOS-Core", "自托管与部署")
a("search:sebbbi/NoGraphicsAPI", "无")
a("search:yang0/handraw-style", "内容创作与分发")
a("search:larashero3-dotcom/lieflat-less-ai-ton", "内容创作与分发")
a("search:N4darae/anti-mage", "安全与合规")
a("search:donvito/codex-astra-luna-orchestrator", AI)
a("search:b-nnett/grok-bot-0.18-reconstructed", AI)
a("hn:49362340", "无")
a("hn:49638934", "自托管与部署", 0, 2)                # 14M 用户服务的运维之痛
a("trending:monthly:omacom/omarchy", "终端与开发者效率")
a("trending:monthly:modular/modular", AI)
a("trending:monthly:tashfeenahmed/freellmapi", AI)
a("trending:monthly:jingyaogong/minimind", AI)
a("search:EverettFish/holo-card-studio", "内容创作与分发")
a("hn:49529863", "无")
a("hn:49479539", "监控与可观测")                      # 看回放找 bug 的产品讨论
a("hn:49440835", "无")
a("hn:49561582", AI)                                  # 17k 次 agent 选工具实测
a("hn:49511248", AI)                                  # Agent Memory 文件格式
a("hn:49499762", "无")
a("hn:49407702", "自托管与部署", 0, 3)                # 本地 LLM 配置全靠瞎试
a("hn:49400824", AI)
a("hn:49355060", "无")
a("hn:49343414", "终端与开发者效率", 0, 1)            # GitHub 替代品讨论
a("hn:49715456", "无")
a("hn:49729285", "无")
a("hn:49575163", "安全与合规")
a("hn:49546160", "文件与存储同步", 0, 3)              # 备份存储搭建之痛（标题即痛点）
a("hn:49455904", "无")
a("hn:49446083", "无")

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "out", "agent_annotations.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(A, f, ensure_ascii=False, indent=1)
print("标注条数:", len(A), "->", out)
