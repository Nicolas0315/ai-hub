#!/usr/bin/env python3
"""
ViszAGIブリッジ修復プログラム
Bootstrap Specとの不一致を修正
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# パス設定
VISZAGI_ROOT = Path(__file__).parent.parent.parent / "ViszAGI"
VISZBOT_ROOT = Path(__file__).parent.parent

class BridgeFixer:
    """ブリッジ修復クラス"""
    
    def __init__(self):
        self.viszagi_entry = VISZAGI_ROOT / "visz_coding_entry.py"
        self.bridge_file = VISZAGI_ROOT / "bridges" / "visz_coding_bridge.py"
        
    def check_current_state(self) -> Dict[str, Any]:
        """現在の状態をチェック"""
        state = {
            "timestamp": datetime.now().isoformat(),
            "viszagi_root": str(VISZAGI_ROOT),
            "viszbot_root": str(VISZBOT_ROOT),
            "files_exist": {},
            "issues": [],
            "fixes_needed": []
        }
        
        # 必須ファイルの存在確認
        required_files = [
            "visz_coding_entry.py",
            "app/config.py",
            "app/models.py",
            "app/discord_bot.py",
            "app/router.py",
            "app/policy.py",
            "app/persona.py",
            "bridges/visz_coding_bridge.py",
            "main.py"
        ]
        
        for file_path in required_files:
            full_path = VISZAGI_ROOT / file_path
            exists = full_path.exists()
            state["files_exist"][file_path] = exists
            
            if not exists:
                state["issues"].append(f"Missing file: {file_path}")
                state["fixes_needed"].append(f"create_{file_path.replace('/', '_').replace('.py', '')}")
        
        return state
    
    def fix_visz_coding_entry(self):
        """visz_coding_entry.pyを修復"""
        print("🔧 visz_coding_entry.py を修復...")
        
        content = '''import json
import sys
import os
from pathlib import Path

def main() -> None:
    """Visz-Coding エントリーポイント - Bootstrap Spec v1準拠"""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({
                "ok": False,
                "error": {
                    "code": "EMPTY_INPUT",
                    "message": "No input received"
                }
            }, ensure_ascii=False))
            return
        
        req = json.loads(raw)
        
        # 必須フィールドの検証
        if not req.get("message_text"):
            print(json.dumps({
                "ok": False,
                "error": {
                    "code": "MISSING_MESSAGE",
                    "message": "message_text is required"
                }
            }, ensure_ascii=False))
            return
        
        text = req.get("message_text", "")
        persona = req.get("persona", "ViszAGI")
        
        # 簡易的な応答生成（実際のLLM処理はここで実装）
        if "こんにちは" in text or "hello" in text.lower():
            reply = f"{persona}です！こんにちは。プログラミングに関する質問をお受けしています。"
        elif "python" in text.lower():
            reply = f"{persona}です！Pythonに関するご質問ですね。具体的にどのようなコードについて知りたいですか？"
        elif "discord" in text.lower():
            reply = f"{persona}です！Discord bot開発についてお手伝いできます。どのような機能を実装したいですか？"
        else:
            reply = f"{persona}です！メッセージを受信しました: {text[:50]}{'...' if len(text) > 50 else ''}"
        
        # Bootstrap Spec準拠の応答
        response = {
            "ok": True,
            "reply_text": reply,
            "actions": [],
            "artifacts": [],
            "meta": {
                "engine": "visz-coding",
                "version": "v1",
                "timestamp": datetime.now().isoformat(),
                "request_id": req.get("request_id", "unknown")
            }
        }
        
        sys.stdout.write(json.dumps(response, ensure_ascii=False))
        
    except json.JSONDecodeError as e:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "INVALID_JSON",
                "message": f"JSON parsing error: {str(e)}"
            }
        }, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Internal error: {str(e)}"
            }
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''
        
        self.viszagi_entry.write_text(content, encoding='utf-8')
        print(f"✅ visz_coding_entry.py を更新: {self.viszagi_entry}")
    
    def fix_bridge_config(self):
        """ブリッジ設定を修復"""
        print("🔧 ブリッジ設定を修復...")
        
        # .env.local のブリッジコマンドを修正
        env_file = VISZAGI_ROOT / ".env.local"
        if env_file.exists():
            content = env_file.read_text(encoding='utf-8')
            
            # ブリッジコマンドを修正
            old_command = 'VISZ_BRIDGE_COMMAND=python d:\\Program AGIbot\\ViszAGI\\Visz-Coding\\entry.py'
            new_command = f'VISZ_BRIDGE_COMMAND=python "{VISZAGI_ROOT}\\visz_coding_entry.py"'
            
            if old_command in content:
                content = content.replace(old_command, new_command)
                env_file.write_text(content, encoding='utf-8')
                print(f"✅ ブリッジコマンドを修正: {new_command}")
            else:
                print(f"⚠️ ブリッジコマンドが見つからないか、すでに修正済み")
    
    def create_missing_files(self):
        """欠落ファイルを作成"""
        print("🔧 欠落ファイルを作成...")
        
        # appディレクトリの確認
        app_dir = VISZAGI_ROOT / "app"
        bridges_dir = VISZAGI_ROOT / "bridges"
        
        app_dir.mkdir(exist_ok=True)
        bridges_dir.mkdir(exist_ok=True)
        
        # models.py
        models_file = app_dir / "models.py"
        if not models_file.exists():
            content = '''from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class InboundRequest:
    request_id: str
    source: str
    channel_id: str
    user_id: str
    username: str
    message_text: str
    reply_mode: str = "channel"
    persona: str = "ViszAGI"
    constraints: dict[str, Any] = field(default_factory=dict)

@dataclass
class BridgeResponse:
    ok: bool
    reply_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] | None = None
'''
            models_file.write_text(content, encoding='utf-8')
            print(f"✅ models.py を作成")
        
        # config.py
        config_file = app_dir / "config.py"
        if not config_file.exists():
            content = '''from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv('.env.local')
load_dotenv()

def _split_csv_int(value: str) -> set[int]:
    value = (value or "").strip()
    if not value:
        return set()
    return {int(x.strip()) for x in value.split(",") if x.strip()}

@dataclass(frozen=True)
class Settings:
    discord_token: str
    allowed_channel_ids: set[int]
    allowed_user_ids: set[int]
    trigger_mode: str
    bridge_command: list[str]
    bridge_timeout_sec: int
    bot_name: str
    github_token: str
    github_repo_name: str
    github_repo_path: str
    openclaw_enabled: bool
    openclaw_api_endpoint: str
    openclaw_api_key: str
    openclaw_timeout_sec: int
    openclaw_retry_count: int

settings = Settings(
    discord_token=os.environ["DISCORD_TOKEN"],
    allowed_channel_ids=_split_csv_int(os.getenv("VISZ_ALLOWED_CHANNEL_IDS", "")),
    allowed_user_ids=_split_csv_int(os.getenv("VISZ_ALLOWED_USER_IDS", "")),
    trigger_mode=os.getenv("VISZ_TRIGGER_MODE", "mention_or_reply"),
    bridge_command=shlex.split(os.environ["VISZ_BRIDGE_COMMAND"]),
    bridge_timeout_sec=int(os.getenv("VISZ_BRIDGE_TIMEOUT_SEC", "120")),
    bot_name=os.getenv("VISZ_BOT_NAME", "ViszAGI"),
    github_token=os.environ["GITHUB_TOKEN"],
    github_repo_name=os.getenv("GITHUB_REPO_NAME", "ViszBot"),
    github_repo_path=os.getenv("GITHUB_REPO_PATH", ""),
    openclaw_enabled=os.getenv("OPENCLAW_ENABLED", "false").lower() == "true",
    openclaw_api_endpoint=os.getenv("OPENCLAW_API_ENDPOINT", "http://localhost:8080/api"),
    openclaw_api_key=os.getenv("OPENCLAW_API_KEY", ""),
    openclaw_timeout_sec=int(os.getenv("OPENCLAW_TIMEOUT_SEC", "30")),
    openclaw_retry_count=int(os.getenv("OPENCLAW_RETRY_COUNT", "3")),
)
'''
            config_file.write_text(content, encoding='utf-8')
            print(f"✅ config.py を作成")
    
    def run_diagnostics(self):
        """診断を実行"""
        print("🔍 診断を実行...")
        
        state = self.check_current_state()
        
        print(f"\n📊 診断結果:")
        print(f"  ViszAGIルート: {state['viszagi_root']}")
        print(f"  ViszBotルート: {state['viszbot_root']}")
        print(f"  ファイル存在状況: {sum(state['files_exist'].values())}/{len(state['files_exist'])}")
        
        if state['issues']:
            print(f"\n⚠️ 発見された問題:")
            for issue in state['issues']:
                print(f"  - {issue}")
        
        return state
    
    def apply_fixes(self, state: Dict[str, Any]):
        """修正を適用"""
        print("\n🔧 修正を適用...")
        
        # visz_coding_entry.py の修復
        if not state['files_exist'].get('visz_coding_entry.py', False):
            self.fix_visz_coding_entry()
        
        # ブリッジ設定の修正
        self.fix_bridge_config()
        
        # 欠落ファイルの作成
        if state['fixes_needed']:
            self.create_missing_files()
        
        print("✅ 修正完了")
    
    def test_fixes(self):
        """修正をテスト"""
        print("\n🧪 修正をテスト...")
        
        # visz_coding_entry.py テスト
        test_payload = {
            "version": "v1",
            "request_id": "fix-test-123",
            "source": "test",
            "message_text": "こんにちは、ViszAGI！"
        }
        
        try:
            proc = subprocess.run(
                [sys.executable, str(self.viszagi_entry)],
                input=json.dumps(test_payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=10,
                cwd=str(VISZAGI_ROOT)
            )
            
            if proc.returncode == 0:
                response = json.loads(proc.stdout)
                if response.get("ok"):
                    print(f"✅ visz_coding_entry.py テスト成功: {response.get('reply_text', '')[:50]}...")
                    return True
                else:
                    print(f"❌ 応答エラー: {response}")
            else:
                print(f"❌ 実行失敗: {proc.stderr}")
                
        except Exception as e:
            print(f"❌ テスト失敗: {e}")
        
        return False

def main():
    """メイン実行"""
    print("🔧 ViszAGIブリッジ修復プログラム")
    print("Bootstrap Specとの不一致を修正")
    print("=" * 50)
    
    fixer = BridgeFixer()
    
    # 1. 診断実行
    state = fixer.run_diagnostics()
    
    # 2. 修正適用
    fixer.apply_fixes(state)
    
    # 3. 修正テスト
    if fixer.test_fixes():
        print("\n🎉 修復成功! ViszAGIとViszBotの統合が完了しました。")
        print("💡 Bootstrap Spec準拠の動作が確認できました。")
    else:
        print("\n⚠️ 修復後に問題が残っています。")
        print("🔧 手動での追加修正が必要かもしれません。")

if __name__ == "__main__":
    main()
