from regicide.cards import (BASIC_SUITS, Card, build_castle, build_tavern, card_table, jester_card,
                            make_card, number_cards, royal_cards)
import random


def test_number_cards_are_40_unique():
    cards = number_cards()
    assert len(cards) == 40
    assert len({c.id for c in cards}) == 40
    assert {c.value for c in cards} == set(range(1, 11))


def test_values_and_defence():
    assert make_card("A", "H").value == 1
    assert make_card("10", "S").value == 10
    assert make_card("J", "C").value == 10
    assert make_card("Q", "C").value == 15
    assert make_card("K", "C").value == 20
    assert jester_card(1).value == 0
    assert jester_card(1).is_jester
    twofive = make_card("2", "H", id="25H", flags=("twofive",))
    assert twofive.defence_value == 5


def test_tavern_jesters():
    assert len(build_tavern(0)) == 40
    assert len(build_tavern(2)) == 42
    assert sum(1 for c in build_tavern(2) if c.is_jester) == 2


def test_castle_order_jacks_then_queens_then_kings():
    castle = build_castle(random.Random(3))
    assert [c.rank for c in castle] == ["J"] * 4 + ["Q"] * 4 + ["K"] * 4
    assert {c.suit for c in castle[:4]} == set(BASIC_SUITS)


def test_card_roundtrip():
    c = make_card("7", "H", name="x", flags=("corrupted",))
    assert Card.from_dict(c.to_dict()) == c


def test_card_table_rejects_duplicates():
    import pytest
    with pytest.raises(ValueError):
        card_table([make_card("7", "H"), make_card("7", "H")])
