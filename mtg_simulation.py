"""
Monte Carlo simulation for Magic: the Gathering mana bases.
"""

import random
from collections import defaultdict
from typing import List, Dict

from mtg_classes import (
    Land, ManaCost, SlowLand, MultiversalLand, WildsLand,
    FabledLand, StartingTownLand, BasicLand
)


class GameState:
    """Represents the state of a game for simulation."""

    def __init__(self, deck: List, starting_hand_size: int = 7,
                 on_play: bool = True):
        """
        Initialize game state.
        Deck should contain Land objects and None values (non-lands).
        """
        self.deck = deck[:]
        random.shuffle(self.deck)

        self.hand = []
        self.lands_in_play = []
        self.played_land_this_turn = False
        self.turn = 0
        self.on_play = on_play

        # Track available basics in deck by color
        self.available_basics = defaultdict(int)
        for card in self.deck:
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1:
                    color = list(colors)[0]
                    self.available_basics[color] += 1

        # Draw starting hand
        for _ in range(starting_hand_size):
            if self.deck:
                card = self.deck.pop()
                # Update basic tracking
                if card and isinstance(card, BasicLand):
                    colors = card.production.get_all_colors()
                    if len(colors) == 1:
                        color = list(colors)[0]
                        self.available_basics[color] -= 1
                self.hand.append(card)

    def draw_card(self):
        """Draw a card from the deck."""
        if self.deck:
            card = self.deck.pop()
            # Update basic tracking
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1:
                    color = list(colors)[0]
                    self.available_basics[color] -= 1
            self.hand.append(card)

    def start_turn(self):
        """Start a new turn."""
        self.turn += 1
        self.played_land_this_turn = False

        # Draw a card (skip first draw if on the play)
        if not (self.on_play and self.turn == 1):
            self.draw_card()

    def can_cast_spell(self, cost: ManaCost) -> bool:
        """Check if we can cast a spell with the given cost."""
        # Get available mana sources (each land produces 1 mana of its available colors)
        mana_sources = []

        for i, land in enumerate(self.lands_in_play):
            just_played = (i == len(self.lands_in_play) - 1 and self.played_land_this_turn)
            colors = land.get_available_mana(self.lands_in_play[:i], just_played)
            if colors:  # Land can produce mana
                mana_sources.append(colors)

        # Try to pay the cost
        remaining_generic = cost.generic
        needed_colored = dict(cost.colored)
        remaining_hybrid = list(cost.hybrid)
        used_sources = []

        # First, pay specific colored costs
        for color, count in list(needed_colored.items()):
            sources_found = 0
            for idx, source_colors in enumerate(mana_sources):
                if idx in used_sources:
                    continue
                if color in source_colors:
                    used_sources.append(idx)
                    sources_found += 1
                    if sources_found >= count:
                        break

            if sources_found < count:
                return False
            del needed_colored[color]

        # Handle hybrid costs
        for generic_cost, color_part in remaining_hybrid:
            paid = False
            if '/' in color_part:
                # Hybrid colored/colored
                colors = color_part.split('/')
                for idx, source_colors in enumerate(mana_sources):
                    if idx in used_sources:
                        continue
                    if any(c in source_colors for c in colors):
                        used_sources.append(idx)
                        paid = True
                        break
            else:
                # Hybrid generic/colored
                for idx, source_colors in enumerate(mana_sources):
                    if idx in used_sources:
                        continue
                    if color_part in source_colors:
                        used_sources.append(idx)
                        paid = True
                        break

            if not paid:
                # Pay with generic
                remaining_generic += generic_cost - 1 if generic_cost > 0 else 0

        # Finally, pay generic with any remaining mana
        available_for_generic = len(mana_sources) - len(used_sources)
        return available_for_generic >= remaining_generic

    def play_land_optimally(self, target_costs: List[ManaCost]) -> bool:
        """
        Play a land from hand using the optimal strategy.
        Returns True if a land was played.
        """
        if self.played_land_this_turn or not self.hand:
            return False

        # Separate lands into categories
        # Deprioritize multiversal lands (play them last unless needed)
        priority_tapped_lands = []  # Tapped lands to prioritize (non-slowlands, non-multiversal)
        slowlands = []
        untapped_lands = []  # Non-multiversal untapped
        multiversal_lands = []  # Deprioritized

        for card in self.hand:
            # Skip non-land cards
            if card is None or not isinstance(card, Land):
                continue

            land = card

            # Handle StartingTownLand's turn-based tapped state
            if isinstance(land, StartingTownLand):
                land.enters_tapped = self.turn >= 4

            will_enter_tapped = land.check_enters_tapped(self.lands_in_play)

            # Separate multiversal lands for deprioritization
            if isinstance(land, MultiversalLand):
                multiversal_lands.append(land)
            elif will_enter_tapped and isinstance(land, SlowLand):
                slowlands.append(land)
            elif will_enter_tapped:
                priority_tapped_lands.append(land)
            else:
                untapped_lands.append(land)

        # Check if playing any land would let us cast a spell this turn
        # Check non-multiversal lands first
        best_land = None
        for land in untapped_lands + slowlands:
            # Lock color for choice-based lands
            if land.locked_color is None and self._is_choice_land(land):
                # For fetch lands, only consider colors with available basics
                available_colors = None
                if self._is_fetch_land(land):
                    available_colors = {c for c in land.production.get_all_colors()
                                       if self.available_basics[c] > 0}
                land.locked_color = land.choose_color(
                    self.lands_in_play, self.hand, target_costs, available_colors
                )

            # Simulate playing this land
            self.lands_in_play.append(land)
            self.played_land_this_turn = True

            can_cast_any = any(self.can_cast_spell(cost) for cost in target_costs)

            # Undo simulation
            self.lands_in_play.pop()
            self.played_land_this_turn = False

            if can_cast_any:
                best_land = land
                break

        # If no non-multiversal land enables casting, check multiversal lands
        if not best_land:
            for land in multiversal_lands:
                # Lock color for multiversal lands
                if land.locked_color is None:
                    # Multiversal lands don't fetch, so no color restriction
                    land.locked_color = land.choose_color(
                        self.lands_in_play, self.hand, target_costs
                    )

                # Simulate playing this land
                self.lands_in_play.append(land)
                self.played_land_this_turn = True

                can_cast_any = any(self.can_cast_spell(cost) for cost in target_costs)

                # Undo simulation
                self.lands_in_play.pop()
                self.played_land_this_turn = False

                if can_cast_any:
                    best_land = land
                    break

        # If a land enables casting, play it
        if best_land:
            self.hand.remove(best_land)
            self.lands_in_play.append(best_land)
            self.played_land_this_turn = True

            # If this is a fetch land, fetch a basic from the deck
            if self._is_fetch_land(best_land) and best_land.locked_color:
                self._fetch_basic(best_land.locked_color)

            return True

        # Otherwise, play lands in priority order:
        # 1. Priority tapped lands (non-slowland)
        # 2. Untapped lands
        # 3. Slowlands
        # 4. Multiversal lands (deprioritized)

        chosen = None
        candidate_lands = None

        if priority_tapped_lands:
            candidate_lands = priority_tapped_lands
        elif untapped_lands:
            candidate_lands = untapped_lands
        elif slowlands:
            candidate_lands = slowlands
        elif multiversal_lands:
            candidate_lands = multiversal_lands

        if candidate_lands:
            # Lock color for choice-based lands
            for land in candidate_lands:
                if land.locked_color is None and self._is_choice_land(land):
                    # For fetch lands, only consider colors with available basics
                    available_colors = None
                    if self._is_fetch_land(land):
                        available_colors = {c for c in land.production.get_all_colors()
                                           if self.available_basics[c] > 0}
                    land.locked_color = land.choose_color(
                        self.lands_in_play, self.hand, target_costs, available_colors
                    )

            # Pick one with most color overlap
            if target_costs:
                scored_lands = []
                for land in candidate_lands:
                    max_overlap = max(land.shares_colors_with_cost(cost)
                                     for cost in target_costs)
                    scored_lands.append((max_overlap, land))

                # Check if all have same score
                scores = [score for score, _ in scored_lands]
                if len(set(scores)) == 1:
                    # All same, pick randomly
                    chosen = random.choice(candidate_lands)
                else:
                    # Pick the one with highest score
                    scored_lands.sort(key=lambda x: x[0], reverse=True)
                    chosen = scored_lands[0][1]
            else:
                chosen = random.choice(candidate_lands)

            self.hand.remove(chosen)
            self.lands_in_play.append(chosen)
            self.played_land_this_turn = True

            # If this is a fetch land, fetch a basic from the deck
            if self._is_fetch_land(chosen) and chosen.locked_color:
                self._fetch_basic(chosen.locked_color)

            return True

        return False

    def _is_choice_land(self, land: Land) -> bool:
        """Check if a land requires color locking."""
        return isinstance(land, (MultiversalLand, WildsLand, FabledLand, StartingTownLand))

    def _is_fetch_land(self, land: Land) -> bool:
        """Check if a land fetches basics from the deck."""
        return isinstance(land, (WildsLand, FabledLand))

    def _fetch_basic(self, color: str) -> bool:
        """
        Fetch a basic of the specified color from the deck.
        Removes it from the deck to simulate fetching.
        Returns True if successful, False if no basic of that color remains.
        """
        if self.available_basics[color] <= 0:
            return False

        # Find and remove a basic of the chosen color from the deck
        for i, card in enumerate(self.deck):
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1 and color in colors:
                    # Remove this basic from the deck
                    self.deck.pop(i)
                    self.available_basics[color] -= 1
                    return True

        return False


def run_simulation(lands: List[Land], spells: List[ManaCost],
                   max_turn: int, cycles: int, deck_size: int = 60,
                   on_play: bool = True) -> List[Dict[int, float]]:
    """
    Run Monte Carlo simulation.
    Returns list of dicts (one per spell) mapping turn -> success probability.
    """
    # Build full deck with lands and non-lands (represented as None)
    num_lands = len(lands)
    num_nonlands = deck_size - num_lands
    if num_nonlands < 0:
        raise ValueError(f"Too many lands ({num_lands}) for deck size ({deck_size})")

    full_deck = lands + [None] * num_nonlands

    # Track success by spell and turn
    success_by_spell_turn = [defaultdict(int) for _ in spells]

    for cycle in range(cycles):
        # Progress logging
        if (cycle + 1) % 500 == 0:
            print(f"{cycle + 1}", end='', flush=True)
        elif (cycle + 1) % 100 == 0:
            print('.', end='', flush=True)

        game = GameState(full_deck, on_play=on_play)

        for turn in range(1, max_turn + 1):
            game.start_turn()
            game.play_land_optimally(spells)

            # Check each spell individually
            for spell_idx, cost in enumerate(spells):
                if game.can_cast_spell(cost):
                    success_by_spell_turn[spell_idx][turn] += 1

    print()  # New line after progress logging

    # Convert to probabilities
    probabilities_per_spell = []
    for spell_idx in range(len(spells)):
        probabilities = {}
        for turn in range(1, max_turn + 1):
            probabilities[turn] = success_by_spell_turn[spell_idx][turn] / cycles
        probabilities_per_spell.append(probabilities)

    return probabilities_per_spell
