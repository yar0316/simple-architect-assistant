# MCP (Model Context Protocol) セットアップガイド

このドキュメントでは、AWS MCP サーバーの設定方法について説明します。

## 概要

Simple Architect Assistant は AWS の公式 MCP サーバーと統合して、以下の機能を提供します：

- **Core MCP Server**: プロンプト理解とAWSソリューション構築ガイダンス
- **AWS Documentation MCP Server**: AWS公式ドキュメント検索
- **Terraform MCP Server**: 高品質なTerraformコード生成

## 前提条件

### 1. uvx のインストール

MCPサーバーは `uvx` を使用して実行されます。まず `uvx` をインストールしてください：

```bash
# Python pipを使用してuvxをインストール
pip install uvx

# または、公式インストーラーを使用（Linux/Mac）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. AWS認証情報の設定

AWS MCP サーバーが AWS サービスにアクセスするため、適切な認証情報が必要です：

```bash
# AWS CLIの設定
aws configure

# または環境変数での設定
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-northeast-1
```

## MCP設定ファイル

MCPサーバーの設定は `config/mcp_config.json` で管理されています。

### デフォルト設定（Windows対応）

Windows環境での動作を優先し、以下の設定をデフォルトとしています：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "awslabs-core-mcp-server", 
        "awslabs.core-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    },
    "awslabs.aws-documentation-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "awslabs-aws-documentation-mcp-server",
        "awslabs.aws-documentation-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    },
    "awslabs.terraform-mcp-server": {
      "command": "uvx",
      "args": [
        "--from", 
        "awslabs-terraform-mcp-server",
        "awslabs.terraform-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    }
  }
}
```

**重要**: Windows環境では `--from` オプションと `.exe` 拡張子が必要です。これは[こちらの記事](https://qiita.com/revsystem/items/911999b174dc5f3cf29d)で説明されているWindows固有の要件です。

### プラットフォーム固有設定

Mac/Linux環境では、より簡潔な設定を使用できます。`platform_overrides` セクションで自動的に適用されます：

```json
{
  "platform_overrides": {
    "darwin": {
      "mcpServers": {
        "awslabs.core-mcp-server": {
          "command": "uvx",
          "args": ["awslabs.core-mcp-server@latest"]
        }
      }
    },
    "linux": {
      "mcpServers": {
        "awslabs.core-mcp-server": {
          "command": "uvx", 
          "args": ["awslabs.core-mcp-server@latest"]
        }
      }
    }
  }
}
```

## 設定のカスタマイズ

### MCPサーバーの無効化

特定のサーバーを無効にするには、`disabled` を `true` に設定します：

```json
{
  "mcpServers": {
    "awslabs.terraform-mcp-server": {
      "disabled": true
    }
  }
}
```

### ログレベルの変更

より詳細なログが必要な場合は、ログレベルを変更します：

```json
{
  "env": {
    "FASTMCP_LOG_LEVEL": "DEBUG"
  }
}
```

### Windows環境での調整

現在の設定は既にWindows環境に最適化されています。問題が発生する場合の代替設定例：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "python",
      "args": ["-m", "uvx", "--from", "awslabs-core-mcp-server", "awslabs.core-mcp-server.exe"]
    }
  }
}
```

または、uvxを直接指定する場合：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "uvx.exe",
      "args": ["--from", "awslabs-core-mcp-server", "awslabs.core-mcp-server.exe"]
    }
  }
}
```

## トラブルシューティング

### 1. 404 Not Found エラー

MCPサーバーが見つからない場合：

1. uvxが正しくインストールされているか確認
2. ネットワーク接続を確認
3. パッケージ名が正しいか確認

```bash
# uvxの動作確認
uvx --version

# MCPサーバーパッケージの確認
uvx run awslabs.core-mcp-server@latest --help
```

### 2. 権限エラー

AWS関連の権限エラーが発生する場合：

1. AWS認証情報が正しく設定されているか確認
2. 必要なIAM権限があるか確認
3. リージョン設定を確認

### 3. フォールバックモード

MCPサーバーが利用できない場合、アプリケーションは自動的にフォールバックモードで動作します：

- 基本的なAWSガイダンス機能は継続
- 静的なTerraformテンプレート提供
- エラーメッセージは最小限

## 開発者向け情報

### MCP統合の実装

`src/services/mcp_client.py` でMCP統合が実装されています：

- `MCPClientService`: メインのMCPクライアント
- `get_mcp_client()`: Streamlitセッション管理
- フォールバック機能付きエラーハンドリング

### 新しいMCPサーバーの追加

1. `config/mcp_config.json` に新しいサーバー設定を追加
2. `src/services/mcp_client.py` に対応するメソッドを実装
3. 必要に応じてUIコンポーネントを更新

### テスト

MCPサーバーの動作を個別にテストする場合：

```bash
# Core MCPサーバーのテスト
uvx run awslabs.core-mcp-server@latest

# AWS Documentation MCPサーバーのテスト
uvx run awslabs.aws-documentation-mcp-server@latest
```

## 参考資料

- [AWS MCP Servers 公式ドキュメント](https://awslabs.github.io/mcp/)
- [Model Context Protocol 仕様](https://modelcontextprotocol.io/)
- [uvx 公式ドキュメント](https://docs.astral.sh/uv/)