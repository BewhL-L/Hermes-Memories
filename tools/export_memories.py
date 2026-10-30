#!/usr/bin/env python3
"""把 mem0 里的记忆导出成与框架无关的资产文件。

产出（默认写到 ../exports/）：
  memories-YYYYMMDD-HHMMSS.jsonl   结构化全量，适合 diff / 迁移 / 版本管理
  MEMORY.full.md                   可读版，按写入日期分组

为什么要有这个脚本：
  记忆是资产，mem0 只是当前使用的索引。导出的 JSONL 不依赖任何框架，
  换成 Graphiti / Letta / 手写 SQLite 时，数据都在。

用法：
  python export_memories.py
  python export_memories.py --out D:/backup/mem --user hermes-local-user
  python export_memories.py --base http://localhost:8888 --key <api-key>

不传 --key 时自动从 ~/.hermes/.env 读取 MEM0_API_KEY。
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERMES_ENV = Path.home() / ".hermes" / ".env"
# Hermes 常跑在 WSL 里，Windows 侧的 ~/.hermes 可能不存在；按顺序回退。
ENV_CANDIDATES = [
    HERMES_ENV,
    Path(r"\\wsl.localhost\Ubuntu\home\luo\.hermes\.env"),
]
DEFAULT_BASE = "http://localhost:8888"
DEFAULT_USER = "hermes-local-user"


def resolve_env_file(explicit: str = "") -> Path | None:
    """定位 .env：显式参数 > HERMES_ENV 环境变量 > 默认候选列表。"""
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    override = os.environ.get("HERMES_ENV", "")
    if override:
        path = Path(override)
        if path.exists():
            return path
    for candidate in ENV_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_env_file(path: Path) -> dict[str, str]:
    """读取 KEY=VALUE 形式的 .env；解析失败的行直接跳过，不抛异常。"""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_opener(base_url: str):
    """访问 localhost 时禁用代理，其余地址沿用系统代理设置。"""
    host = urllib.parse.urlparse(base_url).hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def request_json(opener, base_url: str, path: str, api_key: str, payload=None, timeout=60):
    req = urllib.request.Request(base_url.rstrip("/") + path)
    if api_key:
        req.add_header("X-API-Key", api_key)
    if payload is not None:
        req.data = json.dumps(payload).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with opener.open(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body.strip() else {}


def fetch_all(opener, base_url: str, api_key: str, user_id: str) -> list[dict]:
    """拉全量记忆。mem0 的 get_all 默认上限很小，这里显式放大 top_k。"""
    query = urllib.parse.urlencode({"user_id": user_id, "top_k": 1000})
    data = request_json(opener, base_url, f"/memories?{query}", api_key)
    if isinstance(data, dict):
        return data.get("results") or []
    return data if isinstance(data, list) else []


def normalise(record: dict) -> dict:
    """只保留迁移需要的字段，丢弃 text_lemmatized 等可重算的派生物。"""
    return {
        "id": record.get("id"),
        "memory": record.get("memory") or record.get("data") or "",
        "user_id": record.get("user_id"),
        "agent_id": record.get("agent_id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "metadata": record.get("metadata"),
    }


def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_markdown(records: list[dict], path: Path, user_id: str) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        stamp = (record.get("created_at") or "")[:10] or "unknown"
        grouped[stamp].append(record)

    lines = [
        f"# 记忆全量导出（{user_id}）",
        "",
        f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 条数：{len(records)}",
        "- 说明：本文件由 export_memories.py 生成，重新导出会覆盖；",
        "  需要长期维护的结论请写入手工维护的 MEMORY.md。",
        "",
    ]
    for day in sorted(grouped, reverse=True):
        lines.append(f"## {day}（{len(grouped[day])} 条）")
        lines.append("")
        for record in grouped[day]:
            text = " ".join(str(record.get("memory", "")).split())
            if text:
                lines.append(f"- {text}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 mem0 记忆为框架无关的资产文件")
    parser.add_argument("--base", default=os.environ.get("MEM0_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--key", default="")
    parser.add_argument("--user", default=os.environ.get("MEM0_USER_ID", DEFAULT_USER))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "exports"))
    parser.add_argument("--env", default="", help="显式指定 Hermes 的 .env 路径")
    parser.add_argument("--rolling", action="store_true",
                        help="写固定文件名 memories.jsonl（历史交给 git），而非带时间戳的新文件")
    args = parser.parse_args()

    env_file = resolve_env_file(args.env)
    api_key = args.key or (load_env_file(env_file).get("MEM0_API_KEY", "") if env_file else "")
    if not api_key:
        print(f"警告：未找到 MEM0_API_KEY（查找位置：{env_file or ENV_CANDIDATES}），将以无鉴权方式请求")

    opener = build_opener(args.base)
    try:
        raw = fetch_all(opener, args.base, api_key, args.user)
    except Exception as exc:  # noqa: BLE001 - 诊断信息比堆栈更有用
        print(f"导出失败：{exc}")
        return 1

    records = [normalise(item) for item in raw if item.get("memory") or item.get("data")]
    records.sort(key=lambda item: item.get("created_at") or "")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jsonl_path = out_dir / ("memories.jsonl" if args.rolling else f"memories-{stamp}.jsonl")
    md_path = out_dir / "MEMORY.full.md"

    write_jsonl(records, jsonl_path)
    write_markdown(records, md_path, args.user)

    print(f"导出 {len(records)} 条")
    print(f"  结构化：{jsonl_path}")
    print(f"  可读版：{md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
