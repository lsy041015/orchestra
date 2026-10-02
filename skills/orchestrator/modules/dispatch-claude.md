# Dispatching a Claude worker

Part of `orchestra:orchestrator`. Read it before dispatching a task routed to a Claude worker.
`<this skill's base directory>` below is the directory of `orchestra:orchestrator`.

**Claude worker**: use the `Agent` tool.

| Effort | subagent_type |
|--------|---------------|
| high | `orchestra:implementer` |
| medium | `orchestra:implementer-medium` |
| xhigh | `orchestra:implementer-xhigh` |

Pass `model` from the routing value. Effort comes from the agent definition;
efforts other than medium, high and xhigh have no agent: ask the user to pick one of those.

Record a scope baseline right before dispatching a Claude worker or sending it
a new task, and check it before each review of that task, including after fix
rounds. `<workspace>` is the directory `sdd-workspace` prints:

```text
node "<this skill's base directory>/scripts/scope-check.mjs" before --cwd "<project>" --state "<workspace>/task-N-scope.json"
node "<this skill's base directory>/scripts/scope-check.mjs" after --cwd "<project>" --state "<workspace>/task-N-scope.json" --allowed "<files>"
```

`after` prints the same `Scope:` line as a Codex worker and also counts files
the worker committed. `--allowed` is a comma-separated list relative to `--cwd`;
end an entry with `/` to allow a whole directory (`src/retry.ts,test/fixtures/`).
An entry that names the repository root is rejected (exit code 2). `--cwd` is the
repository root.

The check needs `node` and `git`. When either is missing, count the check as
`unchecked`, review `git status` and the whole diff yourself, and say why.
Caches the task's own commands write (`__pycache__/`, `node_modules/`) show as
`outside allowed` without `(ignored)` when the project has no ignore rule for
them: add the rule to `.git/info/exclude` before the first baseline.
