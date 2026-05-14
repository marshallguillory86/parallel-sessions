# Security policy

## Reporting a vulnerability

If you find a security issue, please email **marshallguillory@gmail.com** instead of opening a public issue. Best-effort response within 7 days. No bounty.

## Threat model

`parallel-sessions` runs entirely on the operator's local machine. It:

- Parses a `plan.toml` with the stdlib `tomllib`.
- Invokes `git` and `gh` via `subprocess.run` with the operator's path strings.
- Writes a generated `THREAD_BRIEF.md` into each worktree.
- Appends a single line (`THREAD_BRIEF.md`) to each worktree's `.git/info/exclude`.

It does **not** open network sockets, handle credentials, or read/write outside the current git repo.

## In scope

- Any input (`plan.toml` contents, path strings) that causes the CLI to exec arbitrary commands.
- Path-overlap bypass that lets two threads write to the same directory tree.
- Worktree cleanup deleting a dirty or unmerged tree.

## Out of scope

- Issues in `git`, `gh`, or the Claude Code CLI itself — report those upstream.
- Operator running `parallel-sessions` against a repo whose history they don't own.
