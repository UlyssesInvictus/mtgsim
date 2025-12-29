"""
Monte Carlo simulation for Magic: the Gathering mana bases.
"""

import random
from collections import defaultdict
from typing import List, Dict

from mtg_classes import Land, ManaCost, SlowLand


class GameState:
    """Represents the state of a game for simulation."""

    def __init__(self, deck: List[Land], starting_hand_size: int = 7,
                 on_play: bool = True):
        self.deck = deck[:]
        random.shuffle(self.deck)

        self.hand = []
        self.lands_in_play = []
        self.played_land_this_turn = False
        self.turn = 0
        self.on_play = on_play

        # Draw starting hand
        for _ in range(starting_hand_size):
            if self.deck:
                self.hand.append(self.deck.pop())

    def draw_card(self):
        """Draw a card from the deck."""
        if self.deck:
            self.hand.append(self.deck.pop())

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

        # Separate lands that enter tapped vs untapped
        # Also separate slowlands from other tapped lands (slowlands not prioritized)
        priority_tapped_lands = []  # Tapped lands to prioritize (non-slowlands)
        slowlands = []
        untapped_lands = []

        for land in self.hand:
            will_enter_tapped = land.check_enters_tapped(self.lands_in_play)
            if will_enter_tapped and isinstance(land, SlowLand):
                slowlands.append(land)
            elif will_enter_tapped:
                priority_tapped_lands.append(land)
            else:
                untapped_lands.append(land)

        # Check if playing an untapped land or slowland would let us cast a spell this turn
        best_land = None
        for land in untapped_lands + slowlands:
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

        # If an untapped land or slowland lets us cast, play it
        if best_land:
            self.hand.remove(best_land)
            self.lands_in_play.append(best_land)
            self.played_land_this_turn = True
            return True

        # Otherwise, prioritize non-slowland tapped lands
        if priority_tapped_lands:
            # Among priority tapped lands, pick the one with most color overlap
            if target_costs:
                scored_lands = []
                for land in priority_tapped_lands:
                    max_overlap = max(land.shares_colors_with_cost(cost)
                                     for cost in target_costs)
                    scored_lands.append((max_overlap, land))

                # Check if all have same score
                scores = [score for score, _ in scored_lands]
                if len(set(scores)) == 1:
                    # All same, pick randomly
                    chosen = random.choice(priority_tapped_lands)
                else:
                    # Pick the one with highest score
                    scored_lands.sort(key=lambda x: x[0], reverse=True)
                    chosen = scored_lands[0][1]
            else:
                chosen = random.choice(priority_tapped_lands)

            self.hand.remove(chosen)
            self.lands_in_play.append(chosen)
            self.played_land_this_turn = True
            return True

        # No priority tapped lands, play an untapped land or slowland
        other_lands = untapped_lands + slowlands
        if other_lands:
            # Pick one with most color overlap
            if target_costs:
                scored_lands = []
                for land in other_lands:
                    max_overlap = max(land.shares_colors_with_cost(cost)
                                     for cost in target_costs)
                    scored_lands.append((max_overlap, land))

                scored_lands.sort(key=lambda x: x[0], reverse=True)
                chosen = scored_lands[0][1]
            else:
                chosen = other_lands[0]

            self.hand.remove(chosen)
            self.lands_in_play.append(chosen)
            self.played_land_this_turn = True
            return True

        return False


def run_simulation(lands: List[Land], spells: List[ManaCost],
                   max_turn: int, cycles: int, on_play: bool = True) -> List[Dict[int, float]]:
    """
    Run Monte Carlo simulation.
    Returns list of dicts (one per spell) mapping turn -> success probability.
    """
    # Track success by spell and turn
    success_by_spell_turn = [defaultdict(int) for _ in spells]

    for cycle in range(cycles):
        # Progress logging
        if (cycle + 1) % 500 == 0:
            print(f"\r{cycle + 1}", end='', flush=True)
        elif (cycle + 1) % 100 == 0:
            print('.', end='', flush=True)

        game = GameState(lands, on_play=on_play)

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
