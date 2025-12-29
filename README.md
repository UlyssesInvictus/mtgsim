note: yes I used AI for a lot of this, excuse any robot speak + obviously broken code

# MTG Mana Base Simulator

A Monte Carlo simulation tool for analyzing Magic: the Gathering mana bases. This simulator helps you determine the probability of being able to cast specific spells by certain turns, given your deck's land configuration.

## Overview

This tool simulates thousands of games to calculate the likelihood of having the right mana available to cast your target spells. It accounts for various land types, their unique behaviors (entering tapped/untapped), and intelligent land-playing strategies.

## Features

- **Multiple Land Types**: Supports 14 different land types including basics, shocks, duals, fastlands, slowlands, fetchlands, and more
- **Cycler Support**: Cards that convert to basics from the deck when enough lands are in play
- **Choice-Based Lands**: Intelligent color selection for lands that must lock to a single color (multiversal, wilds, fabled, starting town)
- **Mulligan Support**: Automatic mulligan decisions based on hand quality with intelligent card selection
- **Complex Mana Costs**: Handles generic mana, colored mana, and hybrid mana costs
- **Intelligent Play Strategy**: Automatically prioritizes land plays based on spell castability and land types
- **Configurable Settings**: Customize Monte Carlo cycles, play/draw position, and deck size

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

Section headers (`LANDS`, `SPELLS`, `CYCLERS`, `SETTINGS`) are optional. If not provided, use blank lines to separate sections (first paragraph = lands, second = spells, third = cyclers, fourth = settings).

With headers:

```
LANDS
<land_type> <mana_production> <count>
...

SPELLS
<mana_cost>
...

CYCLERS
<mana_production> <cycling_cost> <count>
...

SETTINGS
<setting_name> <value>
...
```

Without headers (paragraph-based):

```
<land_type> <mana_production> <count>
...

<mana_cost>
...

<mana_production> <cycling_cost> <count>
...

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

| Type           | Behavior                                                                                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `basic`        | Produces one color, enters untapped (must specify only 1 color)                                                                                                    |
| `shock`        | Produces specified colors, enters untapped                                                                                                                         |
| `dual`         | Same as shock                                                                                                                                                      |
| `fastland`     | Enters tapped if 3+ lands already in play                                                                                                                          |
| `slowland`     | Enters tapped if 2 or fewer lands in play                                                                                                                          |
| `surveil`      | Always enters tapped                                                                                                                                               |
| `verge`        | Produces 2 colors, but second color only available if there's a shock/dual/surveil in play that produces one of the verge's colors (must specify exactly 2 colors) |
| `wilds`        | Fetches basics from deck, always enters tapped, locks to a single basic type when played (must specify WUBRG)                                                      |
| `tapped`       | Generic tapped land, always enters tapped                                                                                                                          |
| `fetch`        | No restrictions, enters untapped                                                                                                                                   |
| `untapped`     | Generic untapped land, no restrictions, enters untapped                                                                                                            |
| `multiversal`  | Taps for any color but locks to a single choice, enters untapped, deprioritized for late play (must specify WUBRG)                                                 |
| `fabled`       | Fetches basics from deck, locks to a single basic type, enters untapped if 3+ lands in play                                                                        |
| `startingtown` | Taps for any color including colorless but locks to a single choice, enters tapped if turn 4+ (must specify WUBRGC)                                                |

### Cyclers

Cyclers are cards that can be converted to basic lands from the deck once you have enough lands in play. They represent cards like cycling lands or other mana sources that can be transformed into lands.

**Format**: `<mana_production> <cycling_cost> <count>`

- **mana_production**: The single color of basic land this cycler fetches (must be exactly one color: W, U, B, R, or G)
- **cycling_cost**: Positive integer representing the number of lands needed in play before this cycler can be converted
- **count**: Number of these cyclers in the deck

**Behavior**:

- When you have lands in play >= cycling_cost, any eligible cyclers in hand are automatically converted to basics
- Cycling happens at the start of each turn, before deciding which land to play
- The fetched basic enters "tapped" for that turn (can't be used to cast spells the same turn it's cycled as a proxy for the mana spent on cycling, but still allowing you to cycle the "previous" turn)
- Uses the same fetch methodology as wilds/fabled lands (searches deck, removes basic, shuffles)

**Example**:

```
CYCLERS
W 3 4
R 2 2
```

This means:

- 4 cyclers that fetch white basics when you have 3+ lands in play
- 2 cyclers that fetch red basics when you have 2+ lands in play

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
basic W 15
basic U 5
shock WU 4
fastland UR 3
surveil BG 2

SPELLS
1WWW
2UW

CYCLERS
W 3 2

SETTINGS
cycles 10000
play true
deck_size 60
```

## Example Output

```
Running simulation with 29 lands and 2 cycler(s) and 2 target spell(s)...
Monte Carlo cycles: 10000
On the play

Results (probability of casting each spell by turn):
============================================================
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
-

## Heuristics

This simulator makes some simplifying assumptions:

- **Life total is not a concern** (no life payments modeled)
- **The only priority is casting the desired spells** We don't care about any sequencing other than those that let us cast our desired spells as soon as possible

To that end, some heuristics are applied to handle different land types but also pilot "intelligently" with those goals in mind.

### Land Playing Strategy

The simulator uses an intelligent land-playing strategy:

1. **Check for immediate casting**: First checks if playing any land would enable casting a target spell this turn. If a land enables casting, it's played immediately (multiversal lands are checked last in this phase).
2. **Priority-based selection**: If no land enables casting, plays lands in the following priority order:
   - Priority tapped lands (non-slowlands, non-multiversal)
   - Untapped lands (non-multiversal)
   - Slowlands
   - Multiversal lands (deprioritized for late play)
3. **Color optimization**: Among lands of the same priority, chooses the one that shares the most colors with target spells
4. **Random tiebreaking**: If multiple lands are equally good, randomly selects one

#### Choice-Based Land Color Selection

For lands that must lock to a single color (multiversal, wilds, fabled, starting town), the simulator uses an intelligent heuristic:

- **+10 points**: Colors needed for target spells
- **+5 points**: Colors not currently produced by lands in play
- **+3 points**: Colors not available in hand
- **-1 point per land**: Redundancy penalty (existing lands producing that color)
- **Random tiebreak**: Among highest-scoring colors

**Note**: Slowlands are not prioritized for early play since they enter tapped when you need them to enter untapped (turn 1-3).

### Mulligan Strategy

The simulator automatically performs mulligans based on opening hand quality:

#### Mulligan Decision Rules

1. **First two mulligans** (7 and 6 card hands):

   - Mulligan if hand has 1 or fewer lands
   - Mulligan if hand has 6 or more lands

2. **Third mulligan** (5 card hand):

   - Only mulligan if hand has 0 lands or all lands

3. **Fourth mulligan onwards** (4 cards or fewer):
   - Keep any hand

#### Card Selection for Bottoming

After each mulligan, one card per mulligan is placed on the bottom of the deck:

- **Prioritizes non-lands**: Even though non-optimal for real gameplay, this maximizes mana availability for casting spells
- **Random selection**: If only lands remain in hand, selects randomly

## Contributing

This is a simulation tool with room for enhancement. Potential improvements include:

- Better mulligan strategies (considering spell curve, specific spell requirements, color requirements)
- More sophisticated mulligan card selection (keeping lands that match spell colors, keeping early plays)
- More sophisticated land sequencing
- Full fetchland support with proper fetching mechanics (tracking which lands can be fetched, validating fetch targets remain in deck)
- Better fetch heuristics (optimal fetch target selection based on future spell needs, color fixing priorities, and deck composition)

## License

This project is open source and available for educational and personal use.
