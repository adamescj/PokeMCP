"""Memory addresses and constants for Pokemon Fire Red (US v1.0 / BPRE)."""

# Save block pointers (these contain addresses to the actual data)
ADDR_SAVEBLOCK1_PTR = 0x03005008
ADDR_SAVEBLOCK2_PTR = 0x0300500C
ADDR_SAVEBLOCK3_PTR = 0x03005010

# Party data
ADDR_PARTY_START = 0x02024284
ADDR_PARTY_COUNT = 0x02024029
POKEMON_DATA_SIZE = 100

# Enemy/battle data
ADDR_ENEMY_PARTY_START = 0x0202402C
ADDR_BATTLE_FLAGS = 0x02022B4C
ADDR_BATTLE_TYPE = 0x020386AC

# SaveBlock1 offsets (from dereferenced pointer)
SB1_PLAYER_X = 0x00
SB1_PLAYER_Y = 0x02
SB1_MAP_NUM = 0x04
SB1_MAP_BANK = 0x05
SB1_MONEY = 0x0290
SB1_FLAGS = 0x0EE0

# SaveBlock2 offsets
SB2_PLAYER_NAME = 0x00
SB2_MONEY_KEY = 0x0F20

# Badge flag indices (within the flags array)
BADGE_FLAG_BASE = 0x820
NUM_BADGES = 8
BADGE_NAMES = [
    "Boulder",
    "Cascade",
    "Thunder",
    "Rainbow",
    "Soul",
    "Marsh",
    "Volcano",
    "Earth",
]

# GBA button constants (matching mGBA key IDs)
BUTTONS = {
    "A": 0,
    "B": 1,
    "SELECT": 2,
    "START": 3,
    "RIGHT": 4,
    "LEFT": 5,
    "UP": 6,
    "DOWN": 7,
    "R": 8,
    "L": 9,
}

# Pokemon substructure order table (indexed by PV % 24)
# Each entry is (Growth, Attacks, EVs/Condition, Misc) indices
SUBSTRUCTURE_ORDER = [
    (0, 1, 2, 3),  # 0: GAEM
    (0, 1, 3, 2),  # 1: GAME
    (0, 2, 1, 3),  # 2: GEAM
    (0, 2, 3, 1),  # 3: GEMA
    (0, 3, 1, 2),  # 4: GMAE
    (0, 3, 2, 1),  # 5: GMEA
    (1, 0, 2, 3),  # 6: AGEM
    (1, 0, 3, 2),  # 7: AGME
    (1, 2, 0, 3),  # 8: AEGM
    (1, 2, 3, 0),  # 9: AEMG (corrected: this is AEMG)
    (1, 3, 0, 2),  # 10: AMGE (corrected)
    (1, 3, 2, 0),  # 11: AMEG (corrected)
    (2, 0, 1, 3),  # 12: EAGM
    (2, 0, 3, 1),  # 13: EAMG (corrected)
    (2, 1, 0, 3),  # 14: EGAM
    (2, 1, 3, 0),  # 15: EGMA (corrected)
    (2, 3, 0, 1),  # 16: EMAG (corrected)
    (2, 3, 1, 0),  # 17: EMGA (corrected)
    (3, 0, 1, 2),  # 18: MAGE (corrected)
    (3, 0, 2, 1),  # 19: MAEG (corrected)
    (3, 1, 0, 2),  # 20: MGAE (corrected)
    (3, 1, 2, 0),  # 21: MGEA (corrected)
    (3, 2, 0, 1),  # 22: MEAG (corrected)
    (3, 2, 1, 0),  # 23: MEGA
]

# Gen III character encoding table (for Pokemon nicknames and trainer names)
GEN3_CHARSET = {
    0xBB: "A", 0xBC: "B", 0xBD: "C", 0xBE: "D", 0xBF: "E",
    0xC0: "F", 0xC1: "G", 0xC2: "H", 0xC3: "I", 0xC4: "J",
    0xC5: "K", 0xC6: "L", 0xC7: "M", 0xC8: "N", 0xC9: "O",
    0xCA: "P", 0xCB: "Q", 0xCC: "R", 0xCD: "S", 0xCE: "T",
    0xCF: "U", 0xD0: "V", 0xD1: "W", 0xD2: "X", 0xD3: "Y",
    0xD4: "Z", 0xD5: "a", 0xD6: "b", 0xD7: "c", 0xD8: "d",
    0xD9: "e", 0xDA: "f", 0xDB: "g", 0xDC: "h", 0xDD: "i",
    0xDE: "j", 0xDF: "k", 0xE0: "l", 0xE1: "m", 0xE2: "n",
    0xE3: "o", 0xE4: "p", 0xE5: "q", 0xE6: "r", 0xE7: "s",
    0xE8: "t", 0xE9: "u", 0xEA: "v", 0xEB: "w", 0xEC: "x",
    0xED: "y", 0xEE: "z", 0xA1: "0", 0xA2: "1", 0xA3: "2",
    0xA4: "3", 0xA5: "4", 0xA6: "5", 0xA7: "6", 0xA8: "7",
    0xA9: "8", 0xAA: "9", 0xAB: "!", 0xAC: "?", 0xAD: ".",
    0xAE: "-", 0xB4: "'", 0x00: " ", 0xFF: "",  # 0xFF = string terminator
}


def decode_gen3_string(data: bytes) -> str:
    """Decode a Gen III encoded string to UTF-8."""
    result = []
    for byte in data:
        if byte == 0xFF:  # String terminator
            break
        result.append(GEN3_CHARSET.get(byte, "?"))
    return "".join(result)
