# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-14

### Added

- `parallel-sessions fanout <plan.toml>` — create N worktrees with a generated `THREAD_BRIEF.md` per thread.
- `parallel-sessions status` — per-worktree branch, ahead count, dirty state, last commit.
- `parallel-sessions converge [--no-push]` — push branches + open one PR per worktree, ordered by `merge_order`.
- `parallel-sessions cleanup` — remove worktrees whose branches are merged to `origin/<main>`; refuses dirty or unmerged worktrees.
- Claude Code skill at `skills/parallel-sessions/SKILL.md`.
- Plan validation: 3–5 threads, unique ids + branches, no overlapping owned paths (directory-prefix collision check).
- Auto-excludes `THREAD_BRIEF.md` from each worktree's `git status` via `.git/info/exclude`.
- CI on Python 3.11 / 3.12 / 3.13: ruff lint, pytest, end-to-end fanout smoke.
- Release workflow: tag → build sdist+wheel → attached GitHub Release.
