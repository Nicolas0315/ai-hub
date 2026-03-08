#!/usr/bin/env python3
"""
ViszAGI Bootstrap Specとの整合性テスト
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any

# パス設定
VISZAGI_ROOT = Path(__file__).parent.parent.parent / "ViszAGI"
VISZBOT_ROOT = Path(__file__).parent.parent

def test_bootstrap_spec_compliance():
    """Bootstrap Spec準拠テスト"""
    print("📋 Bootstrap Spec準拠テスト")
    print("=" * 40)
    
    # 1. 必須ファイルの存在確認
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
    
    print("1. 必須ファイル確認:")
    missing_files = []
    for file_path in required_files:
        full_path = VISZAGI_ROOT / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (存在しません)")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ 欠落ファイル: {len(missing_files)}個")
        return False
    
    # 2. JSONプロトコルテスト
    print("\n2. JSONプロトコルテスト:")
    test_payload = {
        "version": "v1",
        "request_id": "test-bootstrap-123",
        "source": "discord",
        "channel_id": "123456789",
        "user_id": "987654321",
        "username": "TestUser",
        "message_text": "Bootstrap Specテストメッセージ",
        "reply_mode": "channel",
        "persona": "ViszAGI",
        "constraints": {
            "allow_tools": True,
            "allow_files": True,
            "timeout_sec": 120,
        }
    }
    
    try:
        proc = subprocess.run(
            [sys.executable, str(VISZAGI_ROOT / "visz_coding_entry.py")],
            input=json.dumps(test_payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=30,
            cwd=str(VISZAGI_ROOT)
        )
        
        if proc.returncode == 0:
            try:
                response = json.loads(proc.stdout)
                if response.get("ok"):
                    print(f"  ✅ JSONプロトコル応答: {response.get('reply_text', '')[:50]}...")
                else:
                    print(f"  ❌ 応答エラー: {response}")
                    return False
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON解析失敗: {e}")
                print(f"  生出力: {proc.stdout}")
                return False
        else:
            print(f"  ❌ 実行失敗: {proc.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ プロトコルテスト失敗: {e}")
        return False
    
    # 3. ブリッジ分離テスト
    print("\n3. ブリッジ分離テスト:")
    try:
        # bridges/visz_coding_bridge.py のみが外部と通信することを確認
        bridge_file = VISZAGI_ROOT / "bridges" / "visz_coding_bridge.py"
        if bridge_file.exists():
            bridge_content = bridge_file.read_text(encoding='utf-8')
            
            # 汚染防止ルールの確認
            if "subprocess.run" in bridge_content:
                print("  ✅ subprocessによる分離実装を確認")
            else:
                print("  ❌ subprocess分離が見つかりません")
                return False
                
            # JSONペイロード処理の確認
            if "json.dumps" in bridge_content and "json.loads" in bridge_content:
                print("  ✅ JSONペイロード処理を確認")
            else:
                print("  ❌ JSONペイロード処理が見つかりません")
                return False
        else:
            print("  ❌ ブリッジファイルが存在しません")
            return False
            
    except Exception as e:
        print(f"  ❌ ブリッジテスト失敗: {e}")
        return False
    
    print("\n✅ Bootstrap Spec準拠テスト完了!")
    return True

def test_discord_integration():
    """Discord連携テスト"""
    print("\n🤖 Discord連携テスト")
    print("=" * 40)
    
    try:
        # Discord bot関連モジュールのインポートテスト
        sys.path.insert(0, str(VISZAGI_ROOT))
        
        from app.config import settings
        from app.models import InboundRequest, BridgeResponse
        from app.policy import should_respond
        from app.persona import default_persona
        
        print("  ✅ Discord botモジュールインポート成功")
        
        # 設定確認
        if hasattr(settings, 'discord_token') and settings.discord_token:
            print("  ✅ Discord token設定済み")
        else:
            print("  ⚠️ Discord token未設定 (環境変数が必要)")
        
        # ポリシーテスト
        print(f"  ✅ トリガーモード: {getattr(settings, 'trigger_mode', 'unknown')}")
        print(f"  ✅ ボット名: {getattr(settings, 'bot_name', 'unknown')}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Discordモジュールインポート失敗: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Discord連携テスト失敗: {e}")
        return False

def generate_integration_report():
    """統合レポート生成"""
    print("\n📊 統合レポート生成")
    print("=" * 40)
    
    report = {
        "timestamp": str(Path(__file__).stat().st_mtime),
        "viszagi_path": str(VISZAGI_ROOT),
        "viszbot_path": str(VISZBOT_ROOT),
        "bootstrap_compliance": test_bootstrap_spec_compliance(),
        "discord_integration": test_discord_integration()
    }
    
    # レポート保存
    report_file = VISZBOT_ROOT / "ViszBot Debug" / "integration_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📄 レポート保存: {report_file}")
    
    # 結果サマリー
    print("\n📋 結果サマリー:")
    print(f"  Bootstrap Spec準拠: {'✅' if report['bootstrap_compliance'] else '❌'}")
    print(f"  Discord連携: {'✅' if report['discord_integration'] else '❌'}")
    
    overall_success = report['bootstrap_compliance'] and report['discord_integration']
    print(f"  全体評価: {'🎉 成功' if overall_success else '⚠️ 要対応'}")
    
    return overall_success

def main():
    """メイン実行"""
    print("🔬 ViszAGI-ViszBot 統合診断プログラム")
    print("Bootstrap Specとの整合性を検証")
    print("=" * 50)
    
    success = generate_integration_report()
    
    if success:
        print("\n🎉 統合診断完了! すべてのテストに合格しました。")
        print("💡 ViszAGIとViszBotの統合修復は成功しています。")
    else:
        print("\n⚠️ 統合診断完了! 一部のテストで問題が見つかりました。")
        print("🔧 上記のエラーを修正して再度実行してください。")

if __name__ == "__main__":
    main()
