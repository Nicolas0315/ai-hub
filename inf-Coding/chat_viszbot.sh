#!/bin/bash
# A local chat bridge for ViszBot from inf-Coding

MESSAGE="$*"
if [ -z "$MESSAGE" ]; then
    echo "Usage: ./chat_viszbot.sh <message>"
    exit 1
fi

JSON_PAYLOAD=$(cat <<JSON
{
  "request_id": "local-cli-$(date +%s)",
  "message_text": "${MESSAGE}",
  "constraints": {
    "require_vis_coding": true,
    "require_vis_bridge": true,
    "require_kl_beta": true
  }
}
JSON
)

echo "[User]: ${MESSAGE}" >> viszbot_chat.md
echo "Waiting for ViszBot..."

# Call vis_coding_entry.py directly
VENV_PYTHON="../ViszBot/venv/bin/python3"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

OUTPUT=$(echo "$JSON_PAYLOAD" | $VENV_PYTHON ../ViszBot/vis_coding_entry.py)

# Extract reply_text using python
REPLY=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('reply_text', 'Error or blocked'))" 2>/dev/null)

if [ -z "$REPLY" ]; then
    REPLY="[Error parsing response]: $OUTPUT"
fi

echo -e "\n[ViszBot]:\n${REPLY}\n" >> viszbot_chat.md
echo "----------------------------------------" >> viszbot_chat.md

echo -e "\n[ViszBot]:\n${REPLY}\n"
echo "(Chat appended to viszbot_chat.md)"

