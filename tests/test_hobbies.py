from typing import get_args

import pytest

from golden_hour.hobbies import CATEGORIES, HOBBIES, Rule, categories_for, classify
from golden_hour.models import Hobby


def test_every_hobby_mapped_to_known_categories():
    assert set(HOBBIES) == set(get_args(Hobby))
    for cats in HOBBIES.values():
        assert cats and all(c in CATEGORIES for c in cats)


def test_every_category_reachable_and_has_template():
    reachable = {c for cats in HOBBIES.values() for c in cats}
    assert reachable == set(CATEGORIES)
    assert all(c.template for c in CATEGORIES.values())


def test_no_hobbies_means_all_categories():
    assert categories_for([]) == list(CATEGORIES)


def test_categories_union_keeps_order_without_duplicates():
    assert categories_for(["history", "art"]) == ["history", "museum", "art"]
    assert categories_for(["nature", "photography"]) == ["park", "water", "view", "art", "history"]


@pytest.mark.parametrize(
    "rule,selector",
    [
        (Rule("tourism", ("artwork",)), '["tourism"="artwork"]'),
        (Rule("leisure", ("park", "garden")), '["leisure"~"^(park|garden)$"]'),
        (
            Rule("amenity", ("cafe",), also=(("outdoor_seating", "yes"),)),
            '["amenity"="cafe"]["outdoor_seating"="yes"]',
        ),
    ],
)
def test_rule_selector(rule, selector):
    assert rule.selector() == selector


@pytest.mark.parametrize(
    "tags,cats,expected",
    [
        ({"leisure": "garden"}, ["park"], ("park", "garden")),
        ({"waterway": "canal"}, ["water"], ("water", "canal")),
        ({"amenity": "cafe"}, ["cafe"], None),  # no outdoor seating
        ({"amenity": "cafe", "outdoor_seating": "yes"}, ["cafe"], ("cafe", "cafe")),
        ({"historic": "memorial"}, ["park", "history"], ("history", "memorial")),
        ({"historic": "memorial"}, ["park"], None),  # category not requested
        ({"tourism": "museum"}, ["museum"], ("museum", "museum")),
    ],
)
def test_classify(tags, cats, expected):
    assert classify(tags, cats) == expected


def test_covered_categories():
    assert {k for k, c in CATEGORIES.items() if c.covered} == {"museum", "library", "cafe"}
