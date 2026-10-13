"""Verify trusted actor identity validation and active child-profile resolution."""

from dataclasses import asdict

import pytest

from kidland.actors import TrustedActorContext
from kidland.commands import create_kid_profile
from kidland.queries import resolve_kid_profile


def test_actor_context_is_serializable_identity_only() -> None:
    """Verify actor serialization contains only member identity and role."""
    actor = TrustedActorContext("parent-member", "parent")
    assert asdict(actor) == {"member_uuid": "parent-member", "role": "parent"}


def test_unresolved_actor_is_rejected() -> None:
    """Verify a blank member identity cannot create a trusted actor context."""
    with pytest.raises(ValueError):
        TrustedActorContext(" ", "child")


def test_only_one_active_matching_profile_is_resolved() -> None:
    """Verify resolution ignores inactive profiles and rejects missing active ones."""
    profile = create_kid_profile("Alex", linked_member_uuid="child-member")
    create_kid_profile("Old Alex", active=False, linked_member_uuid="child-member")
    assert resolve_kid_profile("child-member") == profile
    profile.active = False
    with pytest.raises(ValueError):
        resolve_kid_profile("child-member")


def test_stale_relationship_tag_does_not_prove_ownership() -> None:
    """Verify a stale member tag cannot override the profile's current member link."""
    profile = create_kid_profile("Alex", linked_member_uuid="child-member")
    profile.linked_member_uuid = "different-member"
    with pytest.raises(ValueError):
        resolve_kid_profile("child-member")
