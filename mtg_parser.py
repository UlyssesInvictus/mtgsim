"""
Input file parsing for Magic: the Gathering mana base simulation.
"""

import sys
from typing import List, Dict, Tuple

from mtg_classes import Land, ManaCost, ManaProduction, LAND_TYPES


def parse_input_file(filename: str) -> Tuple[List[Land], List[ManaCost], Dict[str, any]]:
    """Parse the input file and return lands, spells, and settings."""
    try:
        with open(filename, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file '{filename}' not found.")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)

    lands = []
    spells = []
    settings = {
        'cycles': 20000,
        'play': True,
        'draw': False,
        'deck_size': 60
    }
    settings_provided = set()  # Track which settings were explicitly provided

    current_section = None
    line_num = 0

    for line in lines:
        line_num += 1
        line_upper = line.upper()

        if line_upper == 'LANDS':
            current_section = 'lands'
            continue
        elif line_upper == 'SPELLS':
            current_section = 'spells'
            continue
        elif line_upper == 'SETTINGS':
            current_section = 'settings'
            continue

        if current_section == 'lands':
            try:
                parts = line.split()
                if len(parts) < 3:
                    raise ValueError("Land line must have: <type> <production> <count>")

                land_type = parts[0].lower()
                production_str = parts[1]
                count = int(parts[2])

                if land_type not in LAND_TYPES:
                    raise ValueError(f"Unknown land type: {land_type}")

                production = ManaProduction(production_str)
                land_class = LAND_TYPES[land_type]

                # Validate production using land class validation method if available
                if hasattr(land_class, 'validate_production'):
                    land_class.validate_production(production)
                for _ in range(count):
                    lands.append(land_class(production, 1))

            except (ValueError, IndexError) as e:
                print(f"Error parsing land at line {line_num}: {line}")
                print(f"  {str(e)}")
                print("Run with --help (-h) flag for usage instructions.")
                sys.exit(1)

        elif current_section == 'spells':
            try:
                cost = ManaCost(line)
                spells.append(cost)
            except Exception as e:
                print(f"Error parsing spell at line {line_num}: {line}")
                print(f"  {str(e)}")
                print("Run with --help (-h) flag for usage instructions.")
                sys.exit(1)

        elif current_section == 'settings':
            try:
                parts = line.split()
                if len(parts) < 2:
                    continue

                key = parts[0].lower()
                value_str = parts[1].lower()

                # Handle different setting types
                if key in ['play', 'draw']:
                    # Boolean settings
                    if value_str in ['true', 't', '1', 'yes', 'y']:
                        settings[key] = True
                    elif value_str in ['false', 'f', '0', 'no', 'n']:
                        settings[key] = False
                    else:
                        raise ValueError(f"Invalid boolean value for {key}: {value_str}")
                    settings_provided.add(key)
                elif key in ['cycles', 'deck_size', 'decksize']:
                    # Integer settings
                    value = int(value_str)
                    if key == 'decksize':
                        key = 'deck_size'  # Normalize to deck_size
                    if value <= 0:
                        raise ValueError(f"{key} must be a positive integer")
                    settings[key] = value
                else:
                    # Try to parse as integer for unknown settings
                    settings[key] = int(value_str)
            except Exception as e:
                print(f"Error parsing setting at line {line_num}: {line}")
                print(f"  {str(e)}")
                print("Run with --help (-h) flag for usage instructions.")
                sys.exit(1)

    if not lands:
        print("Error: No lands specified in input file.")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)

    if not spells:
        print("Error: No spells specified in input file.")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)

    # Validate play/draw settings only if both were explicitly provided
    if 'play' in settings_provided and 'draw' in settings_provided:
        if settings['play'] == settings['draw']:
            print("Error: 'play' and 'draw' settings must be opposite values.")
            print("If play=true, draw must be false (or vice versa).")
            print("Run with --help (-h) flag for usage instructions.")
            sys.exit(1)
    elif 'play' in settings_provided:
        # Only play was provided, set draw to opposite
        settings['draw'] = not settings['play']
    elif 'draw' in settings_provided:
        # Only draw was provided, set play to opposite
        settings['play'] = not settings['draw']

    return lands, spells, settings
