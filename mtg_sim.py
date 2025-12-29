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

USAGE:
    python mtg_sim.py [filename] [--help]

    filename: Path to input file (default: inputs.txt)
    --help, -h: Show this help message

INPUT FILE FORMAT:

Section headers (LANDS, SPELLS, CYCLERS, SETTINGS) are optional. Use blank lines to
separate sections if headers are omitted.

    <land_type> <mana_production> <count>
    ...

    <mana_cost>
    ...

    <mana_production> <cycling_cost> <count>
    ...

    <setting_name> <value>
    ...

MANA NOTATION:
    Colors: W (white), U (blue), B (black), R (red), G (green), C (colorless)
    Production: WU (AND), W/U (OR), {R/U}U (choice + required)
    Costs: 2G (generic + colored), {3/R} (hybrid generic/colored)

LAND TYPES:
    basic, shock, dual, fastland, slowland, surveil, verge, wilds, tapped,
    fetch, untapped, multiversal, fabled, startingtown

CYCLERS:
    Cards that convert to basics when enough lands are in play
    cycling_cost = number of lands needed in play to cycle

SETTINGS:
    cycles <number>        - Monte Carlo iterations (default: 20000)
    play <true/false>      - On the play (default: true)
    draw <true/false>      - On the draw (default: false)
    deck_size <number>     - Total deck size (default: 60)

EXAMPLE:
    basic W 20
    shock WU 4

    1WWW
    2UW

    W 3 2

    cycles 10000

For full details on land behaviors, mulligan strategy, and algorithm specifics,
see the README.md file.
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
    lands, spells, cyclers, settings = parse_input_file(args.filename)
    cycles = settings.get('cycles', 20000)
    on_play = settings.get('play', True)
    deck_size = settings.get('deck_size', 60)

    cycler_count = len(cyclers)
    cycler_msg = f" and {cycler_count} cycler(s)" if cycler_count > 0 else ""
    print(f"Running simulation with {len(lands)} lands{cycler_msg} and {len(spells)} target spell(s)...")
    print(f"Monte Carlo cycles: {cycles}")
    print(f"On the {'play' if on_play else 'draw'}")
    print()

    # Run simulation for turns 1-10
    max_turn = 10
    probabilities_per_spell = run_simulation(lands, spells, cyclers, max_turn, cycles,
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
