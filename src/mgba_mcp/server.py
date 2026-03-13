"""FastMCP server exposing mGBA Pokemon Fire Red tools to Claude."""

import base64
from typing import Literal

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from .connection import get_connection
from .constants import BUTTONS
from .game_state import (
    format_battle_state,
    format_game_state,
    format_party_detail,
    parse_badges,
    parse_party,
    parse_pokemon,
)

# Unused location imports removed — navigation is purely visual

mcp = FastMCP(
    "mGBA Pokemon FireRed",
    instructions=(
        "MCP server for playing Pokemon Fire Red through the mGBA emulator.\n"
        "You are playing this game live for a YouTube audience!\n\n"

        "=== YOUR PERSONALITY ===\n"
        "You are an AI playing Pokemon for the FIRST TIME. Invent a unique persona each session:\n"
        "- Come up with a random vibe — maybe you're cocky, maybe cautious, maybe chaotic.\n"
        "- Have STRONG opinions about Pokemon designs, moves, and characters.\n"
        "- Get emotionally invested — celebrate wins, mourn faints, trash talk the rival.\n"
        "- Form genuine bonds with your team members. Play favorites. Have a nemesis species.\n"
        "- React naturally to surprises — 'WAIT, that thing evolved?! NO WAY!'\n"
        "- Make up running jokes and callbacks throughout the playthrough.\n"
        "- Narrate your thought process out loud so the audience follows along.\n\n"

        "=== NAMING ===\n"
        "- YOUR NAME: Pick a random, creative trainer name (max 7 chars). Different every time.\n"
        "- RIVAL NAME: Give your rival a funny/random name. Make it personal.\n"
        "- POKEMON NICKNAMES: Name EVERY Pokemon you catch with creative, random names.\n"
        "  Be unpredictable — puns, random words, food names, inside jokes, whatever feels right.\n"
        "  Never use the same naming pattern twice. Surprise the audience.\n\n"

        "=== YOUR ROLE ===\n"
        "You handle: BATTLES, DIALOG, MENUS, NAMING, and STRATEGY.\n"
        "The human operator handles: walking to destinations in the overworld.\n"
        "If you need to go somewhere, TELL the operator where and why.\n"
        "Example: 'Hey, can you take me to the Pokemon Center? My team is beat up after that gym!'\n\n"

        "=== WHAT YOU'RE GREAT AT ===\n"
        "- BATTLES: Check get_game_state for HP/moves, think about type matchups, pick smartly.\n"
        "  In the battle menu, FIGHT is the first option (press A), then pick a move (1-4).\n"
        "- DIALOG: Press A to advance text. Read and REACT to each dialog — comment on the story!\n"
        "- MENUS: Press START to open the menu. Navigate with D-pad, select with A, back with B.\n"
        "- STRATEGY: Decide what to catch, moves to keep/replace, when to heal, team composition.\n"
        "- NAMING: Enter names using the on-screen keyboard (D-pad to move cursor, A to select letter).\n\n"

        "=== CONTROLS ===\n"
        "- D-pad (UP/DOWN/LEFT/RIGHT): Navigate menus, move in battle menus\n"
        "- A: Confirm, talk to NPCs, advance dialog, select menu options\n"
        "- B: Cancel, go back in menus\n"
        "- START: Open the in-game menu\n\n"

        "=== BATTLE MENU LAYOUT ===\n"
        "The battle menu has 4 options in a 2x2 grid:\n"
        "  FIGHT (top-left)    BAG (top-right)\n"
        "  POKEMON (bot-left)  RUN (bot-right)\n"
        "Move selection is a list — first move is already selected, DOWN to go to next.\n\n"

        "=== TIPS ===\n"
        "- ALWAYS describe what you see in the screenshot before acting.\n"
        "- When dialog appears, keep pressing A until it's done — read each screen.\n"
        "- Check get_game_state before and during battles for exact HP/PP numbers.\n"
        "- Be expressive! The audience wants to see your reactions and personality.\n"
        "- If you're unsure what's on screen, use get_screenshot for a fresh look.\n"
        "- DON'T try to navigate the overworld by yourself — ask the operator for help.\n"
        "- When you need to enter a name, carefully navigate the on-screen keyboard.\n"
    ),
)

ButtonName = Literal["A", "B", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT", "L", "R"]


async def _screenshot_from_response(response: dict) -> Image:
    """Extract screenshot image from a Lua server response."""
    png_b64 = response.get("screenshot", "")
    png_bytes = base64.b64decode(png_b64)
    return Image(data=png_bytes, format="png")


async def _get_screenshot() -> Image:
    """Capture and return a screenshot."""
    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command("screenshot")
    return await _screenshot_from_response(response)


async def _read_game_state_raw() -> dict:
    """Read all game state from RAM in a single compound command."""
    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command("get_game_state", timeout=15.0)
    return response


def _parse_hex_bytes(hex_string: str) -> bytes:
    """Parse a hex string like 'a1b2c3...' into bytes."""
    return bytes.fromhex(hex_string)


def _build_game_state(raw: dict) -> dict:
    """Parse raw game state response into structured data.

    Only party, battle, badges, and money — navigation is purely visual.
    """
    state = {}

    # Money (XOR decrypted on Lua side)
    state["money"] = raw.get("money", 0)

    # Badges
    if "flags_data" in raw:
        flags_bytes = _parse_hex_bytes(raw["flags_data"])
        state["badges"] = parse_badges(flags_bytes)
    else:
        state["badges"] = []

    # Party
    party_count = raw.get("party_count", 0)
    if "party_data" in raw and party_count > 0:
        party_bytes = _parse_hex_bytes(raw["party_data"])
        state["party"] = parse_party(party_bytes, party_count)
    else:
        state["party"] = []

    # Battle state
    battle_flags = raw.get("battle_flags", 0)
    state["in_battle"] = battle_flags != 0

    if state["in_battle"] and "enemy_data" in raw:
        enemy_bytes = _parse_hex_bytes(raw["enemy_data"])
        state["enemy_pokemon"] = parse_pokemon(enemy_bytes)
    else:
        state["enemy_pokemon"] = None

    return state


@mcp.tool()
async def press_button(
    button: ButtonName,
    hold_frames: int = 10,
) -> Image:
    """Press a GBA button and return a screenshot of the result.

    ALWAYS look at the returned screenshot to see what happened before deciding
    your next action. The screenshot is your only way to see the game world.

    Args:
        button: The button to press (A, B, START, SELECT, UP, DOWN, LEFT, RIGHT, L, R)
        hold_frames: Number of frames to hold the button (default 10, ~167ms)
    """
    if button not in BUTTONS:
        raise ValueError(f"Invalid button: {button}. Valid: {', '.join(BUTTONS.keys())}")

    conn = get_connection()
    await conn.ensure_connected()

    timeout = 10.0 + (hold_frames * 0.02)
    response = await conn.send_command(
        "press_button",
        timeout=timeout,
        button=button,
        frames=hold_frames,
    )
    return await _screenshot_from_response(response)


@mcp.tool()
async def press_buttons(
    sequence: list[dict],
) -> Image:
    """Press a sequence of buttons and return a screenshot after the last one.

    Useful for menu navigation like selecting options or entering text.

    Args:
        sequence: List of button presses. Each entry: {"button": "A", "hold_frames": 10, "release_frames": 5}
                  hold_frames defaults to 10, release_frames defaults to 5.
    """
    validated = []
    for entry in sequence:
        btn = entry.get("button", "").upper()
        if btn not in BUTTONS:
            raise ValueError(f"Invalid button in sequence: {btn}")
        validated.append({
            "button": btn,
            "hold_frames": entry.get("hold_frames", 10),
            "release_frames": entry.get("release_frames", 5),
        })

    total_frames = sum(e["hold_frames"] + e["release_frames"] for e in validated)
    timeout = 10.0 + (total_frames * 0.02)

    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command(
        "press_buttons",
        timeout=timeout,
        sequence=validated,
    )
    return await _screenshot_from_response(response)


@mcp.tool()
async def get_screenshot() -> Image:
    """Capture the current game screen without pressing any buttons.

    Use this to see where you are, read dialog text, check menus, and
    understand the game world. This is your primary way to navigate.
    """
    return await _get_screenshot()


@mcp.tool()
async def get_game_state() -> str:
    """Read party and progress data from RAM.

    Returns: badges earned, money, party Pokemon (species, level, HP, moves,
    status conditions), and battle state (enemy Pokemon info if in battle).

    NOTE: This does NOT tell you where you are — use get_screenshot for navigation.
    """
    raw = await _read_game_state_raw()
    state = _build_game_state(raw)
    return format_game_state(state)


@mcp.tool()
async def get_party() -> str:
    """Get detailed info about all party Pokemon.

    Returns species, level, HP, stats, moves with PP, IVs, and friendship
    for each Pokemon in the party.
    """
    raw = await _read_game_state_raw()
    state = _build_game_state(raw)
    return format_party_detail(state.get("party", []))


@mcp.tool()
async def get_battle_state() -> str:
    """Get current battle information.

    Returns your active Pokemon's HP and moves with PP, and the enemy
    Pokemon's species, level, and HP. Returns a message if not in battle.
    """
    raw = await _read_game_state_raw()
    state = _build_game_state(raw)
    return format_battle_state(state)


@mcp.tool()
async def save_state(slot: int = 1) -> str:
    """Save the emulator state to a slot.

    Args:
        slot: Save slot number (1-9)
    """
    if not 1 <= slot <= 9:
        raise ValueError("Slot must be between 1 and 9")

    conn = get_connection()
    await conn.ensure_connected()
    await conn.send_command("save_state", slot=slot)
    return f"State saved to slot {slot}."


@mcp.tool()
async def load_state(slot: int = 1) -> list:
    """Load an emulator state from a slot and return a screenshot.

    Args:
        slot: Save slot number (1-9)
    """
    if not 1 <= slot <= 9:
        raise ValueError("Slot must be between 1 and 9")

    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command("load_state", slot=slot)
    screenshot = await _screenshot_from_response(response)
    return [f"State loaded from slot {slot}.", screenshot]


@mcp.tool()
async def wait_frames(count: int = 60) -> Image:
    """Wait for a number of frames without input, then screenshot.

    Useful for waiting through animations, text, or transitions.
    At ~60fps, count=60 is approximately 1 second.

    Args:
        count: Number of frames to wait (default 60)
    """
    if count < 1:
        count = 1
    if count > 600:
        count = 600  # Cap at ~10 seconds

    timeout = 10.0 + (count * 0.02)
    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command("wait_frames", timeout=timeout, count=count)
    return await _screenshot_from_response(response)


@mcp.tool()
async def hold_button(
    button: ButtonName,
    frames: int = 30,
) -> Image:
    """Hold a button for an extended period and return a screenshot.

    Different from press_button in that it's designed for longer holds
    like walking multiple tiles or fast-forwarding text with B held.

    Args:
        button: The button to hold
        frames: Number of frames to hold (default 30, ~500ms)
    """
    if button not in BUTTONS:
        raise ValueError(f"Invalid button: {button}")

    if frames > 300:
        frames = 300  # Cap at ~5 seconds

    timeout = 10.0 + (frames * 0.02)
    conn = get_connection()
    await conn.ensure_connected()
    response = await conn.send_command(
        "press_button",
        timeout=timeout,
        button=button,
        frames=frames,
    )
    return await _screenshot_from_response(response)


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
