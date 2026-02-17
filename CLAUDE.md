# Katala - インフルエンサーツール予測モデリング

Next.js App Router + Tailwind CSS構成のインフルエンサーマッチングプラットフォーム。

## ワークフロー

1. `tasks.json`を読み込み、次の未完了タスク（IDが最小、depends_onが全完了）を見つける
2. ステータスを「進行中」に設定
3. タスクの説明に基づいて実行
4. 完了条件を確認し、ステータスを「完了」に設定、outputに結果を追加
5. **1つのタスクを完了したら終了する**

## 環境

- Node/npm、TypeScript
- テスト: vitest (npm test)
- 日本語UI

## ルール

- 一度に1つのタスクのみ処理して終了する
- tasks.json は必ず更新する
- 不明確な場合は「未完了」のまま、outputにブロッカーを記録
- コードスタイル: 既存コードに従う（DRY/KISS/YAGNI）
- git commit はConventional Commits形式
- Zodバリデーション必須
