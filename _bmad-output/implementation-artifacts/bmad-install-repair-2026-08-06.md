# BMAD Installation Repair — 2026-08-06

## Scope

Restore and update the project-local BMAD installation for Claude Code while
preserving the existing Codex configuration.

## Commands and Results

1. `npx bmad-method install --action update --tools claude-code,codex --yes`
   - Completed through the BMAD installer.
   - Installed the 46 base Core/BMM skills to both `.claude/skills` and
     `.agents/skills`.
   - Preserved eight custom BMAD files.

2. `uv tool upgrade bmad-loop --reinstall`
   - Refreshed the uv-managed `bmad-loop` tool from its canonical Git source.
   - Updated source revision from `e137b0d` to `c0d76af` (package version remains
     `0.9.0`).

3. `npx bmad-method install --action update --tools claude-code,codex --custom-source https://github.com/bmad-code-org/bmad-loop.git --yes`
   - Registered the external `bmad-loop` module through BMAD's installer.
   - Manifest now records `bmad-loop` v0.9.1 from
     `https://github.com/bmad-code-org/bmad-loop` at `67aa802`.
   - Installed 49 skills for each supported CLI.

4. `bmad-loop init --project /Users/antonio/howdoidata/projects/f1_analytics --cli claude --cli codex --force-skills`
   - Refreshed the three Loop skills for both CLIs.
   - Confirmed Claude and Codex hooks are registered.
   - Preserved the existing policy, which uses Codex for dev, review, and triage.

5. `bmad-loop validate --project /Users/antonio/howdoidata/projects/f1_analytics`
   - Passed: BMAD config, policy, sprint status, clean worktree, tmux, process
     host, Codex adapter/hooks, and upstream skills.

## Result

Claude Code is installed at `.claude/skills` with 49 BMAD skills and the
project's Loop hooks in `.claude/settings.json`. Codex remains installed and
registered at `.agents/skills`.

## One-Time User Action

Start `claude` once from this project and accept its workspace-trust and hooks
approval dialogs before running `bmad-loop run`; spawned Loop sessions cannot
answer those prompts.
