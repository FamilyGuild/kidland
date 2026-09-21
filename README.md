# KidLand

First FamilyGuild module and first MVP family workflow.

## Purpose

Turn everyday child responsibilities into a simple first loop of `FamQuests`, `FamCoins`, and `FamStore`. XP, levels, and character growth come after the basic loop proves useful.

## Source of Truth

Canonical module documentation is in `../fg-docs/docs/modules/kidland.md`.

## Initial Scope

- consume foundation-owned household and member context,
- KidLand child profiles,
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
- `dbzero-pro>=0.6.4` with `import dbzero as db0` at runtime,
- `dbzero-modelkit>=1.2` for focused model primitives.

## Implemented Domain Foundation

KidLand currently provides child profiles, the auditable FamCoins ledger, and
minimal persisted FamQuest and FamStore entities for multilingual text. The
quest lifecycle, store purchase workflow, recurrence, UI, and core integration
remain separate implementation steps.

FamQuest titles and descriptions, FamStore item titles, descriptions and
fulfillment notes, and purchase title snapshots use `ML_String`. KidLand text
resolution explicitly falls back to the primary string when a requested
translation is absent.

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

AWS credentials and the temporary pip token stay outside this repository. Run `bash ../scripts/logout_aws_codeartifacts.sh` from this subproject directory when you want to restore the prior user pip index URL.

### Verify a fresh environment

Use Python 3.12 explicitly. An existing environment containing legacy `dbzero`
can import `dbzero` and run older tests without satisfying this project's
dependencies. Creating a venv over an existing `.venv` does not clean it.

To preserve your current environment, create a fresh local checkout outside the
workspace. Authenticate from the original workspace first, then run the commands
below from the fresh checkout. Keep KidLand and core environments separate;
do not copy packages from an old environment.

Install and verify from the fresh checkout:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m pip check
./.venv/bin/python -c 'from importlib.metadata import version; print("dbzero-pro", version("dbzero-pro"))'
./.venv/bin/python -c 'import dbzero as db0; print(db0.__name__)'
./.venv/bin/python -m pytest
```

The installed version must satisfy `pyproject.toml`; a legacy `dbzero`
distribution is not a substitute for `dbzero-pro`. Restore the prior pip index
using the logout helper in the original workspace, including after a failed
installation. Never commit environments, pip configuration, or authentication
output. These checks verify declared dependencies, not exact-version locking.

## Rule

Keep this module's domain logic clean and independently understandable, but run the first MVP through the thin FamilyGuild foundation app.
