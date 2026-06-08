# KidLand - Agent Guidelines

## Scope

`kidland/` is the first FamilyGuild module and first MVP family workflow.

Use this scope for KidLand implementation work, including FamQuests, quest approvals, FamCoins, FamStore, purchases, KidLand history, and role-specific KidLand views.

## Boundaries

- Keep KidLand domain logic inside `kidland/`.
- Treat `fg-docs/` as the source of truth for product and module scope.
- Reference `fg-core/` when integration with the foundation shell is needed.
- Ask before changing `fg-core/`, `famledger/`, or cross-module contracts.
- Do not build full FamilyGuild platform behavior inside KidLand.

## MVP Rules

- Focus on the 30-day private family validation loop.
- Use trusted member switching through the FamilyGuild foundation for the first private test.
- Keep production authentication out of the first private test unless the user explicitly changes scope.
- Keep XP, levels, and character growth secondary to the basic FamQuest, FamCoins, and FamStore loop.

## Source of Truth

- Workspace rules: `../AGENTS.md`
- KidLand module doc: `../fg-docs/docs/modules/kidland.md`
- MVP plan: `../fg-docs/docs/product/mvp-plan.md`
- Modular architecture: `../fg-docs/docs/architecture/modular-platform.md`
- Workspace architecture plan: `../fg-docs/docs/architecture/workspace-architecture-plan.md`

## Development Defaults

- Use Python, NiceGUI, FastAPI, and dbzero.
- Use full type annotations in Python.
- Use tests for non-trivial domain logic once implementation begins.
- Keep imports ordered as standard library, third-party, then local.
- Use dbzero terminology correctly: state management, memo objects, prefixes, tags, and atomic updates.
