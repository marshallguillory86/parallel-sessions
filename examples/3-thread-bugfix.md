# Example: 3 unrelated bug fixes in parallel

Scenario: three production bugs filed against unrelated subsystems. None depend on the others, none share files. Perfect fanout candidate.

## The plan

```toml
[[threads]]
id = 1
branch = "fix-checkout-rounding"
goal = "Fix off-by-one rounding in cart total when discount > 50%"
owns = ["services/cart/", "tests/cart/"]
forbids = ["services/notifications/", "platform/jobs/"]
merge_order = 1

[[threads]]
id = 2
branch = "fix-email-utf8"
goal = "Email digest mangles non-ASCII subject lines"
owns = ["services/notifications/email/", "tests/notifications/email/"]
forbids = ["services/cart/", "platform/jobs/"]
merge_order = 2

[[threads]]
id = 3
branch = "fix-job-retry-storm"
goal = "Background job retries with no backoff after redis flap"
owns = ["platform/jobs/", "tests/platform/jobs/"]
forbids = ["services/cart/", "services/notifications/"]
merge_order = 3
```

## Why this is a good fanout candidate

- Three filed bugs, three reviewers expected — one PR per bug keeps review clean.
- Each fix is small (under a day), so the coordination overhead of three worktrees + three PRs is amortized cheaply.
- Owned paths are genuinely disjoint. No two threads can collide.

## Why you might NOT fan this out

If all three bugs trace back to the same shared dependency (say, a util in `platform/shared/`), the fanout breaks down — whoever lands first wins, the other two rebase. In that case, fix the shared util in one thread first, then fan out the bug fixes after.

This is the kind of judgment the `plan.toml` step forces you to make *before* you spawn three Claude sessions and discover the conflict three hours in.
