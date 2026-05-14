# parallel-sessions

A Claude Code skill + CLI for running 3-5 Claude Code sessions in parallel on the same repo, via [git worktrees](https://git-scm.com/docs/git-worktree).

> Inspired by A. Horn's tip on LinkedIn:
> *Run 3-5 sessions in parallel → Use Git worktrees to run parallel Claude Code sessions on the same repo so you can progress multiple threads without mixing context.*

The mechanics of `git worktree add` are trivial. The hard parts — and what this skill enforces — are:

- **Path-ownership discipline.** If two threads both edit `services/auth/`, you get merge hell, not parallel speedup. The CLI refuses to fan out when owned paths overlap.
- **Plan-first.** You write a `plan.toml` declaring which thread owns which paths *before* any worktree is created.
- **Re-convergence.** One PR per thread, titled and ordered to match your declared merge sequence.

## Install

```bash
git clone https://github.com/marshallguillory86/parallel-sessions
cd parallel-sessions
pip install -e .
```

This puts the `parallel-sessions` CLI on your PATH.

To register the skill with Claude Code:

```bash
mkdir -p ~/.claude/skills/parallel-sessions
ln -s "$(pwd)/skills/parallel-sessions/SKILL.md" ~/.claude/skills/parallel-sessions/SKILL.md
```

Now `/parallel-sessions` is available inside any Claude Code session.

## Quickstart

From any git repo with a clean working tree:

```bash
# 1. Copy the template, edit it to describe your 3-5 threads.
cp /path/to/parallel-sessions/templates/plan.toml.example plan.toml
$EDITOR plan.toml

# 2. Fan out: creates worktrees/thread-1, thread-2, … on new branches.
parallel-sessions fanout plan.toml

# 3. The CLI prints N invocations like:
#       cd worktrees/thread-1 && claude
#    Open each in its own terminal. The skill never auto-launches terminals —
#    every session is human-attended.

# 4. Check progress across threads.
parallel-sessions status

# 5. When threads are ready: push branches + open one PR each.
parallel-sessions converge          # or: --no-push to dry-run

# 6. After PRs merge, clean up.
parallel-sessions cleanup
```

## Using it inside Claude Code

Type `/parallel-sessions` in any Claude Code session. Claude will:

1. Help you draft the `plan.toml` (especially the path-ownership map).
2. Refuse to proceed if any two threads claim overlapping paths.
3. Run `parallel-sessions fanout` for you and print the per-terminal invocations.

## The plan file

```toml
[[threads]]
id = 1
branch = "extract-auth"
goal = "Move auth middleware out of services/api into services/auth"
owns = ["services/auth/", "tests/auth/"]
forbids = ["services/payments/", "platform/models/"]
merge_order = 1

[[threads]]
id = 2
# ...
```

The CLI generates a `THREAD_BRIEF.md` in each worktree from these fields, so the Claude session inside that worktree sees the goal + the path rules.

## When to use it

Good fits:
- N independent refactors in the same repo
- N unrelated bug fixes
- N feature flags / experiments scoped to disjoint modules

Bad fits — the CLI will refuse or you should pick a different tool:
- Tasks that touch overlapping files (CLI refuses).
- Single tasks (just use one session).
- Sub-agent fanout *inside* one session — use Claude Code's built-in `Agent` tool with `isolation: "worktree"` instead.

## Design tradeoff

The skill optimizes for **human-attended parallelism**: one operator, N terminals, N reviewable PRs. It deliberately does *not*:
- Auto-launch terminals (you'd lose oversight per thread)
- Auto-merge PRs (you decide landing order, even if you already declared one)
- Resolve cross-thread merge conflicts (if they happen despite the path map, you fix them at PR-merge time)

The win is the **plan + path-ownership gate** at the front, plus the **mechanical re-convergence** at the back. The middle — the actual coding — is just N normal Claude Code sessions.

## License

MIT
