# Kani API Client

Katala-Claw bridge mediation API クライアント。再試行ロジック、タイムアウト処理、モックデータフォールバックを実装。

## 使用方法

### 基本的な使用

```typescript
import { kaniClient, getMediationData } from '@/lib/kani';

// データを取得して調停リクエストを実行
const data = await getMediationData('user-a-id', 'user-b-id', {
  dwellTime: 45,
  interactions: 3,
  hasInteracted: true,
});

const result = await kaniClient.mediate(data);
console.log('Mediation Score:', result.mediationScore);
```

### カスタム設定

```typescript
import { KaniClient } from '@/lib/kani';

const client = new KaniClient({
  baseUrl: 'http://100.77.205.126:3000',
  timeout: 10000, // 10秒
  maxRetries: 5,
  retryDelay: 2000, // 2秒
  useMockData: false,
});

const response = await client.mediate({
  identityA: myIdentityA,
  identityB: myIdentityB,
  xParams: myXParams,
});
```

### モックデータを使用

```typescript
import { KaniClient } from '@/lib/kani';

const client = new KaniClient({
  useMockData: true,
});

// 常にモックデータを返す
const response = await client.mediate(request);
```

### ヘルスチェック

```typescript
import { kaniClient } from '@/lib/kani';

const isHealthy = await kaniClient.healthCheck();
console.log('Kani API Status:', isHealthy ? 'OK' : 'Down');
```

## API エンドポイント

### POST /api/kani

調停リクエストを実行。

**Request Body:**
```json
{
  "identityA": { /* 16 dimensions */ },
  "identityB": { /* 16 dimensions */ },
  "xParams": {
    "dwellTimeSeconds": 30,
    "shareVelocity": 0.5,
    "reciprocalInteraction": false
  }
}
```

**Response:**
```json
{
  "mediationScore": 78.5,
  "synergyScore": 82.3,
  "recommendations": [
    "共通の価値観を重視したコミュニケーション",
    "相互理解を深めるための対話時間の確保"
  ],
  "timestamp": "2026-02-14T12:00:00.000Z",
  "status": "success"
}
```

### GET /api/kani

ヘルスチェック。

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-14T12:00:00.000Z"
}
```

## フォールバック動作

1. 最大再試行回数まで Kani API への接続を試行
2. 指数バックオフを使用して再試行間隔を調整
3. 全ての再試行が失敗した場合、自動的にモックデータを返す
4. タイムアウトは 5 秒（設定可能）

## 設定項目

| パラメータ | デフォルト | 説明 |
|----------|-----------|------|
| `baseUrl` | `http://100.77.205.126:3000` | Kani API のベース URL |
| `timeout` | `5000` | リクエストタイムアウト (ミリ秒) |
| `maxRetries` | `3` | 最大再試行回数 |
| `retryDelay` | `1000` | 再試行の初期遅延 (ミリ秒) |
| `useMockData` | `false` | 常にモックデータを使用 |

## データプロバイダー

### getIdentityByUserId

ユーザーIDからidentityを取得（TODO: データベース連携）

### getCurrentUserIdentity

現在のユーザーのidentityを取得（TODO: 認証システム連携）

### generateXParams

インタラクションコンテキストからX-Algorithmパラメータを生成

### getMediationData

調停リクエストに必要な全てのデータを一度に取得
