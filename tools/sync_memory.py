#!/usr/bin/env python3
"""把手工维护的 MEMORY.md 同步进 mem0（原文写入，不走 LLM 抽取）。

设计取舍：
  MEMORY.md 是"记忆的源文件"，mem0 是"检索索引"。
  同步时用 infer=false —— 记忆的措辞由你决定，不让模型改写或截断。
  重复执行安全：远端已存在完全相同内容的条目时跳过。

MEMORY.md 格式约定：
  每行以 "- " 或 "* " 开头的条目 = 一条记忆；"## 标题"只用于分组，不入库。
  行尾写 <!-- skip --> 的条目会被忽略（便于留草稿）。

用法：
  python sync_memory.py --dry-run     # 只打印将要写入的条目，不落库
  python sync_memory.py               # 真正写入
  python sync_memory.py --file other.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERMES_ENV = Path.home() / ".hermes" / ".env"
ENV_CANDIDATES = [
    HERMES_ENV,
    Path(r"\\wsl.localhost\Ubuntu\home\luo\.hermes\.env"),
]
STATE_FILE = ROOT / ".sync-state.json"
DEFAULT_BASE = "http://localhost:8888"
DEFAULT_USER = "hermes-local-user"

BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def resolve_env_file(explicit: str = "") -> Path | None:
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


def parse_facts(path: Path) -> list[str]:
    """抽取 MEMORY.md 里的条目；忽略代码块与带 skip 标记的行。"""
    facts: list[str] = []
    in_code = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = BULLET.match(line)
        if not match:
            continue
        fact = match.group(1).strip()
        if not fact or "<!-- skip -->" in fact:
            continue
        if fact.startswith("[ ]") or fact.startswith("[x]"):
            continue
        facts.append(" ".join(fact.split()))
    return facts


def fact_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"version": 1, "entries": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def remote_texts(opener, base_url: str, api_key: str, user_id: str) -> set[str]:
    query = urllib.parse.urlencode({"user_id": user_id, "top_k": 1000})
    try:
        data = request_json(opener, base_url, f"/memories?{query}", api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"警告：读取远端记忆失败（{exc}），本次将跳过远端去重")
        return set()
    items = data.get("results") if isinstance(data, dict) else data
    texts = set()
    for item in items or []:
        value = item.get("memory") or item.get("data") or ""
        if value:
            texts.add(" ".join(str(value).split()))
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 MEMORY.md 到 mem0")
    parser.add_argument("--file", default=str(ROOT / "MEMORY.md"))
    parser.add_argument("--base", default=os.environ.get("MEM0_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--key", default="")
    parser.add_argument("--user", default=os.environ.get("MEM0_USER_ID", DEFAULT_USER))
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入")
    parser.add_argument("--env", default="", help="显式指定 Hermes 的 .env 路径")
    args = parser.parse_args()

    md_path = Path(args.file)
    if not md_path.exists():
        print(f"找不到 {md_path}")
        return 1

    facts = parse_facts(md_path)
    if not facts:
        print("MEMORY.md 中没有可同步的条目")
        return 0

    env_file = resolve_env_file(args.env)
    api_key = args.key or (load_env_file(env_file).get("MEM0_API_KEY", "") if env_file else "")
    if not api_key:
        print("警告：未找到 MEM0_API_KEY，将以无鉴权方式请求（远端若开启鉴权会返回 401）")
    opener = build_opener(args.base)
    existing = remote_texts(opener, args.base, api_key, args.user)
    state = load_state()
    entries = state.setdefault("entries", {})

    pending: list[tuple[str, str]] = []
    for fact in facts:
        key = fact_id(fact)
        if fact in existing:
            entries.setdefault(key, {"text": fact, "mem0_id": None, "synced_at": None,
                                     "note": "remote-duplicate"})
            continue
        if key in entries and entries[key].get("mem0_id"):
            continue
        pending.append((key, fact))

    print(f"MEMORY.md 条目 {len(facts)} 条；远端已有 {len(existing)} 条；待写入 {len(pending)} 条")
    if args.dry_run:
        for key, fact in pending:
            print(f"  [dry-run] {key}  {fact[:70]}")
        return 0

    written = 0
    for key, fact in pending:
        payload = {
            "messages": [{"role": "user", "content": fact}],
            "user_id": args.user,
            "infer": False,
            "metadata": {"source": "MEMORY.md"},
        }
        try:
            response = request_json(opener, args.base, "/memories", api_key, payload)
            results = response.get("results") if isinstance(response, dict) else None
            mem0_id = None
            if isinstance(results, list) and results:
                mem0_id = results[0].get("id") or results[0].get("memory_id")
            entries[key] = {"text": fact, "mem0_id": mem0_id,
                            "synced_at": datetime.now().isoformat(timespec="seconds")}
            written += 1
            print(f"  + {key}  {fact[:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {key} 写入失败：{exc}")

    save_state(state)
    print(f"完成：写入 {written} 条，状态保存至 {STATE_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
