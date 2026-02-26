#!/bin/bash

# ==============================================================================
# Katala Discord Log Automation Script (Incremental Sync)
# Purpose: Smartly export logs from multiple servers based on last sync date.
# ==============================================================================

# Configuration
TOKEN="${DISCORD_TOKEN}"
EXPORTER_PATH="/Users/nicolas/Downloads/DiscordChatExporter.Cli/DiscordChatExporter.Cli.exe"
STATE_FILE="/Users/nicolas/work/katala/data/sync_state.json"
BASE_DIR="/Users/nicolas/work/katala/data/automated_logs"

# Servers to sync (Minimized to avoid BAN risk)
# Currently only "Matsuri" and specific important server are active.
SERVERS=(
    "1242312678198644818:Matsuri"
    "1230078622963073108:Target_Server"
)

# Load last sync date (Default to 7 days ago if no state)
LAST_SYNC=$(python3 -c "import json, os, datetime; f='$STATE_FILE'; print(json.load(open(f))['last_sync'] if os.path.exists(f) else (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d'))")

echo "🚀 Starting Incremental Sync since: $LAST_SYNC"

for ENTRY in "${SERVERS[@]}"; do
    GUILD_ID="${ENTRY%%:*}"
    SERVER_NAME="${ENTRY#*:}"
    OUTPUT_DIR="$BASE_DIR/$SERVER_NAME"
    mkdir -p "$OUTPUT_DIR"

    echo "--- Syncing $SERVER_NAME ($GUILD_ID) ---"
    
    # Random sleep to mimic human behavior and avoid rate limits
    SLEEP_TIME=$(( ( RANDOM % 120 )  + 60 ))
    echo "Sleeping for $SLEEP_TIME seconds to stay under the radar..."
    sleep $SLEEP_TIME

    # Export using --after filter for efficiency
    # Added random delay per channel inside export could be better, but we start with guild-level delay
    dotnet "$EXPORTER_PATH" exportguild -t "$TOKEN" -g "$GUILD_ID" -f Json -o "$OUTPUT_DIR" --after "$LAST_SYNC" --parallel 1
done

# Update sync state to today
python3 -c "import json, datetime; print(json.dumps({'last_sync': datetime.datetime.now().strftime('%Y-%m-%d')}))" > "$STATE_FILE"

echo "✅ Incremental Sync Completed. Triggering Katala Analysis..."
python3 /Users/nicolas/work/katala/scripts/process_matsuri_logs.py
