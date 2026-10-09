"""Hobbies and the OpenStreetMap place categories they map to (spec 002, design §3).

Each category is defined once as tag rules. The same rules build the Overpass query and classify
the elements that come back, so the two can't drift apart.
"""

from dataclasses import dataclass

from golden_hour.models import Hobby


@dataclass(frozen=True)
class Rule:
    key: str
    values: tuple[str, ...]
    also: tuple[tuple[str, str], ...] = ()  # extra exact-match tags, e.g. outdoor_seating=yes

    def selector(self) -> str:
        if len(self.values) == 1:
            sel = f'["{self.key}"="{self.values[0]}"]'
        else:
            sel = f'["{self.key}"~"^({"|".join(self.values)})$"]'
        return sel + "".join(f'["{k}"="{v}"]' for k, v in self.also)

    def kind(self, tags: dict) -> str | None:
        value = tags.get(self.key)
        if value in self.values and all(tags.get(k) == v for k, v in self.also):
            return value
        return None


@dataclass(frozen=True)
class Category:
    key: str
    rules: tuple[Rule, ...]
    template: str  # fallback line when the model can't write one (R9.3)
    covered: bool = False

    def kind(self, tags: dict) -> str | None:
        return next((k for r in self.rules if (k := r.kind(tags))), None)


CATEGORIES: dict[str, Category] = {
    c.key: c
    for c in [
        Category(
            "park",
            (Rule("leisure", ("park", "garden", "nature_reserve", "common")),),
            "Walk one slow loop and find the quietest spot.",
        ),
        Category(
            "water",
            (Rule("natural", ("water",)), Rule("waterway", ("river", "canal"))),
            "Stand by the water for a few minutes and watch how the light moves on it.",
        ),
        Category(
            "view",
            (Rule("tourism", ("viewpoint",)), Rule("natural", ("peak",))),
            "Take in the view and pick out the furthest thing you can see.",
        ),
        Category(
            "art",
            (Rule("tourism", ("artwork",)),),
            "Look at it from three different angles before you decide what you think.",
        ),
        Category(
            "history",
            (
                Rule(
                    "historic",
                    ("monument", "memorial", "castle", "fort", "ruins", "archaeological_site"),
                ),
            ),
            "Read whatever is written on it and imagine the street when it was new.",
        ),
        Category(
            "museum",
            (Rule("tourism", ("museum", "gallery")),),
            "A good covered stop: walk there and back, and look at the building outside.",
            covered=True,
        ),
        Category(
            "library",
            (Rule("amenity", ("library",)),),
            "Walk over, and if there's a bench outside, read a page or two.",
            covered=True,
        ),
        Category(
            "cafe",
            (Rule("amenity", ("cafe",), also=(("outdoor_seating", "yes"),)),),
            "Sit outside for a few minutes and watch the street go by.",
            covered=True,
        ),
        Category(
            "sport",
            (Rule("leisure", ("pitch", "track", "sports_centre", "fitness_station")),),
            "Do one lap or a few stretches, at whatever pace feels good.",
        ),
    ]
}

# First category = strongest match for that hobby.
HOBBIES: dict[Hobby, tuple[str, ...]] = {
    "photography": ("view", "water", "art", "history", "park"),
    "nature": ("park", "water", "view"),
    "history": ("history", "museum"),
    "art": ("art", "museum"),
    "running": ("park", "water", "sport"),
    "reading": ("park", "library", "cafe"),
    "coffee": ("cafe", "park"),
    "sports": ("sport", "park"),
}


def categories_for(hobbies: list[Hobby]) -> list[str]:
    """Categories to search, in order of first appearance; all of them if no hobbies (R7.2)."""
    if not hobbies:
        return list(CATEGORIES)
    seen: dict[str, None] = {}
    for h in hobbies:
        for c in HOBBIES[h]:
            seen.setdefault(c, None)
    return list(seen)


def classify(tags: dict, categories: list[str]) -> tuple[str, str] | None:
    """(category, kind) for the first requested category whose rules match the tags."""
    for key in categories:
        kind = CATEGORIES[key].kind(tags)
        if kind:
            return key, kind
    return None
