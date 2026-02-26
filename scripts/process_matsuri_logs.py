import json
import os
import glob
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import sys

@dataclass
class UserProfileVector:
    user_id: str
    username: str
    mbti_estimate: str = "UNKNOWN"
    interests: List[str] = None
    expertise_score: Dict[str, float] = None
    tone_analysis: Dict[str, float] = None
    message_count: int = 0

class KatalaLogProcessor:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.user_data = {}

    def process_all_logs(self):
        log_files = glob.glob(os.path.join(self.log_dir, "**/*.json"), recursive=True)
        print(f"Found {len(log_files)} log files.")
        
        for file_path in log_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    messages = data.get('messages', [])
                    for msg in messages:
                        author = msg.get('author', {})
                        u_id = author.get('id')
                        u_name = author.get('name')
                        content = msg.get('content', '')
                        
                        if u_id not in self.user_data:
                            self.user_data[u_id] = {
                                'name': u_name,
                                'texts': [],
                                'count': 0
                            }
                        
                        if content:
                            self.user_data[u_id]['texts'].append(content)
                        self.user_data[u_id]['count'] += 1
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    def get_summary(self):
        # Sort users by message count
        sorted_users = sorted(self.user_data.items(), key=lambda x: x[1]['count'], reverse=True)
        return sorted_users[:20] # Top 20 for initial insight

if __name__ == "__main__":
    log_dir = "/Users/nicolas/work/katala/data/matsuri_logs/discord log"
    processor = KatalaLogProcessor(log_dir)
    processor.process_all_logs()
    top_users = processor.get_summary()
    
    print("\n--- Top 20 Active Users in Matsuri Server ---")
    for u_id, data in top_users:
        print(f"User: {data['name']} (ID: {u_id}) - Messages: {data['count']}")
