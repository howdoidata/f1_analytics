---
title: "Keep .bmad-loop/policy.toml Gitignored — Tracking It Conflicts With The Installer"
status: accepted
created: 2026-08-08
source_material:
  - _bmad-output/implementation-artifacts/deferred-work.md (bmad-build multi-goal split, 2026-08-08)
  - _bmad-output/planning-artifacts/decisions/track-bmad-workspace-memlogs-2026-08-08.md
  - ~/.local/share/uv/tools/bmad-loop/lib/python3.14/site-packages/bmad_loop/install.py (bmad-loop v0.9.1, commit 67aa802)
---

# Keep .bmad-loop/policy.toml Gitignored — Tracking It Conflicts With The Installer

## Purpose

Resolves the `.bmad-loop/policy.toml` item deferred during the 2026-08-08
gitignore audit's multi-goal split: `bmad-loop init` gitignores this file
wholesale, but it mixes genuinely machine-specific settings ([tui] pane
sizes, [mux] backend) with project-wide orchestration policy ([gates],
[review], [scm], [adapter] CLI routing — e.g. which coding CLI runs dev vs.
review) that is invisible to git and unreviewable by the team.

## Decision

**Keep it gitignored — do not track it.** Tracking was attempted and
reverted. `bmad_loop/install.py`'s `init` command unconditionally re-appends
`.bmad-loop/policy.toml` to `.gitignore` whenever that exact line is absent,
and separately warns to `git rm --cached` it once it detects the file is
tracked — both hardcoded, with no suppression flag. Tracking the file
would not be a one-time fix: every future `init` run (registering a new
adapter, an upgrade) would re-dirty `.gitignore` and print a nag urging the
opposite of this decision.

This project does not modify its locally-installed `bmad-loop` package to
work around that: the tool is uv-managed from an external Git source and any
local edit would be silently discarded by the next `uv tool upgrade
--reinstall` — already a routine operation here — leaving a fix that looks
present but isn't.

**Left unresolved by this decision:** the project-wide orchestration policy
`policy.toml` carries ([gates], [review], [scm], [adapter] routing) remains
invisible to git and unreviewable by the team. The only clean fix is
upstream: `bmad-loop init` would need to split machine-local keys ([mux],
[tui]) into a separate gitignored file from project-shared ones, or accept a
`--track-policy` style opt-out from its own gitignore-enforcement. Neither
exists today.

## Status

Accepted. `.gitignore` and `.bmad-loop/policy.toml` both reverted to their
pre-investigation state. The underlying visibility gap is filed as still-open
in `deferred-work.md`, now scoped correctly as an upstream `bmad-loop`
limitation rather than something this repo can fix alone.
