# Model choice and routing

Part of `orchestra:orchestrator`. Read it when a tier has no confirmed routing value yet.


Before asking the user, read `~/.claude/orchestra.json` and `<project>/.orchestra.json`;
ignore either file if it does not exist. Merge `routing` by key, with project
values taking precedence. A project `options` array replaces the user array;
otherwise use the user array. The values use this schema:

```json
{
  "routing": {
    "easy": "codex gpt-6-luna/medium",
    "medium": "claude sonnet/high",
    "hard": "claude opus/high",
    "ui": "claude opus/high"
  },
  "options": ["codex gpt-6-luna/medium", "codex gpt-6-luna/high",
              "claude sonnet/high", "claude opus/high"]
}
```

Routing values have the form `<codex|claude> <model>/<effort>`.
- Claude: `<model>` is a model alias the `Agent` tool accepts (for example
  `sonnet`, `opus`, `haiku`). Effort `high` uses `orchestra:implementer`,
  `medium` uses `orchestra:implementer-medium` and `xhigh` uses
  `orchestra:implementer-xhigh`.
- Codex: `<model>` is any model your Codex CLI account can use; `<effort>` is
  one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`.
  Not every model supports every effort. When Codex's model cache
  (`$CODEX_HOME/models_cache.json`, default `~/.codex`) lists the model without
  that effort, the worker returns `Status: BLOCKED` before Codex runs; any other
  unsupported pair comes back from Codex as a failed run.

Use the `ui` key for separately routed UI tasks and `hard` for other hard
tasks; without a `ui` value, UI tasks use `hard`. If a file is not valid JSON
or a value does not match the form, tell the user which one and ask instead of
guessing. If every tier in the task table has a routing value, skip questions
and show the mapping on one line. A cloned repository can ship its own
`.orchestra.json`, and its values spend the user's quota: when any value comes
from the project file, show it and get one confirmation for that project
before the first dispatch. Ask with `AskUserQuestion` only for tiers without a
value, using the merged `options` array or the four example choices above when
it is absent. The user may enter
another model through `Other`. Record the final mapping in the ledger as
`Routing: Easy=..., Medium=..., Hard=..., UI=...` when UI is a separate tier.
