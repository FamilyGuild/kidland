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
- `dbzero-pro>=0.6.0` with `import dbzero as db0` at runtime.

## Development

Run tests from this directory:

```bash
./.venv/bin/python -m pytest
```

Install development dependencies first if needed:

```bash
cd ..
bash scripts/login_aws_codeartifacts.sh
cd kidland
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
```

AWS credentials and the temporary pip token stay outside this repository. Run `bash ../scripts/logout_aws_codeartifacts.sh` from the workspace root when you want to restore the prior user pip index URL.

## Rule

Keep this module's domain logic clean and independently understandable, but run the first MVP through the thin FamilyGuild foundation app.
