# PokeMCP - AI Plays Pokemon Fire Red

An MCP server that lets Claude play Pokemon Fire Red through the mGBA emulator. Built for YouTube content — Claude has its own personality, names its Pokemon, trash-talks its rival, and reacts to everything happening in the game.

## How It Works

```
Claude <-> FastMCP Server (Python) <-> TCP Socket <-> Lua Script (inside mGBA)
```

**Split gameplay model:**
- **Claude handles:** Battles, dialog, menus, naming (trainer/rival/Pokemon), team strategy
- **Human operator handles:** Overworld navigation (walking to destinations)
- **Navigation is purely visual** — Claude reads screenshots to understand the game world
- **RAM reading** is used only for party Pokemon stats, battle data, badges, and money

## Prerequisites

- **mGBA** v0.10+ — [mgba.io](https://mgba.io)
- **Python** 3.12+
- **uv** — `pip install uv`
- **Pokemon Fire Red ROM** — US v1.0 (game code: BPRE)

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Load the Lua script in mGBA

1. Open mGBA and load your Pokemon Fire Red ROM
2. Go to **Tools > Scripting**
3. **File > Load Script** → select `lua/mgba_server.lua`
4. Console should show: `MCP Server listening on 127.0.0.1:5555`

### 3. Configure Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pokemon-firered": {
      "command": "C:\\Users\\YOUR_USER\\AppData\\Roaming\\Python\\Python312\\Scripts\\uv.exe",
      "args": ["--directory", "C:/path/to/mGba MCP", "run", "mgba-mcp"]
    }
  }
}
```

> **Note:** Use the full path to `uv.exe` — Claude Desktop may not have it in PATH. Find it with `python -c "import shutil; print(shutil.which('uv'))"`.

### 4. Play!

Start a conversation with Claude. It will invent a personality, pick a trainer name, and start playing.

## Available Tools

| Tool | Description |
|------|-------------|
| `press_button` | Press a GBA button and get a screenshot |
| `press_buttons` | Press a sequence of buttons with timing |
| `get_screenshot` | See the current game screen |
| `get_game_state` | Read badges, money, party Pokemon, battle state from RAM |
| `get_party` | Detailed party info (stats, moves, IVs) |
| `get_battle_state` | Battle details (your/enemy Pokemon, HP, moves, PP) |
| `save_state` | Save emulator state (slots 1-9) |
| `load_state` | Load emulator state |
| `wait_frames` | Wait through animations/transitions |
| `hold_button` | Hold a button for extended walking/scrolling |

## What Claude Reads from RAM

- **Party Pokemon** — Species, level, HP, moves with PP, stats, IVs, status conditions
- **Badges** — Which gym badges have been earned
- **Money** — Current funds (XOR-decrypted)
- **Battle state** — Enemy Pokemon species, level, HP, moves

Navigation and dialog are handled **visually** through screenshots only.

## Claude's Personality

Each session, Claude invents a unique persona:
- Picks its own trainer name and rival name
- Names every Pokemon with creative nicknames
- Has strong opinions about Pokemon, moves, and characters
- Gets emotionally invested — celebrates wins, mourns faints
- Narrates its thought process for the audience
- All commentary in Spanish for YouTube content

## Project Structure

```
├── pyproject.toml
├── src/mgba_mcp/
│   ├── server.py        # FastMCP tools + personality instructions
│   ├── connection.py    # TCP client for mGBA communication
│   ├── game_state.py    # Pokemon Fire Red RAM parser
│   └── constants.py     # Memory addresses and lookup tables
├── lua/
│   └── mgba_server.lua  # Lua TCP server loaded into mGBA
└── data/
    ├── pokemon_species.json
    ├── pokemon_moves.json
    └── map_names.json
```

## Tips for YouTube Recording

- **Save states are your friend** — save before gyms, important battles, or risky catches
- **Let Claude fail** — mistakes and reactions are entertaining content
- **Navigate for Claude** — walk to destinations, let Claude handle the rest
- **Nudge when stuck** — tell Claude "we're at the Pokemon Center" or "there's a trainer ahead"
- **The game is in English but Claude comments in Spanish** — great for bilingual content

## Important Notes

- ROM must be US v1.0 (BPRE) for memory addresses to work
- Load the Lua script in mGBA **before** starting Claude Desktop
- mGBA must stay open while playing
- The Lua script auto-detects the ROM and warns if it doesn't match

## License

MIT
