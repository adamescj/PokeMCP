-- mGBA MCP Server - Lua TCP server for Pokemon Fire Red
-- Load this script in mGBA via Tools > Scripting > File > Load Script
-- It creates a TCP server that the Python MCP server connects to.
--
-- IMPORTANT: Load a ROM first, then load this script.
-- Or load the script first — it will wait for the ROM to be ready.

local PORT = 5555
local server = nil
local client = nil
local buffer = ""
local screenshot_counter = 0
local server_started = false

-- Button state tracking
local active_keys = {}       -- {key_id = frames_remaining}
local input_queue = {}       -- sequential button press queue
local pending_response = nil -- response to send after input completes
local wait_counter = 0       -- frames to wait before responding

-- GBA key constants (raw integer values, no dependency on C.GBA_KEY)
local KEY_MAP = {
    A = 0,
    B = 1,
    SELECT = 2,
    START = 3,
    RIGHT = 4,
    LEFT = 5,
    UP = 6,
    DOWN = 7,
    R = 8,
    L = 9,
}

-- Memory addresses for Pokemon Fire Red (US v1.0 / BPRE)
local ADDR = {
    SAVEBLOCK1_PTR = 0x03005008,
    SAVEBLOCK2_PTR = 0x0300500C,
    PARTY_START = 0x02024284,
    PARTY_COUNT = 0x02024029,
    ENEMY_PARTY_START = 0x0202402C,
    BATTLE_FLAGS = 0x02022B4C,
    -- SaveBlock1 offsets
    SB1_PLAYER_X = 0x00,
    SB1_PLAYER_Y = 0x02,
    SB1_MAP_NUM = 0x04,
    SB1_MAP_BANK = 0x05,
    SB1_MONEY = 0x0290,
    SB1_FLAGS = 0x0EE0,
    -- SaveBlock2 offsets
    SB2_MONEY_KEY = 0x0F20,
}

-- Screenshot directory (use script's own directory)
local SCRIPT_DIR = ""
do
    local info = debug.getinfo(1, "S")
    if info and info.source then
        local src = info.source:gsub("^@", "")
        SCRIPT_DIR = src:match("(.+)[/\\]") or "."
    end
end

-- ============================================================
-- Base64 encoder (pure Lua)
-- ============================================================

local b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

local function base64_encode(data)
    local result = {}
    local len = #data
    local i = 1
    while i <= len do
        local a = string.byte(data, i)
        local b = i + 1 <= len and string.byte(data, i + 1) or 0
        local c = i + 2 <= len and string.byte(data, i + 2) or 0
        local triple = a * 65536 + b * 256 + c

        local idx1 = math.floor(triple / 262144) + 1
        local idx2 = math.floor(triple / 4096) % 64 + 1
        local idx3 = math.floor(triple / 64) % 64 + 1
        local idx4 = triple % 64 + 1

        result[#result + 1] = string.sub(b64chars, idx1, idx1)
        result[#result + 1] = string.sub(b64chars, idx2, idx2)
        result[#result + 1] = (i + 1 <= len) and string.sub(b64chars, idx3, idx3) or "="
        result[#result + 1] = (i + 2 <= len) and string.sub(b64chars, idx4, idx4) or "="

        i = i + 3
    end
    return table.concat(result)
end

-- ============================================================
-- JSON encoder/decoder (minimal, sufficient for our protocol)
-- ============================================================

local function json_encode(val)
    if val == nil then
        return "null"
    elseif type(val) == "boolean" then
        return val and "true" or "false"
    elseif type(val) == "number" then
        if val ~= val then return "null" end  -- NaN
        if val == math.huge or val == -math.huge then return "null" end
        -- Use integer format for whole numbers to avoid scientific notation
        if math.type(val) == "integer" then
            return string.format("%d", val)
        end
        return tostring(val)
    elseif type(val) == "string" then
        local escaped = val:gsub('[\\"]', function(c) return "\\" .. c end)
        escaped = escaped:gsub("\n", "\\n")
        escaped = escaped:gsub("\r", "\\r")
        escaped = escaped:gsub("\t", "\\t")
        return '"' .. escaped .. '"'
    elseif type(val) == "table" then
        -- Check if array or object
        local is_array = #val > 0 or next(val) == nil
        if is_array then
            local parts = {}
            for i, v in ipairs(val) do
                parts[#parts + 1] = json_encode(v)
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, v in pairs(val) do
                parts[#parts + 1] = json_encode(tostring(k)) .. ":" .. json_encode(v)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return "null"
end

local function json_decode(str)
    str = str:match("^%s*(.-)%s*$")  -- trim
    if str == "null" then return nil end
    if str == "true" then return true end
    if str == "false" then return false end

    local num = tonumber(str)
    if num then return num end

    -- string
    if str:sub(1, 1) == '"' then
        local s = str:sub(2, -2)
        s = s:gsub('\\"', '"')
        s = s:gsub("\\\\", "\\")
        s = s:gsub("\\n", "\n")
        s = s:gsub("\\r", "\r")
        s = s:gsub("\\t", "\t")
        return s
    end

    -- object
    if str:sub(1, 1) == "{" then
        local result = {}
        local content = str:sub(2, -2)
        if content:match("^%s*$") then return result end

        local pos = 1
        while pos <= #content do
            local ws = content:match("^[%s,]*()", pos)
            if ws then pos = ws end
            if pos > #content then break end

            local key_end = content:find(':', pos)
            if not key_end then break end
            local key_str = content:sub(pos, key_end - 1):match('^%s*"(.-)"%s*$')
            if not key_str then break end
            pos = key_end + 1

            ws = content:match("^%s*()", pos)
            if ws then pos = ws end

            local val, new_pos = nil, pos
            local ch = content:sub(pos, pos)

            if ch == '"' then
                local str_end = pos + 1
                while str_end <= #content do
                    if content:sub(str_end, str_end) == '"' and content:sub(str_end - 1, str_end - 1) ~= '\\' then
                        break
                    end
                    str_end = str_end + 1
                end
                val = json_decode(content:sub(pos, str_end))
                new_pos = str_end + 1
            elseif ch == '{' or ch == '[' then
                local depth = 1
                local bracket_end = pos + 1
                local open = ch
                local close = ch == '{' and '}' or ']'
                while bracket_end <= #content and depth > 0 do
                    local c = content:sub(bracket_end, bracket_end)
                    if c == open then depth = depth + 1
                    elseif c == close then depth = depth - 1 end
                    bracket_end = bracket_end + 1
                end
                val = json_decode(content:sub(pos, bracket_end - 1))
                new_pos = bracket_end
            else
                local token = content:match("([^,}%]%s]+)", pos)
                if token then
                    val = json_decode(token)
                    new_pos = pos + #token
                end
            end

            result[key_str] = val
            pos = new_pos
        end
        return result
    end

    -- array
    if str:sub(1, 1) == "[" then
        local result = {}
        local content = str:sub(2, -2)
        if content:match("^%s*$") then return result end

        local pos = 1
        while pos <= #content do
            local ws = content:match("^[%s,]*()", pos)
            if ws then pos = ws end
            if pos > #content then break end

            local ch = content:sub(pos, pos)
            local val, new_pos = nil, pos

            if ch == '"' then
                local str_end = pos + 1
                while str_end <= #content do
                    if content:sub(str_end, str_end) == '"' and content:sub(str_end - 1, str_end - 1) ~= '\\' then
                        break
                    end
                    str_end = str_end + 1
                end
                val = json_decode(content:sub(pos, str_end))
                new_pos = str_end + 1
            elseif ch == '{' or ch == '[' then
                local depth = 1
                local bracket_end = pos + 1
                local open = ch
                local close = ch == '{' and '}' or ']'
                while bracket_end <= #content and depth > 0 do
                    local c = content:sub(bracket_end, bracket_end)
                    if c == open then depth = depth + 1
                    elseif c == close then depth = depth - 1 end
                    bracket_end = bracket_end + 1
                end
                val = json_decode(content:sub(pos, bracket_end - 1))
                new_pos = bracket_end
            else
                local token = content:match("([^,}%]%s]+)", pos)
                if token then
                    val = json_decode(token)
                    new_pos = pos + #token
                end
            end

            result[#result + 1] = val
            pos = new_pos
        end
        return result
    end

    return nil
end

-- ============================================================
-- Helper: bytes to hex string
-- ============================================================

local function bytes_to_hex(data)
    local hex = {}
    for i = 1, #data do
        hex[#hex + 1] = string.format("%02x", string.byte(data, i))
    end
    return table.concat(hex)
end

-- ============================================================
-- Screenshot helper
-- ============================================================

local function take_screenshot()
    if not emu then return "" end
    screenshot_counter = screenshot_counter + 1
    -- Use script directory for temp screenshots
    local path = SCRIPT_DIR .. "/screenshot_mcp_" .. screenshot_counter .. ".png"
    emu:screenshot(path)

    -- Read the file and base64 encode
    local f = io.open(path, "rb")
    if not f then
        -- Fallback: try with backslashes on Windows
        path = SCRIPT_DIR .. "\\screenshot_mcp_" .. screenshot_counter .. ".png"
        f = io.open(path, "rb")
        if not f then
            console:error("Failed to open screenshot file: " .. path)
            return ""
        end
    end
    local data = f:read("*a")
    f:close()

    -- Clean up the temp file
    os.remove(path)

    return base64_encode(data)
end

-- ============================================================
-- Command handlers
-- ============================================================

local function handle_screenshot(request)
    local b64 = take_screenshot()
    return { id = request.id, screenshot = b64 }
end

local function handle_press_button(request)
    local button_name = request.button
    local frames = request.frames or 10
    local key = KEY_MAP[button_name]
    if not key then
        return { id = request.id, error = "Unknown button: " .. tostring(button_name) }
    end

    -- Set the key active and track frames
    active_keys[key] = frames
    emu:addKey(key)

    -- Queue the response to be sent after frames elapse + screenshot
    pending_response = { id = request.id, needs_screenshot = true }
    wait_counter = frames + 2  -- extra frames for the input to register

    return nil  -- response will be sent later from frame callback
end

local function handle_press_buttons(request)
    local sequence = request.sequence or {}

    -- Build input queue
    input_queue = {}
    for _, entry in ipairs(sequence) do
        local key = KEY_MAP[entry.button]
        if key then
            table.insert(input_queue, {
                key = key,
                hold_frames = entry.hold_frames or 10,
                release_frames = entry.release_frames or 5,
                state = "pending",
                counter = 0,
            })
        end
    end

    -- Start the first input
    if #input_queue > 0 then
        input_queue[1].state = "holding"
        input_queue[1].counter = input_queue[1].hold_frames
        emu:addKey(input_queue[1].key)
    end

    pending_response = { id = request.id, needs_screenshot = true }
    return nil  -- handled in frame callback
end

local function handle_read_memory(request)
    local address = request.address
    local length = request.length or 1

    local data = emu:readRange(address, length)
    return {
        id = request.id,
        data = bytes_to_hex(data),
        address = address,
        length = length,
    }
end

local function handle_get_game_state(request)
    local result = { id = request.id }

    -- Read SaveBlock pointers (no location data — navigation is visual only)
    local sb1_ptr = emu:read32(ADDR.SAVEBLOCK1_PTR)
    local sb2_ptr = emu:read32(ADDR.SAVEBLOCK2_PTR)

    -- Money (XOR encrypted) - Lua 5.4 uses ~ for XOR
    local money_raw = emu:read32(sb1_ptr + ADDR.SB1_MONEY)
    local money_key = emu:read32(sb2_ptr + ADDR.SB2_MONEY_KEY)
    result.money = money_raw ~ money_key

    -- Flags (read 300 bytes starting from the flags offset, covers badge flags at bit 0x820)
    local flags_start = sb1_ptr + ADDR.SB1_FLAGS
    local flags_data = emu:readRange(flags_start, 300)
    result.flags_data = bytes_to_hex(flags_data)

    -- Party count
    result.party_count = emu:read8(ADDR.PARTY_COUNT)

    -- Party data (6 * 100 bytes)
    local party_data = emu:readRange(ADDR.PARTY_START, 6 * 100)
    result.party_data = bytes_to_hex(party_data)

    -- Battle flags
    result.battle_flags = emu:read32(ADDR.BATTLE_FLAGS)

    -- Enemy data (first enemy Pokemon, 100 bytes)
    if result.battle_flags ~= 0 then
        local enemy_data = emu:readRange(ADDR.ENEMY_PARTY_START, 100)
        result.enemy_data = bytes_to_hex(enemy_data)
    end

    return result
end

local function handle_save_state(request)
    local slot = request.slot or 1
    emu:saveStateSlot(slot)
    return { id = request.id, status = "saved", slot = slot }
end

local function handle_load_state(request)
    local slot = request.slot or 1
    emu:loadStateSlot(slot)
    -- Take screenshot after loading
    local b64 = take_screenshot()
    return { id = request.id, status = "loaded", slot = slot, screenshot = b64 }
end

local function handle_wait_frames(request)
    local count = request.count or 60
    wait_counter = count
    pending_response = { id = request.id, needs_screenshot = true }
    return nil  -- handled in frame callback
end

-- Command dispatch table
local COMMANDS = {
    screenshot = handle_screenshot,
    press_button = handle_press_button,
    press_buttons = handle_press_buttons,
    read_memory = handle_read_memory,
    get_game_state = handle_get_game_state,
    save_state = handle_save_state,
    load_state = handle_load_state,
    wait_frames = handle_wait_frames,
}

-- ============================================================
-- Process incoming data
-- ============================================================

local function send_response(response)
    if not client then return end
    local json_str = json_encode(response) .. "\n"
    local ok, err = pcall(function() client:send(json_str) end)
    if not ok then
        console:log("Send failed: " .. tostring(err))
        client = nil
        buffer = ""
    end
end

local function process_command(line)
    local request = json_decode(line)
    if not request or not request.cmd then
        send_response({ error = "Invalid command", id = request and request.id })
        return
    end

    local handler = COMMANDS[request.cmd]
    if not handler then
        send_response({ error = "Unknown command: " .. request.cmd, id = request.id })
        return
    end

    local response = handler(request)
    if response then
        send_response(response)
    end
end

local function process_buffer()
    while true do
        local newline_pos = buffer:find("\n")
        if not newline_pos then break end

        local line = buffer:sub(1, newline_pos - 1)
        buffer = buffer:sub(newline_pos + 1)

        if #line > 0 then
            local ok, err = pcall(process_command, line)
            if not ok then
                console:error("Error processing command: " .. tostring(err))
                send_response({ error = "Internal error: " .. tostring(err) })
            end
        end
    end
end

-- ============================================================
-- Frame callback - handles input timing and deferred responses
-- ============================================================

local function on_frame()
    -- Handle active key releases
    for key, frames in pairs(active_keys) do
        if frames <= 1 then
            emu:clearKey(key)
            active_keys[key] = nil
        else
            active_keys[key] = frames - 1
        end
    end

    -- Handle input queue (sequential button presses)
    if #input_queue > 0 then
        local current = input_queue[1]

        if current.state == "holding" then
            current.counter = current.counter - 1
            if current.counter <= 0 then
                emu:clearKey(current.key)
                current.state = "releasing"
                current.counter = current.release_frames
            end
        elseif current.state == "releasing" then
            current.counter = current.counter - 1
            if current.counter <= 0 then
                table.remove(input_queue, 1)
                if #input_queue > 0 then
                    input_queue[1].state = "holding"
                    input_queue[1].counter = input_queue[1].hold_frames
                    emu:addKey(input_queue[1].key)
                end
            end
        end
    end

    -- Handle wait counter
    if wait_counter > 0 then
        wait_counter = wait_counter - 1
    end

    -- Send deferred response when ready
    if pending_response and wait_counter <= 0 and #input_queue == 0 and next(active_keys) == nil then
        local response = pending_response
        pending_response = nil

        if response.needs_screenshot then
            response.screenshot = take_screenshot()
            response.needs_screenshot = nil
        end

        send_response(response)
    end

    -- Poll for incoming data directly (more reliable than socket callbacks)
    if client then
        local ok, data = pcall(function() return client:receive(4096) end)
        if ok and data then
            buffer = buffer .. data
        elseif not ok then
            console:log("Client receive error, disconnecting")
            client = nil
            buffer = ""
        end
        process_buffer()
    end

    -- Try to accept new connection if no client
    if not client and server then
        local ok, new_client = pcall(function() return server:accept() end)
        if ok and new_client then
            client = new_client
            buffer = ""
            console:log("MCP client connected!")
        end
    end
end

-- ============================================================
-- Server setup - deferred until emulator core is ready
-- ============================================================

local function start_server()
    if server_started then return end
    server_started = true

    -- Check game code if emu is available
    if emu then
        local ok, game_code = pcall(function() return emu:getGameCode() end)
        if ok and game_code then
            if not game_code:find("BPRE") then
                console:warn("WARNING: Expected Pokemon Fire Red (BPRE), got: " .. tostring(game_code))
                console:warn("Memory addresses may be incorrect for this ROM!")
            else
                console:log("Detected Pokemon Fire Red (BPRE) - OK")
            end
        end
    end

    server = socket.bind("127.0.0.1", PORT)
    if not server then
        console:error("Failed to bind to port " .. PORT)
        return
    end
    server:listen(1)

    console:log("MCP Server listening on 127.0.0.1:" .. PORT)
    console:log("Waiting for Python MCP client to connect...")
    console:log("(Connection and data polling handled in frame callback)")

    -- Register frame callback
    callbacks:add("frame", on_frame)
end

-- ============================================================
-- Initialization: wait for emulator to be ready
-- ============================================================

-- If emu is already available (ROM loaded before script), start immediately
if emu then
    console:log("Emulator core detected, starting server...")
    start_server()
else
    -- Wait for the "start" callback which fires when a ROM is loaded
    console:log("Waiting for ROM to be loaded...")
    callbacks:add("start", function()
        console:log("ROM loaded! Starting MCP server...")
        start_server()
    end)
end
