# KidLand

First FamilyGuild module and first MVP family workflow.

## Purpose

Turn everyday child responsibilities into a simple first loop of `FamQuests`, `FamCoins`, and `FamStore`. XP, levels, and character growth come after the basic loop proves useful.

## MVP Status

Documentation draft exists in `../fg-docs/docs/modules/kidland.md`.

Implementation has not started yet. The first MVP should run inside a minimal FamilyGuild foundation shell from `../fg-core`.

## Initial Scope

- family setup,
- parent account,
- child profiles,
- FamQuests,
- quest approvals,
- FamCoins ledger,
- FamStore,
- purchases,
- basic history,
- child dashboard,
- parent dashboard.

## Initial Stack

- Python,
- NiceGUI,
- FastAPI,
- dbzero.

## Development

Run tests from this directory:

```bash
./.venv/bin/python -m pytest
```

Install development dependencies first if needed:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
```

## Rule

Keep this module's domain logic clean and independently understandable, but run the first MVP through the thin FamilyGuild foundation app.
