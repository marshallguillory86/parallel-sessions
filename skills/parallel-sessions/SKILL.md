---
name: parallel-sessions
description: Use when the user wants to run 3-5 Claude Code sessions in parallel on the same repo via git worktrees, fan out independent task threads, validate that threads don't claim overlapping paths, or re-converge worktree branches into PRs. Skip for single-threaded work, for sub-agent fanout inside one session (use the Agent tool with isolation="worktree" instead), or when the listed tasks touch overlapping files.
---

# Parallel Sessions

## Purpose

Fan out 3-5 **independent** task threads into 3-5 git worktrees, each driven by its own Claude Code session, then re-converge each thread as a separate PR. The skill's value is **path-ownership discipline** + **mechanical re-convergence**, not the `git worktree add` call itself.

## When to invoke

- The user explicitly asks for parallel Claude Code sessions, worktree fanout, or N-way parallelism on one repo.
- The user lists 3+ independent tasks and asks how to attack them at once.
- The user references this skill by name (`/parallel-sessions`).

## When NOT to invoke

- Listed tasks touch overlapping files. Merge cost will exceed parallel speedup — refuse and say so.
- Single task that fits in one session.
- The user wants sub-agents *inside* one session — direct them to the `Agent` tool with `isolation: "worktree"` instead.

## Core workflow

### 1. Plan (always first)

Before any worktree gets created, walk the operator through a plan. Use `templates/plan.toml.example` as a starting point. Required per thread:

- **id** (1..N, unique)
- **branch** (short kebab-case slug)
- **goal** (one sentence)
- **owns** (list of paths this thread is allowed to edit)
- **forbids** (list of paths this thread must not touch — usually the union of other threads' `owns`)
- **merge_order** (intended landing sequence)

**Hard validation rules — refuse fanout if any fails:**

- Thread count is 3..5. Two threads is just two sessions; >5 the coordination cost dominates.
- No two threads share an `owns` path or have one path that is a prefix of another's. Overlap = merge hell.
- Branch names are unique.
- IDs are unique.

If the user lists tasks where overlap is unavoidable, **stop and say so**. Suggest serializing the overlapping pair into one thread instead.

### 2. Fanout

```bash
parallel-sessions fanout plan.toml
```

The CLI:
- Refuses if the working tree is dirty.
- Creates `worktrees/thread-<id>/` per thread, on a branch named `parallel/<branch>-thread-<id>` off current `HEAD`.
- Drops a generated `THREAD_BRIEF.md` into each worktree (goal, owned/forbidden paths, merge order).
- Prints the `cd <worktree> && claude` invocations the operator opens in separate terminals.

**The skill does NOT launch the terminals.** The operator does, so every thread is human-attended.

### 3. Status

```bash
parallel-sessions status
```

Per-worktree: branch, ahead/behind main, dirty/clean, last commit. Use when the operator asks "where are we?"

### 4. Converge

```bash
parallel-sessions converge          # pushes + opens PRs
parallel-sessions converge --no-push   # prints the commands, runs nothing
```

For each worktree with commits ahead of main:
- Push the branch to `origin`.
- Open a PR titled `[thread-<id>] <goal>`, body links to the generated `THREAD_BRIEF.md`.
- PRs are created in the declared `merge_order`.

The skill stops here. The operator (or CI auto-merge) handles the actual merge.

### 5. Cleanup

```bash
parallel-sessions cleanup
```

Removes worktrees whose branch is merged into `origin/<main>`. Refuses to touch dirty worktrees or worktrees with unmerged commits.

## Hard rules

- **Never auto-launch terminals.** Print the commands; the operator runs them.
- **Never auto-merge PRs.** Operator decides.
- **Never delete a dirty worktree** or one with unmerged commits.
- **Refuse fanout on overlapping owned paths** — even if the user insists. Suggest serializing the conflicting pair.
- **Refuse fanout on a dirty working tree.** Stash or commit first.

## Tradeoff to communicate up-front

The mechanics are easy. The **plan** is the work — if path ownership isn't actually clean, the operator pays the cost in merge conflicts at the end, regardless of how many parallel sessions ran. When in doubt, fewer threads with sharper boundaries beats more threads with fuzzy ones.
