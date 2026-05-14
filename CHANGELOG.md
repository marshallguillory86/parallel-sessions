# Changelog

## 0.1.0 — initial release

- `parallel-sessions fanout <plan.toml>` — create N worktrees with per-thread `THREAD_BRIEF.md`, refuses on overlapping owned paths or dirty working tree.
- `parallel-sessions status` — per-worktree branch, ahead count, dirty state, last commit.
- `parallel-sessions converge [--no-push]` — push branches + open one PR per worktree, ordered by `merge_order`.
- `parallel-sessions cleanup` — remove worktrees whose branches are merged to `origin/<main>`; refuses dirty or unmerged worktrees.
- Claude Code skill at `skills/parallel-sessions/SKILL.md`.
