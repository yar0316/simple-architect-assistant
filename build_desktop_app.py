#!/usr/bin/env python3
"""
Simple Architect Assistant デスクトップアプリケーション ビルドスクリプト
streamlit-desktop-app を使用してデスクトップアプリケーションを生成します。
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Simple Architect Assistant デスクトップアプリビルダー')
    parser.add_argument('--name', '-n', default='simple-architect-assistant', 
                       help='アプリケーション名 (デフォルト: simple-architect-assistant)')
    parser.add_argument('--onefile', '-o', action='store_true',
                       help='単一実行ファイルとしてビルド')
    parser.add_argument('--clean', '-c', action='store_true',
                       help='ビルド前にdistディレクトリをクリーンアップ')
    parser.add_argument('--version', '-v', default='1.0.0',
                       help='アプリケーションバージョン (デフォルト: 1.0.0)')
    
    args = parser.parse_args()
    
    # プロジェクトルートを取得
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print(f"🚀 Simple Architect Assistant デスクトップアプリビルドを開始...")
    print(f"📂 プロジェクトルート: {project_root}")
    print(f"📱 アプリケーション名: {args.name}")
    print(f"🏷️  バージョン: {args.version}")
    
    # 事前チェック
    if not check_prerequisites():
        sys.exit(1)
    
    # クリーンアップ
    if args.clean:
        cleanup_build_files()
    
    # 設定ファイルの準備
    prepare_config_files()
    
    # ビルド実行
    build_desktop_app(args.name, args.onefile, args.version)
    
    # 後処理
    post_build_processing(args.name)
    
    print(f"✅ デスクトップアプリビルドが完了しました！")
    print(f"📦 実行ファイル: dist/{args.name}/")
    print(f"🎯 配布準備完了")


def check_prerequisites():
    """必要な依存関係とファイルのチェック"""
    print("🔍 前提条件をチェック中...")
    
    # 必要なファイルの存在確認
    required_files = [
        'src/app.py',
        'requirements.txt',
        'config/mcp_config.json',
        '.streamlit/secrets.toml.example'
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ 必要なファイルが見つかりません: {file_path}")
            return False
    
    # streamlit-desktop-app の存在確認
    try:
        import streamlit_desktop_app
        print("✅ streamlit-desktop-app が利用可能です")
    except ImportError:
        print("❌ streamlit-desktop-app がインストールされていません")
        print("   以下のコマンドでインストールしてください:")
        print("   pip install streamlit-desktop-app")
        return False
    
    # Streamlit の存在確認
    try:
        import streamlit
        print("✅ Streamlit が利用可能です")
    except ImportError:
        print("❌ Streamlit がインストールされていません")
        return False
    
    return True


def cleanup_build_files():
    """ビルドファイルのクリーンアップ"""
    print("🧹 ビルドファイルをクリーンアップ中...")
    
    cleanup_dirs = ['dist', 'build', '__pycache__']
    for dir_name in cleanup_dirs:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"🗑️  {dir_name} を削除しました")


def prepare_config_files():
    """設定ファイルの準備"""
    print("⚙️  設定ファイルを準備中...")
    
    # dist用設定ディレクトリの作成
    dist_config_dir = Path('dist_config')
    dist_config_dir.mkdir(exist_ok=True)
    
    # mcp_config.json のコピー
    shutil.copy2('config/mcp_config.json', dist_config_dir / 'mcp_config.json')
    
    # secrets.toml.example のコピー
    dist_streamlit_dir = dist_config_dir / '.streamlit'
    dist_streamlit_dir.mkdir(exist_ok=True)
    shutil.copy2('.streamlit/secrets.toml.example', dist_streamlit_dir / 'secrets.toml.example')
    
    print("✅ 設定ファイルの準備が完了しました")


def build_desktop_app(app_name, onefile=False, version='1.0.0'):
    """デスクトップアプリのビルド"""
    print("🔨 デスクトップアプリをビルド中...")
    
    # ビルドコマンドの構築
    cmd = [
        'streamlit-desktop-app',
        'build',
        'src/app.py',
        '--name', app_name,
        '--version', version,
        '--add-data', 'config:config',
        '--add-data', '.streamlit:streamlit',
        '--add-data', 'src:src',
        '--add-data', 'dist_config:dist_config',
        '--hidden-import', 'streamlit',
        '--hidden-import', 'boto3',
        '--hidden-import', 'langchain',
        '--hidden-import', 'langchain_aws',
        '--hidden-import', 'langchain_community',
        '--hidden-import', 'langchain_mcp_adapters',
        '--hidden-import', 'pydantic',
        '--collect-all', 'streamlit',
        '--collect-all', 'boto3',
        '--collect-all', 'langchain'
    ]
    
    # onefileオプションの追加
    if onefile:
        cmd.append('--onefile')
    
    # ビルド実行
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ ビルドが正常に完了しました")
        print(f"📝 ビルドログ: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"❌ ビルドエラー: {e}")
        print(f"🔍 エラー詳細: {e.stderr}")
        raise


def post_build_processing(app_name):
    """ビルド後の後処理"""
    print("🔧 ビルド後処理を実行中...")
    
    app_dir = Path(f'dist/{app_name}')
    
    if app_dir.exists():
        # 設定ファイルの配置
        setup_config_files_in_dist(app_dir)
        
        # 実行権限の設定（Unix系の場合）
        if os.name != 'nt':
            executable_path = app_dir / app_name
            if executable_path.exists():
                os.chmod(executable_path, 0o755)
                print(f"🔐 実行権限を設定しました: {executable_path}")
        
        # README.txtの作成
        create_distribution_readme(app_dir)
        
        print("✅ ビルド後処理が完了しました")
    else:
        print(f"⚠️  配布ディレクトリが見つかりません: {app_dir}")


def setup_config_files_in_dist(app_dir):
    """配布用設定ファイルのセットアップ"""
    print("📋 配布用設定ファイルをセットアップ中...")
    
    # 設定ディレクトリの作成
    config_dir = app_dir / 'config'
    config_dir.mkdir(exist_ok=True)
    
    streamlit_dir = app_dir / '.streamlit'
    streamlit_dir.mkdir(exist_ok=True)
    
    # dist_config から設定ファイルをコピー
    if Path('dist_config/mcp_config.json').exists():
        shutil.copy2('dist_config/mcp_config.json', config_dir / 'mcp_config.json')
    
    if Path('dist_config/.streamlit/secrets.toml.example').exists():
        shutil.copy2('dist_config/.streamlit/secrets.toml.example', 
                    streamlit_dir / 'secrets.toml.example')
    
    print("✅ 配布用設定ファイルのセットアップが完了しました")


def create_distribution_readme(app_dir):
    """配布用READMEファイルの作成"""
    readme_content = """# Simple Architect Assistant - デスクトップアプリ

## 必要なセットアップ

### 1. AWS設定（必須）
1. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. `secrets.toml` を編集してAWS設定を入力：
   ```toml
   [aws]
   profile = "your-aws-profile-name"
   region = "us-east-1"
   ```

### 2. MCP設定（オプション）
- `config/mcp_config.json` を直接編集してMCPサーバーを設定
- 新しいMCPサーバーを追加したり、既存の設定を変更できます
- 基本的な利用では変更不要です

## 起動方法

### Windows
```
simple-architect-assistant.exe
```

### macOS/Linux
```
./simple-architect-assistant
```

## 設定ファイルの編集

### AWS設定 (.streamlit/secrets.toml)
- AWSプロファイルとリージョンを設定
- AWS CLI が設定済みであることが前提

### MCP設定 (config/mcp_config.json)
- MCPサーバーの有効/無効を切り替え: `"disabled": true/false`
- 新しいMCPサーバーを追加可能
- 環境変数も設定可能

## トラブルシューティング

### よくある問題
1. **AWS認証エラー**
   - `.streamlit/secrets.toml` の設定を確認
   - AWS CLI の設定を確認: `aws configure list`
   - Bedrock利用権限があるか確認

2. **MCPサーバー接続エラー**
   - `config/mcp_config.json` の設定を確認
   - uvxがインストールされているか確認
   - 無効化して使用することも可能: `"disabled": true`

3. **起動が遅い**
   - 初回起動時は依存関係の読み込みで時間がかかります
   - 2回目以降は高速化されます

## サポート
- GitHub Issues: https://github.com/yar0316/simple-architect-assistant/issues
- ドキュメント: README.md を参照
"""
    
    readme_path = app_dir / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"📖 配布用READMEを作成しました: {readme_path}")


if __name__ == '__main__':
    main()