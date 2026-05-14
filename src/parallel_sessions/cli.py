"""parallel-sessions CLI: fanout / status / converge / cleanup."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError as err:  # pragma: no cover
    sys.stderr.write("parallel-sessions requires Python 3.11+ (needs tomllib)\n")
    raise SystemExit(2) from err


THREAD_BRIEF = "THREAD_BRIEF.md"
NO_WORKTREES = "no worktrees"


# ---------- plan parsing + validation ----------


def load_plan(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _paths_collide(a: str, b: str) -> bool:
    """True iff two owned paths claim overlapping directory trees.

    Exact match collides. Directory-prefix collides. Substring without a
    directory boundary does NOT collide (e.g. `services/auth` and
    `services/auth-v2` are siblings, not parent/child).
    """
    a = a.strip().rstrip("/") + "/"
    b = b.strip().rstrip("/") + "/"
    if a == b:
        return True
    return a.startswith(b) or b.startswith(a)


def validate_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    threads = plan.get("threads", [])
    if not 3 <= len(threads) <= 5:
        die(f"plan must declare 3-5 threads (got {len(threads)})")

    _check_required_fields(threads)
    _check_uniqueness(threads)
    _check_path_overlap(threads)

    return sorted(threads, key=lambda t: t.get("merge_order", t["id"]))


def _check_required_fields(threads: list[dict[str, Any]]) -> None:
    required = {"id", "branch", "goal", "owns"}
    for t in threads:
        missing = required - set(t.keys())
        if missing:
            die(f"thread {t.get('id', '?')} missing fields: {sorted(missing)}")
        if not t["owns"]:
            die(f"thread {t['id']} has empty owns — declare at least one owned path")


def _check_uniqueness(threads: list[dict[str, Any]]) -> None:
    ids = [t["id"] for t in threads]
    if len(set(ids)) != len(ids):
        die("thread ids must be unique")
    branches = [t["branch"] for t in threads]
    if len(set(branches)) != len(branches):
        die("thread branches must be unique")


def _check_path_overlap(threads: list[dict[str, Any]]) -> None:
    for i, t_a in enumerate(threads):
        for t_b in threads[i + 1 :]:
            collision = _find_overlap(t_a["owns"], t_b["owns"])
            if collision is not None:
                pa, pb = collision
                die(
                    f"path overlap: thread {t_a['id']} owns '{pa}' overlaps "
                    f"thread {t_b['id']} owns '{pb}'"
                )


def _find_overlap(owns_a: list[str], owns_b: list[str]) -> tuple[str, str] | None:
    for pa in owns_a:
        for pb in owns_b:
            if _paths_collide(pa, pb):
                return pa, pb
    return None


# ---------- git helpers ----------


def git_repo_root() -> Path:
    out = _capture(["git", "rev-parse", "--show-toplevel"])
    return Path(out.strip())


def git_head() -> str:
    return _capture(["git", "rev-parse", "HEAD"]).strip()


def working_tree_dirty(cwd: Path | None = None) -> bool:
    out = _capture(["git", "status", "--porcelain"], cwd=cwd)
    return bool(out.strip())


def detect_main_branch() -> str:
    for branch in ("main", "master"):
        try:
            _capture(["git", "rev-parse", "--verify", f"refs/heads/{branch}"])
            return branch
        except subprocess.CalledProcessError:
            continue
    die("could not detect main branch (tried 'main' and 'master')")


def _capture(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(cmd, text=True, cwd=str(cwd) if cwd else None, stderr=subprocess.PIPE)


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check).returncode


# ---------- subcommands ----------


def cmd_fanout(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan).resolve()
    if not plan_path.exists():
        die(f"plan file not found: {plan_path}")

    plan = load_plan(plan_path)
    threads = validate_plan(plan)

    repo_root = git_repo_root()
    if working_tree_dirty():
        die("working tree is dirty — commit or stash before fanout")

    worktrees_dir = repo_root / "worktrees"
    worktrees_dir.mkdir(exist_ok=True)

    head = git_head()
    for t in threads:
        wt_path = worktrees_dir / f"thread-{t['id']}"
        if wt_path.exists():
            die(f"worktree already exists: {wt_path} — run 'parallel-sessions cleanup' first")
        branch = f"parallel/{t['branch']}-thread-{t['id']}"
        _run(["git", "worktree", "add", "-b", branch, str(wt_path), head])
        _write_thread_brief(wt_path, t)

    _print_invocations(threads, worktrees_dir)


def cmd_status(args: argparse.Namespace) -> None:
    repo_root = git_repo_root()
    worktrees_dir = repo_root / "worktrees"
    if not worktrees_dir.exists():
        print(NO_WORKTREES)
        return

    main_branch = detect_main_branch()
    rows = []
    for wt in sorted(worktrees_dir.iterdir()):
        if not (wt / ".git").exists():
            continue
        branch = _capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt).strip()
        try:
            ahead = _capture(["git", "rev-list", "--count", f"{main_branch}..HEAD"], cwd=wt).strip()
        except subprocess.CalledProcessError:
            ahead = "?"
        dirty = "dirty" if working_tree_dirty(cwd=wt) else "clean"
        last = _capture(["git", "log", "-1", "--format=%h %s"], cwd=wt).strip()
        rows.append((wt.name, branch, ahead, dirty, last))

    if not rows:
        print(NO_WORKTREES)
        return

    print(f"{'WORKTREE':<14} {'BRANCH':<48} {'AHEAD':<6} {'STATE':<6} LAST COMMIT")
    for r in rows:
        print(f"{r[0]:<14} {r[1]:<48} {r[2]:<6} {r[3]:<6} {r[4]}")


def cmd_converge(args: argparse.Namespace) -> None:
    repo_root = git_repo_root()
    worktrees_dir = repo_root / "worktrees"
    if not worktrees_dir.exists():
        die("no worktrees to converge")

    main_branch = detect_main_branch()

    candidates = []
    for wt in sorted(worktrees_dir.iterdir()):
        if not (wt / ".git").exists():
            continue
        try:
            ahead = int(_capture(["git", "rev-list", "--count", f"{main_branch}..HEAD"], cwd=wt).strip())
        except (subprocess.CalledProcessError, ValueError):
            ahead = 0
        if ahead == 0:
            continue
        branch = _capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt).strip()
        brief = wt / THREAD_BRIEF
        goal = _parse_goal(brief) if brief.exists() else branch
        candidates.append((wt, branch, goal))

    if not candidates:
        print("no threads have new commits — nothing to converge")
        return

    for wt, branch, goal in candidates:
        title = f"[{wt.name}] {goal}"
        body = "Opened by parallel-sessions. See `THREAD_BRIEF.md` in the worktree for goal + path ownership."
        if args.no_push:
            print(f"# {wt.name}")
            print(f"git -C {wt} push -u origin {branch}")
            print(f"gh pr create --head {branch} --title {title!r} --body {body!r}")
            print()
        else:
            print(f"pushing {branch}…")
            _run(["git", "push", "-u", "origin", branch], cwd=wt)
            print(f"opening PR for {wt.name}…")
            _run(["gh", "pr", "create", "--head", branch, "--title", title, "--body", body], cwd=wt)


def cmd_cleanup(args: argparse.Namespace) -> None:
    repo_root = git_repo_root()
    worktrees_dir = repo_root / "worktrees"
    if not worktrees_dir.exists():
        print(NO_WORKTREES)
        return

    main_branch = detect_main_branch()
    # Best-effort fetch so 'merged into origin/main' check is accurate.
    subprocess.run(["git", "fetch", "origin"], check=False)

    removed: list[str] = []
    skipped: list[tuple[str, str]] = []
    for wt in sorted(worktrees_dir.iterdir()):
        if not (wt / ".git").exists():
            continue
        verdict = _cleanup_one(wt, main_branch)
        if verdict[0] == "removed":
            removed.append(wt.name)
        else:
            skipped.append((wt.name, verdict[1]))

    _print_cleanup_report(removed, skipped)


def _cleanup_one(wt: Path, main_branch: str) -> tuple[str, str]:
    """Inspect one worktree; remove it if safe. Return (verdict, detail)."""
    if working_tree_dirty(cwd=wt):
        return "skipped", "dirty"
    branch = _capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt).strip()
    if not _is_merged_to_origin(wt, main_branch):
        return "skipped", "unmerged commits"
    _run(["git", "worktree", "remove", str(wt)])
    subprocess.run(["git", "branch", "-D", branch], check=False)
    return "removed", ""


def _is_merged_to_origin(wt: Path, main_branch: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", "HEAD", f"origin/{main_branch}"],
            cwd=str(wt),
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _print_cleanup_report(removed: list[str], skipped: list[tuple[str, str]]) -> None:
    if removed:
        print(f"removed: {', '.join(removed)}")
    if skipped:
        print("skipped:")
        for name, reason in skipped:
            print(f"  {name} ({reason})")
    if not removed and not skipped:
        print("nothing to clean up")


# ---------- helpers for fanout output ----------


def _write_thread_brief(wt_path: Path, thread: dict[str, Any]) -> None:
    owns = thread.get("owns", [])
    forbids = thread.get("forbids", [])
    brief = wt_path / THREAD_BRIEF
    _exclude_locally(wt_path, THREAD_BRIEF)
    brief.write_text(
        f"""# Thread {thread['id']}: {thread['branch']}

## Goal
{thread['goal']}

## Owned paths (you may edit)
{_fmt_list(owns)}

## Forbidden paths (do NOT edit)
{_fmt_list(forbids)}

## Merge order
Position {thread.get('merge_order', '?')} in the declared landing sequence.

---
Generated by parallel-sessions. Do not commit this file.
"""
    )


def _exclude_locally(wt_path: Path, pattern: str) -> None:
    """Append `pattern` to the worktree's per-checkout exclude file.

    Keeps THREAD_BRIEF.md out of `git status` without touching the user's
    repo-wide .gitignore.
    """
    try:
        exclude_path = Path(
            _capture(["git", "rev-parse", "--git-path", "info/exclude"], cwd=wt_path).strip()
        )
    except subprocess.CalledProcessError:
        return
    if not exclude_path.is_absolute():
        exclude_path = wt_path / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text() if exclude_path.exists() else ""
    if pattern in existing.splitlines():
        return
    sep = "" if existing.endswith("\n") or not existing else "\n"
    exclude_path.write_text(f"{existing}{sep}{pattern}\n")


def _fmt_list(items: list[str]) -> str:
    if not items:
        return "_(none)_"
    return "\n".join(f"- `{i}`" for i in items)


def _parse_goal(brief: Path) -> str:
    in_goal = False
    for line in brief.read_text().splitlines():
        if line.strip() == "## Goal":
            in_goal = True
            continue
        if in_goal:
            line = line.strip()
            if line.startswith("#"):
                break
            if line:
                return line
    return "untitled"


def _print_invocations(threads: list[dict[str, Any]], worktrees_dir: Path) -> None:
    print()
    print(f"created {len(threads)} worktrees. open each in its own terminal:")
    print()
    for t in threads:
        wt = worktrees_dir / f"thread-{t['id']}"
        print(f"  # thread {t['id']}: {t['goal']}")
        print(f"  cd {wt} && claude")
        print()
    print("when threads are ready to merge:  parallel-sessions converge")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


# ---------- entry point ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parallel-sessions")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fanout = sub.add_parser("fanout", help="create worktrees from a plan.toml")
    p_fanout.add_argument("plan", help="path to plan.toml")
    p_fanout.set_defaults(func=cmd_fanout)

    p_status = sub.add_parser("status", help="show status across all worktrees")
    p_status.set_defaults(func=cmd_status)

    p_converge = sub.add_parser("converge", help="push branches + open one PR per worktree")
    p_converge.add_argument("--no-push", action="store_true", help="print commands, do not push or open PRs")
    p_converge.set_defaults(func=cmd_converge)

    p_cleanup = sub.add_parser("cleanup", help="remove merged worktrees")
    p_cleanup.set_defaults(func=cmd_cleanup)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
