#!/usr/bin/env python3
"""
統合配布スクリプト
Simple Architect Assistant の複数配布方法を統一的に管理
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.deploy_to_s3 import S3Deployer
    S3_DEPLOY_AVAILABLE = True
except ImportError:
    S3_DEPLOY_AVAILABLE = False


class DistributionManager:
    """統合配布管理クラス"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        統合配布管理を初期化
        
        Args:
            config_file: 設定ファイルのパス
        """
        self.logger = self._setup_logging()
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config(config_file)
        self.distribution_log = []
        
    def _setup_logging(self) -> logging.Logger:
        """ログ設定"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = self.project_root / "config" / "distribution.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"設定ファイル読み込みエラー: {e}")
        
        # デフォルト設定
        return {
            "github": {
                "enabled": True,
                "auto_tag": True,
                "create_release": True,
                "draft": False,
                "prerelease": False
            },
            "s3": {
                "enabled": False,
                "bucket_name": os.getenv("S3_BUCKET_NAME", ""),
                "region": os.getenv("AWS_REGION", "us-east-1"),
                "profile": os.getenv("AWS_PROFILE", "default"),
                "prefix": "releases/simple-architect-assistant/",
                "presign_expiry_days": 7
            },
            "notifications": {
                "email_recipients": []
            }
        }
    
    def _log_action(self, action: str, status: str, details: Dict[str, Any] = None):
        """アクションをログに記録"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "status": status,
            "details": details or {}
        }
        self.distribution_log.append(log_entry)
        
        if status == "success":
            self.logger.info(f"✅ {action}")
        elif status == "error":
            self.logger.error(f"❌ {action}")
        else:
            self.logger.info(f"🔄 {action}")
    
    def check_prerequisites(self) -> bool:
        """前提条件をチェック"""
        self.logger.info("🔍 前提条件チェック中...")
        
        # 必要なファイルの存在確認
        required_files = [
            "build_desktop_app.py",
            "requirements.txt",
            "src/app.py"
        ]
        
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                self._log_action(f"必要ファイル確認: {file_path}", "error")
                return False
        
        # Git設定確認
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
            self._log_action("Git利用可能性確認", "success")
        except subprocess.CalledProcessError:
            self._log_action("Git利用可能性確認", "error", {"message": "Gitがインストールされていません"})
            return False
        
        # GitHub CLI確認（オプション）
        if self.config["github"]["enabled"]:
            try:
                subprocess.run(["gh", "--version"], check=True, capture_output=True)
                self._log_action("GitHub CLI利用可能性確認", "success")
            except subprocess.CalledProcessError:
                self.logger.warning("GitHub CLIが利用できません。手動でのリリース作成が必要です")
                self._log_action("GitHub CLI利用可能性確認", "warning")
        
        # S3配布の前提条件確認
        if self.config["s3"]["enabled"]:
            if not S3_DEPLOY_AVAILABLE:
                self._log_action("S3配布機能確認", "error", {"message": "S3配布機能が利用できません"})
                return False
            
            if not self.config["s3"]["bucket_name"]:
                self._log_action("S3バケット名確認", "error", {"message": "S3バケット名が設定されていません"})
                return False
        
        self.logger.info("✅ 前提条件チェック完了")
        return True
    
    def build_application(self, version: str, clean: bool = True) -> bool:
        """アプリケーションをビルド"""
        self.logger.info(f"🔨 アプリケーションビルド開始: バージョン={version}")
        
        try:
            # ビルドコマンド構築
            build_cmd = ["python", "build_desktop_app.py", "--version", version]
            if clean:
                build_cmd.append("--clean")
            
            # ビルド実行
            result = subprocess.run(
                build_cmd,
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True
            )
            
            self._log_action("アプリケーションビルド", "success", {
                "version": version,
                "clean": clean,
                "output": result.stdout.split('\n')[-5:] if result.stdout else []
            })
            
            return True
            
        except subprocess.CalledProcessError as e:
            self._log_action("アプリケーションビルド", "error", {
                "version": version,
                "error": str(e),
                "stderr": e.stderr
            })
            return False
    
    def deploy_to_github(self, version: str, tag_prefix: str = "v") -> bool:
        """GitHub Releasesに配布"""
        if not self.config["github"]["enabled"]:
            self.logger.info("GitHub配布は無効化されています")
            return True
        
        self.logger.info(f"📦 GitHub配布開始: バージョン={version}")
        
        try:
            tag_name = f"{tag_prefix}{version}"
            
            # Gitタグの作成
            if self.config["github"]["auto_tag"]:
                subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"], 
                             cwd=self.project_root, check=True)
                subprocess.run(["git", "push", "origin", tag_name], 
                             cwd=self.project_root, check=True)
                
                self._log_action("Gitタグ作成・プッシュ", "success", {"tag": tag_name})
            
            # GitHub Releasesリリース作成
            if self.config["github"]["create_release"]:
                self._create_github_release(version, tag_name)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self._log_action("GitHub配布", "error", {
                "version": version,
                "error": str(e)
            })
            return False
    
    def _create_github_release(self, version: str, tag_name: str):
        """GitHub Releaseを作成"""
        archive_path = self.project_root / "dist" / f"simple-architect-assistant-{version}.zip"
        
        if not archive_path.exists():
            # アーカイブを作成
            subprocess.run([
                "zip", "-r", f"simple-architect-assistant-{version}.zip", "simple-architect-assistant"
            ], cwd=self.project_root / "dist", check=True)
        
        # リリースノートを生成
        release_notes = self._generate_release_notes(version)
        
        # GitHub CLI でリリース作成
        try:
            cmd = [
                "gh", "release", "create", tag_name,
                str(archive_path),
                "--title", f"Simple Architect Assistant {tag_name}",
                "--notes", release_notes
            ]
            
            if self.config["github"]["draft"]:
                cmd.append("--draft")
            
            if self.config["github"]["prerelease"]:
                cmd.append("--prerelease")
            
            subprocess.run(cmd, cwd=self.project_root, check=True)
            self._log_action("GitHub Release作成", "success", {"tag": tag_name})
            
        except subprocess.CalledProcessError:
            self.logger.warning("GitHub CLIでのリリース作成に失敗しました。手動作成が必要です")
            self._log_action("GitHub Release作成", "warning", {"tag": tag_name})
    
    def _generate_release_notes(self, version: str) -> str:
        """リリースノートを生成"""
        return f"""## Simple Architect Assistant {version}

### 📦 配布パッケージ
- デスクトップアプリケーション（Windows/macOS/Linux対応）
- AWS Bedrock Claude 4 Sonnet統合
- MCP拡張機能サポート

### 🚀 セットアップ
1. ZIPファイルをダウンロード・解凍
2. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
3. AWS設定を編集
4. 実行ファイルを起動

### 📋 主な機能
- AWS構成提案チャット
- Terraformコード生成
- リアルタイムコスト分析
- 設定ファイル編集による機能拡張

### 🆘 サポート
- GitHub Issues: https://github.com/yar0316/simple-architect-assistant/issues
- ドキュメント: docs/build.md, docs/distribution-guide.md
"""
    
    def deploy_to_s3(self, version: str) -> bool:
        """S3署名付きURLで配布"""
        if not self.config["s3"]["enabled"]:
            self.logger.info("S3配布は無効化されています")
            return True
        
        if not S3_DEPLOY_AVAILABLE:
            self.logger.error("S3配布機能が利用できません")
            return False
        
        self.logger.info(f"☁️  S3配布開始: バージョン={version}")
        
        try:
            # S3配布スクリプトを実行
            s3_deployer = S3Deployer()
            s3_deployer.config = self.config  # 設定を共有
            
            deployment_info = s3_deployer.deploy(version, clean=False, save_info=True)
            
            self._log_action("S3配布", "success", {
                "version": version,
                "presigned_url": deployment_info["deployment_info"]["download"]["presigned_url"],
                "expires_at": deployment_info["deployment_info"]["download"]["expires_at"]
            })
            
            return True
            
        except Exception as e:
            self._log_action("S3配布", "error", {
                "version": version,
                "error": str(e)
            })
            return False
    
    def send_notifications(self, version: str, distribution_results: Dict[str, bool]):
        """通知を送信"""
        # 現在は通知機能を無効化
        self.logger.info("📢 通知機能は無効化されています")
        return
    
    def save_distribution_log(self, version: str):
        """配布ログを保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.project_root / f"distribution_log_{version}_{timestamp}.json"
        
        log_data = {
            "version": version,
            "timestamp": timestamp,
            "config": self.config,
            "log": self.distribution_log
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"📝 配布ログ保存: {log_file}")
    
    def distribute(self, version: str, methods: List[str] = None) -> Dict[str, bool]:
        """統合配布プロセスを実行"""
        self.logger.info(f"🚀 統合配布プロセス開始: バージョン={version}")
        
        # 前提条件チェック
        if not self.check_prerequisites():
            self.logger.error("前提条件チェックに失敗しました")
            return {}
        
        # アプリケーションビルド
        if not self.build_application(version):
            self.logger.error("アプリケーションビルドに失敗しました")
            return {}
        
        # 配布方法の決定
        if methods is None:
            methods = []
            if self.config["github"]["enabled"]:
                methods.append("github")
            if self.config["s3"]["enabled"]:
                methods.append("s3")
        
        # 各配布方法を実行
        distribution_results = {}
        
        for method in methods:
            if method == "github":
                distribution_results["github"] = self.deploy_to_github(version)
            elif method == "s3":
                distribution_results["s3"] = self.deploy_to_s3(version)
            else:
                self.logger.warning(f"未知の配布方法: {method}")
        
        # 通知送信
        self.send_notifications(version, distribution_results)
        
        # ログ保存
        self.save_distribution_log(version)
        
        # 結果表示
        self._display_results(version, distribution_results)
        
        return distribution_results
    
    def _display_results(self, version: str, results: Dict[str, bool]):
        """結果を表示"""
        print("\n" + "="*60)
        print(f"🎉 統合配布プロセス完了: {version}")
        print("="*60)
        
        for method, success in results.items():
            status = "✅ 成功" if success else "❌ 失敗"
            print(f"{method.upper()}: {status}")
        
        successful_count = sum(results.values())
        total_count = len(results)
        
        print(f"\n📊 結果サマリー: {successful_count}/{total_count} 成功")
        
        if successful_count == total_count:
            print("🎯 すべての配布方法が成功しました！")
        elif successful_count > 0:
            print("⚠️  一部の配布方法が失敗しました。ログを確認してください。")
        else:
            print("❌ すべての配布方法が失敗しました。")
        
        print("="*60)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Simple Architect Assistant 統合配布ツール')
    parser.add_argument('--version', '-v', required=True, help='バージョン番号 (例: 1.0.0)')
    parser.add_argument('--config', '-c', help='設定ファイルパス')
    parser.add_argument('--methods', '-m', nargs='+', choices=['github', 's3'], 
                       help='配布方法を指定 (デフォルト: 設定ファイルに従う)')
    parser.add_argument('--dry-run', action='store_true', help='ドライランモード（実際の配布は行わない）')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🧪 ドライランモード: 実際の配布は行いません")
        return
    
    try:
        manager = DistributionManager(args.config)
        results = manager.distribute(args.version, args.methods)
        
        # 終了コードを設定
        if all(results.values()):
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n配布プロセスが中断されました")
        sys.exit(1)
    except Exception as e:
        logging.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()