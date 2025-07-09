# Simple Architect Assistant - 配布ガイド

このドキュメントでは、Simple Architect Assistantデスクトップアプリの配布方法について詳細に説明します。

## 配布方法の比較

### 概要

| 観点 | S3署名付きURL | GitHub Releases |
|------|---------------|-----------------|
| **適用場面** | クローズドな配布（特定ユーザーのみ） | オープンな配布（不特定多数） |
| **セキュリティ** | 高（URL知る人のみ + 有効期限設定可能） | 中（パブリックは誰でも、プライベートは制限可能） |
| **コスト** | 有料（S3ストレージ + データ転送料金） | 無料（パブリックリポジトリ） |
| **利便性** | 配布者：低（URLの再生成・再共有）<br>受取手：高（URL直接アクセス） | 配布者：高（自動化可能）<br>受取手：高（常に最新版入手可能） |
| **管理のしやすさ** | 中（ファイル管理とURL管理が分離） | 高（Gitバージョン管理と完全統合） |

## 1. S3署名付きURLでの配布

### 特徴

限定されたユーザーへのセキュアな配布に適した方法。

### メリット

- **高いセキュリティ**: URLを知っている人しかアクセス不可
- **有効期限設定**: アクセス期間の制御が可能
- **きめ細かいアクセス制御**: IAMポリシーとの組み合わせ

### デメリット

- **コスト発生**: S3利用料金（ストレージ + データ転送）
- **管理の手間**: 更新のたびにURL再生成・再共有が必要
- **URLの漏洩リスク**: URL自体が認証情報となる

### 配布手順

#### 1. デスクトップアプリのビルド

```bash
# 基本ビルド
python build_desktop_app.py

# または単一ファイルビルド
python build_desktop_app.py --onefile

# 配布用ZIPファイル作成
cd dist
zip -r simple-architect-assistant.zip simple-architect-assistant/
```

#### 2. S3バケットへのアップロード

```bash
# ZIP圧縮されたアプリをS3にアップロード
aws s3 cp simple-architect-assistant.zip s3://your-bucket-name/apps/simple-architect-assistant-v1.0.0.zip
```

#### 3. 署名付きURLの生成

```bash
# 7日間有効な署名付きURLを生成
aws s3 presign s3://your-bucket-name/apps/simple-architect-assistant-v1.0.0.zip --expires-in 604800
```

#### 4. URLの共有

生成されたURLを配布したいユーザーにメール等で通知

### 自動化例（AWS CLI + スクリプト）

```bash
#!/bin/bash
VERSION=$(date +"%Y%m%d_%H%M%S")
BUCKET_NAME="your-bucket-name"
FILE_NAME="simple-architect-assistant-${VERSION}.zip"

# ビルド
python build_desktop_app.py --clean
cd dist
zip -r ${FILE_NAME} simple-architect-assistant/

# S3アップロード
aws s3 cp ${FILE_NAME} s3://${BUCKET_NAME}/apps/

# 署名付きURL生成（7日間有効）
URL=$(aws s3 presign s3://${BUCKET_NAME}/apps/${FILE_NAME} --expires-in 604800)

echo "配布URL: ${URL}"
echo "有効期限: 7日間"
```

## 2. GitHub Releasesでの配布

### 特徴

オープンソースプロジェクトのような広範囲への配布に最適。

### メリット

- **無料**: パブリックリポジトリは完全無料
- **優れたバージョン管理**: Gitタグと連動した明確なバージョン管理
- **高い利便性**: ユーザーはいつでも任意のバージョンをダウンロード可能
- **自動化可能**: GitHub Actionsでの完全自動化が可能

### デメリット

- **公開性**: パブリックリポジトリは全て公開される

### 配布手順

#### 1. デスクトップアプリのビルド

```bash
# ビルド実行
python build_desktop_app.py --clean --version "1.0.0"

# 配布用ファイル準備
cd dist
zip -r simple-architect-assistant-v1.0.0.zip simple-architect-assistant/
```

#### 2. Gitタグの作成

```bash
# リリース用タグを作成
git add .
git commit -m "Release v1.0.0: Initial desktop app release"
git tag -a v1.0.0 -m "Version 1.0.0 - Desktop application release"
git push origin main
git push origin v1.0.0
```

#### 3. GitHub Releaseの作成

##### GitHub CLI使用

```bash
gh release create v1.0.0 \
  ./dist/simple-architect-assistant-v1.0.0.zip \
  --title "Simple Architect Assistant v1.0.0" \
  --notes "$(cat <<EOF
## 🎉 Simple Architect Assistant デスクトップアプリ初回リリース

### 新機能
- Streamlitベースのデスクトップアプリケーション
- MCP統合による拡張可能なAWS支援機能
- AWS Bedrock Claude 4 Sonnet統合

### セットアップ
1. ZIPファイルをダウンロード・解凍
2. \`.streamlit/secrets.toml.example\` を \`.streamlit/secrets.toml\` にコピー
3. AWS設定を編集
4. \`simple-architect-assistant.exe\` を実行

### システム要件
- Windows 10以上 / macOS 10.15以上 / Linux
- AWS CLI設定済み環境
- インターネット接続（MCP機能使用時）

### サポート
- Issues: https://github.com/yar0316/simple-architect-assistant/issues
- ドキュメント: [BUILD.md](BUILD.md)
EOF
)"
```

##### GitHub Web UI使用

1. GitHubリポジトリの「Releases」ページへアクセス
2. 「Create a new release」をクリック
3. タグ：「v1.0.0」を選択または作成
4. リリースタイトル：「Simple Architect Assistant v1.0.0」
5. ビルドしたZIPファイルをドラッグ＆ドロップ
6. リリースノートを記入
7. 「Publish release」をクリック

#### 4. GitHub Actions自動化（推奨）

`.github/workflows/release.yml` を作成：

```yaml
name: Build and Release Desktop App

on:
  push:
    tags:
      - 'v*'

jobs:
  build-and-release:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Build desktop app
      run: |
        python build_desktop_app.py --clean --version ${GITHUB_REF#refs/tags/}
    
    - name: Create distribution archive
      run: |
        cd dist
        zip -r simple-architect-assistant-${GITHUB_REF#refs/tags/}.zip simple-architect-assistant/
    
    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/simple-architect-assistant-*.zip
        generate_release_notes: true
        make_latest: true
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 3. 推奨配布方法

### プロジェクトの性質に基づく推奨

**Simple Architect Assistant**の場合：

#### GitHub Releases を推奨する理由

1. **オープンソースプロジェクト**: 既にパブリックリポジトリで開発
2. **広範囲な利用想定**: AWS利用者全般への配布を想定
3. **コスト効率**: 無料で利用可能
4. **バージョン管理**: 明確なバージョン履歴とリリースノート
5. **自動化**: CI/CDパイプラインとの統合が容易

#### 実装手順

1. GitHub Actionsワークフロー設定
2. リリース用タグ作成時の自動ビルド・配布
3. リリースノートの自動生成
4. 複数OS対応（Windows/macOS/Linux）の並行ビルド

### ハイブリッド戦略

必要に応じて両方の方法を併用：

- **公開版**: GitHub Releasesで一般配布
- **クローズドベータ版**: S3署名付きURLで限定配布
- **エンタープライズ版**: S3 + IAM制御での組織内配布

## 4. セキュリティ考慮事項

### 配布時のセキュリティ

- **実行ファイルのウイルススキャン**: 配布前の必須チェック
- **デジタル署名**: 信頼性向上のための署名追加
- **チェックサム公開**: ダウンロードファイルの整合性確認

### 設定ファイルの保護

- **secrets.toml**: 配布に含めない（exampleのみ）
- **機密情報の分離**: AWSクレデンシャルは別管理
- **設定テンプレート**: 安全な初期設定ガイド

## 5. まとめ

| シナリオ | 推奨方法 | 理由 |
|---------|---------|------|
| **一般公開** | GitHub Releases | 無料、管理容易、バージョン管理統合 |
| **社内限定** | S3署名付きURL | セキュア、アクセス制御、有効期限設定 |
| **ベータテスト** | S3署名付きURL | 限定配布、フィードバック収集期間制御 |
| **オープンソース** | GitHub Releases | 透明性、コミュニティ、自動化 |

Simple Architect Assistantプロジェクトでは、**GitHub Releases**を主要配布方法として採用し、必要に応じてS3署名付きURLを補完的に活用することを推奨します。

## 6. GitHub Actions設定ガイド

### GitHubトークンの設定

#### 6.1 既存のシークレット確認方法

リポジトリに登録されているシークレットは、セキュリティ上の理由から値を直接確認できません。存在するシークレット名のみ確認可能です。

**確認手順:**
1. 対象のGitHubリポジトリにアクセス
2. **[Settings]** タブをクリック
3. 左サイドバーから **[Secrets and variables]** > **[Actions]** を選択
4. **[Repository secrets]** セクションでシークレット名一覧を確認

#### 6.2 Personal Access Token (PAT) の生成

**生成手順:**
1. GitHubの右上プロフィール画像をクリック → **[Settings]**
2. 左サイドバーの **[Developer settings]** をクリック
3. **[Personal access tokens]** > **[Fine-grained tokens]** を選択（推奨）
4. **[Generate new token]** をクリック
5. 以下の設定を行う：
   - **Note**: `GitHub Actions Release Automation`
   - **Expiration**: 適切な有効期限を設定（推奨：90日）
   - **Repository access**: 対象リポジトリのみ選択
   - **Permissions**:
     - **Repository permissions** > **Contents**: `Read and write`
     - **Repository permissions** > **Metadata**: `Read`
     - **Repository permissions** > **Pull requests**: `Read and write`（必要に応じて）
6. **[Generate token]** をクリック
7. **生成されたトークンをコピー**（この画面でのみ表示）

#### 6.3 GitHub Actionsでの設定

**リポジトリシークレット設定:**
1. リポジトリの **[Settings]** > **[Secrets and variables]** > **[Actions]**
2. **[New repository secret]** をクリック
3. 以下のシークレットを設定：

| シークレット名 | 説明 | 必須 |
|---------------|------|------|
| `GITHUB_TOKEN` | 自動生成（設定不要） | GitHub Releases用 |
| `S3_BUCKET_NAME` | S3バケット名 | S3配布用 |
| `AWS_ACCESS_KEY_ID` | AWSアクセスキーID | S3配布用 |
| `AWS_SECRET_ACCESS_KEY` | AWSシークレットアクセスキー | S3配布用 |

#### 6.4 GITHUB_TOKEN vs Personal Access Token

| 特徴 | GITHUB_TOKEN | Personal Access Token |
|------|-------------|----------------------|
| **発行元** | GitHub Actionsが自動生成 | ユーザーが手動生成 |
| **スコープ** | 実行中のリポジトリのみ | ユーザー設定による |
| **有効期限** | ジョブ実行中のみ | ユーザー設定による |
| **他ワークフロー実行** | ❌ 不可 | ✅ 可能 |
| **用途** | 基本的なリポジトリ操作 | 連鎖ワークフロー、外部連携 |

**使い分け:**
- **GITHUB_TOKEN**: 単純なリリース作成に使用
- **Personal Access Token**: 他のワークフローをトリガーする場合に使用

### 6.5 自動化ワークフロー

本プロジェクトでは以下のワークフローを提供：

#### GitHub Releases自動化
```yaml
# .github/workflows/release-github.yml
# v* タグのプッシュで自動実行
# 手動実行も可能
```

#### S3配布自動化
```yaml
# .github/workflows/deploy-s3.yml
# s3-* タグのプッシュで自動実行
# 手動実行も可能
```

### 6.6 使用例

#### GitHub Releases配布
```bash
# 1. コード変更をコミット
git add .
git commit -m "Release v1.0.0: Add new features"

# 2. タグを作成してプッシュ
git tag v1.0.0
git push origin v1.0.0

# 3. GitHub Actionsが自動でリリースを作成
```

#### S3配布
```bash
# 1. S3配布用タグを作成
git tag s3-v1.0.0
git push origin s3-v1.0.0

# 2. GitHub Actionsが自動でS3にアップロード
```

#### 手動実行
```bash
# GitHub CLIを使用
gh workflow run release-github.yml -f version=v1.0.0

# または統合配布スクリプト
python scripts/distribute.py --version 1.0.0 --methods github s3
```

### 6.7 トラブルシューティング

#### よくある問題

1. **権限エラー**
   - PATの権限スコープを確認
   - リポジトリアクセス権限を確認

2. **シークレットが見つからない**
   - シークレット名のスペルを確認
   - シークレットが正しいリポジトリに設定されているか確認

3. **ワークフローが実行されない**
   - タグの命名規則を確認（v1.0.0, s3-v1.0.0）
   - ワークフローファイルの構文を確認

4. **AWS認証エラー**
   - AWS_ACCESS_KEY_IDとAWS_SECRET_ACCESS_KEYを確認
   - IAMポリシーでS3アクセス権限を確認

#### デバッグ方法

1. **GitHub Actionsログ確認**
   - リポジトリの[Actions]タブでログを確認
   - 失敗したステップの詳細を確認

2. **ローカルテスト**
   ```bash
   # 配布スクリプトのローカルテスト
   python scripts/distribute.py --version 1.0.0 --dry-run
   ```

3. **設定ファイル確認**
   ```bash
   # 設定ファイルの構文チェック
   python -m json.tool config/distribution.json
   ```

Simple Architect Assistantプロジェクトでは、**GitHub Releases**を主要配布方法として採用し、必要に応じてS3署名付きURLを補完的に活用することを推奨します。
