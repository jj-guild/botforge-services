"""royaume-persistant-v1 — the persistent realm's tests (Drasah 20/11).

« Créer un royaume n'engage pas » : the shell survives seasons (the
wipe never drops it), founding provisions a DORMANT habitat (only 🏰 Le
royaume shows), and the chez-soi window reads it (Ma seigneurie with
fondation + crown transfer, Présentation, Voir la saison, Palmarès,
Quitter).
"""

from __future__ import annotations

from typing import Any

import pytest


class FakeRealmStorage:
    """An in-memory storage honouring the ModStorage collection seam."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> "FakeRealmCollection":
        return FakeRealmCollection(self.docs)


class FakeRealmCollection:
    """replace_one/find/delete_one — enough for the realm CRUD."""

    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._docs = docs

    async def replace_one(self, flt: dict[str, Any], document: dict[str, Any], upsert: bool = False) -> None:
        self._docs[str(flt["_id"])] = dict(document)

    async def find(self, _flt: dict[str, Any]) -> "FakeRealmCursor":
        return FakeRealmCursor(list(self._docs.values()))

    async def delete_one(self, flt: dict[str, Any]) -> None:
        self._docs.pop(str(flt["_id"]), None)


class FakeRealmCursor:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


# ---------------------------------------------------------------------------
# The shell + service (realms.py)
# ---------------------------------------------------------------------------


def _service(storage: FakeRealmStorage | None = None):
    """Sync: the store + service build; the async ops ride asyncio.run.

    A SHARED storage emulates the persistent Mongo collection — the
    doc survives across service instances, exactly like the real
    collection survives across seasons.
    """
    from botforge.mods.kingdom.realms import RealmService

    class _Store:
        def __init__(self) -> None:
            self.storage = storage or FakeRealmStorage()

        async def upsert_realm(self, document: dict[str, Any]) -> None:
            await self.storage.collection("realms").replace_one(
                {"_id": document["_id"]}, document, upsert=True
            )

        async def find_realms(self) -> list[dict[str, Any]]:
            cursor = await self.storage.collection("realms").find({})
            return [dict(doc) async for doc in cursor]

        async def delete_realm(self, realm_id: str) -> None:
            await self.storage.collection("realms").delete_one({"_id": realm_id})

    return RealmService(_Store())



def test_founding_creates_a_persistent_shell() -> None:
    """Founding crowns the Roi, provisions NOTHING season-side, persists."""
    import asyncio

    shared = FakeRealmStorage()
    service = _service(shared)
    realm = asyncio.run(service.found_realm("42", "Drasah", "Château Noir"))
    assert realm.slug == "chateau-noir"
    assert realm.king_id == "42"
    assert realm.member_ids == []
    assert realm.id.startswith("realm:")
    # the second read (a NEW service over the same store) finds it —
    # the shell PERSISTS (the doc survives, unlike season kingdoms)
    again = asyncio.run(_service(shared).realm_of_member("42"))
    assert again is not None and again.name == "Château Noir"


def test_founding_refuses_duplicates_and_wanderers() -> None:
    """One realm per player, one slug per realm — the rules of the land."""
    from botforge.mods.kingdom.realms import RealmError

    import asyncio

    service = _service()
    asyncio.run(service.found_realm("1", "A", "Roc"))
    with pytest.raises(RealmError) as dup_slug:
        asyncio.run(service.found_realm("2", "B", "roc"))
    assert dup_slug.value.context["name"] == "roc"
    with pytest.raises(RealmError):
        asyncio.run(service.found_realm("1", "A", "Autre"))
    with pytest.raises(RealmError):
        asyncio.run(service.found_realm("3", "C", "x"))  # 1 char < NAME_MIN


def test_leave_transfer_presentation_join_request_rules() -> None:
    """The Roi writes, the members leave, the crown moves, entry is asked."""
    from botforge.mods.kingdom.realms import RealmError

    import asyncio

    service = _service()
    realm = asyncio.run(service.found_realm("1", "Roi", "Roc"))
    realm = asyncio.run(service.save_habitat(realm.id, {"category": "9", "hub": "10"}))

    # members ride the shell (found-then-join is tranche 2's door; the
    # store-level sibling covers the rule engines below)
    stored = asyncio.run(service.realm_of_member("1"))
    assert stored.discord["hub"] == "10"

    with pytest.raises(RealmError):
        asyncio.run(service.leave_realm(realm.id, "1"))  # the King cannot leave
    with pytest.raises(RealmError):
        asyncio.run(service.set_presentation(realm.id, "2", "nope"))  # Roi ONLY
    with pytest.raises(RealmError):
        asyncio.run(service.transfer_crown(realm.id, "2", "3"))  # not the King

    # ask the season entry (the Roi manifests, an admin accepts — T2)
    with_request = asyncio.run(service.request_season_entry(realm.id, "1", "season-1"))
    assert with_request.join_request["season_id"] == "season-1"
    cleared = asyncio.run(service.clear_join_request(realm.id))
    assert cleared.join_request is None
    stored = asyncio.run(service.realm_of_slug("roc"))
    assert stored.king_name == "Roi"


# ---------------------------------------------------------------------------
# The declared surfaces (#381) — every realm window is in views.yaml
# ---------------------------------------------------------------------------


def test_every_realm_surface_is_declared() -> None:
    from botforge.discord.ui.view_footer import require_declared_view_id

    from botforge.mods.kingdom.cogs.realms import (
        HOME_SURFACE,
        HUB_SURFACE,
        PALMARES_SURFACE,
        PRESENTATION_SURFACE,
        SEASON_SURFACE,
        SEIGNEURIE_SURFACE,
    )

    for view_id in (
        HUB_SURFACE,
        HOME_SURFACE,
        SEIGNEURIE_SURFACE,
        PRESENTATION_SURFACE,
        SEASON_SURFACE,
        PALMARES_SURFACE,
    ):
        require_declared_view_id(view_id)  # raises when NOT declared


def test_the_realm_strings_carry_fr_en_parity() -> None:
    """Every realm string exists in both locales (the parity rule)."""
    from botforge.mods.kingdom.cogs.realm_strings import _REALM_STRINGS

    fr, en = _REALM_STRINGS["fr"], _REALM_STRINGS["en"]
    assert set(fr) == set(en), (set(fr) ^ set(en))
    for key, value in fr.items():
        for ph in ("{0}", "{king}", "{count}", "{when}", "{season}", "{note}", "{excerpt}"):
            assert (ph in value) == (ph in en[key]), key


# ---------------------------------------------------------------------------
# The habitat — dormant provisioning, adoption by slug, single pass
# ---------------------------------------------------------------------------


class FakeUser:
    def __init__(self, uid: int) -> None:
        self.id = uid


def test_dormant_hides_every_salon_but_the_hub() -> None:
    """DORMANT_HIDDEN_KEYS — Discussions/Territoire/Alliances masked."""
    from botforge.mods.kingdom.cogs.realms import DORMANT_HIDDEN_KEYS, REALM_SALONS

    keys = {key for key, _name in REALM_SALONS}
    assert DORMANT_HIDDEN_KEYS == ("discussions", "territory", "alliances")
    assert "hub" in keys and "hub" not in DORMANT_HIDDEN_KEYS


def test_ensure_realm_structure_provisions_and_adopts() -> None:
    """Provisioning creates the category + 4 salons, adopts by slug, ids returned."""

    class FakeCategory:
        def __init__(self, name: str) -> None:
            self.name = name
            self.id = 777
            self.channels: list[Any] = []

    class FakeChannel:
        def __init__(self, name: str, category: FakeCategory) -> None:
            self.name = name
            self.id = 700 + len(category.channels)
            self.category = category
            category.channels.append(self)

        async def edit(self, name: str = "") -> None:
            self.name = name

        async def set_permissions(self, member: Any, **kw: Any) -> None:
            pass

    class FakeGuild:
        def __init__(self) -> None:
            self.categories: list[Any] = []

        async def create_category(self, name: str, overwrites: Any = None) -> FakeCategory:
            category = FakeCategory(name)
            self.categories.append(category)
            return category

        async def create_text_channel(self, name: str, category: Any = None) -> FakeChannel:
            return FakeChannel(name, category)

    import asyncio

    from botforge.mods.kingdom.cogs.realms import ensure_realm_structure
    from botforge.mods.kingdom.realms import RealmShellModel

    realm = RealmShellModel(
        _id="realm:roc-1", name="Roc", slug="roc", king_id="1", king_name="Roi"
    )
    guild = FakeGuild()
    ids = asyncio.run(
        ensure_realm_structure(guild, realm, dormant=True)
    )
    assert set(ids) == {"category", "discussions", "hub", "territory", "alliances"}
    names = [c.name for c in guild.categories[0].channels]
    assert names == ["🔒 Discussions", "🏰 Le royaume", "🌍 Territoire", "🏆 Alliances"]
    # idempotent: a SECOND pass adopts, never duplicates
    ids2 = asyncio.run(
        ensure_realm_structure(guild, realm, dormant=True)
    )
    assert len(guild.categories) == 1
    assert len(guild.categories[0].channels) == 4
    assert ids2["hub"] == ids["hub"]


def test_the_hub_template_carries_both_states() -> None:  # deliberately mis-named? no — the hub layout
    """The hub template renders dormant (grey) and vivant (gold) alike."""
    from botforge.mods.kingdom.cogs.realms import hub_layout
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings
    from botforge.mods.kingdom.realms import RealmShellModel

    realm = RealmShellModel(
        _id="realm:roc-1", name="Roc", slug="roc", king_id="1", king_name="Roi"
    )
    strings = realm_strings("fr")
    dormant = hub_layout(realm, strings, dormant=True)
    awake = hub_layout(realm, strings, dormant=False)
    assert "hors-jeu" in str(strings["realm_hors_jeu_zone"])
    # both states deploy (the views build, no raise)
    assert dormant is not None and awake is not None


def test_the_hub_carries_its_illustration_in_both_locales() -> None:
    """The hub's artwork is DATA present in fr AND en (the designer's 21/11
    ask — an empty realm_artwork renders a text-only hub silently)."""
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    for locale in ("fr", "en"):
        artwork = str(realm_strings(locale).get("realm_artwork", "") or "")
        assert artwork.startswith("https://"), f"the {locale} hub must carry its artwork"
        assert "Royaume" in artwork or "royaume" in artwork


def test_the_wipe_never_lists_the_shell_collection() -> None:
    """REALMS_COLLECTION stays OUTSIDE the season wipe (persistence rule)."""
    from botforge.mods.kingdom.storage import REALMS_COLLECTION, SEASON_WIPE_COLLECTIONS

    assert REALMS_COLLECTION not in SEASON_WIPE_COLLECTIONS


def test_the_dormant_door_carries_the_season_actions() -> None:
    """hub-dormant-actions (Drasah 21/11) : l'Entrée n'est pas un
    rouage — la porte s'ouvre même sans engagement, et à sa droite le
    royaume endormi porte sa saison : « Voir la saison » puis l'acte
    « ⚔️ Inscrire son royaume ». Une demande en attente cache l'acte
    (l'état vit dans la fenêtre chez-soi) ; le hub vivant garde la
    porte seule."""
    from botforge.mods.kingdom.cogs.realms import hub_layout
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings
    from botforge.mods.kingdom.realms import RealmShellModel

    def _custom_ids(layout: Any) -> list[str]:
        import json

        payload = json.dumps(layout.to_components())
        return [
            cid
            for cid in (
                "kingdom:realm:home:roc",
                "kingdom:realm:nav:season:roc",
                "kingdom:realm:join:roc",
            )
            if cid in payload
        ]

    strings = realm_strings("fr")
    realm = RealmShellModel(
        _id="realm:roc-1", name="Roc", slug="roc", king_id="1", king_name="Roi"
    )
    # the dormant door opens WITHOUT engagement, beside the season actions
    dormant = _custom_ids(hub_layout(realm, strings, dormant=True))
    assert dormant == [
        "kingdom:realm:home:roc",
        "kingdom:realm:nav:season:roc",
        "kingdom:realm:join:roc",
    ], "the door opens even unengaged, with the season actions to its RIGHT, in order"
    # a pending request hides the act (the state lives in chez-soi)
    pending = RealmShellModel(
        _id="realm:roc-1",
        name="Roc",
        slug="roc",
        king_id="1",
        king_name="Roi",
        join_request={"season_id": "s1", "requested_at": 1},
    )
    pending_ids = _custom_ids(hub_layout(pending, strings, dormant=True))
    assert "kingdom:realm:nav:season:roc" in pending_ids
    assert "kingdom:realm:join:roc" not in pending_ids, "a manifested request hides the act"
    # the awake hub carries the door alone (its halls are the season's)
    awake = _custom_ids(hub_layout(realm, strings, dormant=False))
    assert "kingdom:realm:home:roc" in awake
    assert "kingdom:realm:nav:season:roc" not in awake
    assert "kingdom:realm:join:roc" not in awake
    # the act's label lives in BOTH locales (the fr/en parity rule)
    assert "Inscrire son royaume" in realm_strings("fr")["realm_hub_join_button"]
    assert "Enroll" in realm_strings("en")["realm_hub_join_button"]
