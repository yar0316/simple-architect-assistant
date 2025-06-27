# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 基本方針

- **言語**: 常に日本語で応答します。
- **指示の厳守**: ユーザーの指示に正確に従います。指示されていない変更（特にUI/UX、技術スタックのバージョン）は行いません。変更が必要な場合は、必ず理由を添えて提案し、承認を得てから実行します。
- **思考プロセス**: 作業に着手する前に、思考プロセス（Plan）を簡潔に提示し、ユーザーの承認を得てから実行します。
- **既存コードの尊重**: 新しいコードを追加・変更する際は、必ず既存のファイル構成、コーディングスタイル、命名規則を踏襲します。

## プロジェクト概要

**Simple Architect Assistant** - AWS Bedrock (Claude 3.7 Sonnet) とMCP (Model Context Protocol) サーバーを活用したAWSインフラ設計支援のStreamlitウェブアプリケーション。チャット形式でAWSアーキテクチャ提案、コスト計算、Terraformコード生成を支援します。

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
- **AIモデル**: AWS Bedrock経由のClaude 3.7 Sonnet (MODEL_ID: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`)
- **プロンプト**: `src/prompts/` ディレクトリに分離されたシステムプロンプト

### 重要ファイル
- `src/app.py`: チャットインターフェースとAWS Bedrock統合のメインStreamlitアプリケーション
- `src/prompts/solution_architect_system_prompt.txt`: AWSソリューションアーキテクトとしてのAIロールを定義するシステムプロンプト
- `requirements.txt`: Python依存関係 (streamlit, boto3)

### アプリケーションフロー
1. ユーザーがチャットインターフェースでAWSインフラ要件を入力
2. システムがファイルからAWSソリューションアーキテクトプロンプトを読み込み
3. ストリーミングレスポンスでAWS Bedrock Claude 3.7 Sonnetにリクエスト送信
4. AIがWell-Architected Frameworkに従ったAWSアーキテクチャ推奨事項を提供
5. レスポンスにはサービス推奨、コスト考慮事項、セキュリティベストプラクティスが含まれる

### 計画されたMCP統合
アプリケーションは機能強化のためAWS MCP Serversとの統合を想定:
- **AWS Documentation MCP**: 最新のベストプラクティスとサービス情報
- **Cost Analysis MCP**: リアルタイム料金計算
- **Terraform MCP**: Infrastructure as Code生成
- **Core MCP**: ファイル操作とテンプレート管理

### セッション管理
- Streamlitセッション状態でのチャット履歴維持
- リアルタイム更新でのストリーミングレスポンス
- AWSサービス障害に対するエラーハンドリング

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

### 将来の拡張予定
- コスト最適化のためのプロンプトキャッシュ（60-90%コスト削減目標）
- Terraformコード生成機能
- アーキテクチャ図生成
- マルチ環境サポート（dev/prod）