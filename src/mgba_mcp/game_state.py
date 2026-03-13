"""Pokemon Fire Red RAM parser and game state extraction."""

import json
import struct
from pathlib import Path

from .constants import (
    BADGE_FLAG_BASE,
    BADGE_NAMES,
    GEN3_CHARSET,
    NUM_BADGES,
    POKEMON_DATA_SIZE,
    SUBSTRUCTURE_ORDER,
    decode_gen3_string,
)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

_species_names: dict[int, str] | None = None
_move_names: dict[int, dict] | None = None
_map_names: dict[str, str] | None = None


def _load_species() -> dict[int, str]:
    global _species_names
    if _species_names is None:
        with open(DATA_DIR / "pokemon_species.json") as f:
            raw = json.load(f)
        _species_names = {int(k): v for k, v in raw.items()}
    return _species_names


def _load_moves() -> dict[int, dict]:
    global _move_names
    if _move_names is None:
        with open(DATA_DIR / "pokemon_moves.json") as f:
            raw = json.load(f)
        _move_names = {int(k): v for k, v in raw.items()}
    return _move_names


def _load_maps() -> dict[str, str]:
    global _map_names
    if _map_names is None:
        with open(DATA_DIR / "map_names.json") as f:
            _map_names = json.load(f)
    return _map_names


def get_species_name(species_id: int) -> str:
    names = _load_species()
    return names.get(species_id, f"Unknown({species_id})")


def get_move_info(move_id: int) -> dict:
    moves = _load_moves()
    return moves.get(move_id, {"name": f"Unknown({move_id})", "type": "???", "pp": 0})


def get_map_name(bank: int, number: int) -> str:
    maps = _load_maps()
    return maps.get(f"{bank}.{number}", f"Unknown Map ({bank}.{number})")


def decrypt_substructures(
    encrypted_data: bytes, personality_value: int, ot_id: int
) -> tuple[bytes, bytes, bytes, bytes]:
    """Decrypt and reorder the 4 Pokemon substructures.

    Args:
        encrypted_data: 48 bytes of encrypted substructure data (bytes 32-79)
        personality_value: The Pokemon's personality value
        ot_id: The Original Trainer ID (full 32-bit)

    Returns:
        Tuple of (growth, attacks, evs, misc) each 12 bytes, in canonical order.
    """
    key = personality_value ^ ot_id

    # Decrypt by XORing each 4-byte word
    decrypted = bytearray(48)
    for i in range(0, 48, 4):
        word = struct.unpack_from("<I", encrypted_data, i)[0]
        word ^= key
        struct.pack_into("<I", decrypted, i, word)

    # Split into 4 blocks of 12 bytes
    blocks = [bytes(decrypted[i : i + 12]) for i in range(0, 48, 12)]

    # Reorder based on personality value
    order = SUBSTRUCTURE_ORDER[personality_value % 24]
    # order tells us which substructure is at each position
    # order[0] = index of block that contains Growth data
    # We need to find which position each substructure is at
    result = [b""] * 4
    for position, substruct_type in enumerate(order):
        result[substruct_type] = blocks[position]

    return (result[0], result[1], result[2], result[3])


def parse_growth_substructure(data: bytes) -> dict:
    """Parse the Growth substructure (12 bytes)."""
    species = struct.unpack_from("<H", data, 0)[0]
    item = struct.unpack_from("<H", data, 2)[0]
    experience = struct.unpack_from("<I", data, 4)[0]
    pp_bonuses = data[8]
    friendship = data[9]
    return {
        "species_id": species,
        "species": get_species_name(species),
        "held_item": item,
        "experience": experience,
        "pp_bonuses": pp_bonuses,
        "friendship": friendship,
    }


def parse_attacks_substructure(data: bytes) -> list[dict]:
    """Parse the Attacks substructure (12 bytes)."""
    moves = []
    for i in range(4):
        move_id = struct.unpack_from("<H", data, i * 2)[0]
        if move_id == 0:
            continue
        pp = data[8 + i]
        move_info = get_move_info(move_id)
        moves.append({
            "id": move_id,
            "name": move_info["name"],
            "type": move_info["type"],
            "pp": pp,
            "max_pp": move_info["pp"],
        })
    return moves


def parse_evs_substructure(data: bytes) -> dict:
    """Parse the EVs/Condition substructure (12 bytes)."""
    return {
        "hp_ev": data[0],
        "atk_ev": data[1],
        "def_ev": data[2],
        "spd_ev": data[3],
        "spatk_ev": data[4],
        "spdef_ev": data[5],
        "coolness": data[6],
        "beauty": data[7],
        "cuteness": data[8],
        "smartness": data[9],
        "toughness": data[10],
        "feel": data[11],
    }


def parse_misc_substructure(data: bytes) -> dict:
    """Parse the Misc substructure (12 bytes)."""
    pokerus = data[0]
    met_location = data[1]
    origins = struct.unpack_from("<H", data, 2)[0]
    iv_egg_ability = struct.unpack_from("<I", data, 4)[0]

    # Extract IVs (5 bits each, packed into 30 bits)
    hp_iv = iv_egg_ability & 0x1F
    atk_iv = (iv_egg_ability >> 5) & 0x1F
    def_iv = (iv_egg_ability >> 10) & 0x1F
    spd_iv = (iv_egg_ability >> 15) & 0x1F
    spatk_iv = (iv_egg_ability >> 20) & 0x1F
    spdef_iv = (iv_egg_ability >> 25) & 0x1F
    is_egg = bool((iv_egg_ability >> 30) & 1)
    ability_bit = (iv_egg_ability >> 31) & 1

    return {
        "pokerus": pokerus,
        "met_location": met_location,
        "hp_iv": hp_iv,
        "atk_iv": atk_iv,
        "def_iv": def_iv,
        "spd_iv": spd_iv,
        "spatk_iv": spatk_iv,
        "spdef_iv": spdef_iv,
        "is_egg": is_egg,
        "ability_slot": ability_bit,
    }


def parse_pokemon(data: bytes) -> dict | None:
    """Parse a single 100-byte Pokemon data structure.

    Returns None if the slot is empty.
    """
    if len(data) < POKEMON_DATA_SIZE:
        return None

    personality_value = struct.unpack_from("<I", data, 0)[0]
    ot_id = struct.unpack_from("<I", data, 4)[0]

    # Check for empty slot
    if personality_value == 0 and ot_id == 0:
        return None

    nickname = decode_gen3_string(data[8:18])
    ot_name = decode_gen3_string(data[20:27])

    # Decrypt substructures (bytes 32-79)
    growth_data, attacks_data, evs_data, misc_data = decrypt_substructures(
        data[32:80], personality_value, ot_id
    )

    growth = parse_growth_substructure(growth_data)
    moves = parse_attacks_substructure(attacks_data)
    evs = parse_evs_substructure(evs_data)
    misc = parse_misc_substructure(misc_data)

    # Battle stats (bytes 80-99, unencrypted)
    status_condition = struct.unpack_from("<I", data, 80)[0]
    level = data[84]
    current_hp = struct.unpack_from("<H", data, 86)[0]
    max_hp = struct.unpack_from("<H", data, 88)[0]
    attack = struct.unpack_from("<H", data, 90)[0]
    defense = struct.unpack_from("<H", data, 92)[0]
    speed = struct.unpack_from("<H", data, 94)[0]
    sp_atk = struct.unpack_from("<H", data, 96)[0]
    sp_def = struct.unpack_from("<H", data, 98)[0]

    return {
        "personality_value": personality_value,
        "nickname": nickname,
        "ot_name": ot_name,
        "species_id": growth["species_id"],
        "species": growth["species"],
        "held_item": growth["held_item"],
        "experience": growth["experience"],
        "level": level,
        "current_hp": current_hp,
        "max_hp": max_hp,
        "attack": attack,
        "defense": defense,
        "speed": speed,
        "sp_atk": sp_atk,
        "sp_def": sp_def,
        "status_condition": status_condition,
        "moves": moves,
        "evs": evs,
        "ivs": {
            "hp": misc["hp_iv"],
            "atk": misc["atk_iv"],
            "def": misc["def_iv"],
            "spd": misc["spd_iv"],
            "spatk": misc["spatk_iv"],
            "spdef": misc["spdef_iv"],
        },
        "friendship": growth["friendship"],
        "is_egg": misc["is_egg"],
    }


def parse_party(raw_data: bytes, count: int) -> list[dict]:
    """Parse party Pokemon data.

    Args:
        raw_data: Raw bytes containing all party Pokemon (count * 100 bytes)
        count: Number of Pokemon in the party (1-6)
    """
    party = []
    for i in range(min(count, 6)):
        offset = i * POKEMON_DATA_SIZE
        pokemon_data = raw_data[offset : offset + POKEMON_DATA_SIZE]
        pokemon = parse_pokemon(pokemon_data)
        if pokemon:
            party.append(pokemon)
    return party


def parse_badges(flags_data: bytes) -> list[str]:
    """Parse badge flags from the save block flags array.

    Args:
        flags_data: Raw bytes of the flags array region
    """
    badges = []
    for i in range(NUM_BADGES):
        flag_index = BADGE_FLAG_BASE + i
        byte_offset = flag_index // 8
        bit_offset = flag_index % 8
        if byte_offset < len(flags_data):
            if flags_data[byte_offset] & (1 << bit_offset):
                badges.append(BADGE_NAMES[i])
    return badges


def format_game_state(state: dict) -> str:
    """Format parsed game state into a readable string for Claude.

    Navigation is purely visual (screenshots). This only shows party/battle/progress data.
    """
    lines = []

    # Progress
    badges = state.get("badges", [])
    lines.append(f"Badges: {len(badges)}/8 [{', '.join(badges) if badges else 'None'}]")
    lines.append(f"Money: ${state.get('money', 0):,}")

    # Party
    party = state.get("party", [])
    lines.append(f"\nParty ({len(party)} Pokemon):")
    for i, p in enumerate(party, 1):
        move_names = ", ".join(m["name"] for m in p.get("moves", []))
        status = ""
        sc = p.get("status_condition", 0)
        if sc != 0:
            # Decode status condition flags
            statuses = []
            if sc & 0x7:
                statuses.append("SLP")
            if sc & 0x8:
                statuses.append("PSN")
            if sc & 0x10:
                statuses.append("BRN")
            if sc & 0x20:
                statuses.append("FRZ")
            if sc & 0x40:
                statuses.append("PAR")
            if sc & 0x80:
                statuses.append("TOX")
            status = f" [{'/'.join(statuses)}]" if statuses else " [STATUS]"
        lines.append(
            f"  {i}. {p['species']} Lv.{p['level']} "
            f"HP: {p['current_hp']}/{p['max_hp']}{status} "
            f"[{move_names}]"
        )

    # Battle state
    if state.get("in_battle"):
        lines.append(f"\n** BATTLE ACTIVE **")
        enemy = state.get("enemy_pokemon")
        if enemy:
            lines.append(
                f"  Enemy: {enemy['species']} Lv.{enemy['level']} "
                f"HP: {enemy['current_hp']}/{enemy['max_hp']}"
            )
            if enemy.get("moves"):
                enemy_moves = ", ".join(m["name"] for m in enemy["moves"])
                lines.append(f"  Enemy moves: [{enemy_moves}]")
    else:
        lines.append("\nNot in battle")

    return "\n".join(lines)


def format_party_detail(party: list[dict]) -> str:
    """Format detailed party info."""
    lines = [f"Party ({len(party)} Pokemon):"]
    for i, p in enumerate(party, 1):
        lines.append(f"\n--- {i}. {p['nickname']} ({p['species']}) ---")
        lines.append(f"  Level: {p['level']}")
        lines.append(f"  HP: {p['current_hp']}/{p['max_hp']}")
        lines.append(f"  Stats: ATK={p['attack']} DEF={p['defense']} SPD={p['speed']} SPATK={p['sp_atk']} SPDEF={p['sp_def']}")

        if p.get("moves"):
            lines.append("  Moves:")
            for m in p["moves"]:
                lines.append(f"    - {m['name']} ({m['type']}) PP: {m['pp']}/{m['max_pp']}")

        ivs = p.get("ivs", {})
        lines.append(
            f"  IVs: HP={ivs.get('hp',0)} ATK={ivs.get('atk',0)} DEF={ivs.get('def',0)} "
            f"SPD={ivs.get('spd',0)} SPATK={ivs.get('spatk',0)} SPDEF={ivs.get('spdef',0)}"
        )
        lines.append(f"  Friendship: {p.get('friendship', 0)}")
        if p.get("held_item", 0) > 0:
            lines.append(f"  Held Item ID: {p['held_item']}")
    return "\n".join(lines)


def format_battle_state(state: dict) -> str:
    """Format battle state info."""
    if not state.get("in_battle"):
        return "Not currently in battle."

    lines = ["BATTLE STATE"]

    # Player's active Pokemon
    party = state.get("party", [])
    if party:
        p = party[0]
        lines.append(
            f"Your Pokemon: {p['species']} Lv.{p['level']} "
            f"HP: {p['current_hp']}/{p['max_hp']}"
        )
        if p.get("moves"):
            lines.append("Available Moves:")
            for m in p["moves"]:
                lines.append(f"  {m['name']} ({m['type']}) PP: {m['pp']}/{m['max_pp']}")

    # Enemy Pokemon
    enemy = state.get("enemy_pokemon")
    if enemy:
        lines.append(
            f"\nEnemy: {enemy['species']} Lv.{enemy['level']} "
            f"HP: {enemy['current_hp']}/{enemy['max_hp']}"
        )

    return "\n".join(lines)
