import json
import os
import glob
from collections import Counter
import re

def analyze_user_deep(user_id, log_dir):
    texts = []
    log_files = glob.glob(os.path.join(log_dir, "**/*.json"), recursive=True)
    
    for file_path in log_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for msg in data.get('messages', []):
                if msg.get('author', {}).get('id') == user_id:
                    content = msg.get('content', '')
                    if content:
                        texts.append(content)
    
    # Simple Keyword Analysis
    keywords = ["AI", "OpenClaw", "3D", "Blender", "Dev", "Python", "GPT", "Claude", "デザイン", "自動化"]
    found_keywords = Counter()
    all_text = " ".join(texts).lower()
    
    for kw in keywords:
        count = all_text.count(kw.lower())
        if count > 0:
            found_keywords[kw] = count
            
    return {
        "count": len(texts),
        "top_keywords": found_keywords.most_common(5),
        "sample_text": texts[:3]
    }

if __name__ == "__main__":
    log_dir = "/Users/nicolas/work/katala/data/matsuri_logs/discord log"
    # Analyze Top 5 non-bot users
    target_users = [
        ("sotono", "253936160177389569"),
        ("light0904", "620636551176519683"),
        ("kinketsugod", "552129088026837005"),
        ("4o", "628362436608786434"),
        ("iori.dev", "278021785168117760")
    ]
    
    results = {}
    for name, u_id in target_users:
        results[name] = analyze_user_deep(u_id, log_dir)
        
    print(json.dumps(results, indent=2, ensure_ascii=False))
