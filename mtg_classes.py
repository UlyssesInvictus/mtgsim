"""
Classes for Magic: the Gathering mana base simulation.
Includes mana production, mana costs, and land types.
"""

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Dict, Set


class ManaProduction:
    """Represents mana that a land can produce."""

    def __init__(self, production_str: str):
        """
        Parse mana production string.
        Examples:
        - 'W' -> single white mana
        - 'WG' -> white AND green
        - 'W/G' -> white OR green
        - '{R/U}U' -> (red OR blue) AND blue
        """
        self.options = []  # List of options, each is a set of colors

        # Split by brackets to handle complex patterns
        parts = re.findall(r'\{([^}]+)\}|([WUBRGC])', production_str)

        for bracket_part, single_part in parts:
            part = bracket_part if bracket_part else single_part
            if '/' in part:
                # This is an OR option
                colors = [c for c in part.split('/')]
                self.options.append(colors)
            else:
                # This is a required color
                for color in part:
                    self.options.append([color])

    def get_all_colors(self) -> Set[str]:
        """Get all possible colors this land can produce."""
        colors = set()
        for option in self.options:
            colors.update(option)
        return colors

    def get_colors_in_order(self) -> List[str]:
        """Get all possible colors this land can produce, preserving order."""
        colors = []
        seen = set()
        for option in self.options:
            for color in option:
                if color not in seen:
                    colors.append(color)
                    seen.add(color)
        return colors

    def get_required_colors(self) -> Set[str]:
        """Get colors that are always produced (no choice)."""
        required = set()
        for option in self.options:
            if len(option) == 1:
                required.add(option[0])
        return required

    def has_color(self, color: str) -> bool:
        """Check if this land can produce the given color."""
        return color in self.get_all_colors()


class ManaCost:
    """Represents the mana cost of a spell."""

    def __init__(self, cost_str: str):
        """
        Parse mana cost string.
        Examples:
        - '2G' -> 2 generic + 1 green
        - '{1}UB' -> 1 generic + 1 blue + 1 black
        - '{3/R}{3/W}' -> (3 generic OR 1 red) AND (3 generic OR 1 white)
        """
        self.cost_str = cost_str  # Store original string for display
        self.generic = 0
        self.colored = defaultdict(int)  # color -> count
        self.hybrid = []  # List of (generic_cost, color) tuples

        # Find all bracketed patterns and numbers/letters
        tokens = re.findall(r'\{([^}]+)\}|(\d+)|([WUBRGC])', cost_str)

        for bracket, number, color in tokens:
            if bracket:
                # Handle hybrid costs like {3/R}
                if '/' in bracket:
                    parts = bracket.split('/')
                    if parts[0].isdigit():
                        # Hybrid generic/colored
                        self.hybrid.append((int(parts[0]), parts[1]))
                    else:
                        # Hybrid colored/colored - treat as requiring one of them
                        self.hybrid.append((0, parts[0] + '/' + parts[1]))
                else:
                    # Just a number in brackets
                    self.generic += int(bracket)
            elif number:
                self.generic += int(number)
            elif color:
                self.colored[color] += 1

    def total_mana_needed(self) -> int:
        """Calculate the minimum total mana needed."""
        total = self.generic + sum(self.colored.values())
        for generic_part, _ in self.hybrid:
            total += 1 if generic_part == 0 else 1  # Each hybrid is at least 1 mana
        return total


class Land(ABC):
    """Abstract base class for lands."""

    def __init__(self, land_type: str, production: ManaProduction, count: int):
        self.land_type = land_type
        self.production = production
        self.count = count
        self.enters_tapped = False

    @abstractmethod
    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        """Check if this land enters tapped given current board state."""
        pass

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """
        Get available mana from this land.
        Returns empty set if the land can't be tapped (just played and entered tapped).
        """
        if just_played and self.enters_tapped:
            return set()
        return self.production.get_all_colors()

    def shares_colors_with_cost(self, cost: ManaCost) -> int:
        """Count how many colors this land shares with a spell cost."""
        land_colors = self.production.get_all_colors()
        spell_colors = set(cost.colored.keys())

        # Also check hybrid costs
        for _, color in cost.hybrid:
            if '/' in color:
                spell_colors.update(color.split('/'))
            else:
                spell_colors.add(color)

        return len(land_colors & spell_colors)


class ShockLand(Land):
    """Shock land: taps for all colors without restriction."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('shock', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False


class DualLand(Land):
    """Dual land: same as shock."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('dual', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False


class FastLand(Land):
    """Fast land: enters tapped if 3+ lands already in play."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('fastland', production, count)

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = len(lands_in_play) >= 3
        return self.enters_tapped


class SlowLand(Land):
    """Slow land: enters tapped if 2 or fewer lands in play."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('slowland', production, count)

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = len(lands_in_play) <= 2
        return self.enters_tapped


class SurveilLand(Land):
    """Surveil land: always enters tapped."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('surveil', production, count)
        self.enters_tapped = True

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = True
        return True


class VergeLand(Land):
    """
    Verge land: second color only available if there's a shock/dual/surveil
    that taps for one of the verge's colors.
    """

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('verge', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that verge produces exactly 2 colors."""
        if len(production.get_all_colors()) != 2:
            raise ValueError("Verge lands must produce exactly 2 colors")

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """Verge only taps for second color if condition is met."""
        if just_played and self.enters_tapped:
            return set()

        colors = self.production.get_colors_in_order()
        if len(colors) < 2:
            return set(colors)

        # First color is always available
        available = {colors[0]}

        # Check if we have a shock/dual/surveil with one of our colors
        for land in lands_in_play:
            if land is self:
                continue
            if isinstance(land, (ShockLand, DualLand, SurveilLand)):
                land_colors = land.production.get_all_colors()
                if any(c in land_colors for c in colors):
                    # Condition met, second color is available
                    available.add(colors[1])
                    break

        return available


class BasicLand(Land):
    """Basic land: produces one color."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('basic', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that basic land produces only one color."""
        if len(production.get_all_colors()) > 1:
            raise ValueError("Basic lands can only produce one color")


class WildsLand(Land):
    """Wilds: taps for WUBRG, always enters tapped."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('wilds', production, count)
        self.enters_tapped = True

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = True
        return True

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that wilds produces WUBRG."""
        colors = production.get_all_colors()
        if colors != {'W', 'U', 'B', 'R', 'G'}:
            raise ValueError("Wilds must produce WUBRG")


class TappedLand(Land):
    """Generic tapped land: always enters tapped."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('tapped', production, count)
        self.enters_tapped = True

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = True
        return True


class FetchLand(Land):
    """Fetch land: no restrictions, always enters untapped."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('fetch', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False


class UntappedLand(Land):
    """Generic untapped land: no restrictions, always enters untapped."""

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('untapped', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False


# Map of land type names to classes
LAND_TYPES = {
    'shock': ShockLand,
    'dual': DualLand,
    'fastland': FastLand,
    'slowland': SlowLand,
    'surveil': SurveilLand,
    'verge': VergeLand,
    'basic': BasicLand,
    'wilds': WildsLand,
    'tapped': TappedLand,
    'fetch': FetchLand,
    'untapped': UntappedLand,
}
