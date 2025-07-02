# Simple Architect Assistant

AIを活用してAWSのインフラ構成設計を支援するWebアプリケーションです。
Streamlitで構築されており、AWS BedrockとMCP Serverを利用します。

## 前提条件

- Python 3.9+
- [uv](https://github.com/astral-sh/uv)

## 利用方法

### 1. 仮想環境のセットアップ

このプロジェクトでは `uv` をパッケージ管理に利用します。はじめに、仮想環境を作成し、有効化してください。

```bash
# .venv ディレクトリに仮想環境を作成します
uv venv
```

仮想環境を有効化します。

**Windows (コマンドプロンプト) の場合:**

```cmd
.venv\Scripts\activate
```

**Windows (PowerShell) の場合:**

```powershell
.venv\Scripts\Activate.ps1
```

**macOS/Linux の場合:**

```bash
source .venv/bin/activate
```

### 2. 依存関係のインストール

仮想環境を有効化した状態で、`uv` を使って必要なPythonパッケージをインストールします。

```bash
uv pip install -r requirements.txt
```

### 3. 設定

このアプリケーションは、設定にStreamlitのSecrets管理機能を利用します。

1. **設定ファイルの確認:**
    設定ファイルは `.streamlit/secrets.toml` にあります。

2. **設定ファイルの編集:**
    AWSプロファイルとリージョン情報をファイルに記述してください。`default` 以外のプロファイルを使用する場合は、適宜修正してください。

    ```toml
    # .streamlit/secrets.toml

    [aws]
    profile = "default"
    region = "us-east-1"
    ```

## アプリケーションの実行

プロジェクトのルートディレクトリから以下のコマンドを実行して、Streamlitアプリケーションを起動します。

```bash
streamlit run src/app.py
```

ブラウザで `http://localhost:8501` にアクセスすると、アプリケーションが表示されます。

## MCP (Model Context Protocol) 統合

このアプリケーションは AWS の公式 MCP サーバーと統合して、より高度なAWS構成支援を提供します。

### MCP統合の前提条件

1. **uvx のインストール**
   ```bash
   pip install uvx
   ```

2. **AWS認証情報の設定**
   ```bash
   aws configure
   ```

### MCP設定のカスタマイズ

MCP サーバーの設定は `config/mcp_config.json` で管理されています。詳細な設定方法については [MCP セットアップガイド](docs/mcp_setup.md) を参照してください。

**重要**: MCP統合が利用できない場合でも、アプリケーションはフォールバックモードで動作し、基本的な機能は継続して利用できます。

## 機能

このアプリケーションは複数のページで構成されており、**AI エージェントモード**がデフォルトで有効化されています：

### 🤖 AI エージェントモード（LangChain ReAct Agent）

**自律的なAI Assistant**がユーザーの要求を理解し、適切なツールを選択・実行して包括的な回答を提供します：

- **自動的なツール選択**: 質問内容に応じて最適なMCPツールを自動選択
- **思考プロセスの可視化**: エージェントの判断過程をリアルタイム表示
- **継続的な学習**: 過去の対話履歴を活用した一貫性のある提案
- **無限ループ防止**: 効率的な情報収集で適切なタイミングでの回答生成
- **パフォーマンス最適化**: リクエストキャッシュによる50-80%の応答時間短縮

### AWS構成提案チャット

- **AWS Well-Architected Framework**に基づいた構成提案
- チャット形式での要件ヒアリング
- コスト効率とセキュリティを考慮した推奨構成
- **エージェント特化ツール**: 
  - AWS Documentation検索
  - Core MCP ガイダンス
  - **コスト分析** (このページ専用)

### Terraformコード生成

- AWS Terraformコードの自動生成
- モジュール化されたベストプラクティス準拠のコード
- 複数環境対応（dev/prod/staging）
- セキュリティとコスト最適化を考慮した設定
- **エージェント特化ツール**: 
  - AWS Documentation検索
  - Core MCP ガイダンス
  - **Terraformコード生成** (このページ専用)

### ページ間連携

- AWS構成提案からTerraformコード生成への自動引き継ぎ
- セッション状態の適切な管理
- Streamlitの左サイドバーからページ切り替え可能

### 手動モード

エージェントモードを無効化した場合は、従来の手動ツール呼び出しモードで動作します。

## トラブルシューティング

### MCP関連のエラー

- **404 Not Found エラー**: [MCP セットアップガイド](docs/mcp_setup.md) の「トラブルシューティング」セクションを参照
- **フォールバックモード**: MCP統合が利用できない場合でも基本機能は動作します
- **設定の調整**: `config/mcp_config.json` で各プラットフォームに応じた設定を調整可能
