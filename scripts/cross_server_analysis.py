import json
import os
import glob
from collections import Counter
import sys

class KatalaMultiServerProcessor:
    def __init__(self, log_dirs: Dict[str, str]):
        self.log_dirs = log_dirs
        self.user_data = {}

    def process_all_logs(self):
        for server_name, log_dir in self.log_dirs.items():
            log_files = glob.glob(os.path.join(log_dir, "**/*.json"), recursive=True)
            print(f"Processing {server_name}: Found {len(log_files)} log files.")
            
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
                                    'servers': Counter(),
                                    'texts': [],
                                    'count': 0
                                }
                            
                            self.user_data[u_id]['servers'][server_name] += 1
                            if content:
                                self.user_data[u_id]['texts'].append(content)
                            self.user_data[u_id]['count'] += 1
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    def get_cross_server_summary(self):
        # Users active in more than 1 server
        cross_users = {u_id: data for u_id, data in self.user_data.items() if len(data['servers']) > 1}
        sorted_users = sorted(cross_users.items(), key=lambda x: x[1]['count'], reverse=True)
        return sorted_users

if __name__ == "__main__":
    log_configs = {
        "Matsuri": "/Users/nicolas/work/katala/data/matsuri_logs/discord log",
        "Author": "/Users/nicolas/work/katala/data/author_server_logs/hissya-log"
    }
    processor = KatalaMultiServerProcessor(log_configs)
    processor.process_all_logs()
    cross_users = processor.get_cross_server_summary()
    
    print("\n--- Cross-Server Active Users (Matsuri & Author) ---")
    for u_id, data in cross_users:
        server_stats = ", ".join([f"{s}: {c}" for s, c in data['servers'].items()])
        print(f"User: {data['name']} (ID: {u_id}) - Total: {data['count']} ({server_stats})")
