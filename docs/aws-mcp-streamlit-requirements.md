# Simple Architect Assistant - Streamlitアプリ要件定義書

## 1. プロジェクト概要

### 1.1 プロジェクト名

**Simple Architect Assistant** - AWSインフラ構成支援ツール

### 1.2 目的

AWS MCP Serversを活用し、AWSインフラの構成検討からコード化まで一貫して支援するWebアプリケーションの開発

### 1.3 対象ユーザー

- 個人開発者
- 小規模チームの開発者
- AWSアーキテクチャ検討を効率化したいエンジニア

### 1.4 技術スタック

- **フロントエンド**: Streamlit
- **バックエンド**: Python 3.12+
- **AI/LLM**: Amazon Bedrock (Claude 3.7 Sonnet)
- **プロンプトキャッシュ**: Amazon Bedrock Prompt Caching（コスト最適化）
- **MCP統合**: AWS MCP Servers
- **ホスティング**: AWS App Runner（将来）

## 2. 機能要件

### 2.1 Phase 1: 基本機能（MVP）

#### 2.1.1 機能1: AWSインフラ構成提案とコスト計算

**概要**: チャット形式でAWSアーキテクチャの提案と概算コストを提供

**詳細機能**:

- ユーザー要件の自然言語入力
- AWS Documentation MCPによる最新ベストプラクティス参照
- Cost Analysis MCPによるリアルタイム料金計算
- 複数の構成パターン提案
- コスト比較表の表示

**入力例**:

```
「月間1万ユーザーのWebアプリケーションを構築したいです。
データベースはPostgreSQLを使用し、高可用性が必要です。」
```

**出力例**:

- 推奨アーキテクチャ説明
- 使用サービス一覧（ALB, ECS Fargate, RDS等）
- 月額概算費用（$XXX - $XXX）
- 代替案の提示

#### 2.1.2 機能2: Terraformコード生成

**概要**: チャット形式の指示からTerraformコードを自動生成

**詳細機能**:

- 構成要件の自然言語入力
- AWS Terraform MCPによるベストプラクティス適用
- モジュール化されたコード生成
- ファイル構成の自動提案
- 生成コードのダウンロード機能

**入力例**:

```
「ALB + ECS Fargate + RDS PostgreSQLの構成で、
開発・本番環境を分けたTerraformコードを作成してください」
```

**出力例**:

```
terraform/
├── environments/
│   ├── dev/
│   └── prod/
├── modules/
│   ├── vpc/
│   ├── ecs/
│   └── rds/
└── variables.tf
```

### 2.2 Phase 2: 拡張機能（将来実装）

#### 2.2.1 機能3: 構成図自動生成

**概要**: XML/PlantUMLによるアーキテクチャ図の自動生成

**詳細機能**:

- アーキテクチャの自動図式化
- AWS公式アイコンの使用
- 複数フォーマット対応（PNG, SVG, PlantUML）
- 図の編集・カスタマイズ機能

## 3. 非機能要件

### 3.1 性能要件

- チャット応答時間: 30秒以内（プロンプトキャッシュ使用時は15秒以内）
- ファイル生成時間: 60秒以内（プロンプトキャッシュ使用時は30秒以内）
- 同時ユーザー数: 10名程度（個人利用想定）
- **プロンプトキャッシュ効率**: キャッシュヒット率70%以上を目標

### 3.2 セキュリティ要件

- AWS SSOによる認証
- 機密情報の非保存
- セッション管理の実装
- **プロンプトキャッシュのセキュリティ**: アカウント固有キャッシュの利用

### 3.3 コスト効率要件

- **プロンプトキャッシュ活用**: 最大90%のコスト削減を目標
- **キャッシュ対象**: システムプロンプト、AWS料金情報、ドキュメント参照
- **キャッシュ有効期間**: 5分間（アクセス毎にリセット）

### 3.4 可用性要件

- 開発期間中: ローカル実行（99%）
- 本格運用: App Runner（99.9%目標）

## 4. MCP Server活用方針とプロンプトキャッシュ戦略

### 4.1 プロンプトキャッシュ最適化アーキテクチャ

**キャッシュ対象の分類**:

- **固定コンテキスト**: システムプロンプト、AWS Well-Architected原則
- **半固定コンテキスト**: 料金情報、ベストプラクティス文書
- **動的コンテキスト**: ユーザーの具体的な要件（キャッシュ対象外）

**キャッシュ戦略**:

```python
# キャッシュポイント設定例
cache_structure = {
    "system_prompt": "AWS専門家としての基本指示",
    "pricing_data": "EC2, RDS, S3等の料金情報", 
    "best_practices": "セキュリティとコスト最適化指針",
    "cache_checkpoint": "ここまでをキャッシュ",
    "user_query": "動的なユーザー要求"
}
```

### 4.2 AWS Documentation MCP

**活用場面**:

- 最新のAWSサービス情報取得
- ベストプラクティスの参照
- サービス制限・前提条件の確認

**実装方針**:

```python
# プロンプトキャッシュ対応のドキュメント検索
async def search_with_cache(query):
    # キャッシュされた基本情報の上に追加検索
    docs = await aws_documentation_mcp.search_documentation(
        query="ECS Fargate best practices"
    )
    
    # 検索結果をキャッシュ対象として追加
    cached_context = build_cached_context(docs)
    return cached_context
```

### 4.3 AWS Labs Cost Analysis MCP

**活用場面**:

- リアルタイム料金計算
- コスト最適化提案
- 料金比較レポート生成

**プロンプトキャッシュ最適化**:

```python
# 料金情報のキャッシュ化
class CachedCostAnalyzer:
    def __init__(self):
        self.cached_pricing = {}  # よく使用される料金をキャッシュ
    
    async def get_cached_pricing(self, services):
        # 基本料金情報をキャッシュコンテキストに含める
        pricing_context = await self.build_pricing_cache(services)
        
        # 動的計算はキャッシュ後に実行
        report = await cost_analysis_mcp.generate_cost_report(
            cached_context=pricing_context,
            dynamic_usage=user_requirements
        )
        return report
```

### 4.4 AWS Terraform MCP

**活用場面**:

- Terraformコードテンプレート生成
- ベストプラクティス適用
- モジュール構造の最適化

**プロンプトキャッシュ活用**:

```python
# Terraform生成のキャッシュ最適化
class CachedTerraformGenerator:
    def __init__(self):
        self.terraform_templates = self.load_cached_templates()
    
    def load_cached_templates(self):
        # 基本的なTerraformパターンをキャッシュ
        return {
            "system_prompt": "Terraformベストプラクティス",
            "common_modules": "VPC, ECS, RDS等の標準モジュール",
            "security_patterns": "セキュリティグループ設定パターン"
        }
```

### 4.5 Core MCP

**活用場面**:

- ファイル操作
- テンプレート管理
- 設定ファイル処理

**実装方針**:

```python
# ファイル出力
await core_mcp.write_file(
    path="terraform/main.tf",
    content=generated_terraform_code
)
```

## 5. UI/UX設計

### 5.1 画面構成

#### 5.1.1 メインページレイアウト

```
┌─────────────────────────────────┐
│ Simple Architect Assistant      │
├─────────────────────────────────┤
│ [サイドバー]     [メインエリア]    │
│ - 機能選択      - チャット画面     │
│ - 設定         - 結果表示       │
│ - キャッシュ状況 - ファイル出力     │
│ - 履歴         - コスト情報      │
└─────────────────────────────────┘
```

#### 5.1.2 サイドバー機能

- **機能選択**:
  - 💬 構成提案＆コスト計算
  - 🔧 Terraformコード生成
  - 📊 構成図生成（Phase 2）
- **設定**:
  - AWSプロファイル選択
  - 出力形式設定
  - プロンプトキャッシュ設定
- **キャッシュ状況**:
  - キャッシュヒット率表示
  - トークン使用量統計
  - コスト削減効果
- **履歴**:
  - 過去のチャット履歴
  - 生成ファイル一覧

#### 5.1.3 メインエリア機能

- **チャット画面**:
  - ユーザー入力エリア
  - AI応答表示
  - 進行状況インジケーター
- **結果表示**:
  - コスト計算結果
  - アーキテクチャ説明
  - 推奨事項一覧
  - **キャッシュ効果表示**（トークン削減率、レスポンス改善率）
- **ファイル出力**:
  - 生成コードのプレビュー
  - ダウンロードボタン
  - ZIP形式での一括ダウンロード

### 5.2 ユーザーフロー

#### 5.2.1 構成提案＆コスト計算フロー

```
1. 要件入力 → 2. MCP処理 → 3. 結果表示 → 4. 詳細確認
   ↓              ↓            ↓            ↓
「Webアプリ構築」 → ドキュメント参照 → 構成案提示 → コスト詳細
                 料金計算
```

#### 5.2.2 Terraformコード生成フロー

```
1. 構成指定 → 2. コード生成 → 3. プレビュー → 4. ダウンロード
   ↓            ↓            ↓            ↓
「ECS+RDS」 → Terraform MCP → コード表示 → ファイル出力
```

## 6. 開発計画

### 6.1 Phase 1 開発スケジュール（4-6週間）

#### Week 1-2: 基盤開発

- Streamlitアプリの基本構造
- AWS SSO認証の統合
- MCP Server接続の実装
- **プロンプトキャッシュ機能の実装**

#### Week 3-4: 機能1実装

- チャット機能の実装
- AWS Documentation MCP統合
- Cost Analysis MCP統合
- 基本的なUI実装

#### Week 5-6: 機能2実装

- Terraform MCP統合
- ファイル生成・ダウンロード機能
- エラーハンドリング
- テスト・デバッグ

### 6.2 Phase 2 開発スケジュール（将来）

- 構成図生成機能
- UI/UXの改善
- パフォーマンス最適化
- App Runnerへのデプロイ

## 7. 技術的考慮事項

### 7.1 MCP Server統合の課題

- **非同期処理**: Streamlitでの非同期MCP呼び出し
- **エラーハンドリング**: MCP接続失敗時の対応
- **レート制限**: API呼び出し頻度の制限
- **プロンプトキャッシュ管理**: キャッシュミス時の対応戦略

### 7.2 セッション管理

- チャット履歴の保持
- 生成ファイルの一時保存
- ユーザー設定の永続化

### 7.3 パフォーマンス最適化

- MCP応答の並列処理
- **プロンプトキャッシュの効果的活用**
- 結果のキャッシュ機能
- 大量データの分割処理
- **キャッシュヒット率の最大化**

## 8. 成功指標

### 8.1 Phase 1目標

- 基本機能の動作確認
- 10件以上の構成提案実績
- Terraformコード生成の成功率 80%以上
- **プロンプトキャッシュによるコスト削減 60%以上**

### 8.2 長期目標

- 月間利用回数: 100回以上
- ユーザー満足度: 4.0/5.0以上
- 生成コードの品質向上
- **プロンプトキャッシュ効率 80%以上維持**

## 9. リスクと対策

### 9.1 技術的リスク

- **MCP Server不安定性**: フォールバック機能の実装
- **Bedrock料金**: 使用量監視とアラート設定（プロンプトキャッシュで軽減）
- **認証エラー**: 詳細なエラーガイダンス
- **キャッシュミス**: キャッシュ戦略の最適化とフォールバック

### 9.2 運用リスク

- **ドキュメント更新遅れ**: 定期的なMCP Server更新
- **ユーザビリティ**: 継続的なUI改善
