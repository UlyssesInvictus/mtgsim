# MTG Mana Base Simulator

A Monte Carlo simulation tool for analyzing Magic: the Gathering mana bases. This simulator helps you determine the probability of being able to cast specific spells by certain turns, given your deck's land configuration.

## Overview

This tool simulates thousands of games to calculate the likelihood of having the right mana available to cast your target spells. It accounts for various land types, their unique behaviors (entering tapped/untapped), and intelligent land-playing strategies.

## Features

- **Multiple Land Types**: Supports 11 different land types including basics, shocks, duals, fastlands, slowlands, fetchlands, and more
- **Complex Mana Costs**: Handles generic mana, colored mana, and hybrid mana costs
- **Intelligent Play Strategy**: Automatically prioritizes land plays based on spell castability and land types
- **Configurable Settings**: Customize Monte Carlo cycles, play/draw position, and deck size
- **Statistical Analysis**: Get turn-by-turn probability breakdowns

## Important Simplifications

This simulator makes several simplifying assumptions:

- **Deck thinning does not occur** (deck size remains constant, apart from draws)
- **Life total is not a concern** (no life payments modeled)
- **Fetch lands do not check** that fetchable lands remain in the deck
- **Fetch lands do not narrow** the user's choice after fetching down to a single type
- **All lands in hand** are assumed to be distinct playable options

## Installation

No installation required! Just ensure you have Python 3.6+ installed.

## Usage

```bash
python mtg_sim.py [input_file]
```

If no input file is specified, it defaults to `inputs.txt`.

### Getting Help

```bash
python mtg_sim.py --help
```

## Input File Format

### Basic Structure

```
LANDS
<land_type> <mana_production> <count>
...

SPELLS
<mana_cost>
...

SETTINGS
<setting_name> <value>
...
```

### Mana Production Format

- **Single color**: `W`, `U`, `B`, `R`, `G`, `C` (white, blue, black, red, green, colorless)
- **Multiple colors (AND)**: `WU` (produces white AND blue)
- **Choice of colors (OR)**: `W/U` (produces white OR blue)
- **Complex patterns**: `{R/U}U` (produces red OR blue, AND blue)

### Mana Cost Format

- **Generic mana**: `2`, `3`, etc. (can be paid with any color)
- **Colored mana**: `W`, `U`, `B`, `R`, `G`
- **Examples**:
  - `2G` → 2 generic + 1 green
  - `{1}UB` → 1 generic + 1 blue + 1 black
  - `{3/R}{3/W}` → (3 generic OR 1 red) AND (3 generic OR 1 white)

### Land Types

| Type       | Behavior                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `basic`    | Produces one color, enters untapped (must specify only 1 color)                                                                                                    |
| `shock`    | Produces specified colors, enters untapped                                                                                                                         |
| `dual`     | Same as shock                                                                                                                                                      |
| `fastland` | Enters tapped if 3+ lands already in play                                                                                                                          |
| `slowland` | Enters tapped if 2 or fewer lands in play                                                                                                                          |
| `surveil`  | Always enters tapped                                                                                                                                               |
| `verge`    | Produces 2 colors, but second color only available if there's a shock/dual/surveil in play that produces one of the verge's colors (must specify exactly 2 colors) |
| `wilds`    | Produces WUBRG, always enters tapped (must specify WUBRG)                                                                                                          |
| `tapped`   | Generic tapped land, always enters tapped                                                                                                                          |
| `fetch`    | No restrictions, enters untapped                                                                                                                                   |
| `untapped` | Generic untapped land, no restrictions, enters untapped                                                                                                            |

### Settings

| Setting                   | Type    | Default | Description                                           |
| ------------------------- | ------- | ------- | ----------------------------------------------------- |
| `cycles`                  | integer | 20000   | Number of Monte Carlo iterations                      |
| `play`                    | boolean | true    | Whether you're on the play                            |
| `draw`                    | boolean | false   | Whether you're on the draw (must be opposite of play) |
| `deck_size` or `decksize` | integer | 60      | Total deck size                                       |

**Note**: For boolean settings, accepted values are: `true`/`false`, `t`/`f`, `yes`/`no`, `y`/`n`, `1`/`0`

## Example Input File

```
LANDS
basic W 20
shock WU 4
fastland UR 3
surveil BG 2

SPELLS
1WWW
2UW

SETTINGS
cycles 10000
play true
deck_size 60
```

## Example Output

```
Running simulation with 29 lands and 2 target spell(s)...
Monte Carlo cycles: 10000
On the play

Results (probability of casting target spell by turn):
--------------------------------------------------
Turn  1:   0.00%
Turn  2:  56.23%
Turn  3:  39.45%
Turn  4:   4.32%
Turn  5:   0.00%
Turn  6:   0.00%
Turn  7:   0.00%
Turn  8:   0.00%
Turn  9:   0.00%
Turn 10:   0.00%
--------------------------------------------------
Total:   100.00% (by turn 10)
```

## Project Structure

```
mtg_sim.py          # Main executable (wrapper)
mtg_classes.py      # Land classes, mana production, and mana costs
mtg_parser.py       # Input file parsing and validation
mtg_simulation.py   # Game state and Monte Carlo simulation logic
test_mtg_mana_sim.py # Comprehensive test suite
inputs.txt          # Example input file
README.md           # This file
```

## Testing

Run the comprehensive test suite:

```bash
python test_mtg_mana_sim.py
```

The test suite includes:

- **Class Tests**: Testing individual classes and their behaviors
- **Input Validation Tests**: Testing file parsing and validation
- **Mana Consumption Tests**: Testing spell casting and mana availability

## Land Playing Strategy

The simulator uses an intelligent land-playing strategy:

1. **Check for immediate casting**: First checks if playing any land would enable casting a target spell this turn
2. **Prioritize tapped lands**: Prioritizes playing lands that enter tapped (except slowlands) to save untapped lands for future turns
3. **Color optimization**: Among lands of the same priority, chooses the one that shares the most colors with target spells
4. **Random tiebreaking**: If multiple lands are equally good, randomly selects one

**Note**: Slowlands are not prioritized for early play since they enter tapped when you need them to enter untapped (turn 1-3).

## Contributing

This is a simulation tool with room for enhancement. Potential improvements include:

- Mulligan strategy simulation
- More sophisticated land sequencing
- Deck thinning simulation for fetch lands

## License

This project is open source and available for educational and personal use.

## Acknowledgments

Built as a tool for Magic: the Gathering players to optimize their mana bases through statistical analysis.
