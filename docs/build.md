# Simple Architect Assistant - ビルドガイド

## デスクトップアプリビルド手順

### 1. 環境準備

```bash
# 依存関係をインストール
uv pip install -r requirements.txt

# または pip を使用
pip install -r requirements.txt
```

### 2. ビルド実行

```bash
# 基本ビルド
python build_desktop_app.py

# カスタムビルド（例）
python build_desktop_app.py --name "MyAWSAssistant" --onefile --clean --version "1.0.0"
```

### 3. ビルドオプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--name` | アプリケーション名 | `simple-architect-assistant` |
| `--onefile` | 単一実行ファイルとして生成 | `False` |
| `--clean` | ビルド前にクリーンアップ | `False` |
| `--version` | アプリケーションバージョン | `1.0.0` |

### 4. 生成されるファイル

```
dist/
└── simple-architect-assistant/
    ├── simple-architect-assistant.exe  # 実行ファイル
    ├── _internal/                      # 依存関係
    ├── config/
    │   └── mcp_config.json            # MCP設定（編集可能）
    ├── .streamlit/
    │   └── secrets.toml.example       # AWS設定テンプレート
    └── README.txt                     # 配布用説明書
```

## エンドユーザーの設定

配布先で以下の設定ファイルを手動編集：

1. **AWS設定**: `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`
2. **MCP設定**: `config/mcp_config.json` （直接編集）

## 配布用ZIP作成

```bash
cd dist
zip -r simple-architect-assistant.zip simple-architect-assistant/
```

## 詳細ガイド

詳細な情報は [docs/DESKTOP_APP_GUIDE.md](docs/DESKTOP_APP_GUIDE.md) を参照してください。