"""Verify multilingual domain text resolution, persistence, and purchase snapshots."""

from datetime import UTC, date, datetime
from pathlib import Path

import dbzero as db0
import pytest
from dbzero_modelkit import LanguageCode, ML_String

from kidland.models import FamQuest, FamQuestStatus, FamStoreItem, FamStorePurchase
from kidland.commands import create_kid_profile
from kidland.multilingual_helpers import (
    resolve_multilingual_text,
    snapshot_multilingual_text,
)


def test_resolves_translation_or_primary_text() -> None:
    """Verify requested translations resolve with primary-text fallback."""
    english_primary = ML_String(
        "Clean your room",
        LanguageCode.LEN,
        {LanguageCode.LPL: "Posprzątaj swój pokój"},
    )
    polish_primary = ML_String(
        "Czas na film",
        LanguageCode.LPL,
        {LanguageCode.LEN: "Movie time"},
    )
    primary_only = ML_String("Read a book", LanguageCode.LEN)

    assert resolve_multilingual_text(english_primary, LanguageCode.LPL) == (
        "Posprzątaj swój pokój"
    )
    assert resolve_multilingual_text(polish_primary, LanguageCode.LEN) == "Movie time"
    assert resolve_multilingual_text(primary_only, LanguageCode.LPL) == "Read a book"


def test_allows_empty_optional_multilingual_text() -> None:
    """Verify optional quest and store text can resolve to an empty string."""
    empty_description = ML_String("", LanguageCode.LEN)
    quest = FamQuest(
        title=ML_String("Feed the cat", LanguageCode.LEN),
        description=empty_description,
        reward=5, occurrence_date=date(2026, 1, 1), created_by="parent-member",
        status=FamQuestStatus.available,
    )
    item = FamStoreItem(
        title=ML_String("Choose dessert", LanguageCode.LEN),
        description=empty_description,
        fulfillment_note=ML_String("", LanguageCode.LEN),
        cost=10, item_type="reward", title_primary_language=LanguageCode.LEN,
    )

    assert resolve_multilingual_text(quest.description, LanguageCode.LPL) == ""
    assert resolve_multilingual_text(item.fulfillment_note, LanguageCode.LPL) == ""


def test_multilingual_domain_text_persists_across_reopen(tmp_path: Path) -> None:
    """Verify quest, store, and purchase texts retain translations after reopening."""
    quest = FamQuest(
        title=ML_String(
            "Walk the dog",
            LanguageCode.LEN,
            {LanguageCode.LPL: "Wyprowadź psa"},
        ),
        description=ML_String("Before dinner", LanguageCode.LEN),
        reward=5, occurrence_date=date(2026, 1, 1), created_by="parent-member",
        status=FamQuestStatus.available,
    )
    item = FamStoreItem(
        title=ML_String(
            "Dodatkowy czas na grę",
            LanguageCode.LPL,
            {LanguageCode.LEN: "Extra game time"},
        ),
        description=ML_String("30 minut", LanguageCode.LPL),
        cost=10, item_type="reward", title_primary_language=LanguageCode.LPL,
        fulfillment_note=ML_String(
            "Rodzic uruchamia minutnik",
            LanguageCode.LPL,
            {LanguageCode.LEN: "A parent starts the timer"},
        ),
    )
    purchase = FamStorePurchase(
        title_snapshot=snapshot_multilingual_text(item.title, LanguageCode.LPL),
        kid_profile=create_kid_profile("Alex"), item=item, cost_snapshot=10,
        purchased_at=datetime.now(UTC),
    )
    quest_uuid = db0.uuid(quest)
    item_uuid = db0.uuid(item)
    purchase_uuid = db0.uuid(purchase)

    db0.commit()
    db0.close()
    db0.init(str(tmp_path / "db0"), prefix="kidland")

    restored_quest = db0.fetch(quest_uuid, FamQuest)
    restored_item = db0.fetch(item_uuid, FamStoreItem)
    restored_purchase = db0.fetch(purchase_uuid, FamStorePurchase)

    assert resolve_multilingual_text(restored_quest.title, LanguageCode.LPL) == (
        "Wyprowadź psa"
    )
    assert resolve_multilingual_text(restored_quest.description, LanguageCode.LPL) == (
        "Before dinner"
    )
    assert resolve_multilingual_text(restored_item.title, LanguageCode.LEN) == (
        "Extra game time"
    )
    assert resolve_multilingual_text(restored_item.description, LanguageCode.LEN) == (
        "30 minut"
    )
    assert resolve_multilingual_text(
        restored_item.fulfillment_note, LanguageCode.LEN
    ) == "A parent starts the timer"
    assert resolve_multilingual_text(
        restored_purchase.title_snapshot, LanguageCode.LEN
    ) == "Extra game time"


def test_purchase_title_snapshot_is_independent() -> None:
    """Verify purchase snapshots retain original text independently of item edits."""
    item_title = ML_String(
        "Movie night",
        LanguageCode.LEN,
        {LanguageCode.LPL: "Wieczór filmowy"},
    )
    snapshot = snapshot_multilingual_text(item_title, LanguageCode.LEN)
    item = FamStoreItem(item_title, ML_String("", LanguageCode.LEN),
                        ML_String("", LanguageCode.LEN), 10, "reward", LanguageCode.LEN)
    purchase = FamStorePurchase(snapshot, create_kid_profile("Alex"), item, 10,
                                 datetime.now(UTC))

    item_title.value = "Updated movie night"

    assert db0.uuid(purchase.title_snapshot) != db0.uuid(item_title)
    assert purchase.title_snapshot.value == "Movie night"
    assert resolve_multilingual_text(
        purchase.title_snapshot, LanguageCode.LPL
    ) == "Wieczór filmowy"


def test_snapshot_requires_the_explicit_primary_language() -> None:
    """Verify snapshot creation rejects a language other than the source primary."""
    title = ML_String(
        "Movie night",
        LanguageCode.LEN,
        {LanguageCode.LPL: "Wieczór filmowy"},
    )

    with pytest.raises(ValueError, match="primary_language"):
        snapshot_multilingual_text(title, LanguageCode.LPL)
