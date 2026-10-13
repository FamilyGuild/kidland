"""KidLand child profile models."""

from dataclasses import dataclass

import dbzero as db0


@db0.memo(id="/familyguild/kidland/KidProfile")
@dataclass
class KidProfile:
    """A child profile owned by KidLand."""

    display_name: str
    active: bool = True
    linked_member_uuid: str | None = None
