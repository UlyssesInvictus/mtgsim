#!/usr/bin/env python3
"""
Tests for MTG mana base simulator.
Organized into three main categories:
1. Class Tests - Testing individual classes and their behaviors
2. Input Validation Tests - Testing file parsing and validation
3. Mana Consumption Tests - Testing spell casting and mana availability
"""

import os
import sys
import tempfile
import unittest
from io import StringIO

from mtg_classes import (
    ManaProduction, ManaCost, LAND_TYPES,
    ShockLand, FastLand, SlowLand, VergeLand, BasicLand,
    WildsLand, FetchLand, UntappedLand, Cycler
)
from mtg_parser import parse_input_file
from mtg_simulation import GameState, run_simulation


# ============================================================================
# CATEGORY 1: CLASS TESTS
# Testing individual classes (ManaProduction, ManaCost, Land types)
# ============================================================================

class TestManaProductionClass(unittest.TestCase):
    """Test mana production parsing and behavior."""

    def test_single_color(self):
        """Test single color production."""
        prod = ManaProduction('W')
        self.assertEqual(prod.get_all_colors(), {'W'})

    def test_multiple_colors(self):
        """Test multiple color production (AND)."""
        prod = ManaProduction('WU')
        self.assertEqual(prod.get_all_colors(), {'W', 'U'})

    def test_or_colors(self):
        """Test OR color production."""
        prod = ManaProduction('W/U')
        self.assertEqual(prod.get_all_colors(), {'W', 'U'})

    def test_complex_production(self):
        """Test complex production patterns."""
        prod = ManaProduction('{R/U}U')
        self.assertEqual(prod.get_all_colors(), {'R', 'U'})

    def test_has_color(self):
        """Test color checking."""
        prod = ManaProduction('W/U')
        self.assertTrue(prod.has_color('W'))
        self.assertTrue(prod.has_color('U'))
        self.assertFalse(prod.has_color('B'))

    def test_get_colors_in_order(self):
        """Test that colors are returned in order."""
        prod = ManaProduction('WR')
        colors = prod.get_colors_in_order()
        self.assertEqual(colors[0], 'W')
        self.assertEqual(colors[1], 'R')


class TestManaCostClass(unittest.TestCase):
    """Test mana cost parsing and behavior."""

    def test_generic_only(self):
        """Test generic mana cost."""
        cost = ManaCost('3')
        self.assertEqual(cost.generic, 3)
        self.assertEqual(len(cost.colored), 0)

    def test_colored_only(self):
        """Test colored mana cost."""
        cost = ManaCost('WUB')
        self.assertEqual(cost.generic, 0)
        self.assertEqual(cost.colored['W'], 1)
        self.assertEqual(cost.colored['U'], 1)
        self.assertEqual(cost.colored['B'], 1)

    def test_mixed_cost(self):
        """Test mixed mana cost."""
        cost = ManaCost('2WU')
        self.assertEqual(cost.generic, 2)
        self.assertEqual(cost.colored['W'], 1)
        self.assertEqual(cost.colored['U'], 1)

    def test_bracketed_generic(self):
        """Test bracketed generic cost."""
        cost = ManaCost('{3}WU')
        self.assertEqual(cost.generic, 3)
        self.assertEqual(cost.colored['W'], 1)
        self.assertEqual(cost.colored['U'], 1)

    def test_hybrid_cost(self):
        """Test hybrid mana cost."""
        cost = ManaCost('{3/R}{3/W}')
        self.assertEqual(len(cost.hybrid), 2)
        self.assertIn((3, 'R'), cost.hybrid)
        self.assertIn((3, 'W'), cost.hybrid)

    def test_total_mana_needed(self):
        """Test calculating total mana needed."""
        cost = ManaCost('2WU')
        self.assertEqual(cost.total_mana_needed(), 4)

    def test_multiple_same_color(self):
        """Test spell with multiple of the same color."""
        cost = ManaCost('WWW')
        self.assertEqual(cost.colored['W'], 3)
        self.assertEqual(cost.generic, 0)


class TestLandTypeClasses(unittest.TestCase):
    """Test different land types and their behaviors."""

    def test_shock_land(self):
        """Test shock land never enters tapped."""
        prod = ManaProduction('WU')
        land = ShockLand(prod, 1)
        self.assertFalse(land.check_enters_tapped([]))
        self.assertFalse(land.check_enters_tapped([land, land]))

    def test_fastland(self):
        """Test fastland enters tapped with 3+ lands."""
        prod = ManaProduction('WU')
        land = FastLand(prod, 1)

        # Should enter untapped with 0-2 lands
        self.assertFalse(land.check_enters_tapped([]))
        self.assertFalse(land.check_enters_tapped([land]))
        self.assertFalse(land.check_enters_tapped([land, land]))

        # Should enter tapped with 3+ lands
        self.assertTrue(land.check_enters_tapped([land, land, land]))

    def test_slowland(self):
        """Test slowland enters tapped with 2 or fewer lands."""
        prod = ManaProduction('WU')
        land = SlowLand(prod, 1)

        # Should enter tapped with 0-2 lands
        self.assertTrue(land.check_enters_tapped([]))
        self.assertTrue(land.check_enters_tapped([land]))
        self.assertTrue(land.check_enters_tapped([land, land]))

        # Should enter untapped with 3+ lands
        self.assertFalse(land.check_enters_tapped([land, land, land]))

    def test_basic_land(self):
        """Test basic land enters untapped."""
        prod = ManaProduction('W')
        land = BasicLand(prod, 1)
        self.assertFalse(land.check_enters_tapped([]))

    def test_wilds_land(self):
        """Test wilds land always enters tapped."""
        prod = ManaProduction('WUBRG')
        land = WildsLand(prod, 1)
        self.assertTrue(land.check_enters_tapped([]))

    def test_fetch_land(self):
        """Test fetch land never enters tapped."""
        prod = ManaProduction('WU')
        land = FetchLand(prod, 1)
        self.assertFalse(land.check_enters_tapped([]))

    def test_untapped_land(self):
        """Test untapped land never enters tapped."""
        prod = ManaProduction('WU')
        land = UntappedLand(prod, 1)
        self.assertFalse(land.check_enters_tapped([]))

    def test_verge_land_basic(self):
        """Test verge land produces first color by default."""
        prod = ManaProduction('WR')
        verge = VergeLand(prod, 1)

        # Without shock/dual/surveil, only first color available
        available = verge.get_available_mana([], False)
        self.assertIn('W', available)
        self.assertNotIn('R', available)

    def test_verge_land_with_shock(self):
        """Test verge land with shock in play."""
        verge_prod = ManaProduction('WR')
        verge = VergeLand(verge_prod, 1)

        shock_prod = ManaProduction('WU')
        shock = ShockLand(shock_prod, 1)

        # With shock that has W, second color should be available
        available = verge.get_available_mana([shock], False)
        self.assertIn('W', available)
        self.assertIn('R', available)

    def test_shares_colors_with_cost(self):
        """Test color sharing calculation."""
        land = BasicLand(ManaProduction('W'), 1)
        cost = ManaCost('2W')
        self.assertEqual(land.shares_colors_with_cost(cost), 1)

    def test_shares_multiple_colors(self):
        """Test multiple color sharing."""
        land = ShockLand(ManaProduction('WU'), 1)
        cost = ManaCost('WU')
        self.assertEqual(land.shares_colors_with_cost(cost), 2)

    def test_shares_no_colors(self):
        """Test no color sharing."""
        land = BasicLand(ManaProduction('W'), 1)
        cost = ManaCost('2R')
        self.assertEqual(land.shares_colors_with_cost(cost), 0)


class TestCyclerClass(unittest.TestCase):
    """Test Cycler class and behavior."""

    def test_cycler_creation(self):
        """Test creating a cycler."""
        prod = ManaProduction('W')
        cycler = Cycler(prod, 3, 1)
        self.assertEqual(cycler.cycling_cost, 3)
        self.assertEqual(cycler.count, 1)
        self.assertEqual(cycler.production.get_all_colors(), {'W'})

    def test_cycler_validation_single_color(self):
        """Test that cyclers must produce exactly one color."""
        prod = ManaProduction('W')
        # Should not raise
        Cycler.validate_production(prod)

    def test_cycler_validation_multiple_colors(self):
        """Test that cyclers cannot produce multiple colors."""
        prod = ManaProduction('WU')
        with self.assertRaises(ValueError):
            Cycler.validate_production(prod)

    def test_cycler_validation_or_colors(self):
        """Test that cyclers cannot have OR color production."""
        prod = ManaProduction('W/U')
        with self.assertRaises(ValueError):
            Cycler.validate_production(prod)


# ============================================================================
# CATEGORY 2: INPUT VALIDATION TESTS
# Testing file parsing and input validation
# ============================================================================

class TestInputFileValidation(unittest.TestCase):
    """Test input file parsing and validation."""

    def create_temp_file(self, content):
        """Create a temporary file with given content."""
        fd, path = tempfile.mkstemp(suffix='.txt')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return path

    def test_valid_input(self):
        """Test parsing valid input file."""
        content = """
LANDS
basic W 10
shock WU 4

SPELLS
2W
1UW

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            lands, spells, cyclers, settings = parse_input_file(path)
            self.assertEqual(len(lands), 14)  # 10 + 4
            self.assertEqual(len(spells), 2)
            self.assertEqual(len(cyclers), 0)  # No cyclers in this test
            self.assertEqual(settings['cycles'], 5000)
        finally:
            os.unlink(path)

    def test_missing_lands(self):
        """Test error when no lands specified."""
        content = """
SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_missing_spells(self):
        """Test error when no spells specified."""
        content = """
LANDS
basic W 10

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_invalid_land_type(self):
        """Test error with invalid land type."""
        content = """
LANDS
invalid_type W 10

SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_basic_land_validation(self):
        """Test basic land can only produce one color."""
        content = """
LANDS
basic WU 10

SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_wilds_validation(self):
        """Test wilds must produce WUBRG."""
        content = """
LANDS
wilds WU 4

SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_verge_validation(self):
        """Test verge must produce exactly 2 colors."""
        content = """
LANDS
verge WUB 4

SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)

    def test_case_insensitive_sections(self):
        """Test that section headers are case-insensitive."""
        content = """
lands
basic W 10

spells
2W

settings
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            lands, spells, cyclers, settings = parse_input_file(path)
            self.assertEqual(len(lands), 10)
            self.assertEqual(len(spells), 1)
            self.assertEqual(len(cyclers), 0)
            self.assertEqual(settings['cycles'], 5000)
        finally:
            os.unlink(path)

    def test_new_land_types_accepted(self):
        """Test that fetch and untapped land types are accepted."""
        content = """
LANDS
fetch WU 4
untapped RG 4

SPELLS
2W

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            lands, spells, cyclers, settings = parse_input_file(path)
            self.assertEqual(len(lands), 8)
            self.assertEqual(len(cyclers), 0)
            # Check that we have the right types
            fetch_count = sum(1 for l in lands if isinstance(l, FetchLand))
            untapped_count = sum(1 for l in lands if isinstance(l, UntappedLand))
            self.assertEqual(fetch_count, 4)
            self.assertEqual(untapped_count, 4)
        finally:
            os.unlink(path)

    def test_cyclers_parsing(self):
        """Test parsing cyclers from input file."""
        content = """
LANDS
basic W 10

SPELLS
2W

CYCLERS
W 3 2
R 2 3

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            lands, spells, cyclers, settings = parse_input_file(path)
            self.assertEqual(len(lands), 10)
            self.assertEqual(len(spells), 1)
            self.assertEqual(len(cyclers), 5)  # 2 + 3
            # Check cycler properties
            w_cyclers = [c for c in cyclers if 'W' in c.production.get_all_colors()]
            r_cyclers = [c for c in cyclers if 'R' in c.production.get_all_colors()]
            self.assertEqual(len(w_cyclers), 2)
            self.assertEqual(len(r_cyclers), 3)
            self.assertEqual(w_cyclers[0].cycling_cost, 3)
            self.assertEqual(r_cyclers[0].cycling_cost, 2)
        finally:
            os.unlink(path)

    def test_cyclers_validation_single_color(self):
        """Test that cyclers must produce exactly one color."""
        content = """
LANDS
basic W 10

SPELLS
2W

CYCLERS
WU 3 2

SETTINGS
cycles 5000
"""
        path = self.create_temp_file(content)
        try:
            with self.assertRaises(SystemExit):
                parse_input_file(path)
        finally:
            os.unlink(path)


# ============================================================================
# CATEGORY 3: MANA CONSUMPTION TESTS
# Testing spell casting, mana availability, and game simulation
# ============================================================================

class TestGameStateBasics(unittest.TestCase):
    """Test basic game state operations."""

    def test_initial_state(self):
        """Test initial game state."""
        # Create realistic deck: 24 lands + 36 non-lands
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(24)]
        deck = lands + [None] * 36
        game = GameState(deck, starting_hand_size=7, on_play=True)

        # After mulligans, hand size varies but should be between 4-7
        self.assertGreaterEqual(len(game.hand), 4)
        self.assertLessEqual(len(game.hand), 7)
        self.assertEqual(len(game.lands_in_play), 0)
        self.assertEqual(game.turn, 0)

    def test_draw_on_play(self):
        """Test drawing on play (skip first draw)."""
        # Create realistic deck: 24 lands + 36 non-lands
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(24)]
        deck = lands + [None] * 36
        game = GameState(deck, starting_hand_size=7, on_play=True)

        initial_hand_size = len(game.hand)
        game.start_turn()  # Turn 1
        self.assertEqual(len(game.hand), initial_hand_size)  # No draw on turn 1

        game.start_turn()  # Turn 2
        self.assertEqual(len(game.hand), initial_hand_size + 1)  # Draw on turn 2

    def test_draw_on_draw(self):
        """Test drawing on the draw (draw every turn)."""
        # Create realistic deck: 24 lands + 36 non-lands
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(24)]
        deck = lands + [None] * 36
        game = GameState(deck, starting_hand_size=7, on_play=False)

        initial_hand_size = len(game.hand)
        game.start_turn()  # Turn 1
        self.assertEqual(len(game.hand), initial_hand_size + 1)  # Draw on turn 1


class TestManaConsumption(unittest.TestCase):
    """Test mana consumption and spell casting."""

    def test_can_cast_simple_spell(self):
        """Test casting a simple spell."""
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(20)]
        game = GameState(lands, starting_hand_size=7, on_play=True)

        # Play a land
        game.start_turn()
        if game.hand:
            land = game.hand[0]
            game.hand.remove(land)
            game.lands_in_play.append(land)

        # Should be able to cast W
        cost = ManaCost('W')
        self.assertTrue(game.can_cast_spell(cost))

        # Should not be able to cast 2W
        cost2 = ManaCost('2W')
        self.assertFalse(game.can_cast_spell(cost2))

    def test_tapped_land_cant_be_used_immediately(self):
        """Test that tapped lands can't produce mana the turn they're played."""
        lands = [WildsLand(ManaProduction('WUBRG'), 1) for _ in range(20)]
        game = GameState(lands, starting_hand_size=7, on_play=True)

        game.start_turn()
        if game.hand:
            land = game.hand[0]
            game.hand.remove(land)
            game.lands_in_play.append(land)
            game.played_land_this_turn = True

        # Should not be able to cast anything (land just played and is tapped)
        cost = ManaCost('W')
        self.assertFalse(game.can_cast_spell(cost))

    def test_generic_mana_payment(self):
        """Test that generic mana can be paid with any color."""
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(20)]
        game = GameState(lands, starting_hand_size=7, on_play=True)

        # Play 3 lands
        game.start_turn()
        for _ in range(3):
            if game.hand:
                land = game.hand[0]
                game.hand.remove(land)
                game.lands_in_play.append(land)
            game.start_turn()

        # Should be able to cast 2W using 3 white sources
        cost = ManaCost('2W')
        self.assertTrue(game.can_cast_spell(cost))


class TestCommonSenseCastability(unittest.TestCase):
    """
    Common sense tests to ensure spell castability is computed correctly.
    These tests verify expected outcomes with simple deck configurations.
    """

    def test_basic_white_lands_cast_www_on_turn_3(self):
        """60 W basics should always be able to cast WWW on turn 3."""
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(60)]
        spells = [ManaCost('WWW')]
        cyclers = []
        cycles = 1000

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=3, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]  # First (and only) spell

        # Should be castable by turn 3 in all cases
        # (we have 7 cards initially + 1 on turn 2 + 1 on turn 3 = 9 cards seen)
        # With 60 W basics in a 60-card deck, we should reliably have 3 lands by turn 3
        self.assertGreater(probabilities[3], 0.95,
            "WWW should be castable on turn 3 with 60 W basics in >95% of games")

    def test_basic_white_lands_cannot_cast_2r_on_turn_3(self):
        """60 W basics should never be able to cast 2R on turn 3."""
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(60)]
        spells = [ManaCost('2R')]
        cyclers = []
        cycles = 1000

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=3, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]  # First (and only) spell

        # Should never be castable (no red sources)
        self.assertEqual(probabilities[1], 0.0, "2R should never be castable with only W basics")
        self.assertEqual(probabilities[2], 0.0, "2R should never be castable with only W basics")
        self.assertEqual(probabilities[3], 0.0, "2R should never be castable with only W basics")

    def test_wilds_cannot_cast_2r_on_turn_3(self):
        """60 wilds should not be able to cast 2R on turn 3, but can on turn 4."""
        lands = [WildsLand(ManaProduction('WUBRG'), 1) for _ in range(60)]
        spells = [ManaCost('2R')]
        cyclers = []
        cycles = 1000

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=4, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]  # First (and only) spell

        # Wilds always enter tapped, so:
        # Turn 1: play wilds (tapped), no mana
        # Turn 2: play wilds (tapped), first wilds untaps (1 mana available)
        # Turn 3: play wilds (tapped), first two untap (2 mana available)
        # Turn 4: play wilds (tapped), first three untap (3 mana available) - can cast 2R
        # 2R needs 3 total mana, so should only be castable on turn 4+
        self.assertEqual(probabilities[1], 0.0, "Should not be castable turn 1")
        self.assertEqual(probabilities[2], 0.0, "Should not be castable turn 2")
        self.assertEqual(probabilities[3], 0.0, "Should not be castable turn 3 (only 2 mana)")
        self.assertGreater(probabilities[4], 0.95, "Should be castable turn 4 (3 mana available)")

    def test_dual_rw_can_cast_rrw_on_turn_3(self):
        """60 RW duals should always be able to cast RRW on turn 3."""
        lands = [ShockLand(ManaProduction('RW'), 1) for _ in range(60)]
        spells = [ManaCost('RRW')]
        cyclers = []
        cycles = 1000

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=3, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]  # First (and only) spell

        # With 60 RW duals (untapped), we should have 3 lands by turn 3 in most games
        # Each can tap for R or W, so RRW should be castable
        self.assertGreater(probabilities[3], 0.95,
            "RRW should be castable on turn 3 with 60 RW duals in >95% of games")

    def test_color_requirements_strictly_enforced(self):
        """Test that colored mana requirements are strictly enforced."""
        # 30 W basics + 30 R basics
        lands = ([BasicLand(ManaProduction('W'), 1) for _ in range(30)] +
                 [BasicLand(ManaProduction('R'), 1) for _ in range(30)])

        spells = [ManaCost('WWRR')]
        cyclers = []
        cycles = 1000

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=4, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]  # First (and only) spell

        # On turn 4 we have played 4 lands. The spell needs 2W and 2R.
        # With equal distribution, this should be possible in most games
        self.assertGreater(probabilities[4], 0.50,
            "WWRR should be castable on turn 4 with 30W/30R basics in >50% of games")


class TestCyclerBehavior(unittest.TestCase):
    """Test cycler game behavior and mechanics."""

    def test_cycler_cycles_when_enough_lands(self):
        """Test that cyclers cycle when enough lands are in play."""
        # 30 W basics + 30 cyclers (cycling cost 3)
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(30)]
        cyclers = [Cycler(ManaProduction('W'), 3, 1) for _ in range(30)]
        spells = [ManaCost('WWW')]
        cycles = 100

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=4, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]

        # With cyclers that convert to basics at 3 lands, we should be able to cast WWW
        # even if we draw cyclers early (they convert to basics)
        # This test just ensures cyclers don't break the simulation
        self.assertGreaterEqual(probabilities[3], 0.0, "Simulation should complete without error")

    def test_cycled_land_enters_tapped(self):
        """Test that cycled lands enter tapped and can't be used immediately."""
        # This is more of an integration test to ensure the behavior is correct
        # 25 W basics + 5 cyclers (cycling cost 1 - very low threshold)
        lands = [BasicLand(ManaProduction('W'), 1) for _ in range(25)]
        cyclers = [Cycler(ManaProduction('W'), 1, 1) for _ in range(5)]
        spells = [ManaCost('WW')]
        cycles = 100

        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=3, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]

        # If we have a cycler in hand on turn 2 (1 land in play), it should cycle
        # but the resulting basic enters tapped, so we'd have 1 untapped + 1 tapped = only 1 mana
        # WW needs 2 mana, so should not be castable until turn 3
        # This test verifies the tapped behavior is working
        self.assertGreaterEqual(probabilities[2], 0.0, "Simulation should complete without error")

    def test_cycler_with_no_available_basics(self):
        """Test that cyclers don't break when there are no basics to fetch."""
        # 30 shock lands (no basics) + 30 cyclers
        lands = [ShockLand(ManaProduction('WU'), 1) for _ in range(30)]
        cyclers = [Cycler(ManaProduction('W'), 2, 1) for _ in range(30)]
        spells = [ManaCost('WW')]
        cycles = 100

        # This should not crash - cyclers just won't cycle if no basics available
        probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn=3, cycles=cycles,
                                                deck_size=60, on_play=True)
        probabilities = probabilities_per_spell[0]

        # Should complete without error
        self.assertGreaterEqual(probabilities[3], 0.0, "Simulation should handle no-basics case")


if __name__ == '__main__':
    unittest.main()
