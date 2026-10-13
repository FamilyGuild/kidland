"""Module-local trusted identity boundary; this is not authentication."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TrustedActorContext:
    """Server-resolved member identity, never an authoritative client claim."""

    member_uuid: str
    role: Literal["parent", "child"]

    def __post_init__(self) -> None:
        """Raise ValueError for a blank member UUID or unsupported actor role."""
        if not self.member_uuid.strip() or self.role not in ("parent", "child"):
            raise ValueError("A resolved member UUID and parent/child role are required")


def require_parent(actor: TrustedActorContext) -> None:
    """Reject non-parent actors at module command boundaries."""
    if actor.role != "parent":
        raise ValueError("actor must be a parent")
