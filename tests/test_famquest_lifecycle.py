"""Verify FamQuest lifecycle authorization, history, rewards, and atomic transitions."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import dbzero as db0
import pytest
from dbzero_modelkit import LanguageCode, ML_String

from kidland.actors import TrustedActorContext
from kidland.commands import (
    accept_famquest_offer,
    approve_famquest_completion,
    create_famquest,
    create_kid_profile,
    decline_famquest_offer,
    offer_famquest,
    pick_famquest,
    reject_famquest_completion,
    submit_famquest_completion,
)
from kidland.models import (
    FamQuest,
    FamQuestAssignment,
    FamQuestCompletion,
    KidProfile,
    LedgerEntry,
)
from kidland.queries import calculate_famcoins_balance, resolve_kid_profile

Actors = tuple[TrustedActorContext, TrustedActorContext, KidProfile]


@pytest.fixture
def actors() -> Actors:
    """Return trusted parent and child actors with the child's linked active profile."""
    parent = TrustedActorContext("parent-member", "parent")
    child = TrustedActorContext("child-member", "child")
    profile = create_kid_profile("Alex", linked_member_uuid=child.member_uuid)
    return parent, child, profile


def quest(parent: TrustedActorContext, profile: KidProfile, offered: bool = False) -> FamQuest:
    """Create and return a quest offered to or directly pickable by the profile."""
    return create_famquest(
        parent, ML_String("Read", LanguageCode.LEN),
        ML_String("", LanguageCode.LEN), 10, date(2026, 1, 1),
        target_profile=profile if offered else None,
        eligible_profiles=[] if offered else [profile],
    )


def test_published_reward_is_exactly_once(actors: Actors) -> None:
    """Verify a published quest awards one linked reward despite repeated approval."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    assert occurrence.responsibility_source is None
    pick_famquest(child, occurrence)
    assert occurrence.responsibility_source == "child_pickup"
    completion = submit_famquest_completion(child, occurrence)
    entry = approve_famquest_completion(parent, completion)
    assert occurrence.responsible_profile == profile
    assert entry.source_reference == completion
    assert calculate_famcoins_balance(profile) == 10
    with pytest.raises(ValueError):
        approve_famquest_completion(parent, completion)
    assert len(list(db0.find(LedgerEntry))) == 1


def test_decline_reoffer_and_stale_offer(actors: Actors) -> None:
    """Verify declined offers remain in history and only the current offer is usable."""
    parent, child, profile = actors
    occurrence = quest(parent, profile, offered=True)
    old = occurrence.current_offer
    decline_famquest_offer(child, old)
    assert occurrence.responsible_profile is None
    assert occurrence.responsibility_source is None
    assert old.child_comment is None
    current = offer_famquest(parent, occurrence, profile)
    with pytest.raises(ValueError):
        accept_famquest_offer(child, old)
    with pytest.raises(ValueError):
        offer_famquest(parent, occurrence, profile)
    accept_famquest_offer(child, current)
    assert str(occurrence.responsibility_source) == "parent_assignment"
    assert len(list(db0.find(FamQuestAssignment))) == 2


def test_rejection_preserves_attempt_on_resubmission(actors: Actors) -> None:
    """Verify resubmission preserves rejected attempts and rewards only the new one."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    pick_famquest(child, occurrence)
    first = submit_famquest_completion(child, occurrence)
    with pytest.raises(ValueError):
        reject_famquest_completion(parent, first, " ")
    reject_famquest_completion(parent, first, "Read the last page")
    assert occurrence.responsibility_source == "child_pickup"
    assert calculate_famcoins_balance(profile) == 0
    second = submit_famquest_completion(child, occurrence)
    with pytest.raises(ValueError):
        approve_famquest_completion(parent, first)
    approve_famquest_completion(parent, second)
    assert occurrence.responsibility_source == "child_pickup"
    assert first.review_note == "Read the last page"
    assert str(first.review_status) == "rejected"
    assert len(list(db0.find(FamQuestCompletion))) == 2


def test_wrong_actor_and_mapping_reject_without_mutation(actors: Actors) -> None:
    """Verify invalid actors and ambiguous profile mappings cannot pick a quest."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    with pytest.raises(ValueError):
        pick_famquest(parent, occurrence)
    with pytest.raises(ValueError):
        pick_famquest(TrustedActorContext("unknown", "child"), occurrence)
    create_kid_profile("Duplicate", linked_member_uuid=child.member_uuid)
    with pytest.raises(ValueError):
        pick_famquest(child, occurrence)
    assert str(occurrence.status) == "available"
    assert occurrence.responsible_profile is None


def test_approval_failure_rolls_back(actors: Actors, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify reward-recording failure rolls back review, workflow tags, and ledger."""
    from kidland import commands

    parent, child, profile = actors
    occurrence = quest(parent, profile)
    pick_famquest(child, occurrence)
    completion = submit_famquest_completion(child, occurrence)
    original = commands.record_ledger_entry

    def fail(*args: object, **kwargs: object) -> None:
        """Record the forwarded ledger entry, then raise to exercise atomic rollback."""
        original(*args, **kwargs)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(commands, "record_ledger_entry", fail)
    with pytest.raises(RuntimeError):
        approve_famquest_completion(parent, completion)
    assert str(occurrence.status) == "submitted_for_approval"
    assert str(completion.review_status) == "pending"
    assert calculate_famcoins_balance(profile) == 0
    assert not list(db0.find(LedgerEntry))
    assert completion.reviewed_by is None
    assert completion.reviewed_at is None
    assert list(db0.find(FamQuestCompletion, "kidland.completion.pending_review")) == [completion]
    assert list(db0.find(FamQuest, "kidland.quest.submitted_for_approval")) == [occurrence]
    monkeypatch.setattr(commands, "record_ledger_entry", original)
    approve_famquest_completion(parent, completion)
    assert calculate_famcoins_balance(profile) == 10


def test_reoffer_to_another_child_preserves_history(actors: Actors) -> None:
    """Verify reoffering changes the recipient without erasing the declined offer."""
    parent, child, profile = actors
    sibling = TrustedActorContext("sibling-member", "child")
    other = create_kid_profile("Riley", linked_member_uuid=sibling.member_uuid)
    occurrence = quest(parent, profile, offered=True)
    first = occurrence.current_offer
    assert occurrence.responsible_profile is None
    with pytest.raises(ValueError):
        accept_famquest_offer(parent, first)
    with pytest.raises(ValueError):
        accept_famquest_offer(sibling, first)
    decline_famquest_offer(child, first, "Tomorrow please")
    second = offer_famquest(parent, occurrence, other)
    with pytest.raises(ValueError):
        accept_famquest_offer(child, second)
    accept_famquest_offer(sibling, second)
    for response in (accept_famquest_offer, decline_famquest_offer):
        with pytest.raises(ValueError):
            response(sibling, second)
    with pytest.raises(ValueError):
        offer_famquest(parent, occurrence, profile)
    assert first.child_comment == "Tomorrow please"
    assert first.responded_at is not None
    assert occurrence.responsible_profile == other


def test_command_authorization_and_inactive_profiles(actors: Actors) -> None:
    """Verify lifecycle commands reject wrong roles, ineligible or inactive children."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    with pytest.raises(ValueError):
        quest(child, profile)
    with pytest.raises(ValueError):
        offer_famquest(child, occurrence, profile)
    with pytest.raises(ValueError):
        offer_famquest(parent, occurrence, profile)
    sibling = TrustedActorContext("sibling-member", "child")
    create_kid_profile("Riley", linked_member_uuid=sibling.member_uuid)
    with pytest.raises(ValueError):
        pick_famquest(sibling, occurrence)
    profile.active = False
    with pytest.raises(ValueError):
        pick_famquest(child, occurrence)
    profile.active = True
    pick_famquest(child, occurrence)
    for actor in (parent, sibling):
        with pytest.raises(ValueError):
            submit_famquest_completion(actor, occurrence)
    completion = submit_famquest_completion(child, occurrence)
    with pytest.raises(ValueError):
        submit_famquest_completion(child, occurrence)
    with pytest.raises(ValueError):
        approve_famquest_completion(child, completion)
    with pytest.raises(ValueError):
        reject_famquest_completion(child, completion, "No")
    assert not list(db0.find(LedgerEntry))
    assert str(completion.review_status) == "pending"


@pytest.mark.parametrize("reward", [0, -1])
def test_invalid_creation_leaves_no_occurrence(actors: Actors, reward: int) -> None:
    """Verify a nonpositive reward prevents quest creation without persisted objects."""
    parent, _, profile = actors
    with pytest.raises(ValueError):
        create_famquest(parent, ML_String("Read", LanguageCode.LEN),
                        ML_String("", LanguageCode.LEN), reward, date(2026, 1, 1),
                        eligible_profiles=[profile])
    assert not list(db0.find(FamQuest))


def _race(actions: list[Callable[[], object]]) -> list[bool]:
    """Race two actions and return success flags, treating ValueError as rejection."""
    barrier = Barrier(2)

    def worker(action: Callable[[], object]) -> bool:
        """Synchronize an action's start and report success or ValueError rejection."""
        barrier.wait(timeout=5)
        try:
            action()
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, action) for action in actions]
        return [future.result(timeout=10) for future in futures]


def test_competing_pickups_and_approvals(actors: Actors) -> None:
    """Verify competing pickups select one child and approvals create one reward."""
    parent, child, profile = actors
    sibling = TrustedActorContext("sibling-member", "child")
    other = create_kid_profile("Riley", linked_member_uuid=sibling.member_uuid)
    occurrence = create_famquest(
        parent, ML_String("Read", LanguageCode.LEN), ML_String("", LanguageCode.LEN),
        10, date(2026, 1, 1), eligible_profiles=[profile, other],
    )
    assert sorted(_race([lambda: pick_famquest(child, occurrence),
                         lambda: pick_famquest(sibling, occurrence)])) == [False, True]
    winner = child if occurrence.responsible_profile == profile else sibling
    loser = other if winner == child else profile
    assert not list(db0.find(FamQuest, db0.as_tag(loser), "kidland.quest.picked"))
    completion = submit_famquest_completion(winner, occurrence)
    assert sorted(_race([lambda: approve_famquest_completion(parent, completion),
                         lambda: approve_famquest_completion(parent, completion)])) == [False, True]
    assert len(list(db0.find(LedgerEntry))) == 1
    assert calculate_famcoins_balance(occurrence.responsible_profile) == 10


def test_competing_approve_and_reject(actors: Actors) -> None:
    """Verify concurrent approval and rejection produce one consistent review result."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    pick_famquest(child, occurrence)
    completion = submit_famquest_completion(child, occurrence)
    assert sorted(_race([lambda: approve_famquest_completion(parent, completion),
                         lambda: reject_famquest_completion(parent, completion, "Fix it")])) == [False, True]
    rewarded = str(completion.review_status) == "approved"
    assert str(occurrence.status) == ("rewarded" if rewarded else "returned")
    assert calculate_famcoins_balance(profile) == (10 if rewarded else 0)


def test_competing_accept_and_decline(actors: Actors) -> None:
    """Verify racing responses record one decision and matching responsibility state."""
    parent, child, profile = actors
    occurrence = quest(parent, profile, offered=True)
    offer = occurrence.current_offer
    results = _race([
        lambda: accept_famquest_offer(child, offer),
        lambda: decline_famquest_offer(child, offer, "Tomorrow please"),
    ])
    assert sorted(results) == [False, True]
    accepted = results[0]
    assert str(offer.response_status) == ("accepted" if accepted else "declined")
    assert offer.responded_at is not None
    assert offer.child_comment == (None if accepted else "Tomorrow please")
    assert occurrence.current_offer == offer
    assert occurrence.responsible_profile == (profile if accepted else None)
    assert occurrence.responsibility_source == ("parent_assignment" if accepted else None)
    status = "picked" if accepted else "awaiting_assignment"
    assert str(occurrence.status) == status
    assert list(db0.find(FamQuest, f"kidland.quest.{status}")) == [occurrence]
    assert not list(db0.find(FamQuest, "kidland.quest.awaiting_acceptance"))
    assert not list(db0.find(FamQuestAssignment, "kidland.assignment.awaiting_response"))
    assert list(db0.find(FamQuestAssignment, db0.as_tag(occurrence))) == [offer]
    assert list(db0.find(FamQuest, db0.as_tag(profile))) == ([occurrence] if accepted else [])
    assert not list(db0.find(LedgerEntry))


def test_competing_reoffers(actors: Actors) -> None:
    """Verify racing reoffers preserve history and create only one pending offer."""
    parent, child, profile = actors
    sibling = TrustedActorContext("sibling-member", "child")
    other = create_kid_profile("Riley", linked_member_uuid=sibling.member_uuid)
    occurrence = quest(parent, profile, offered=True)
    declined = occurrence.current_offer
    decline_famquest_offer(child, declined, "Tomorrow please")
    results = _race([
        lambda: offer_famquest(parent, occurrence, profile),
        lambda: offer_famquest(parent, occurrence, other),
    ])
    assert sorted(results) == [False, True]
    current = occurrence.current_offer
    assert current != declined
    assert current.target_profile == (profile if results[0] else other)
    assert str(current.response_status) == "awaiting_response"
    assert current.responded_at is None
    assert str(occurrence.status) == "awaiting_acceptance"
    assert occurrence.responsible_profile is None
    assert occurrence.responsibility_source is None
    assert str(declined.response_status) == "declined"
    assert declined.child_comment == "Tomorrow please"
    assert declined.responded_at is not None
    assert set(db0.find(FamQuestAssignment, db0.as_tag(occurrence))) == {declined, current}
    assert list(db0.find(FamQuestAssignment, "kidland.assignment.awaiting_response")) == [current]
    assert list(db0.find(FamQuest, "kidland.quest.awaiting_acceptance")) == [occurrence]
    assert not list(db0.find(FamQuest, "kidland.quest.awaiting_assignment"))
    with pytest.raises(ValueError):
        accept_famquest_offer(child, declined)
    winner = child if results[0] else sibling
    accept_famquest_offer(winner, current)
    assert occurrence.responsible_profile == current.target_profile
    assert not list(db0.find(LedgerEntry))


def test_rejection_changes_only_reviewed_occurrence(actors: Actors) -> None:
    """Verify reviewing one dated occurrence leaves another pending attempt unchanged."""
    parent, child, profile = actors
    historical = quest(parent, profile)
    later = create_famquest(
        parent, ML_String("Read", LanguageCode.LEN), ML_String("", LanguageCode.LEN),
        10, date(2026, 1, 2), eligible_profiles=[profile],
    )
    pick_famquest(child, historical)
    first = submit_famquest_completion(child, historical)
    pick_famquest(child, later)
    second = submit_famquest_completion(child, later)
    reject_famquest_completion(parent, first, "Finish reading")
    assert str(historical.status) == "returned"
    assert historical.responsible_profile == profile
    assert historical.current_completion == first
    assert str(first.review_status) == "rejected"
    assert first.review_note == "Finish reading"
    assert first.reviewed_by == parent.member_uuid
    assert first.reviewed_at is not None
    assert str(later.status) == "submitted_for_approval"
    assert later.responsible_profile == profile
    assert later.current_completion == second
    assert str(second.review_status) == "pending"
    assert second.review_note is None
    assert second.reviewed_by is None
    assert second.reviewed_at is None
    assert list(db0.find(FamQuest, "kidland.quest.returned")) == [historical]
    assert list(db0.find(FamQuest, "kidland.quest.submitted_for_approval")) == [later]
    assert list(db0.find(FamQuestCompletion, "kidland.completion.pending_review")) == [second]
    assert not list(db0.find(LedgerEntry))
    assert calculate_famcoins_balance(profile) == 0


def test_lifecycle_persists_across_reopen(actors: Actors, tmp_path: Path) -> None:
    """Verify offer history, completion reviews, and linked rewards survive reopening."""
    parent, child, profile = actors
    occurrence = quest(parent, profile, offered=True)
    decline_famquest_offer(child, occurrence.current_offer)
    accept_famquest_offer(child, offer_famquest(parent, occurrence, profile))
    first = submit_famquest_completion(child, occurrence)
    reject_famquest_completion(parent, first, "Finish reading")
    second = submit_famquest_completion(child, occurrence)
    entry = approve_famquest_completion(parent, second)
    identifiers = [db0.uuid(obj) for obj in (occurrence, first, second, entry)]
    db0.close()
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    restored = db0.fetch(identifiers[0], FamQuest)
    old = db0.fetch(identifiers[1], FamQuestCompletion)
    current = db0.fetch(identifiers[2], FamQuestCompletion)
    debit = db0.fetch(identifiers[3], LedgerEntry)
    assert restored.current_completion == current
    assert old.review_note == "Finish reading"
    assert str(restored.current_offer.response_status) == "accepted"
    assert debit.source_reference == current
    assert restored.responsibility_source == "parent_assignment"
    assert resolve_kid_profile(child.member_uuid) == restored.responsible_profile
    assert len(list(db0.find(FamQuestAssignment, db0.as_tag(restored)))) == 2
    assert calculate_famcoins_balance(restored.responsible_profile) == 10


def test_offer_and_review_tags_follow_current_state(actors: Actors) -> None:
    """Verify decline and rejection remove pending tags and expose the new state."""
    parent, child, profile = actors
    occurrence = quest(parent, profile, offered=True)
    offer = occurrence.current_offer
    decline_famquest_offer(child, offer)
    assert not list(db0.find(FamQuestAssignment, "kidland.assignment.awaiting_response"))
    assert not list(db0.find(FamQuest, "kidland.quest.awaiting_acceptance"))
    assert list(db0.find(FamQuest, "kidland.quest.awaiting_assignment")) == [occurrence]
    accept_famquest_offer(child, offer_famquest(parent, occurrence, profile))
    completion = submit_famquest_completion(child, occurrence)
    reject_famquest_completion(parent, completion, "Try again")
    assert not list(db0.find(FamQuestCompletion, "kidland.completion.pending_review"))
    assert list(db0.find(FamQuest, "kidland.quest.returned")) == [occurrence]


def test_pickup_source_is_derived_after_reopen(actors: Actors, tmp_path: Path) -> None:
    """Verify a rewarded self-picked quest retains its derived source after reopening."""
    parent, child, profile = actors
    occurrence = quest(parent, profile)
    pick_famquest(child, occurrence)
    approve_famquest_completion(parent, submit_famquest_completion(child, occurrence))
    identifier = db0.uuid(occurrence)
    db0.close()
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    restored = db0.fetch(identifier, FamQuest)
    assert restored.current_offer is None
    assert restored.responsibility_source == "child_pickup"
