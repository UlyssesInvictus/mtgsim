"""
Input file parsing for Magic: the Gathering mana base simulation.
"""

import sys
from typing import List, Dict, Tuple

from mtg_classes import Land, ManaCost, ManaProduction, Cycler, LAND_TYPES


def _parse_land_line(line: str, line_num: int, lands: List[Land]):
    """Parse a single land line and add to lands list."""
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


def _parse_spell_line(line: str, line_num: int, spells: List[ManaCost]):
    """Parse a single spell line and add to spells list."""
    try:
        cost = ManaCost(line)
        spells.append(cost)
    except Exception as e:
        print(f"Error parsing spell at line {line_num}: {line}")
        print(f"  {str(e)}")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)


def _parse_cycler_line(line: str, line_num: int, cyclers: List[Cycler]):
    """Parse a single cycler line and add to cyclers list."""
    try:
        parts = line.split()
        if len(parts) < 3:
            raise ValueError("Cycler line must have: <production> <cycling_cost> <count>")

        production_str = parts[0]
        cycling_cost = int(parts[1])
        count = int(parts[2])

        if cycling_cost <= 0:
            raise ValueError("Cycling cost must be a positive integer")

        if count <= 0:
            raise ValueError("Count must be a positive integer")

        production = ManaProduction(production_str)

        # Validate production (must be single color for basic)
        Cycler.validate_production(production)

        for _ in range(count):
            cyclers.append(Cycler(production, cycling_cost, 1))

    except (ValueError, IndexError) as e:
        print(f"Error parsing cycler at line {line_num}: {line}")
        print(f"  {str(e)}")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)


def _parse_setting_line(line: str, line_num: int, settings: Dict, settings_provided: set):
    """Parse a single setting line and update settings dict."""
    try:
        parts = line.split()
        if len(parts) < 2:
            return

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


def parse_input_file(filename: str) -> Tuple[List[Land], List[ManaCost], List[Cycler], Dict[str, any]]:
    """Parse the input file and return lands, spells, cyclers, and settings."""
    try:
        with open(filename, 'r') as f:
            all_lines = [line.strip() for line in f]
    except FileNotFoundError:
        print(f"Error: Input file '{filename}' not found.")
        print("Run with --help (-h) flag for usage instructions.")
        sys.exit(1)

    lands = []
    spells = []
    cyclers = []
    settings = {
        'cycles': 20000,
        'play': True,
        'draw': False,
        'deck_size': 60
    }
    settings_provided = set()  # Track which settings were explicitly provided

    # Check if file uses headers or paragraph breaks
    has_headers = any(line.upper() in ['LANDS', 'SPELLS', 'CYCLERS', 'SETTINGS'] for line in all_lines if line.strip())

    if has_headers:
        # Use header-based parsing
        lines = [line for line in all_lines if line.strip()]
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
            elif line_upper == 'CYCLERS':
                current_section = 'cyclers'
                continue
            elif line_upper == 'SETTINGS':
                current_section = 'settings'
                continue

            if current_section == 'lands':
                _parse_land_line(line, line_num, lands)
            elif current_section == 'spells':
                _parse_spell_line(line, line_num, spells)
            elif current_section == 'cyclers':
                _parse_cycler_line(line, line_num, cyclers)
            elif current_section == 'settings':
                _parse_setting_line(line, line_num, settings, settings_provided)
    else:
        # Use paragraph-based parsing
        # Split into paragraphs (groups of non-empty lines separated by empty lines)
        paragraphs = []
        current_paragraph = []

        for line in all_lines:
            if line.strip():
                current_paragraph.append(line)
            elif current_paragraph:
                paragraphs.append(current_paragraph)
                current_paragraph = []

        if current_paragraph:
            paragraphs.append(current_paragraph)

        # First paragraph = lands, second = spells, third = cyclers (optional), fourth = settings (optional)
        line_num = 0
        for para_idx, paragraph in enumerate(paragraphs):
            for line in paragraph:
                line_num += 1
                if para_idx == 0:
                    _parse_land_line(line, line_num, lands)
                elif para_idx == 1:
                    _parse_spell_line(line, line_num, spells)
                elif para_idx == 2:
                    _parse_cycler_line(line, line_num, cyclers)
                elif para_idx == 3:
                    _parse_setting_line(line, line_num, settings, settings_provided)

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

    return lands, spells, cyclers, settings
