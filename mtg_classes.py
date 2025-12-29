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
        self.locked_color = None  # For choice-based lands

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

        # If this land has been locked to a specific color, return only that
        if self.locked_color:
            return {self.locked_color}

        return self.production.get_all_colors()

    def choose_color(self, lands_in_play: List['Land'], hand: List, target_costs: List,
                     available_colors: Set[str] = None) -> str:
        """
        Choose a color for this land to be locked to.
        Uses heuristic: prefer colors not in play/hand, prefer colors in target spells,
        prefer least redundant, random tiebreak.
        """
        # Get possible colors
        possible_colors = available_colors if available_colors else self.production.get_all_colors()
        if not possible_colors:
            return None

        # Get colors already produced by lands in play
        colors_in_play = set()
        for land in lands_in_play:
            if land is not self:
                colors_in_play.update(land.get_available_mana(lands_in_play, False))

        # Get colors in hand
        colors_in_hand = set()
        for card in hand:
            if card and isinstance(card, Land) and card is not self:
                colors_in_hand.update(card.production.get_all_colors())

        # Get colors needed for target spells
        spell_colors = set()
        for cost in target_costs:
            spell_colors.update(cost.colored.keys())
            for _, color_part in cost.hybrid:
                if '/' in color_part:
                    spell_colors.update(color_part.split('/'))
                else:
                    spell_colors.add(color_part)

        # Score each possible color
        scores = {}
        for color in possible_colors:
            score = 0

            # Prefer colors needed for spells
            if color in spell_colors:
                score += 10

            # Prefer colors not in play
            if color not in colors_in_play:
                score += 5

            # Prefer colors not in hand
            if color not in colors_in_hand:
                score += 3

            # Count how many lands in play produce this color (lower is better)
            redundancy = sum(1 for land in lands_in_play
                           if land is not self and color in land.get_available_mana(lands_in_play, False))
            score -= redundancy

            scores[color] = score

        # Choose the color with highest score (random tiebreak)
        import random
        max_score = max(scores.values())
        best_colors = [c for c, s in scores.items() if s == max_score]
        return random.choice(best_colors)

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
    """
    Wilds: fetches basics from deck, always enters tapped.
    Must be locked to a single basic type when played.
    """

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

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """Wilds lands lock to a single basic type when played."""
        if just_played and self.enters_tapped:
            return set()

        if self.locked_color:
            return {self.locked_color}

        # Should be locked by the time we query
        return self.production.get_all_colors()


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


class MultiversalLand(Land):
    """
    Multiversal land: can tap for any color but must be locked to a single choice.
    Should be played late unless needed to cast a spell.
    """

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('multiversal', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = False
        return False

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that multiversal produces WUBRG."""
        colors = production.get_all_colors()
        if colors != {'W', 'U', 'B', 'R', 'G'}:
            raise ValueError("Multiversal lands must produce WUBRG")

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """For multiversal lands, lock to a color when first getting available mana."""
        if just_played and self.enters_tapped:
            return set()

        # If already locked, return that color
        if self.locked_color:
            return {self.locked_color}

        # For multiversal lands, return all colors (caller should lock it)
        return self.production.get_all_colors()


class FabledLand(Land):
    """
    Fabled land: fetches basics, enters untapped if 3+ lands in play.
    Must be locked to a single basic type when played.
    """

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('fabled', production, count)

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        self.enters_tapped = len(lands_in_play) < 3
        return self.enters_tapped

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """Fabled lands lock to a single color (basic type) when played."""
        if just_played and self.enters_tapped:
            return set()

        if self.locked_color:
            return {self.locked_color}

        # Should be locked by the time we query
        return self.production.get_all_colors()


class StartingTownLand(Land):
    """
    Starting town land: taps for WUBRGC, enters tapped if turn 4+.
    Must be locked to a single choice when played.
    """

    def __init__(self, production: ManaProduction, count: int):
        super().__init__('startingtown', production, count)
        self.enters_tapped = False

    def check_enters_tapped(self, lands_in_play: List['Land']) -> bool:
        # This will be set by GameState based on turn count
        return self.enters_tapped

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that starting town produces WUBRGC."""
        colors = production.get_all_colors()
        if colors != {'W', 'U', 'B', 'R', 'G', 'C'}:
            raise ValueError("Starting town lands must produce WUBRGC")

    def get_available_mana(self, lands_in_play: List['Land'], just_played: bool) -> Set[str]:
        """Starting town lands lock to a single color when played."""
        if just_played and self.enters_tapped:
            return set()

        if self.locked_color:
            return {self.locked_color}

        return self.production.get_all_colors()


class Cycler:
    """
    Cycler: A card that can be converted to a basic land from the deck
    once you have enough lands in play.
    """

    def __init__(self, production: ManaProduction, cycling_cost: int, count: int):
        """
        Initialize a cycler.

        Args:
            production: The mana production (determines which basic it can fetch)
            cycling_cost: Number of lands needed in play to cycle
            count: Number of these cyclers in the deck
        """
        self.production = production
        self.cycling_cost = cycling_cost
        self.count = count

    @staticmethod
    def validate_production(production: ManaProduction) -> None:
        """Validate that cycler produces only one color (basic type)."""
        if len(production.get_all_colors()) != 1:
            raise ValueError("Cyclers must produce exactly one color (basic type)")


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
    'multiversal': MultiversalLand,
    'fabled': FabledLand,
    'startingtown': StartingTownLand,
}
