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

KidLand provides child profiles, the auditable FamCoins ledger, multilingual
domain text, and the one-time FamQuest lifecycle. Parents can offer quests for
child acceptance or publish quests for eligible children to pick directly.
Declined offers remain in history and can be followed by a new offer. Only the
responsible child can submit; parents review each attempt, with a required note
on rejection. Resubmissions preserve earlier reviews, and approval atomically
creates exactly one reward entry referencing the approved completion.

`TrustedActorContext` contains only a server-resolved member UUID and role.
Child actions resolve exactly one active linked KidProfile inside KidLand;
parent-selected child targets are separate from the parent actor. The future
Core adapter must construct this context from an active resolved member, never
from authoritative client role claims. This boundary is not authentication.
Standalone ledger profiles may remain unlinked, but cannot act on quests.
Member linkage is established through `create_kid_profile`; do not mutate
linkage directly without updating its lookup relationship.

Quest, assignment-response, and completion-review statuses are separate enums
because each has its own history. Delivery is determined by the lifecycle:
offered quests await acceptance/reassignment, while published quests are
available for pickup. `responsibility_source` is a read-only derived property:
an accepted current offer means parent assignment; responsibility without an
offer means child pickup. Neither fact needs a duplicate persisted enum field.

Store purchases, recurrence, dashboards, activity infrastructure, and Core
integration remain separate implementation steps. New occurrences require full
lifecycle fields; existing title-only scaffold objects are not automatically
migrated into actionable quests.

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
