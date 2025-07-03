# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 基本方針

- **言語**: 常に日本語で応答します。
- **指示の厳守**: ユーザーの指示に正確に従います。指示されていない変更（特にUI/UX、技術スタックのバージョン）は行いません。変更が必要な場合は、必ず理由を添えて提案し、承認を得てから実行します。
- **思考プロセス**: 作業に着手する前に、思考プロセス（Plan）を簡潔に提示し、ユーザーの承認を得てから実行します。
- **既存コードの尊重**: 新しいコードを追加・変更する際は、必ず既存のファイル構成、コーディングスタイル、命名規則を踏襲します。

## 【MUST】Gemini活用

### 三位一体の開発原則

ユーザーの**意思決定**、Claudeの**分析と実行**、Geminiの**検証と助言**を組み合わせ、開発の質と速度を最大化する：

- **ユーザー**：プロジェクトの目的・要件・最終ゴールを定義し、最終的な意思決定を行う**意思決定者**
  - 反面、具体的なコーディングや詳細な計画を立てる力、タスク管理能力ははありません。
- **Claude**：高度な計画力・高品質な実装・リファクタリング・ファイル操作・タスク管理を担う**実行者**
  - 指示に対して忠実に、順序立てて実行する能力はありますが、意志がなく、思い込みは勘違いも多く、思考力は少し劣ります。
- **Gemini**：深いコード理解・Web検索 (Google検索) による最新情報へのアクセス・多角的な視点からの助言・技術的検証を行う**助言者**
  - プロジェクトのコードと、インターネット上の膨大な情報を整理し、的確な助言を与えてくれますが、実行力はありません。

### 実践ガイド

- **ユーザーの要求を受けたら即座に`gemini -p <質問内容>`で壁打ち**を必ず実施
- Geminiの意見を鵜呑みにせず、1意見として判断。聞き方を変えて多角的な意見を抽出
- 基本的にGeminiは検索を絡めて利用すること
- Claude Code内蔵のWebSearchツールは、Geminiがエラーで検索できないとき以外に使用しない
- Geminiがエラーの場合は、聞き方を工夫してリトライ：
  - ファイル名や実行コマンドを渡す（Geminiがコマンドを実行可能）
  - 複数回に分割して聞く

### 主要な活用場面

1. **実現不可能な依頼**: Claude Codeでは実現できない要求への対処 (例: `今日の天気は？`)
2. **前提確認**: ユーザー、Claude自身に思い込みや勘違い、過信がないかどうか逐一確認 (例: `この前提は正しいか？`）
3. **技術調査**: 最新情報・エラー解決・ドキュメント検索・調査方法の確認（例: `Rails 7.2の新機能を調べて`）
4. **設計検証**: アーキテクチャ・実装方針の妥当性確認（例: `この設計パターンは適切か？`）
5. **コードレビュー**: 品質・保守性・パフォーマンスの評価（例: `このコードの改善点は？`）
6. **計画立案**: タスクの実行計画レビュー・改善提案（例: `この実装計画の問題点は？`）
7. **技術選定**: ライブラリ・手法の比較検討 （例: `このライブラリは他と比べてどうか？`）

## プロジェクト概要

**Simple Architect Assistant** - AWS Bedrock (Claude 4 Sonnet) とMCP (Model Context Protocol) サーバーを活用したAWSインフラ設計支援のStreamlitウェブアプリケーション。**LangChain ReAct Agent**による自律的なAI Assistant機能を備え、チャット形式でAWSアーキテクチャ提案、コスト計算、Terraformコード生成を支援します。

## 開発コマンド

### 環境セットアップ

```bash
# uvを使用して仮想環境を作成
uv venv

# 仮想環境を有効化
# Windows (コマンドプロンプト): .venv\Scripts\activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

# 依存関係をインストール
uv pip install -r requirements.txt
```

### アプリケーション実行

```bash
# Streamlit開発サーバー起動
streamlit run src/app.py
```

### 設定

設定ファイルのセットアップ:

```bash
# 設定テンプレートをコピー
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# 設定ファイルを編集してAWSプロファイルとリージョンを設定
```

設定例 (`.streamlit/secrets.toml`):

```toml
[aws]
profile = "default"  # 使用するAWSプロファイル名
region = "us-east-1"  # Bedrockが利用可能なリージョン
```

**セキュリティ注意事項:**

- `.streamlit/secrets.toml` は `.gitignore` で除外されているため、Gitで追跡されません
- 機密情報を含むため、このファイルを公開リポジトリにコミットしないでください
- 各開発者は独自の設定ファイルを作成する必要があります

## アーキテクチャ

### 主要コンポーネント

- **フロントエンド**: チャットベースのStreamlit WebUI
- **バックエンド**: AWS Bedrock連携のPythonアプリケーション
- **AIモデル**: AWS Bedrock経由のClaude 4 Sonnet (MODEL_ID: `us.anthropic.claude-sonnet-4-20250514-v1:0`)
- **AI Agent**: LangChain ReAct Agent による自律的なツール選択・実行
- **プロンプト**: `src/prompts/` ディレクトリに分離されたシステムプロンプト
- **MCP統合**: Model Context Protocol による拡張ツール機能

### 重要ファイル

- `src/app.py`: チャットインターフェースとAWS Bedrock統合のメインStreamlitアプリケーション
- `src/pages/aws_chat.py`: AWS構成提案チャットページ（エージェントモード対応）
- `src/pages/terraform_generator.py`: Terraformコード生成ページ（エージェントモード対応）
- `src/langchain_integration/agent_executor.py`: LangChain ReAct Agent エグゼキューター
- `src/langchain_integration/mcp_tools.py`: ページ特化MCPツール統合
- `src/services/mcp_client.py`: MCP統合サービス（キャッシュ機能付き）
- `src/prompts/agent_system_prompt.txt`: AI Agent用システムプロンプト
- `src/prompts/solution_architect_system_prompt.txt`: AWSソリューションアーキテクト用システムプロンプト
- `requirements.txt`: Python依存関係 (streamlit, boto3, langchain)

### アプリケーションフロー

#### エージェントモード（デフォルト）

1. ユーザーがチャットインターフェースでAWSインフラ要件を入力
2. LangChain ReAct Agent が要件を分析し、必要なツールを自動選択
3. Agent が以下を実行：
   - AWS Documentation検索
   - Core MCPガイダンス取得
   - ページ特化ツール実行（コスト分析またはTerraform生成）
4. Agent がツール結果を統合し、包括的な回答を生成
5. ストリーミングレスポンスでClaude 4 Sonnetが最終回答を提供

#### 手動モード

1. ユーザーがチャットインターフェースでAWSインフラ要件を入力
2. システムがファイルからAWSソリューションアーキテクトプロンプトを読み込み
3. 事前定義されたMCPツール呼び出しで補足情報を取得
4. ストリーミングレスポンスでAWS Bedrock Claude 4 Sonnetにリクエスト送信
5. AIがWell-Architected Frameworkに従ったAWSアーキテクチャ推奨事項を提供

### MCP統合（実装済み）

アプリケーションは以下のMCP機能を統合済み：

- **AWS Documentation MCP**: 最新のベストプラクティスとサービス情報（フォールバック機能実装）
- **Cost Analysis MCP**: リアルタイム料金計算（基本機能実装）
- **Terraform MCP**: Infrastructure as Code生成（テンプレート機能実装）
- **Core MCP**: ファイル操作とテンプレート管理（基本ガイダンス実装）
- **Request Caching**: SHA256ベースのキャッシュ機能（50-80%パフォーマンス向上）
- **Page-specific Optimization**: ページ特化ツール最適化

### セッション管理

- Streamlitセッション状態でのチャット履歴維持
- LangChain Agent メモリ管理（ConversationBufferWindowMemory）
- ページ間データ連携（AWS構成→Terraform生成）
- リアルタイム更新でのストリーミングレスポンス
- AWSサービス障害に対するエラーハンドリング
- セッション状態キーの統一管理とマイグレーション機能

## 開発ノート

### コーディングスタイル

- 既存のPython規約に従う
- AWSサービス連携にはboto3を使用
- ユーザーインターフェース要素の日本語サポート維持
- システムプロンプトは日本語、日本語話者向け

### AWS統合

- プロファイルベース認証でのboto3 Session使用
- より良いユーザー体験のためのBedrockストリーミングレスポンス
- AWS認証情報とサービス問題のエラーハンドリング
- リージョン固有のBedrockクライアント設定

### 実装済み機能

- ✅ **LangChain ReAct Agent統合**: 自律的なツール選択・実行
- ✅ **MCP統合**: Model Context Protocol による拡張ツール機能
- ✅ **リクエストキャッシュ**: 50-80%パフォーマンス向上
- ✅ **Terraformコード生成機能**: 基本テンプレート実装
- ✅ **ページ特化ツール最適化**: aws_chat/terraform_generator専用ツール
- ✅ **無限ループ防止**: エージェント安定化機能
- ✅ **セッション状態管理**: ページ間連携とマイグレーション

### 将来の拡張予定

- 高度なプロンプトキャッシュ（60-90%コスト削減目標）
- アーキテクチャ図生成
- マルチ環境サポート（dev/prod）
- 実際のAWS MCP サーバー統合（現在はフォールバック機能）
