# Dispatching a Claude worker

Part of `orchestra:orchestrator`. Read it before dispatching a task routed to a Claude worker.

**Claude worker**: use the `Agent` tool.

| Effort | subagent_type |
|--------|---------------|
| high | `orchestra:implementer` |
| medium | `orchestra:implementer-medium` |
| xhigh | `orchestra:implementer-xhigh` |

Pass `model` from the routing value. Effort comes from the agent definition;
for another effort, tell the user it needs a new agent file.

Record a scope baseline right before dispatching a Claude worker or sending it
a new task, and check it before each review of that task, including after fix
rounds. `<workspace>` is the directory `sdd-workspace` prints:

```text
node "<this skill's base directory>/scripts/scope-check.mjs" before --cwd "<project>" --state "<workspace>/task-N-scope.json"
node "<this skill's base directory>/scripts/scope-check.mjs" after --cwd "<project>" --state "<workspace>/task-N-scope.json" --allowed "<files>"
```

`after` prints the same `Scope:` line as a Codex worker and also counts files
the worker committed. `--allowed` follows the Codex worker rules in `dispatch-codex.md`.
