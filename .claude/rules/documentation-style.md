---
description: Markdown style for repo docs
paths:
  - "**/*.md"
globs:
  - "**/*.md"
alwaysApply: false
---

# Documentation style

- Write for humans. Technical terms only when they aid precision.
- One emphasis style per span (no stacked bold + backticks).
- Links: `[path/to/file](path/to/file)` with no backticks on link text.
- Literals (paths, commands, env vars): backticks when not linked; bold for plain emphasis only.
- ASCII only: no emojis, em-dashes, or other non-ASCII punctuation.

## README and user guide

[README.md](../../README.md) is the landing page: what Cleave is, install, a short getting started, CLI, and data locations. [docs/user-guide/README.md](../../docs/user-guide/README.md) is the full end-user guide. Both change with every user-visible change (see AGENTS.md).

- Write for someone with no technical background. Say what a thing does for them, not how it works inside. Avoid internal names (`RowKind`, config keys, YAML paths, libprojectM) in the guide.
- Lead with the in-app path: menu items as **Menu > Item**, keys as they appear in the help column (Ctrl+R, Left/Right, PgUp/PgDn).
- Keep H and the help column as the first source of help. Do not copy every option the help column already explains; name the setting and point to H.
- Prefer short tables for keys, options, and choices. One idea per sentence.
- Screenshots live in `docs/user-guide/images/` as PNG, referenced with a relative path. Add one only where it helps a reader find something.
