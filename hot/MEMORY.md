作品集 v31（封面式首屏 + 章节跨页）：issue-v31-pawpage.html，画布 1520-1560、页边 clamp(26px,4.6vw,96px)、folio 用 CSS 计数器生成（不进 innerText），新增两套宠物动作 act-cache（缓存命中）与 act-fallback（失败降级）
§
用户电脑的 Blender 在 D:\Blender\blender.exe（4.5.0），可用 --background --python 脚本建模；已产出 assets3d/Tuanzi.glb 与 Noodle.glb（17k/19k 三角面、17 骨骼、4 段动作 Idle/Walk/CacheHit/Fallback）
§
用户偏好：不要夜版网页（夜间图书馆版本已弃用）；希望布局更宽、页边距更大、波点艺术化、模块可爱风；最终要我输出可复用的提示词文档而不是只改代码
§
作品集 v32 的设计语言（来自参考图像素统计）：白纸 #FBFAF4 + 柠檬黄绿 #D2DE1E + 薄荷青 #12D6A6 + 橄榄褐 #A79D74 + 驼色 #C0B098，文字深绿近黑 #22301F；特征是大块平涂色块（首屏右侧柠檬色块、证据区整块薄荷色卡）+ 色块内铺 26px 白波点 + 纸面 22/44px 极淡网点肌理
§
作品集页面（作品集设计/）构建方式：以 issue-v28-dotpup.html 为内容母版，只拼接 CSS/JS，正文/导航/弹窗/页脚须与母版逐字一致；v33 起全站统一画布 1174（1600 视口左右各 213），左侧竖排书签栏已改成横向条目，立牌基准宽 45px。
§
环境：Hermes 跑在 WSL2 Ubuntu（用户 luo，networkingMode=mirrored），配置目录 ~/.hermes，图形界面经 WSLg；主模型为 SiliconFlow 的 deepseek-ai/DeepSeek-V4.1-Flash，base_url https://api.siliconflow.cn/v1
§
网络：Clash Verge 的 TUN 关闭、mode=rule、混用端口 7897；shell 已导出 http(s)_proxy 且 no_proxy 含 localhost；Windows 系统代理同为 127.0.0.1:7897，Docker Desktop 走 system 代理即可正常 pull
§
记忆分层：热记忆写本文件（每轮注入），温/冷记忆走自托管 mem0（~/mem0/server，API 8888、dashboard 3000、pgvector 8432），抽取模型 zai-org/GLM-5.3-Flash，嵌入 BAAI/bge-m3（1024 维，换嵌入需重建全部向量）
§
记忆资产：C:\Users\23981\Desktop\AI文档\Hermes Memories 为源文件目录（git 仓库，远端 github.com/BewhL-L/Hermes-Memories），MEMORY.md 是唯一事实源；tools/export_memories.py 导出 JSONL 与可读版，tools/sync_memory.py 以 infer=false 原文回写 mem0
§
会话延续：命令行 hermes -c 接续最近一次会话；TUI 内 /resume 列出最近 10 条按序号选取；同一 session 不能同时被桌面端与终端持有
