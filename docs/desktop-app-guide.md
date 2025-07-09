# Simple Architect Assistant - デスクトップアプリ化ガイド

## 概要

Simple Architect Assistant を `streamlit-desktop-app` パッケージを使用してデスクトップアプリケーションとして配布するためのガイドです。

## 前提条件

### 開発環境
- Python 3.8以上
- uv または pip
- 必要な依存関係（requirements.txt）

### 配布先環境
- 配布対象OS（Windows/macOS/Linux）
- インターネット接続（初回MCP設定時）

## ビルド手順

### 1. 依存関係のインストール

```bash
# uvを使用する場合
uv pip install -r requirements.txt

# pipを使用する場合
pip install -r requirements.txt
```

### 2. デスクトップアプリのビルド

```bash
# 基本的なビルド
python build_desktop_app.py

# カスタムオプションでビルド
python build_desktop_app.py --name "MyAWSAssistant" --onefile --clean
```

### 3. ビルドオプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--name` | アプリケーション名 | `simple-architect-assistant` |
| `--onefile` | 単一実行ファイルとして生成 | `False` |
| `--clean` | ビルド前にクリーンアップ | `False` |
| `--version` | アプリケーションバージョン | `1.0.0` |

## 配布ファイル構成

```
dist/
└── simple-architect-assistant/
    ├── simple-architect-assistant.exe  # 実行ファイル（Windows）
    ├── simple-architect-assistant      # 実行ファイル（macOS/Linux）
    ├── _internal/                      # 内部依存関係
    ├── config/
    │   └── mcp_config.json            # MCP設定
    ├── .streamlit/
    │   └── secrets.toml.example       # AWS設定テンプレート
    └── README.txt                     # 配布用説明書
```

## エンドユーザー向けセットアップ

### 1. アプリケーションの起動
```bash
# Windows
simple-architect-assistant.exe

# macOS/Linux
./simple-architect-assistant
```

### 2. 設定ファイルの手動編集

#### AWS設定（必須）
1. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. `secrets.toml` を編集：
   ```toml
   [aws]
   profile = "your-aws-profile-name"
   region = "us-east-1"
   ```

#### MCP設定（オプション）
- `config/mcp_config.json` を直接編集
- MCPサーバーの有効/無効切り替え
- 新しいMCPサーバーの追加

## 技術的詳細

### デスクトップアプリ化の仕組み

1. **streamlit-desktop-app**
   - Streamlitアプリをデスクトップアプリに変換
   - PyInstallerベースの実行ファイル生成
   - WebViewコンポーネントによるUI表示

2. **設定ファイル管理**
   - `ConfigManager`クラスによる統一管理
   - 開発環境とデスクトップアプリ環境の自動判別
   - 設定ファイルパスの適切な管理

3. **MCP統合の維持**
   - 既存のMCP統合機能をそのまま維持
   - `config/mcp_config.json`の編集による設定変更
   - フォールバック機能による高可用性

### ファイル構成の変更

#### 追加ファイル
- `build_desktop_app.py`: ビルドスクリプト
- `src/utils/config_manager.py`: 設定管理ユーティリティ
- `docs/DESKTOP_APP_GUIDE.md`: 本ガイド

#### 変更ファイル
- `requirements.txt`: `streamlit-desktop-app`の追加
- 基本的には既存コードをそのまま維持

## トラブルシューティング

### ビルド時の問題

#### 1. 依存関係エラー
```bash
# 解決方法
pip install streamlit-desktop-app
```

#### 2. メモリ不足エラー
```bash
# 解決方法（onefileオプションを使用しない）
python build_desktop_app.py --name "MyApp"
```

#### 3. モジュールが見つからないエラー
```bash
# 解決方法（hidden-importを追加）
# build_desktop_app.py の cmd リストに追加
'--hidden-import', 'missing_module_name'
```

### 実行時の問題

#### 1. AWS認証エラー
- AWS CLI の設定を確認
- IAM権限の確認（Bedrock利用権限）
- リージョン設定の確認

#### 2. MCP接続エラー
- uvxのインストール確認
- MCPサーバーの設定確認
- インターネット接続の確認

#### 3. 起動が遅い
- 初回起動時は依存関係の読み込みに時間がかかります
- 2回目以降は高速化されます

## 配布時の注意事項

### セキュリティ考慮事項

1. **AWS認証情報**
   - secrets.toml は配布に含めない
   - エンドユーザーが自身で設定する仕組み

2. **実行ファイルの検証**
   - ウイルススキャンの実行
   - デジタル署名の追加（推奨）

3. **ログ情報**
   - 機密情報がログに含まれないよう注意
   - 本番環境ではログレベルを調整

### 配布方法

1. **ZIP圧縮**
   ```bash
   # 配布用ZIPファイルの作成
   cd dist
   zip -r simple-architect-assistant.zip simple-architect-assistant/
   ```

2. **インストーラー作成**
   - NSIS（Windows）
   - DMG（macOS）
   - AppImage（Linux）

3. **GitHub Releases**
   - 実行ファイルのGitHub Releasesでの配布
   - バージョン管理とダウンロード統計

## 今後の拡張

### 予定されている機能

1. **自動更新機能**
   - アプリケーションの自動更新
   - 設定ファイルの自動バックアップ

2. **設定エクスポート/インポート**
   - 設定ファイルの共有機能
   - 組織内での設定標準化

3. **プラグインシステム**
   - カスタムMCPサーバーの追加
   - 機能拡張のためのプラグイン

### 開発者向け情報

#### カスタムビルドスクリプト
```python
# build_desktop_app.py の拡張例
def custom_build_options():
    return {
        '--icon': 'assets/icon.ico',
        '--splash': 'assets/splash.png',
        '--add-data': 'custom_data:custom_data'
    }
```

#### 設定管理の拡張
```python
# config_manager.py の拡張例
def add_custom_config_section(self):
    # カスタム設定セクションの追加
    pass
```

## サポート

### 問題報告
- GitHub Issues: https://github.com/yar0316/simple-architect-assistant/issues
- バグレポート、機能要望はIssuesで管理

### コミュニティ
- ドキュメント: プロジェクトのREADME.md
- 技術情報: CLAUDE.md の「デスクトップアプリ化」セクション

### 開発者向け
- 実装詳細: `src/utils/config_manager.py`
- ビルドスクリプト: `build_desktop_app.py`
- 設定管理: `config/mcp_config.json`