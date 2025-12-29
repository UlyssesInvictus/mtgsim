#!/usr/bin/env python3
"""
Monte Carlo simulation for Magic: the Gathering mana bases.
Simulates the likelihood of casting spells by specific turns.
"""

import argparse
import sys

from mtg_parser import parse_input_file
from mtg_simulation import run_simulation


def print_help():
    """Print help message."""
    help_text = """
Magic: the Gathering Mana Base Monte Carlo Simulator

IMPORTANT SIMPLIFICATIONS:
This simulator makes several simplifying assumptions:
- Life total is not a concern (no life payments modeled)
- Generic fetch lands (fetch/untapped types) do not actually fetch from the deck
- All lands in hand are assumed to be distinct playable options

Note: Fetch lands that specify basic types (wilds, fabled) DO fetch from the deck
and reduce deck size accordingly.

USAGE:
    python mtg_mana_sim.py [filename] [--help]

    filename: Path to input file (default: inputs.txt)
    --help, -h: Show this help message

INPUT FILE FORMAT:

LANDS
<land_type> <mana_production> <count>
...

SPELLS
<mana_cost>
...

SETTINGS
cycles <number>

MANA PRODUCTION FORMAT:
    - Single color: W, U, B, R, G, C (white, blue, black, red, green, colorless)
    - Multiple colors: WU (produces white AND blue)
    - Choice of colors: W/U (produces white OR blue)
    - Complex: {R/U}U (produces red OR blue, AND blue)

MANA COST FORMAT:
    - Generic mana: 2, 3, etc. (can be paid with any color)
    - Colored mana: W, U, B, R, G
    - Examples:
        - 2G: 2 generic + 1 green
        - {1}UB: 1 generic + 1 blue + 1 black
        - {3/R}{3/W}: (3 generic OR 1 red) AND (3 generic OR 1 white)

LAND TYPES:
    - basic: Produces one color, enters untapped (must specify only 1 color)
    - shock: Produces specified colors, enters untapped
    - dual: Same as shock
    - fastland: Enters tapped if 3+ lands already in play
    - slowland: Enters tapped if 2 or fewer lands in play
    - surveil: Always enters tapped
    - verge: Produces 2 colors, but second color only if there's a shock/dual/surveil
             in play that produces one of the verge's colors (must specify exactly 2 colors)
    - wilds: Fetches basics from deck, always enters tapped, locks to a single basic
             type when played (must specify WUBRG)
    - tapped: Generic tapped land, always enters tapped
    - fetch: No restrictions, enters untapped
    - untapped: Generic untapped land, no restrictions, enters untapped
    - multiversal: Taps for any color but locks to a single choice, enters untapped,
                   deprioritized for late play (must specify WUBRG)
    - fabled: Fetches basics from deck, locks to a single basic type, enters untapped
              if 3+ lands in play
    - startingtown: Taps for any color including colorless but locks to a single choice,
                    enters tapped if turn 4+ (must specify WUBRGC)

SETTINGS:
    - cycles: Number of Monte Carlo iterations (default: 20000)
    - play: Whether you're on the play (true/false, default: true)
    - draw: Whether you're on the draw (true/false, default: false)
      Note: You can specify just one of play/draw, and the other will be set automatically.
            If both are specified, they must be opposite values.
    - deck_size or decksize: Total deck size (default: 60)

EXAMPLE INPUT FILE:

LANDS
basic W 20
shock WU 4

SPELLS
1WWW
2UW

SETTINGS
cycles 10000
play true
deck_size 60
"""
    print(help_text)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('filename', nargs='?', default='inputs.txt')
    parser.add_argument('-h', '--help', action='store_true')

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    # Parse input file
    lands, spells, settings = parse_input_file(args.filename)
    cycles = settings.get('cycles', 20000)
    on_play = settings.get('play', True)
    deck_size = settings.get('deck_size', 60)

    print(f"Running simulation with {len(lands)} lands and {len(spells)} target spell(s)...")
    print(f"Monte Carlo cycles: {cycles}")
    print(f"On the {'play' if on_play else 'draw'}")
    print()

    # Run simulation for turns 1-10
    max_turn = 10
    probabilities_per_spell = run_simulation(lands, spells, max_turn, cycles,
                                            deck_size=deck_size, on_play=on_play)

    # Print results for each spell
    print()
    print("Results (probability of casting each spell by turn):")
    print("=" * 60)

    for spell_idx, (spell, probabilities) in enumerate(zip(spells, probabilities_per_spell)):
        print(f"\nSpell {spell_idx + 1}: {spell.cost_str}")
        print("-" * 60)

        # Find first turn with non-zero probability
        first_turn = None
        for turn in range(1, max_turn + 1):
            if probabilities[turn] > 0:
                first_turn = turn
                break

        if first_turn is None:
            print("  Never castable within simulated turns")
            continue

        # Show first turn and next 3 turns
        for turn in range(first_turn, min(first_turn + 4, max_turn + 1)):
            prob = probabilities[turn]
            percentage = prob * 100
            print(f"  Turn {turn:2d}: {percentage:6.2f}%")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
