"""
Monte Carlo simulation for Magic: the Gathering mana bases.
"""

import random
from collections import defaultdict
from typing import List, Dict

from mtg_classes import (
    Land, ManaCost, SlowLand, MultiversalLand, WildsLand,
    FabledLand, StartingTownLand, BasicLand, Cycler, Rock
)


class GameState:
    """Represents the state of a game for simulation."""

    def __init__(self, deck: List, starting_hand_size: int = 7,
                 on_play: bool = True):
        """
        Initialize game state.
        Deck should contain Land objects and None values (non-lands).
        """
        # Store original deck composition for calculating available basics
        self.original_deck = deck[:]

        self.deck = deck[:]
        random.shuffle(self.deck)

        self.hand = []
        self.lands_in_play = []
        self.rocks_in_play = []  # Rocks that have been cast
        self.played_land_this_turn = False
        self.rock_cast_this_turn = None  # The rock cast this turn (for cost deduction)
        self.turn = 0
        self.on_play = on_play
        self.mulligans_taken = 0

        # Draw starting hand and perform mulligans
        self._draw_opening_hand(starting_hand_size)

    def draw_card(self):
        """Draw a card from the deck."""
        if self.deck:
            card = self.deck.pop()
            self.hand.append(card)

    def start_turn(self):
        """Start a new turn."""
        self.turn += 1
        self.played_land_this_turn = False
        self.rock_cast_this_turn = None

        # Draw a card (skip first draw if on the play)
        if not (self.on_play and self.turn == 1):
            self.draw_card()

    def _draw_opening_hand(self, hand_size: int):
        """Draw opening hand and perform mulligans as needed."""
        # Draw initial 7 cards
        for _ in range(7):
            if self.deck:
                card = self.deck.pop()
                self.hand.append(card)

        # Perform mulligans
        while self._should_mulligan():
            self._mulligan()

        # After all mulligans, bottom cards as needed
        cards_to_bottom = self.mulligans_taken
        for _ in range(cards_to_bottom):
            if self.hand:
                self._bottom_card()

    def _should_mulligan(self) -> bool:
        """Decide whether to mulligan based on current hand."""
        hand_size = len(self.hand)
        land_count = sum(1 for card in self.hand if card and isinstance(card, Land))

        # First two mulligans (7 and 6 card hands): mulligan if 1 or less lands, or 6+ lands
        if self.mulligans_taken <= 1:
            return land_count <= 1 or land_count >= 6

        # Third mulligan (5 card hand): only mulligan if 0 lands or all lands
        if self.mulligans_taken == 2:
            return land_count == 0 or land_count == hand_size

        # After that (4 cards or less): keep any hand
        return False

    def _mulligan(self):
        """Perform a mulligan: shuffle hand back, redraw 7."""
        self.mulligans_taken += 1

        # Put hand back into deck
        for card in self.hand:
            self.deck.append(card)

        self.hand = []

        # Shuffle deck
        random.shuffle(self.deck)

        # Draw 7 new cards
        for _ in range(7):
            if self.deck:
                card = self.deck.pop()
                self.hand.append(card)

    def _bottom_card(self):
        """Put a card from hand on the bottom of the deck."""
        if not self.hand:
            return

        # Prioritize bottoming non-lands
        non_lands = [card for card in self.hand if not card or not isinstance(card, Land)]
        if non_lands:
            card_to_bottom = random.choice(non_lands)
        else:
            # All lands, pick randomly
            card_to_bottom = random.choice(self.hand)

        self.hand.remove(card_to_bottom)
        self.deck.insert(0, card_to_bottom)  # Insert at beginning (bottom)

    def _shuffle_deck(self):
        """Shuffle the deck (called after fetching)."""
        random.shuffle(self.deck)

    def _get_available_basics(self) -> Dict[str, int]:
        """
        Compute available basics remaining in deck.
        Returns dict mapping color -> count.
        """
        # Count basics in original deck
        basics_by_color = defaultdict(int)
        for card in self.original_deck:
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1:
                    color = list(colors)[0]
                    basics_by_color[color] += 1

        # Subtract basics in play
        for land in self.lands_in_play:
            if isinstance(land, BasicLand):
                colors = land.production.get_all_colors()
                if len(colors) == 1:
                    color = list(colors)[0]
                    basics_by_color[color] -= 1

        # Subtract basics in hand
        for card in self.hand:
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1:
                    color = list(colors)[0]
                    basics_by_color[color] -= 1

        return basics_by_color

    def can_cast_spell(self, cost: ManaCost) -> bool:
        """Check if we can cast a spell with the given cost."""
        # Get available mana sources (each land produces 1 mana of its available colors)
        mana_sources = []
        filterer_colors = set()  # Colors available via filterer rocks

        # Add mana from lands
        for i, land in enumerate(self.lands_in_play):
            just_played = (i == len(self.lands_in_play) - 1 and self.played_land_this_turn)
            colors = land.get_available_mana(self.lands_in_play[:i], just_played)
            if colors:  # Land can produce mana
                mana_sources.append(colors)

        # Add mana from rocks (excluding the one just cast)
        for rock in self.rocks_in_play:
            # Skip the rock cast this turn when adding to mana sources initially
            # (we'll add it back after deducting its cost)
            if rock == self.rock_cast_this_turn:
                continue

            if rock.is_filterer:
                # Filterer rocks enable color conversion
                filterer_colors.update(rock.production.get_all_colors())
            else:
                # Non-filterer rocks add mana
                mana_sources.append(rock.production.get_all_colors())

        # If we have filterer rocks, expand mana sources to include filterer colors
        if filterer_colors:
            expanded_sources = []
            for source_colors in mana_sources:
                # Each source can now also produce filterer colors
                expanded_colors = source_colors | filterer_colors
                expanded_sources.append(expanded_colors)
            mana_sources = expanded_sources

        # If a rock was cast this turn, first spend mana on its cost
        used_sources = []
        if self.rock_cast_this_turn:
            rock_cost = self.rock_cast_this_turn.cost
            # Try to pay for the rock
            rock_remaining_generic = rock_cost.generic
            rock_needed_colored = dict(rock_cost.colored)
            rock_remaining_hybrid = list(rock_cost.hybrid)

            # Pay colored costs for rock
            for color, count in list(rock_needed_colored.items()):
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
                    return False  # Can't afford the rock
                del rock_needed_colored[color]

            # Handle hybrid costs for rock
            for generic_cost, color_part in rock_remaining_hybrid:
                paid = False
                if '/' in color_part:
                    colors = color_part.split('/')
                    for idx, source_colors in enumerate(mana_sources):
                        if idx in used_sources:
                            continue
                        if any(c in source_colors for c in colors):
                            used_sources.append(idx)
                            paid = True
                            break
                else:
                    for idx, source_colors in enumerate(mana_sources):
                        if idx in used_sources:
                            continue
                        if color_part in source_colors:
                            used_sources.append(idx)
                            paid = True
                            break

                if not paid:
                    rock_remaining_generic += generic_cost - 1 if generic_cost > 0 else 0

            # Pay generic for rock
            available_for_generic = len(mana_sources) - len(used_sources)
            if available_for_generic < rock_remaining_generic:
                return False  # Can't afford the rock

            # Spend the generic mana
            for _ in range(rock_remaining_generic):
                for idx in range(len(mana_sources)):
                    if idx not in used_sources:
                        used_sources.append(idx)
                        break

            # Now add the rock's mana production (it's in play now)
            if self.rock_cast_this_turn.is_filterer:
                # Add filterer colors to all remaining sources
                filterer_colors.update(self.rock_cast_this_turn.production.get_all_colors())
                # Re-expand sources
                expanded_sources = []
                for idx, source_colors in enumerate(mana_sources):
                    if idx in used_sources:
                        expanded_sources.append(source_colors)  # Already used
                    else:
                        expanded_colors = source_colors | filterer_colors
                        expanded_sources.append(expanded_colors)
                mana_sources = expanded_sources
            else:
                # Add non-filterer rock's mana
                mana_sources.append(self.rock_cast_this_turn.production.get_all_colors())

        # Now try to pay the spell cost with remaining mana
        remaining_generic = cost.generic
        needed_colored = dict(cost.colored)
        remaining_hybrid = list(cost.hybrid)

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
                    available_basics = self._get_available_basics()
                    available_colors = {c for c in land.production.get_all_colors()
                                       if available_basics[c] > 0}
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
                        available_basics = self._get_available_basics()
                        available_colors = {c for c in land.production.get_all_colors()
                                           if available_basics[c] > 0}
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
        Shuffles the deck after fetching.
        Returns True if successful, False if no basic of that color remains.
        """
        available_basics = self._get_available_basics()
        if available_basics[color] <= 0:
            return False

        # Find and remove a basic of the chosen color from the deck
        for i, card in enumerate(self.deck):
            if card and isinstance(card, BasicLand):
                colors = card.production.get_all_colors()
                if len(colors) == 1 and color in colors:
                    # Remove this basic from the deck
                    self.deck.pop(i)
                    # Shuffle deck after fetching
                    self._shuffle_deck()
                    return True

        return False

    def cycle_cyclers(self, target_costs: List[ManaCost]):
        """
        Cycle any eligible cyclers in hand.
        This should be called before deciding which land to play.
        """
        cyclers_in_hand = [card for card in self.hand if isinstance(card, Cycler)]

        for cycler in cyclers_in_hand:
            # Check if we have enough lands to cycle
            if len(self.lands_in_play) >= cycler.cycling_cost:
                # Get the colors this cycler can produce
                colors = cycler.production.get_all_colors()

                # Check which colors have available basics
                available_basics = self._get_available_basics()
                fetchable_colors = [c for c in colors if available_basics[c] > 0]

                if not fetchable_colors:
                    continue  # Can't cycle if no basics available

                # Choose which color to fetch using the same heuristic as choice lands
                # Create a dummy land to use the choose_color method
                from mtg_classes import BasicLand
                dummy_land = BasicLand(cycler.production, 1)
                chosen_color = dummy_land.choose_color(
                    self.lands_in_play, self.hand, target_costs,
                    available_colors=set(fetchable_colors)
                )

                if not chosen_color:
                    continue

                # Find and fetch the basic from the deck
                fetched_basic = None
                for i, card in enumerate(self.deck):
                    if card and isinstance(card, BasicLand):
                        card_colors = card.production.get_all_colors()
                        if len(card_colors) == 1 and chosen_color in card_colors:
                            # Remove this basic from the deck
                            fetched_basic = self.deck.pop(i)
                            # Shuffle deck after fetching
                            self._shuffle_deck()
                            break

                if fetched_basic:
                    # Remove cycler from hand
                    self.hand.remove(cycler)

                    # Add the fetched basic to hand (not in play)
                    self.hand.append(fetched_basic)

    def cast_rocks(self, target_costs: List[ManaCost]) -> bool:
        """
        Try to cast rocks from hand.
        Returns True if a rock was cast.
        Cast as soon as possible, but after land play and cycling.
        """
        rocks_in_hand = [card for card in self.hand if isinstance(card, Rock)]

        for rock in rocks_in_hand:
            # Check if we can afford to cast this rock
            if self.can_cast_spell(rock.cost):
                # Cast the rock
                self.hand.remove(rock)
                self.rocks_in_play.append(rock)
                self.rock_cast_this_turn = rock
                return True

        return False


def run_simulation(lands: List[Land], spells: List[ManaCost], cyclers: List[Cycler], rocks: List[Rock],
                   max_turn: int, cycles: int, deck_size: int = 60,
                   on_play: bool = True) -> List[Dict[int, float]]:
    """
    Run Monte Carlo simulation.
    Returns list of dicts (one per spell) mapping turn -> success probability.
    """
    # Build full deck with lands, cyclers, rocks, and non-lands (represented as None)
    num_lands = len(lands)
    num_cyclers = len(cyclers)
    num_rocks = len(rocks)
    num_nonlands = deck_size - num_lands - num_cyclers - num_rocks
    if num_nonlands < 0:
        raise ValueError(f"Too many lands ({num_lands}), cyclers ({num_cyclers}), and rocks ({num_rocks}) for deck size ({deck_size})")

    full_deck = lands + cyclers + rocks + [None] * num_nonlands

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
            # Cycle eligible cyclers before deciding which land to play
            game.cycle_cyclers(spells)
            game.play_land_optimally(spells)
            # Cast rocks after land play
            game.cast_rocks(spells)

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
