# katala_trading — BitFlyer BTC Trading System

3層構造のBTC取引システム + Katala KS/KCS統合

## アーキテクチャ

```
katala_trading/
├── __init__.py              # Package (v0.1.0)
├── bitflyer_client.py       # BitFlyer REST API クライアント
├── data_collector.py        # 履歴データ収集 + OHLCV構築
├── strategy_layer1_sfd.py   # Layer 1: SFD裁定取引
├── strategy_layer2_trend.py # Layer 2: トレンドフォロー (200MA)
├── strategy_layer3_event.py # Layer 3: イベントリスク管理
├── backtest_engine.py       # バックテストフレームワーク
├── ks_trading_bridge.py     # Katala KS42c/KCS-2a 統合
└── trading_bot.py           # メインオーケストレーター
```

## 3層戦略

### Layer 1: SFD裁定 (`strategy_layer1_sfd.py`)
- BTC_JPY vs FX_BTC_JPY の乖離率を監視
- |乖離率| > 5.5% でエントリー → 収束狙い
- Kelly基準でポジションサイジング
- エグジット: 乖離率 < 2% or ストップロス

### Layer 2: トレンドフォロー (`strategy_layer2_trend.py`)
- 200日MA上 → ロングバイアス
- エントリートリガー: ゴールデンクロス / RSI<30 / 出来高確認
- エグジット: 200MA下を2日連続
- リスク: 1トレード2%、ストップ-5%

### Layer 3: イベントリスク (`strategy_layer3_event.py`)
- FOMC/BOJ前24時間でポジション50%削減
- ATRスパイク(3×20日平均)で自動削減
- イベント後24時間クールダウン

## Katala統合 (`ks_trading_bridge.py`)

取引仮説をKatala Claimに変換してKS42cで検証:

```python
from katala_trading.ks_trading_bridge import KSTradingBridge

bridge = KSTradingBridge()

# SFD収束仮説
signal = bridge.process_sfd_signal(
    divergence_pct=6.2,
    base_action="short_fx",
    base_confidence=0.75,
)
print(f"Final confidence: {signal.final_confidence}")
print(f"Design intent: {signal.verdicts[0].design_intent}")
```

- **KS42c**: Claim検証 → 信頼度スコア
- **KCS-2a pattern**: 取引パターンの設計意図を逆推論
- **KS40b consistency**: 複数インジケーターの一貫性チェック

## セットアップ

```bash
# 環境変数 (本番のみ)
export BITFLYER_API_KEY="your_key"
export BITFLYER_API_SECRET="your_secret"

# データ収集
cd /Users/nicolas/work/katala/src
python -m katala_trading.data_collector

# バックテスト実行
python -m katala_trading.backtest_engine

# ペーパートレード (デフォルト)
python -m katala_trading.trading_bot

# ライブトレード
python -m katala_trading.trading_bot --live
```

## バックテスト実行

```bash
python -m katala_trading.backtest_engine
```

出力例:
```
============================================================
  BACKTEST RESULTS SUMMARY
============================================================
  Strategy        Return%  Sharpe   MaxDD%  WinRate     PF  Trades
  -------------- -------- ------- ------- -------- ------ -------
  L1 (SFD)          12.3%    1.24    8.2%    65.0%   1.89     142
  L2 (Trend)         8.7%    0.98   15.3%    58.0%   1.45      23
  L1+L2             20.8%    1.51    9.7%    62.5%   1.67     165
  L1+L2+L3          18.2%    1.73    6.1%    63.0%   1.82     165
============================================================
```

## データ

```
/Users/nicolas/work/katala/data/btc/
├── spot_1h.parquet      # BTC_JPY 1時間足
├── fx_1h.parquet        # FX_BTC_JPY 1時間足
├── spot_1d.parquet      # BTC_JPY 日足
├── sfd_1h.parquet       # SFD乖離率時系列
├── fear_greed.parquet   # Fear & Greed指数
├── equity_curves.json   # バックテスト損益曲線
└── logs/
    ├── bot_YYYYMMDD.log  # ボットログ
    └── trades.jsonl      # 取引ジャーナル
```

## 注意事項

- **通貨**: 全てJPY建て (bitFlyer Japan)
- **時刻**: 全てJST (Asia/Tokyo)
- **SFD**: bitFlyer独自のペナルティ制度（乖離率>5%で課金）
- **APIキー**: 環境変数必須、ハードコード禁止
- **ライブモード**: `--live`フラグ必須 + 手動確認

## 依存関係

```
pandas >= 3.0.0
numpy >= 2.4.2
pandas_ta >= 0.4.71b
requests
websockets (optional, polling fallback)
```

---

Design: Nicolas Ogoshi / Youta Hilono  
Implementation: Shirokuma (OpenClaw AI)  
Version: 0.1.0
