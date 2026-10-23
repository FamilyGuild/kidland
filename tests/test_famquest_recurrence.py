"""Verify dated recurrence schedules, lifecycle isolation and atomic generation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import dbzero as db0
import pytest
from dbzero_modelkit import Calendar, LanguageCode, ML_String

from kidland.actors import TrustedActorContext
from kidland.commands import (
    accept_famquest_offer,
    approve_famquest_completion,
    create_famquest,
    create_famquest_recurrence,
    create_kid_profile,
    decline_famquest_offer,
    generate_famquest_occurrence,
    pick_famquest,
    reject_famquest_completion,
    set_famquest_recurrence_active,
    submit_famquest_completion,
)
from kidland.models import (
    FamQuest,
    FamQuestAssignment,
    FamQuestRecurrence,
    FamQuestStatus,
    KidProfile,
    LedgerEntry,
    RecurrenceCadence,
)

PARENT = TrustedActorContext("parent", "parent")
CHILD = TrustedActorContext("child", "child")


def rule(
    cadence: RecurrenceCadence = RecurrenceCadence.daily,
    start: date = date(2026, 1, 31),
    end: date | None = None,
    offered: bool = False,
) -> tuple[FamQuestRecurrence, KidProfile]:
    """Create a recurrence and its active recipient for domain tests."""
    profile = create_kid_profile("Alex", linked_member_uuid=CHILD.member_uuid)
    recurrence = create_famquest_recurrence(
        PARENT, ML_String("Read", LanguageCode.LEN), ML_String("Details", LanguageCode.LEN),
        10, cadence, start, end_date=end, primary_language=LanguageCode.LEN,
        target_profile=profile if offered else None,
        eligible_profiles=None if offered else [profile],
    )
    return recurrence, profile


@pytest.mark.parametrize(("cadence", "start", "due", "not_due"), [
    (RecurrenceCadence.daily, date(2024, 2, 28), date(2024, 2, 29), date(2024, 2, 27)),
    (RecurrenceCadence.weekly, date(2025, 12, 28), date(2026, 1, 4), date(2026, 1, 5)),
    (RecurrenceCadence.monthly, date(2024, 1, 31), date(2024, 2, 29), date(2024, 2, 28)),
    (RecurrenceCadence.monthly, date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 28)),
    (RecurrenceCadence.monthly, date(2026, 1, 31), date(2026, 3, 31), date(2026, 3, 30)),
    (RecurrenceCadence.monthly, date(2026, 1, 31), date(2026, 4, 30), date(2026, 4, 29)),
    (RecurrenceCadence.monthly, date(2026, 1, 30), date(2026, 3, 30), date(2026, 3, 31)),
    (RecurrenceCadence.monthly, date(2025, 12, 15), date(2026, 1, 15), date(2026, 1, 14)),
])
def test_due_dates(
    cadence: RecurrenceCadence, start: date, due: date, not_due: date,
) -> None:
    """Generate only anchored dates, respecting inclusive bounds and leap years."""
    recurrence, _ = rule(cadence, start, due)
    first = generate_famquest_occurrence(PARENT, recurrence, start)
    last = generate_famquest_occurrence(PARENT, recurrence, due)
    assert first.occurrence_date == start
    assert last.occurrence_date == due
    with pytest.raises(ValueError):
        generate_famquest_occurrence(PARENT, recurrence, not_due)
    with pytest.raises(ValueError):
        generate_famquest_occurrence(PARENT, recurrence, date(2027, 1, 1))
    assert len(list(db0.find(FamQuest))) == 2


@pytest.mark.parametrize("offered", [False, True])
def test_delivery_and_reward_idempotency(offered: bool) -> None:
    """Preserve each delivery path and never regenerate rewards or initial offers."""
    recurrence, profile = rule(offered=offered)
    issuer = TrustedActorContext("other-parent", "parent")
    occurrence = generate_famquest_occurrence(issuer, recurrence, recurrence.start_date)
    assert occurrence.recurrence == recurrence
    assert occurrence.created_by == issuer.member_uuid
    assert occurrence.due_date is None
    assert occurrence.responsible_profile is None
    if offered:
        assert str(occurrence.status) == "awaiting_acceptance"
        assert occurrence.current_offer.offered_by == issuer.member_uuid
        accept_famquest_offer(CHILD, occurrence.current_offer)
    else:
        assert str(occurrence.status) == "available"
        assert list(db0.find(FamQuest, db0.as_tag(profile), "kidland.quest.available")) == [occurrence]
        pick_famquest(CHILD, occurrence)
    completion = submit_famquest_completion(CHILD, occurrence)
    approve_famquest_completion(PARENT, completion)
    assert generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date) == occurrence
    assert len(list(db0.find(LedgerEntry))) == 1
    assert len(list(db0.find(FamQuestAssignment))) == int(offered)


@pytest.mark.parametrize("state", [
    "available", "picked", "submitted_for_approval", "returned", "rewarded", "cancelled",
])
def test_prior_state_does_not_block_generation(state: str) -> None:
    """A preceding occurrence never gates a new date or shares its review state."""
    recurrence, _ = rule()
    first = generate_famquest_occurrence(PARENT, recurrence, date(2026, 1, 31))
    if state not in ("available", "cancelled"):
        pick_famquest(CHILD, first)
    if state in ("submitted_for_approval", "returned", "rewarded"):
        completion = submit_famquest_completion(CHILD, first)
        if state == "returned":
            reject_famquest_completion(PARENT, completion, "Finish reading")
        elif state == "rewarded":
            approve_famquest_completion(PARENT, completion)
    if state == "cancelled":
        db0.tags(first).remove("kidland.quest.available")
        first.status = FamQuestStatus.cancelled
        db0.tags(first).add("kidland.quest.cancelled")
    second = generate_famquest_occurrence(PARENT, recurrence, date(2026, 2, 1))
    assert second != first
    assert str(second.status) == "available"
    assert second.current_completion is None
    assert str(first.status) == state


@pytest.mark.parametrize("declined", [False, True])
def test_pending_and_declined_offers_do_not_block_generation(declined: bool) -> None:
    """Unanswered or declined offers do not gate the next independent offer."""
    recurrence, _ = rule(offered=True)
    first = generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    if declined:
        decline_famquest_offer(CHILD, first.current_offer)
    second = generate_famquest_occurrence(PARENT, recurrence, date(2026, 2, 1))
    assert second.current_offer != first.current_offer
    assert str(second.status) == "awaiting_acceptance"
    assert str(first.status) == ("awaiting_assignment" if declined else "awaiting_acceptance")


@pytest.mark.parametrize("offered", [False, True])
def test_inactive_rules_profiles_and_authorization(offered: bool) -> None:
    """Deactivation prevents creation, not parent retrieval of an existing date."""
    recurrence, profile = rule(offered=offered)
    first = generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    with pytest.raises(ValueError):
        set_famquest_recurrence_active(CHILD, recurrence, False)
    with pytest.raises(ValueError):
        generate_famquest_occurrence(CHILD, recurrence, recurrence.start_date)
    set_famquest_recurrence_active(PARENT, recurrence, False)
    assert generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date) == first
    with pytest.raises(ValueError):
        generate_famquest_occurrence(PARENT, recurrence, date(2026, 2, 1))
    set_famquest_recurrence_active(PARENT, recurrence, True)
    profile.active = False
    assert generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date) == first
    with pytest.raises(ValueError):
        generate_famquest_occurrence(PARENT, recurrence, date(2026, 2, 1))
    assert len(list(db0.find(FamQuest))) == 1


@pytest.mark.parametrize("invalid", ["actor", "title", "reward", "dates", "both", "neither", "inactive"])
def test_invalid_rule_is_not_persisted(invalid: str) -> None:
    """Reject invalid boundary data without retaining a rule or occurrence."""
    profile = create_kid_profile("Alex", active=invalid != "inactive")
    with pytest.raises(ValueError):
        create_famquest_recurrence(
            CHILD if invalid == "actor" else PARENT,
            ML_String(" " if invalid == "title" else "Read", LanguageCode.LEN),
            ML_String("", LanguageCode.LEN), 0 if invalid == "reward" else 10,
            RecurrenceCadence.daily, date(2026, 1, 1),
            primary_language=LanguageCode.LEN,
            end_date=date(2025, 12, 31) if invalid == "dates" else None,
            target_profile=profile if invalid == "both" else None,
            eligible_profiles=[] if invalid == "neither" else [profile],
        )
    assert not list(db0.find(FamQuestRecurrence))
    assert not list(db0.find(FamQuest))


def test_independent_text_and_recipients() -> None:
    """Occurrence text and recipient collections are independent template snapshots."""
    recurrence, profile = rule()
    first = generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    second = generate_famquest_occurrence(PARENT, recurrence, date(2026, 2, 1))
    assert db0.uuid(first.title) != db0.uuid(recurrence.title)
    assert db0.uuid(first.description) != db0.uuid(second.description)
    first.eligible_profiles.clear()
    assert list(recurrence.eligible_profiles) == [profile]
    assert list(second.eligible_profiles) == [profile]


def test_translations_and_explicit_primary_language() -> None:
    """Copy all translations independently without inspecting modelkit private fields."""
    profile = create_kid_profile("Alex")
    title = ML_String("Read", LanguageCode.LEN, {LanguageCode.LPL: "Czytaj"})
    description = ML_String("Details", LanguageCode.LEN, {LanguageCode.LPL: "Opis"})
    with pytest.raises(ValueError):
        create_famquest_recurrence(
            PARENT, title, description, 10, RecurrenceCadence.daily, date(2026, 1, 1),
            primary_language=LanguageCode.LPL, eligible_profiles=[profile],
        )
    assert not list(db0.find(FamQuestRecurrence))
    recurrence = create_famquest_recurrence(
        PARENT, title, description, 10, RecurrenceCadence.daily, date(2026, 1, 1),
        primary_language=LanguageCode.LEN, eligible_profiles=[profile],
    )
    occurrence = generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    title.value = "Changed caller text"
    description.value = "Changed caller description"
    assert occurrence.title.value == recurrence.title.value == "Read"
    assert occurrence.description.value == recurrence.description.value == "Details"
    assert occurrence.title.get(LanguageCode.LPL) == "Czytaj"
    assert occurrence.description.get(LanguageCode.LPL) == "Opis"
    occurrence.title.value = "Changed occurrence"
    occurrence.description.value = "Changed occurrence details"
    assert recurrence.title.value == "Read"
    assert recurrence.description.value == "Details"


@pytest.mark.parametrize("offered", [False, True])
def test_generation_race(offered: bool) -> None:
    """Concurrent generation requests both return the sole persisted occurrence."""
    recurrence, _ = rule(offered=offered)
    barrier = Barrier(2)

    def generate() -> str:
        """Synchronize requests and return their generated occurrence UUID."""
        barrier.wait(timeout=5)
        return db0.uuid(generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(generate) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert results[0] == results[1]
    assert len(list(db0.find(FamQuest))) == 1
    assert len(list(db0.find(FamQuestAssignment))) == int(offered)
    assert not list(db0.find(LedgerEntry))


@pytest.mark.parametrize("offered", [False, True])
def test_calendar_failure_rolls_back(monkeypatch: pytest.MonkeyPatch, offered: bool) -> None:
    """A failure after calendar storage rolls back the slot, quest, offer and tags."""
    recurrence, _ = rule(offered=offered)
    original = Calendar.set

    def fail(calendar: Calendar, day: date, value: object) -> None:
        """Write before failing to exercise rollback of the complete mutation."""
        original(calendar, day, value)
        raise RuntimeError("injected storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(Calendar, "set", fail)
        with pytest.raises(RuntimeError):
            generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    assert recurrence.calendar.get(recurrence.start_date) is None
    assert not list(db0.find(FamQuest))
    assert not list(db0.find(FamQuestAssignment))
    assert not list(db0.find("kidland.quest.awaiting_acceptance"))
    assert not list(db0.find("kidland.assignment.awaiting_response"))
    assert generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)


def test_reopen_and_separate_rules(tmp_path: Path) -> None:
    """Persist calendar slots and keep rules distinct for the same date."""
    recurrence, profile = rule()
    other, _ = rule()
    first = generate_famquest_occurrence(PARENT, recurrence, recurrence.start_date)
    assert generate_famquest_occurrence(PARENT, other, other.start_date) != first
    standalone = create_famquest(
        PARENT, recurrence.title, recurrence.description, 10, recurrence.start_date,
        eligible_profiles=[profile],
    )
    assert standalone.recurrence is None
    recurrence_id, occurrence_id = db0.uuid(recurrence), db0.uuid(first)
    db0.close()
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    restored = db0.fetch(recurrence_id)
    assert db0.uuid(generate_famquest_occurrence(PARENT, restored, restored.start_date)) == occurrence_id
