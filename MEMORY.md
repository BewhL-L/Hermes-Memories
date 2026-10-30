# MEMORY.md — 记忆源文件

> 这份文件是记忆的**唯一事实源**，手工维护、可版本管理。
> `tools/sync_memory.py` 会把下面所有 `- ` 条目原文写入 mem0（`infer=false`，不改写、不截断）。
> 想留草稿又不入库，在行尾加 `<!-- skip -->`。

## 环境与运行

- Hermes 桌面端与 CLI 运行在 WSL2 Ubuntu（用户 luo），图形界面经 WSLg 显示
- Hermes 配置目录是 `~/.hermes`；模型默认走 SiliconFlow，模型 ID 为 `deepseek-ai/DeepSeek-V4.1-Flash`，base_url 为 `https://api.siliconflow.cn/v1`
- 网络走 Clash Verge 的 rule 模式（TUN 已关闭），mixed-port 为 `127.0.0.1:7897`；交互式 shell 已导出 http(s)_proxy，`no_proxy` 含 localhost 与 127.0.0.1；Windows 系统代理同为 7897，Docker Desktop 走 system 代理即可正常 pull
- 主工作区位于 `C:\Users\23981\Desktop\AI文档\BewhY_L知识库\全栈工程知识库\99-项目实战\企业级智能知识库 + AI Agent 平台`

## 记忆系统（自托管 mem0）

- mem0 以 docker compose 自托管，工程目录 `~/mem0/server`；API 8888、dashboard 3000、pgvector 8432
- 记忆抽取模型为 `zai-org/GLM-5.3-Flash`，嵌入模型为 `BAAI/bge-m3`（1024 维）
- 三个容器均已设置 `restart: unless-stopped`，`MEM0_TELEMETRY` 已置为 false
- 记忆资产的导出与回写脚本位于 `C:\Users\23981\Desktop\AI文档\HermesMemory\tools`

## 工作偏好

- 沟通上先给结论，再给证据与边界；不要用"最好/最优"这类无证据的断言
- 涉及修改配置时，先说明影响面与回滚方式

## 草稿区（未同步）

- 待定：是否将中文关键词检索改为 jieba 分词（当前判断：收益边际小，暂不做）<!-- skip -->
