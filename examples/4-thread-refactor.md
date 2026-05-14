# Example: 4-thread refactor

Scenario: a backend repo where four cleanups have been queued for a while and they touch *almost* disjoint areas. Doing them in series would take a week; doing them in parallel takes an afternoon — provided the path boundaries are clean.

## The plan

```toml
[[threads]]
id = 1
branch = "extract-auth"
goal = "Move auth middleware out of services/api into services/auth"
owns = ["services/auth/", "tests/auth/"]
forbids = ["services/payments/", "platform/models/", "services/api/routes/v1/"]
merge_order = 1

[[threads]]
id = 2
branch = "models-package"
goal = "Consolidate ORM models under platform/models"
owns = ["platform/models/", "tests/platform/models/"]
forbids = ["services/auth/", "services/api/routes/v1/", "docs/openapi.yaml"]
merge_order = 2

[[threads]]
id = 3
branch = "deprecate-v1-routes"
goal = "Remove deprecated /v1/* routes and regenerate the OpenAPI spec"
owns = ["services/api/routes/v1/", "docs/openapi.yaml"]
forbids = ["services/auth/", "platform/models/", "scripts/dev/"]
merge_order = 3

[[threads]]
id = 4
branch = "dev-script-cleanup"
goal = "Delete unused scripts under scripts/dev/ and tighten the rest"
owns = ["scripts/dev/"]
forbids = ["services/auth/", "platform/models/", "services/api/routes/v1/"]
merge_order = 4
```

## Walk-through

```bash
$ parallel-sessions fanout plan.toml
created worktree /repo/worktrees/thread-1 on branch parallel/extract-auth-thread-1
created worktree /repo/worktrees/thread-2 on branch parallel/models-package-thread-2
created worktree /repo/worktrees/thread-3 on branch parallel/deprecate-v1-routes-thread-3
created worktree /repo/worktrees/thread-4 on branch parallel/dev-script-cleanup-thread-4

worktrees ready. open each in a separate terminal:

  # thread 1: Move auth middleware out of services/api into services/auth
  cd /repo/worktrees/thread-1 && claude

  # thread 2: Consolidate ORM models under platform/models
  cd /repo/worktrees/thread-2 && claude

  # thread 3: Remove deprecated /v1/* routes and regenerate the OpenAPI spec
  cd /repo/worktrees/thread-3 && claude

  # thread 4: Delete unused scripts under scripts/dev/ and tighten the rest
  cd /repo/worktrees/thread-4 && claude

when threads have commits to land:  parallel-sessions converge
```

Each terminal opens Claude Code inside its own worktree. The first thing Claude sees there is `THREAD_BRIEF.md` with the goal, owned paths, and forbidden paths.

## Mid-flight check

```bash
$ parallel-sessions status
WORKTREE       BRANCH                                          AHEAD STATE  LAST COMMIT
thread-1       parallel/extract-auth-thread-1                      3 clean  a1b2c3d move auth router
thread-2       parallel/models-package-thread-2                    1 dirty  d4e5f6a wip: extract Base
thread-3       parallel/deprecate-v1-routes-thread-3               5 clean  9876543 regenerate openapi
thread-4       parallel/dev-script-cleanup-thread-4                0 clean  102c6b2 (origin/main)
```

Thread 4 hasn't started yet (0 ahead). Thread 2 has uncommitted work. Threads 1 and 3 are committable.

## Converge

```bash
$ parallel-sessions converge
pushing parallel/extract-auth-thread-1...
opened PR: [thread-1] Move auth middleware out of services/api into services/auth
pushing parallel/models-package-thread-2...
opened PR: [thread-2] Consolidate ORM models under platform/models
pushing parallel/deprecate-v1-routes-thread-3...
opened PR: [thread-3] Remove deprecated /v1/* routes and regenerate the OpenAPI spec
```

PRs land in `merge_order`. Thread 4 was skipped (no commits ahead).

## After the PRs merge

```bash
$ parallel-sessions cleanup
removed: thread-1, thread-3
skipped:
  thread-2 (unmerged commits)
  thread-4 (unmerged commits)
```

Cleanup only removes worktrees whose `HEAD` is reachable from `origin/main`. Anything still in flight stays put.
