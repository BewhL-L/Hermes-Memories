#!/usr/bin/env python3
"""把 Hermes 的热记忆快照进仓库（单向只读，不回写）。

背景：
  ~/.hermes/memories/MEMORY.md 与 USER.md 由 Hermes 的 agent 自己维护，
  是最新鲜、最活跃的记忆。它们是 WSL 内的文件，仓库看不到。
  本脚本只做一件事：把它们原样复制到仓库的 hot/ 目录，供 git 留痕。

为什么是单向：
  agent 会持续写这两个文件（带 .lock 与原子替换）。从仓库回写会与它竞争，
  语义上也容易互相覆盖。仓库只做备份与审计，永不写回。

用法：
  python pull_hot.py                    # 只复制
  python pull_hot.py --export           # 复制 + 导出 mem0 全量（滚动文件）
  python pull_hot.py --commit --push    # 复制 + 提交 + 推送
  python pull_hot.py --export --commit --push   # 每日快照的完整动作
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOT_DIR = ROOT / "hot"
LOG_FILE = Path.home() / "AppData" / "Local" / "HermesMemory" / "snapshot.log"

# Hermes 可能跑在 WSL 里（常见），也可能有 Windows 原生安装；按顺序找第一个存在的。
HOT_CANDIDATES = [
    Path(r"\\wsl.localhost\Ubuntu\home\luo\.hermes\memories"),
    Path.home() / ".hermes" / "memories",
]
TARGETS = ("MEMORY.md", "USER.md")


def log(message: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def resolve_hot_dir(explicit: str = "") -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.is_dir() else None
    override = os.environ.get("HERMES_MEMORIES_DIR", "")
    if override:
        path = Path(override)
        if path.is_dir():
            return path
    for candidate in HOT_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def find_git() -> str | None:
    found = shutil.which("git")
    if found:
        return found
    for candidate in (r"D:\Git\cmd\git.exe", r"C:\Program Files\Git\cmd\git.exe"):
        if Path(candidate).exists():
            return candidate
    return None


def run_git(git: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run([git, "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode, output


def snapshot(hot_dir: Path) -> list[str]:
    HOT_DIR.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in TARGETS:
        source = hot_dir / name
        if not source.is_file():
            log(f"跳过 {name}：源文件不存在")
            continue
        data = source.read_bytes()
        target = HOT_DIR / name
        if target.exists() and target.read_bytes() == data:
            log(f"未变化 {name}（{len(data)} 字节）")
            continue
        target.write_bytes(data)
        copied.append(name)
        log(f"已更新 {name}（{len(data)} 字节）")
    return copied


def run_export() -> None:
    script = ROOT / "tools" / "export_memories.py"
    # 子进程固定 UTF-8：计划任务环境下控制台编码是 cp936，中文输出会静默失败。
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(script), "--rolling"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    detail = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    summary = next((line for line in lines if line.startswith("导出")), lines[-1] if lines else "")
    log(f"导出 mem0：{summary or f'退出码 {proc.returncode}，无输出'}")


def commit_and_push(git: str, push: bool) -> None:
    code, _ = run_git(git, "add", "-A")
    if code != 0:
        log("git add 失败")
        return
    code, _ = run_git(git, "diff", "--cached", "--quiet")
    if code == 0:
        log("没有需要提交的变更")
    else:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        code, output = run_git(git, "commit", "-m", f"记忆快照 {stamp}")
        log(f"提交：{'成功' if code == 0 else '失败 ' + output[:120]}")
    if not push:
        return
    code, output = run_git(git, "push", "origin", "HEAD")
    log(f"推送：{'成功' if code == 0 else '失败 ' + output[:160]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="单向快照 Hermes 热记忆到仓库")
    parser.add_argument("--hot-dir", default="", help="显式指定热记忆目录")
    parser.add_argument("--export", action="store_true", help="同时导出 mem0 全量（滚动文件）")
    parser.add_argument("--commit", action="store_true", help="有变更时自动提交")
    parser.add_argument("--push", action="store_true", help="提交后推送到 origin")
    args = parser.parse_args()

    hot_dir = resolve_hot_dir(args.hot_dir)
    if hot_dir is None:
        log("未找到热记忆目录（WSL 未启动？）候选：" + "; ".join(str(p) for p in HOT_CANDIDATES))
        return 1
    log(f"源目录：{hot_dir}")

    changed = snapshot(hot_dir)
    if args.export:
        run_export()

    if args.commit:
        git = find_git()
        if git is None:
            log("未找到 git，跳过提交")
            return 1
        commit_and_push(git, args.push)
    elif changed:
        log("提示：加 --commit 可自动提交")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
