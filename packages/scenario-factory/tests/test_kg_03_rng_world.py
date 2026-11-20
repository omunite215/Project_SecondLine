"""KG-03 §5 · ADR-015: seeded streams, opaque ids, canaries and the synthetic world (plan steps 1–2)."""

import re

from sl_factory.rng import FORBIDDEN, IdMinter, Streams, derive_seed, make_canary
from sl_factory.world import CURRENCIES, build_world, isin_check_digit

OPAQUE = re.compile(r"^[a-z]{2,6}_[0-9A-Za-z]{8,32}$")
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def test_KG_03_streams_are_deterministic_and_independent() -> None:
    a, b = Streams(42), Streams(42)
    assert [a.stream("x").random() for _ in range(3)] == [b.stream("x").random() for _ in range(3)]
    assert Streams(42).stream("x").random() != Streams(42).stream("y").random()
    assert Streams(42).stream("x").random() != Streams(43).stream("x").random()


def test_KG_03_derive_seed_is_stable_and_split_specific() -> None:
    assert derive_seed("dev", 0) == derive_seed("dev", 0)
    assert derive_seed("dev", 0) != derive_seed("dev", 1)
    assert derive_seed("dev", 0) != derive_seed("eval", 0)


def test_KG_03_opaque_ids_never_reveal_a_split() -> None:
    ids = IdMinter(Streams(7).stream("ids"))
    minted = [ids.mint("trd") for _ in range(5000)]
    assert len(set(minted)) == len(minted)
    assert all(OPAQUE.match(i) and not FORBIDDEN.search(i) for i in minted)


def test_KG_03_id_minter_redraws_forbidden_draws() -> None:
    draws = iter(["xxTeStxxxxxx", "abcdefgh1234"])
    ids = IdMinter(Streams(1).stream("ids"), draw=lambda: next(draws))
    assert ids.mint("trd") == "trd_abcdefgh1234"


def test_KG_03_canary_shape() -> None:
    assert re.fullmatch(r"SLCANARY-[0-9a-f]{32}", make_canary(Streams(3).stream("canary")))


def test_KG_03_isin_check_digit_matches_iso6166() -> None:
    assert isin_check_digit("US037833100") == "5"  # public example ISIN US0378331005
    assert isin_check_digit("GB000263494") == "6"  # GB0002634946


def test_KG_03_world_is_synthetic_and_in_policy() -> None:
    w = build_world(Streams(11), IdMinter(Streams(11).stream("ids")))
    assert w.instruments and w.counterparties
    for ins in w.instruments:
        assert ISIN.match(ins.isin) and ins.isin.startswith("QZ")
        assert ins.isin[-1] == isin_check_digit(ins.isin[:-1])
        assert ins.currency in CURRENCIES
    assert build_world(Streams(11), IdMinter(Streams(11).stream("ids"))) == w
