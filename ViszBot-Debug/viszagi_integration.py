#!/usr/bin/env python3
"""
ViszAGIとViszBotの統合修復プログラム
Bootstrap Specに基づいた完全な統合実装
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# パス設定
VISZAGI_ROOT = Path(__file__).parent.parent.parent / "ViszAGI"
VISZBOT_ROOT = Path(__file__).parent.parent

@dataclass
class BridgeResult:
    """ブリッジ実行結果"""
    ok: bool
    reply_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw: dict | None = None

class ViszCodingBridge:
    """ViszAGI Bootstrap Spec準拠のブリッジ実装"""
    
    def __init__(self):
        self.viszagi_entry = VISZAGI_ROOT / "visz_coding_entry.py"
        self.timeout_sec = 120
        
    def call_visz_coding(self, payload: Dict[str, Any]) -> BridgeResult:
        """Visz-Codingエントリーポイントを呼び出す"""
        try:
            proc = subprocess.run(
                [sys.executable, str(self.viszagi_entry)],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_sec,
                cwd=str(VISZAGI_ROOT)
            )
            
            if proc.returncode != 0:
                return BridgeResult(
                    ok=False,
                    error_code="NONZERO_EXIT",
                    error_message=proc.stderr.strip() or f"rc={proc.returncode}",
                )
            
            try:
                data = json.loads(proc.stdout)
            except Exception as e:
                return BridgeResult(
                    ok=False,
                    error_code="BAD_JSON",
                    error_message=f"JSON解析失敗: {e}",
                    raw={"stdout": proc.stdout}
                )
            
            if not data.get("ok"):
                err = data.get("error") or {}
                return BridgeResult(
                    ok=False,
                    error_code=err.get("code", "UNKNOWN"),
                    error_message=err.get("message", "unknown error"),
                    raw=data,
                )
            
            return BridgeResult(
                ok=True,
                reply_text=data.get("reply_text", ""),
                raw=data,
            )
            
        except subprocess.TimeoutExpired:
            return BridgeResult(
                ok=False,
                error_code="TIMEOUT",
                error_message="実行タイムアウト",
            )
        except Exception as e:
            return BridgeResult(
                ok=False,
                error_code="SPAWN_FAILED",
                error_message=str(e),
            )

class ViszAGIIntegration:
    """ViszAGI統合管理クラス"""
    
    def __init__(self):
        self.bridge = ViszCodingBridge()
        
    def create_payload(self, message_text: str, user_id: str = "debug", channel_id: str = "debug") -> Dict[str, Any]:
        """Bootstrap Spec準拠のペイロードを作成"""
        return {
            "version": "v1",
            "request_id": f"debug-{int(time.time())}",
            "source": "discord",
            "channel_id": channel_id,
            "user_id": user_id,
            "username": "DebugUser",
            "message_text": message_text,
            "reply_mode": "channel",
            "persona": "ViszAGI",
            "constraints": {
                "allow_tools": True,
                "allow_files": True,
                "timeout_sec": 120,
            }
        }
    
    def process_message(self, message_text: str) -> BridgeResult:
        """メッセージを処理してViszAGI応答を取得"""
        payload = self.create_payload(message_text)
        return self.bridge.call_visz_coding(payload)

def test_integration():
    """統合テスト実行"""
    print("🔧 ViszAGI-ViszBot 統合テスト")
    print("=" * 50)
    
    # 1. ファイル存在確認
    print("1. ファイル存在確認...")
    viszagi_entry = VISZAGI_ROOT / "visz_coding_entry.py"
    if not viszagi_entry.exists():
        print(f"❌ ViszAGIエントリーポイントが存在しません: {viszagi_entry}")
        return False
    print(f"✅ ViszAGIエントリーポイント確認: {viszagi_entry}")
    
    # 2. ブリッジテスト
    print("\n2. ブリッジ通信テスト...")
    integration = ViszAGIIntegration()
    
    test_messages = [
        "Hello, ViszAGI!",
        "Pythonで簡単な計算機を作ってください",
        "Discord botの作り方を教えて"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n  テスト {i}: {message}")
        result = integration.process_message(message)
        
        if result.ok:
            print(f"  ✅ 応答: {result.reply_text[:100]}...")
        else:
            print(f"  ❌ エラー: {result.error_code} - {result.error_message}")
    
    print("\n" + "=" * 50)
    print("🎉 統合テスト完了!")
    return True

def create_debug_chat():
    """デバッグ用チャットインターフェース"""
    print("\n💬 ViszAGI Debug Chat (終了: 'quit' または 'exit')")
    print("-" * 50)
    
    integration = ViszAGIIntegration()
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                print("👋 デバッグチャットを終了します")
                break
            
            if not user_input:
                continue
            
            print("🤖 ViszAGI: 処理中...")
            result = integration.process_message(user_input)
            
            if result.ok:
                print(f"🤖 ViszAGI: {result.reply_text}")
            else:
                print(f"❌ エラー: {result.error_code} - {result.error_message}")
                
        except KeyboardInterrupt:
            print("\n👋 デバッグチャットを終了します")
            break
        except Exception as e:
            print(f"❌ 予期せぬエラー: {e}")

def main():
    """メイン実行"""
    import time
    
    print("🚀 ViszAGI-ViszBot 統合修復プログラム")
    print("Bootstrap Specに基づいた実装")
    print("=" * 50)
    
    # 統合テスト実行
    if test_integration():
        print("\n✅ 統合修復成功! ViszAGIとViszBotの接続が完了しました。")
        
        # デバッグチャット起動
        create_debug_chat()
    else:
        print("\n❌ 統合修復失敗。設定を確認してください。")

if __name__ == "__main__":
    main()
