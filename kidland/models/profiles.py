"""KidLand child profile models."""

from dataclasses import dataclass

import dbzero as db0


@db0.memo(id="/familyguild/kidland/KidProfile")
@dataclass
class KidProfile:
    """A child profile owned by KidLand.

    Attributes:
        display_name: Child-facing name or nickname.
        active: Whether the profile can participate in new child actions and
            receive ordinary ledger entries. Defaults to True; deactivation
            preserves history and still permits refunds for existing purchases.
        linked_member_uuid: Core member UUID used to resolve a trusted child
            actor to this profile; None means no member is linked.
    """

    display_name: str
    active: bool = True
    linked_member_uuid: str | None = None
