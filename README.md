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

1.  **設定ファイルの確認:**
    設定ファイルは `.streamlit/secrets.toml` にあります。

2.  **設定ファイルの編集:**
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
