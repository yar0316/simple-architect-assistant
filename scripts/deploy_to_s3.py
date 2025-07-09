#!/usr/bin/env python3
"""
S3署名付きURL配布の自動化スクリプト
Simple Architect Assistant デスクトップアプリをS3にアップロードし、署名付きURLを生成
"""

import os
import sys
import json
import argparse
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class S3Deployer:
    """S3配布管理クラス"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        S3配布管理を初期化
        
        Args:
            config_file: 設定ファイルのパス
        """
        self.logger = self._setup_logging()
        self.config = self._load_config(config_file)
        self.project_root = Path(__file__).parent.parent
        
        if not BOTO3_AVAILABLE:
            self.logger.error("boto3がインストールされていません: pip install boto3")
            sys.exit(1)
        
        self.s3_client = None
        self._init_aws_client()
    
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
            "s3": {
                "bucket_name": os.getenv("S3_BUCKET_NAME", ""),
                "region": os.getenv("AWS_REGION", "us-east-1"),
                "profile": os.getenv("AWS_PROFILE", "default"),
                "prefix": "releases/simple-architect-assistant/",
                "presign_expiry_days": 7
            }
        }
    
    def _init_aws_client(self):
        """AWS S3クライアントを初期化"""
        try:
            session = boto3.Session(
                profile_name=self.config["s3"]["profile"],
                region_name=self.config["s3"]["region"]
            )
            self.s3_client = session.client('s3')
            
            # 接続テスト
            self.s3_client.list_buckets()
            self.logger.info(f"AWS S3接続成功: プロファイル={self.config['s3']['profile']}")
            
        except NoCredentialsError:
            self.logger.error("AWS認証情報が見つかりません。AWS CLIの設定を確認してください。")
            sys.exit(1)
        except ClientError as e:
            self.logger.error(f"AWS S3接続エラー: {e}")
            sys.exit(1)
    
    def build_app(self, version: str, clean: bool = True) -> Path:
        """デスクトップアプリをビルド"""
        self.logger.info(f"デスクトップアプリビルド開始: バージョン={version}")
        
        # ビルドコマンド構築
        build_cmd = ["python", "build_desktop_app.py", "--version", version]
        if clean:
            build_cmd.append("--clean")
        
        try:
            # ビルド実行
            result = subprocess.run(
                build_cmd,
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True
            )
            
            self.logger.info("デスクトップアプリビルド完了")
            self.logger.debug(f"ビルド出力: {result.stdout}")
            
            # 生成されたディストリビューションパスを返す
            dist_dir = self.project_root / "dist" / "simple-architect-assistant"
            if not dist_dir.exists():
                raise FileNotFoundError(f"ビルド結果が見つかりません: {dist_dir}")
            
            return dist_dir
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ビルドエラー: {e.stderr}")
            sys.exit(1)
    
    def create_distribution_archive(self, dist_dir: Path, version: str) -> Path:
        """配布用アーカイブを作成"""
        self.logger.info("配布用アーカイブ作成中...")
        
        archive_name = f"simple-architect-assistant-{version}.zip"
        archive_path = self.project_root / "dist" / archive_name
        
        # 既存のアーカイブを削除
        if archive_path.exists():
            archive_path.unlink()
        
        try:
            # ZIP圧縮
            subprocess.run([
                "zip", "-r", archive_name, "simple-architect-assistant"
            ], cwd=self.project_root / "dist", check=True)
            
            self.logger.info(f"アーカイブ作成完了: {archive_path}")
            return archive_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"アーカイブ作成エラー: {e}")
            sys.exit(1)
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """ファイルのSHA256ハッシュを計算"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def upload_to_s3(self, file_path: Path, version: str) -> str:
        """ファイルをS3にアップロード"""
        bucket_name = self.config["s3"]["bucket_name"]
        if not bucket_name:
            self.logger.error("S3バケット名が設定されていません")
            sys.exit(1)
        
        # S3キーを生成
        prefix = self.config["s3"]["prefix"]
        s3_key = f"{prefix}{file_path.name}"
        
        self.logger.info(f"S3アップロード開始: {file_path.name} -> s3://{bucket_name}/{s3_key}")
        
        try:
            # ファイルハッシュを計算
            file_hash = self.calculate_file_hash(file_path)
            
            # メタデータ
            metadata = {
                'version': version,
                'upload_date': datetime.utcnow().isoformat(),
                'sha256': file_hash,
                'source': 'simple-architect-assistant-build-script'
            }
            
            # アップロード実行
            self.s3_client.upload_file(
                str(file_path),
                bucket_name,
                s3_key,
                ExtraArgs={
                    'Metadata': metadata,
                    'ServerSideEncryption': 'AES256'
                }
            )
            
            self.logger.info(f"S3アップロード完了: s3://{bucket_name}/{s3_key}")
            self.logger.info(f"ファイルハッシュ (SHA256): {file_hash}")
            
            return s3_key
            
        except ClientError as e:
            self.logger.error(f"S3アップロードエラー: {e}")
            sys.exit(1)
    
    def generate_presigned_url(self, s3_key: str, expiry_days: Optional[int] = None) -> str:
        """署名付きURLを生成"""
        bucket_name = self.config["s3"]["bucket_name"]
        if expiry_days is None:
            expiry_days = self.config["s3"]["presign_expiry_days"]
        
        expiry_seconds = expiry_days * 24 * 60 * 60
        
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=expiry_seconds
            )
            
            expiry_date = datetime.utcnow() + timedelta(days=expiry_days)
            self.logger.info(f"署名付きURL生成完了")
            self.logger.info(f"有効期限: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} UTC ({expiry_days}日間)")
            
            return presigned_url
            
        except ClientError as e:
            self.logger.error(f"署名付きURL生成エラー: {e}")
            sys.exit(1)
    
    def create_deployment_info(self, s3_key: str, presigned_url: str, version: str, file_path: Path) -> Dict[str, Any]:
        """配布情報を作成"""
        file_hash = self.calculate_file_hash(file_path)
        expiry_date = datetime.utcnow() + timedelta(days=self.config["s3"]["presign_expiry_days"])
        
        return {
            "deployment_info": {
                "version": version,
                "timestamp": datetime.utcnow().isoformat(),
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "sha256": file_hash,
                "s3_location": {
                    "bucket": self.config["s3"]["bucket_name"],
                    "key": s3_key,
                    "region": self.config["s3"]["region"]
                },
                "download": {
                    "presigned_url": presigned_url,
                    "expires_at": expiry_date.isoformat(),
                    "expiry_days": self.config["s3"]["presign_expiry_days"]
                }
            }
        }
    
    def save_deployment_info(self, deployment_info: Dict[str, Any], output_file: Optional[str] = None):
        """配布情報をファイルに保存"""
        if output_file:
            output_path = Path(output_file)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / f"deployment_info_{timestamp}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(deployment_info, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"配布情報を保存: {output_path}")
    
    def deploy(self, version: str, clean: bool = True, save_info: bool = True) -> Dict[str, Any]:
        """完全な配布プロセスを実行"""
        self.logger.info("=== S3配布プロセス開始 ===")
        
        # 1. アプリビルド
        dist_dir = self.build_app(version, clean)
        
        # 2. アーカイブ作成
        archive_path = self.create_distribution_archive(dist_dir, version)
        
        # 3. S3アップロード
        s3_key = self.upload_to_s3(archive_path, version)
        
        # 4. 署名付きURL生成
        presigned_url = self.generate_presigned_url(s3_key)
        
        # 5. 配布情報作成
        deployment_info = self.create_deployment_info(s3_key, presigned_url, version, archive_path)
        
        if save_info:
            self.save_deployment_info(deployment_info)
        
        self.logger.info("=== S3配布プロセス完了 ===")
        
        # 結果表示
        print("\n" + "="*60)
        print("🎉 S3配布完了")
        print("="*60)
        print(f"📦 ファイル名: {archive_path.name}")
        print(f"🏷️  バージョン: {version}")
        print(f"📊 ファイルサイズ: {archive_path.stat().st_size / (1024*1024):.1f} MB")
        print(f"🔒 SHA256: {deployment_info['deployment_info']['sha256']}")
        print(f"☁️  S3ロケーション: s3://{self.config['s3']['bucket_name']}/{s3_key}")
        print(f"⏰ 有効期限: {self.config['s3']['presign_expiry_days']}日間")
        print(f"\n📎 ダウンロードURL:")
        print(f"{presigned_url}")
        print("\n" + "="*60)
        
        return deployment_info


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Simple Architect Assistant S3配布ツール')
    parser.add_argument('--version', '-v', required=True, help='バージョン番号 (例: 1.0.0)')
    parser.add_argument('--config', '-c', help='設定ファイルパス')
    parser.add_argument('--no-clean', action='store_true', help='ビルド前のクリーンアップをスキップ')
    parser.add_argument('--no-save', action='store_true', help='配布情報の保存をスキップ')
    parser.add_argument('--output', '-o', help='配布情報の出力ファイルパス')
    
    args = parser.parse_args()
    
    try:
        deployer = S3Deployer(args.config)
        deployment_info = deployer.deploy(
            version=args.version,
            clean=not args.no_clean,
            save_info=not args.no_save
        )
        
        if args.output:
            deployer.save_deployment_info(deployment_info, args.output)
            
    except KeyboardInterrupt:
        print("\n配布プロセスが中断されました")
        sys.exit(1)
    except Exception as e:
        logging.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()