"""Verify FamStore authorization, atomic accounting and child-specific capacity."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import dbzero as db0
import pytest
from dbzero_modelkit import LanguageCode, ML_String

from kidland import commands as c
from kidland.actors import TrustedActorContext
from kidland.models import ActivityEvent, FamStorePurchase, LedgerEntry, PurchaseStatus
from kidland.queries import calculate_famcoins_balance, get_available_famstore_items

PARENT = TrustedActorContext("parent", "parent")


def setup_store(limit: int | None = 3) -> tuple:
    """Return a funded child, trusted actor and pinned multilingual offer."""
    profile = c.create_kid_profile("Alex", linked_member_uuid="alex")
    actor = TrustedActorContext("alex", "child")
    c.adjust_famcoins_balance(profile, 100, "Initial allowance")
    title = ML_String("Movie", LanguageCode.LEN, {LanguageCode.LPL: "Film"})
    item = c.create_famstore_item(PARENT, title, ML_String("", LanguageCode.LEN),
        ML_String("", LanguageCode.LEN), 10, "reward", LanguageCode.LEN, limit)
    c.pin_famstore_item(PARENT, item, profile)
    return profile, actor, item


@pytest.mark.parametrize("limit", [1, 3, None])
def test_capacity_is_per_child(limit: int | None) -> None:
    """Purchases hide exhausted offers only for their buyer, not siblings."""
    profile, actor, item = setup_store(limit)
    sibling = c.create_kid_profile("Sam", linked_member_uuid="sam")
    c.pin_famstore_item(PARENT, item, sibling)
    for _ in range(limit or 4):
        c.purchase_famstore_item(actor, item)
    assert bool(get_available_famstore_items(actor)) == (limit is None)
    assert get_available_famstore_items(TrustedActorContext("sam", "child")) == [item]
    if limit is not None:
        with pytest.raises(ValueError):
            c.purchase_famstore_item(actor, item)
    assert calculate_famcoins_balance(profile) == 100 - (limit or 4) * 10


def test_cancel_preserves_snapshot_and_refunds_once() -> None:
    """Cancellation preserves original debit and price despite subsequent edits."""
    profile, actor, item = setup_store(1)
    purchase = c.purchase_famstore_item(actor, item)
    item.title.value = "Updated"
    item.cost = 50
    profile.active = False
    c.cancel_famstore_purchase(PARENT, purchase)
    assert calculate_famcoins_balance(profile) == 100
    assert purchase.title_snapshot.value == "Movie"
    assert purchase.title_snapshot.get(LanguageCode.LPL) == "Film"
    assert sorted(entry.amount for entry in db0.find(LedgerEntry, db0.as_tag(purchase))) == [-10, 10]
    with pytest.raises(ValueError):
        c.cancel_famstore_purchase(PARENT, purchase)
    with pytest.raises(ValueError):
        c.mark_purchase_fulfilled(PARENT, purchase)
    profile.active = True
    assert get_available_famstore_items(actor) == [item]


@pytest.mark.parametrize("failure", ["record_ledger_entry", "ActivityEvent"])
def test_purchase_rolls_back(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed debit or event leaves no purchase or accounting effects."""
    profile, actor, item = setup_store(1)

    def fail(*args: object, **kwargs: object) -> None:
        """Inject a genuine storage failure inside the atomic command."""
        raise RuntimeError("injected")

    monkeypatch.setattr(c, failure, fail)
    with pytest.raises(RuntimeError):
        c.purchase_famstore_item(actor, item)
    assert list(db0.find(FamStorePurchase)) == []
    assert list(db0.find(ActivityEvent)) == []
    assert calculate_famcoins_balance(profile) == 100
    assert get_available_famstore_items(actor) == [item]


def test_refund_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failed refund preserves purchased status, consumed capacity and debit."""
    profile, actor, item = setup_store(1)
    purchase = c.purchase_famstore_item(actor, item)

    def fail(*args: object, **kwargs: object) -> None:
        """Inject a refund storage failure."""
        raise RuntimeError("injected")

    monkeypatch.setattr(c, "_write_ledger_entry", fail)
    with pytest.raises(RuntimeError):
        c.cancel_famstore_purchase(PARENT, purchase)
    assert purchase.status == PurchaseStatus.purchased
    assert purchase.cancelled_at is None
    assert list(db0.find(FamStorePurchase, "kidland.purchase.needs_fulfillment")) == [purchase]
    assert calculate_famcoins_balance(profile) == 90
    assert get_available_famstore_items(actor) == []


def test_authorization_visibility_and_fulfillment() -> None:
    """Actor authorization and terminal fulfillment protect store state."""
    profile, actor, item = setup_store(1)
    with pytest.raises(ValueError):
        c.pin_famstore_item(actor, item, profile)
    with pytest.raises(ValueError):
        c.purchase_famstore_item(PARENT, item)
    with pytest.raises(ValueError):
        c.purchase_famstore_item(TrustedActorContext("unknown", "child"), item)
    c.set_famstore_item_enabled(PARENT, item, False)
    assert get_available_famstore_items(actor) == []
    with pytest.raises(ValueError):
        c.purchase_famstore_item(actor, item)
    c.set_famstore_item_enabled(PARENT, item, True)
    purchase = c.purchase_famstore_item(actor, item)
    with pytest.raises(ValueError):
        c.mark_purchase_fulfilled(actor, purchase)
    c.mark_purchase_fulfilled(PARENT, purchase)
    with pytest.raises(ValueError):
        c.cancel_famstore_purchase(PARENT, purchase)
    assert calculate_famcoins_balance(profile) == 90
    assert get_available_famstore_items(actor) == []
    assert list(db0.find(FamStorePurchase, "kidland.purchase.needs_fulfillment")) == []


def test_insufficient_funds_and_repinning() -> None:
    """Repinning retains usage; insufficient funds do not hide an offer."""
    profile, actor, item = setup_store(1)
    item.cost = 101
    assert get_available_famstore_items(actor) == [item]
    with pytest.raises(ValueError):
        c.purchase_famstore_item(actor, item)
    item.cost = 100
    c.purchase_famstore_item(actor, item)
    assert calculate_famcoins_balance(profile) == 0
    c.unpin_famstore_item(PARENT, item, profile)
    c.pin_famstore_item(PARENT, item, profile)
    assert get_available_famstore_items(actor) == []
    c.edit_famstore_item(PARENT, item, item.title, item.description,
        item.fulfillment_note, 100, "reward", LanguageCode.LEN, 2)
    assert get_available_famstore_items(actor) == [item]


@pytest.mark.parametrize("cost,limit", [(0, 1), (-1, 1), (True, 1), (1, 0), (1, -1)])
def test_invalid_price_or_limit(cost: int, limit: int) -> None:
    """Invalid numeric domain inputs cannot create offers."""
    with pytest.raises(ValueError):
        c.create_famstore_item(PARENT, ML_String("Movie", LanguageCode.LEN),
            ML_String("", LanguageCode.LEN), ML_String("", LanguageCode.LEN),
            cost, "reward", LanguageCode.LEN, limit)


def test_purchase_graph_survives_reopen(tmp_path: Path) -> None:
    """Source relationships, snapshots, events and capacity survive reopening."""
    _profile, actor, item = setup_store(1)
    purchase = c.purchase_famstore_item(actor, item)
    handle = db0.uuid(purchase)
    db0.close()
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    restored = db0.fetch(handle, FamStorePurchase)
    assert restored.cost_snapshot == 10
    assert restored.title_snapshot.get(LanguageCode.LPL) == "Film"
    assert calculate_famcoins_balance(restored.kid_profile) == 90
    assert get_available_famstore_items(actor) == []
    event, = db0.find(ActivityEvent, db0.as_tag(restored))
    assert event.source_reference == restored
    assert event.target_role == "parent" and not event.read
    assert restored.parent_informed_at == event.created_at


def test_child_cannot_purchase_sibling_only_offer() -> None:
    """Reject a sibling's offer without creating purchase or accounting effects."""
    profile, actor, item = setup_store()
    sibling = c.create_kid_profile("Sam", linked_member_uuid="sam")
    c.unpin_famstore_item(PARENT, item, profile)
    c.pin_famstore_item(PARENT, item, sibling)

    assert get_available_famstore_items(actor) == []
    assert get_available_famstore_items(TrustedActorContext("sam", "child")) == [item]
    with pytest.raises(ValueError):
        c.purchase_famstore_item(actor, item)

    assert list(db0.find(FamStorePurchase)) == []
    assert list(db0.find(ActivityEvent)) == []
    assert len(list(db0.find(LedgerEntry))) == 1
    assert calculate_famcoins_balance(profile) == 100
    assert calculate_famcoins_balance(sibling) == 0


def test_competing_purchases_cannot_overspend_balance() -> None:
    """Unlimited offers still allow only one purchase when funds cover one."""
    profile, actor, item = setup_store(None)
    c.adjust_famcoins_balance(profile, -90, "Limit available allowance")

    def buy() -> bool:
        """Report whether a competing purchase acquired the available funds."""
        try:
            c.purchase_famstore_item(actor, item)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: buy(), range(2)))

    assert sum(results) == 1
    assert calculate_famcoins_balance(profile) == 0
    purchase, = db0.find(FamStorePurchase)
    debit, = db0.find(LedgerEntry, db0.as_tag(purchase))
    event, = db0.find(ActivityEvent)
    assert purchase.kid_profile == profile
    assert debit.amount == -10
    assert debit.source_reference == purchase
    assert event.source_reference == purchase
    assert get_available_famstore_items(actor) == [item]


def test_competing_last_unit_purchases() -> None:
    """Threads sharing the single writer cannot both buy the final unit."""
    profile, actor, item = setup_store(1)

    def buy() -> bool:
        """Return whether a competing purchase succeeded."""
        try:
            c.purchase_famstore_item(actor, item)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: buy(), range(2)))
    assert sum(results) == 1
    assert calculate_famcoins_balance(profile) == 90


@pytest.mark.parametrize("remove_pin", [True, False])
def test_refund_does_not_restore_disabled_or_unpinned_offer(remove_pin: bool) -> None:
    """Restored capacity never overrides the parent's separate availability choice."""
    profile, actor, item = setup_store(1)
    purchase = c.purchase_famstore_item(actor, item)
    if remove_pin:
        c.unpin_famstore_item(PARENT, item, profile)
    else:
        c.set_famstore_item_enabled(PARENT, item, False)
    c.cancel_famstore_purchase(PARENT, purchase)
    assert get_available_famstore_items(actor) == []
    assert calculate_famcoins_balance(profile) == 100


def test_competing_settlements() -> None:
    """Competing cancellation and fulfillment have exactly one terminal winner."""
    profile, actor, item = setup_store(1)
    purchase = c.purchase_famstore_item(actor, item)

    def settle(cancel: bool) -> bool:
        """Attempt one parent settlement and report a rejected stale transition."""
        try:
            if cancel:
                c.cancel_famstore_purchase(PARENT, purchase)
            else:
                c.mark_purchase_fulfilled(PARENT, purchase)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(settle, [True, False]))
    assert sum(results) == 1
    assert calculate_famcoins_balance(profile) == (
        100 if purchase.status == PurchaseStatus.cancelled else 90
    )


def test_reduced_limit_and_inactive_actor() -> None:
    """Lowering total capacity retains usage; inactive child actors cannot buy."""
    profile, actor, item = setup_store(3)
    c.purchase_famstore_item(actor, item)
    c.purchase_famstore_item(actor, item)
    c.edit_famstore_item(PARENT, item, item.title, item.description,
        item.fulfillment_note, 10, "reward", LanguageCode.LEN, 1)
    assert get_available_famstore_items(actor) == []
    item.purchase_limit_per_child = None
    profile.active = False
    with pytest.raises(ValueError):
        c.purchase_famstore_item(actor, item)


@pytest.mark.parametrize("blank_title,blank_type", [(True, False), (False, True)])
def test_blank_required_text(blank_title: bool, blank_type: bool) -> None:
    """Required primary title and descriptive type reject whitespace."""
    with pytest.raises(ValueError):
        c.create_famstore_item(PARENT,
            ML_String(" " if blank_title else "Movie", LanguageCode.LEN),
            ML_String("", LanguageCode.LEN), ML_String("", LanguageCode.LEN),
            10, " " if blank_type else "reward", LanguageCode.LEN)
