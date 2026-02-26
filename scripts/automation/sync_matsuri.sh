#!/bin/bash

# ==============================================================================
# Katala Discord Log Automation Script
# Purpose: Export logs via DiscordChatExporter.Cli and trigger Katala profiling.
# ==============================================================================

# Configuration
TOKEN="${DISCORD_TOKEN}"
GUILD_ID="1242312678198644818"
OUTPUT_DIR="/Users/nicolas/work/katala/data/matsuri_logs/discord log"
EXPORTER_PATH="/Users/nicolas/Downloads/DiscordChatExporter.Cli/DiscordChatExporter.Cli.exe" # This path needs verification
PYTHON_SCRIPT="/Users/nicolas/work/katala/scripts/process_matsuri_logs.py"

echo "🚀 Starting Discord Log Export for Guild: $GUILD_ID"

# 1. Export logs using CLI (Assuming dotnet or direct executable access)
# Note: For macOS, usually it's 'dotnet DiscordChatExporter.Cli.dll' or a binary
# We will use 'dotnet' if available, otherwise direct execution
if command -v dotnet &> /dev/null; then
    dotnet "$EXPORTER_PATH" exportguild -t "$TOKEN" -g "$GUILD_ID" -f Json -o "$OUTPUT_DIR" --parallel 8
else
    # Fallback to direct execution if binary
    "$EXPORTER_PATH" exportguild -t "$TOKEN" -g "$GUILD_ID" -f Json -o "$OUTPUT_DIR" --parallel 8
fi

echo "✅ Export completed. Triggering Katala Analysis..."

# 2. Run Katala Analysis
python3 "$PYTHON_SCRIPT"

echo "🎯 Automation Cycle Finished."
