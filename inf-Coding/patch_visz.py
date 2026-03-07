import re

with open("../ViszBot/vis_coding_entry.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """
    # Append chat to inf-Coding for local visibility
    try:
        inf_coding_chat = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/viszbot_chat.md")
        with inf_coding_chat.open("a", encoding="utf-8") as f:
            f.write(f"\\n### Request: {request_id}\\n")
            f.write(f"**User**: {text}\\n\\n")
            f.write(f"**ViszBot**: {kl.reply_text}\\n")
            f.write("-" * 40 + "\\n")
    except Exception as e:
        pass

    sys.stdout.write(json.dumps(response_payload, ensure_ascii=False))
"""

content = content.replace("    sys.stdout.write(json.dumps(response_payload, ensure_ascii=False))", patch)

with open("../ViszBot/vis_coding_entry.py", "w", encoding="utf-8") as f:
    f.write(content)
