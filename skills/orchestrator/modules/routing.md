# Model choice and routing

Part of `orchestra:orchestrator`. Read it when a config file exists or the user named Codex.

**Default: Claude workers only.** A tier without a usable value uses `easy` →
`claude sonnet/medium`, `medium` → `claude sonnet/high`, `hard` and `ui` →
`claude sonnet/xhigh`. No question.

**Codex is opt-in.** A `codex` routing value or option applies only when the user
named Codex (or a Codex model) in this conversation; otherwise treat it as unset
and use the default for that tier. Never offer Codex in `AskUserQuestion` unless
the user named it. For each tier the user routed to Codex, use the config's codex
value; ask only when that tier has none, offering the codex entries of `options`
or `codex gpt-6-luna/medium` and `codex gpt-6-luna/high`. Tiers the user did not
name stay on Claude.

Read `~/.claude/orchestra.json` and `<project>/.orchestra.json`; ignore either
file if it does not exist. Merge `routing` by key, with project values taking
precedence. A project `options` array replaces the user array; otherwise use the
user array. The values use this schema:

```json
{
  "routing": {
    "easy":   "claude sonnet/medium",
    "medium": "claude sonnet/high",
    "hard":   "claude sonnet/xhigh",
    "ui":     "claude sonnet/xhigh"
  },
  "options": ["claude sonnet/high", "claude sonnet/xhigh", "claude opus/high",
              "codex gpt-6-luna/medium", "codex gpt-6-luna/high"]
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
guessing. Show the final mapping on one line. A cloned repository can ship its
own `.orchestra.json`, and its values spend the user's quota: when any value
comes from the project file, show it and get one confirmation for that project
before the first dispatch. The user may enter another model through `Other`.
Record the final mapping in the ledger as
`Routing: Easy=..., Medium=..., Hard=..., UI=...` when UI is a separate tier.
