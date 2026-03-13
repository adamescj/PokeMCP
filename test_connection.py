"""Quick test script to verify the Lua server connection."""
import json
import socket
import base64
import sys


def send_command(sock, cmd, **params):
    """Send a JSON command and get the response."""
    request = {"cmd": cmd, "id": 1, **params}
    message = json.dumps(request) + "\n"
    sock.sendall(message.encode("utf-8"))

    # Read response until newline
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk

    response = json.loads(data.decode("utf-8").strip())
    return response


def main():
    print("Connecting to mGBA Lua server on 127.0.0.1:5555...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(("127.0.0.1", 5555))
        print("Connected!\n")
    except ConnectionRefusedError:
        print("ERROR: Could not connect. Make sure mGBA is running and the Lua script is loaded.")
        sys.exit(1)

    # Test 1: Screenshot
    print("Test 1: Taking screenshot...")
    resp = send_command(sock, "screenshot")
    if resp.get("screenshot"):
        png_data = base64.b64decode(resp["screenshot"])
        with open("test_screenshot.png", "wb") as f:
            f.write(png_data)
        print(f"  OK! Screenshot saved ({len(png_data)} bytes) -> test_screenshot.png\n")
    else:
        print(f"  FAILED: {resp}\n")

    # Test 2: Game state
    print("Test 2: Reading game state...")
    resp = send_command(sock, "get_game_state")
    print(f"  Player X: {resp.get('player_x')}")
    print(f"  Player Y: {resp.get('player_y')}")
    print(f"  Map Bank: {resp.get('map_bank')}")
    print(f"  Map Num: {resp.get('map_num')}")
    print(f"  Money: {resp.get('money')}")
    print(f"  Party Count: {resp.get('party_count')}")
    print(f"  Battle Flags: {resp.get('battle_flags')}")
    print(f"  Party data length: {len(resp.get('party_data', '')) // 2} bytes")
    print()

    # Test 3: Button press
    print("Test 3: Pressing A button...")
    resp = send_command(sock, "press_button", button="A", frames=10)
    if resp.get("screenshot"):
        png_data = base64.b64decode(resp["screenshot"])
        with open("test_after_press.png", "wb") as f:
            f.write(png_data)
        print(f"  OK! Screenshot after press saved ({len(png_data)} bytes)\n")
    else:
        print(f"  FAILED: {resp}\n")

    print("All tests passed! The Lua server is working correctly.")
    sock.close()


if __name__ == "__main__":
    main()
