# PokeMCP - mGBA MCP Server for Pokemon Fire Red

An MCP (Model Context Protocol) server that lets AI assistants play Pokemon Fire Red through the mGBA emulator. The server provides tools to see the game screen, press buttons, and read game state directly from RAM.

## Architecture

```
AI Assistant <-> FastMCP Server (Python) <-> TCP Socket <-> Lua Script (inside mGBA)
```

- A **Lua script** runs inside mGBA as a TCP server on `localhost:5555`
- The **Python MCP server** connects as a TCP client and exposes game controls as MCP tools
- Communication uses newline-delimited JSON over TCP

## Prerequisites

- **mGBA** v0.10+ — Download from [mgba.io](https://mgba.io)
- **Python** 3.12+
- **uv** — `pip install uv`
- **Pokemon Fire Red ROM** — US v1.0 (game code: BPRE). Memory addresses are version-specific.

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Load the Lua script in mGBA

1. Open mGBA and load your Pokemon Fire Red ROM
2. Go to **Tools > Scripting**
3. In the scripting window: **File > Load Script**
4. Select `lua/mgba_server.lua` from this project
5. The scripting console should show: `MCP Server listening on 127.0.0.1:5555`

### 3. Configure your MCP client

Add to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "pokemon-firered": {
      "command": "uv",
      "args": ["--directory", "C:/path/to/mGba MCP", "run", "mgba-mcp"]
    }
  }
}
```

### 4. Play!

Start a conversation and the AI can use the tools to play the game.

## Available Tools

| Tool | Description |
|------|-------------|
| `press_button` | Press a GBA button (A, B, Start, Select, Up, Down, Left, Right, L, R) and get a screenshot |
| `press_buttons` | Press a sequence of buttons with timing control |
| `get_screenshot` | Capture the current game screen |
| `get_game_state` | Read full state from RAM: location, badges, money, party, battle status |
| `get_party` | Detailed party Pokemon info (stats, moves, IVs, friendship) |
| `get_battle_state` | Current battle info (your/enemy Pokemon, HP, moves, PP) |
| `save_state` | Save emulator state to a slot (1-9) |
| `load_state` | Load emulator state from a slot |
| `wait_frames` | Advance N frames without input (for animations/transitions) |
| `hold_button` | Hold a button for an extended period (walking, text scrolling) |

## Game State from RAM

The server reads Pokemon Fire Red's RAM to extract:

- **Player location** — Map name, X/Y coordinates
- **Party Pokemon** — Species, level, HP, moves with PP, stats, IVs
- **Badges** — Which gym badges have been earned
- **Money** — Current funds (XOR-decrypted)
- **Battle state** — Whether in battle, enemy Pokemon info

This gives the AI full situational awareness beyond just the screenshot.

## Project Structure

```
├── pyproject.toml          # Python project config
├── src/mgba_mcp/
│   ├── server.py           # FastMCP tool definitions
│   ├── connection.py       # TCP client for mGBA communication
│   ├── game_state.py       # Pokemon Fire Red RAM parser
│   └── constants.py        # Memory addresses and lookup tables
├── lua/
│   └── mgba_server.lua     # Lua TCP server for mGBA
└── data/
    ├── pokemon_species.json # Species ID -> name (Gen I-III)
    ├── pokemon_moves.json   # Move ID -> name/type/PP
    └── map_names.json       # Map bank.number -> location name
```

## Important Notes

- The ROM **must** be US v1.0 (BPRE) for memory addresses to be correct
- The Lua script must be loaded in mGBA **before** the MCP server tries to connect
- mGBA must remain open with the game running while using the tools
- Save states are emulator save states, not in-game saves
- The Lua script will warn in the console if the ROM doesn't match BPRE

## License

MIT
