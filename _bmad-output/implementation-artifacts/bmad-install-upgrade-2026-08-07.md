# BMAD Installation Upgrade — 2026-08-07

## Scope

Add the `bmb` (BMad Builder) module and move `core`/`bmm` onto the
`bmad-method@next` pre-release channel, so the `bmad-build` /
`bmad-build-auto` skills (and the rest of the pre-release skill set) are
available in Claude Code and Codex. Triggered by comparing this project's
skill list against a newer sibling install that already had these skills.

## Commands and Results

1. `npx bmad-method install --action update --tools claude-code,codex --modules bmb --directory "$(pwd)" --yes`
   - Added the external `bmb` module (BMad Builder v2.1.0, stable channel,
     sha `d54981a`).
   - Installed 18 skills to `.claude/skills` and `.agents/skills`:
     `bmad-agent-builder`, `bmad-module-builder`, `bmad-workflow-builder`,
     `bmad-bmb-setup`, `bmad-eval-runner`, and supporting files.
   - Did **not** produce `bmad-build` / `bmad-build-auto` — those turned out
     to belong to `bmm`'s pre-release channel, not `bmb`.

2. `npx bmad-method@next install --action update --tools claude-code,codex --directory "$(pwd)" --yes`
   - Running the CLI via the npm `next` dist-tag (currently
     `6.10.1-next.51`) is what actually moves the *built-in* `core`/`bmm`
     modules off `@latest` (`6.10.0`) — the installer's own `--next <code>`
     module flag only affects externally-fetched modules (`bmb`, `tea`,
     `cis`, `wds`, custom sources), not `core`/`bmm`, which ship inside the
     npm package itself.
   - `core`: `6.10.0` → `6.10.1-next.51`. `bmm`: `6.10.0` → `6.10.1-next.51`.
   - `bmb` was refreshed to `main @ e6935f2` (prerelease launches default
     all external modules to the `next` channel unless pinned).
   - Result: 54 skills installed per tool. `bmad-dev-auto`, `bmad-quick-dev`,
     `bmad-dev-story`, `bmad-create-story` became deprecated forwarders to
     `bmad-build` / `bmad-build-auto`. Several other skills merged
     (`bmad-editorial-review-*` and `bmad-review-*` → `bmad-review`;
     `bmad-technical-research` / `bmad-market-research` / `bmad-domain-research`
     → `bmad-deep-recon`; `bmad-document-project` /
     `bmad-generate-project-context` → `bmad-project-context`;
     `bmad-sprint-status` → `bmad-sprint-planning`).
   - Side effect: the `bmad-loop` external module (originally registered via
     `--custom-source`, not an official module) was silently dropped from
     the manifest — `--yes` only carries forward modules the installer
     recognizes as "existing" (`core`, `bmm`, `bmb`), not custom-source
     ones. Its three skills (`bmad-loop-setup`, `bmad-loop-resolve`,
     `bmad-loop-sweep`) disappeared from `.claude/skills` /
     `.agents/skills`. The `.bmad-loop/` hook scripts, policy, and the
     separately uv-managed `bmad-loop` CLI tool (0.9.0) were untouched, so
     the Claude Code hooks kept firing — only the skill *definitions* were
     lost.

3. `npx bmad-method@next install --action update --tools claude-code,codex --modules core,bmm,bmb --custom-source https://github.com/bmad-code-org/bmad-loop.git --directory "$(pwd)" --yes`
   - Re-registered `bmad-loop` as a custom-source module (same source as the
     2026-08-06 repair). Resolved to `main @ 70d1e9f`.
   - Restored the three `bmad-loop-*` skills.
   - Result: 57 skills installed per tool.

4. `bmad-loop validate --project "$(pwd)"`
   - Passed: BMAD config, policy, sprint status, clean worktree, tmux,
     process host, Claude hooks, and — notably — "upstream skills present
     (bmad-build-auto + review layers)", confirming the Loop orchestrator's
     dependency on the renamed skill resolves correctly.

## Result

`_bmad/_config/manifest.yaml`:

| module    | version           | source   |
|-----------|--------------------|----------|
| core      | 6.10.1-next.51     | built-in |
| bmm       | 6.10.1-next.51     | built-in |
| bmb       | main @ e6935f2     | external (channel: next) |
| bmad-loop | main @ 70d1e9f     | external (custom-source) |

Claude Code (`.claude/skills`) and Codex (`.agents/skills`) each have 57
BMAD skills, including `bmad-build`, `bmad-build-auto`,
`bmad-agent-builder`, `bmad-module-builder`, `bmad-workflow-builder`,
`bmad-bmb-setup`, `bmad-eval-runner`, and the three `bmad-loop-*` skills.

None of this touched tracked files — `.claude/`, `.agents/`, and `_bmad/*`
(except `_bmad/custom/`) are gitignored, so the upgrade is local machine
state, not a repo change.

## Caveats

- **Pre-release channel.** `core`/`bmm` now track the unreleased
  `bad-method@next` npm tag, not a stable release. Skill names and behavior
  under `_bmad/bmm` may shift again before `6.10.1` tags stable. `bmb` and
  `bmad-loop` are similarly tracking their `main` branches rather than a
  pinned tag.
- **Custom-source modules drop silently on `--yes` updates that omit
  `--custom-source`.** Any future `bmad-method install --action update
  --yes` run that doesn't explicitly re-pass `--custom-source
  https://github.com/bmad-code-org/bmad-loop.git` will likely drop
  `bmad-loop` again — re-run step 3's command (or an equivalent) afterward
  and confirm with `bmad-loop validate`.
- **Rollback.** To return to the stable channel:
  `npx bmad-method install --action update --tools claude-code,codex --directory "$(pwd)" --yes`
  (no `@next`) — this restores `core`/`bmm` to `6.10.0` and the pre-upgrade
  skill names. `bmad-loop` would still need `--custom-source` re-passed to
  survive that update.
