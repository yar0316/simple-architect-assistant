"""
設定ファイル管理ユーティリティ
デスクトップアプリでの設定ファイルパス管理（基本機能のみ）
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import logging


class ConfigManager:
    """設定ファイル管理クラス（基本機能のみ）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_desktop_app = self._detect_desktop_app()
        self.config_dir = self._get_config_dir()
        self.streamlit_dir = self._get_streamlit_dir()
        
    def _detect_desktop_app(self) -> bool:
        """デスクトップアプリ環境かどうかを検出"""
        # PyInstallerでパッケージされた場合の検出
        if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
            return True
        
        # streamlit-desktop-appでパッケージされた場合の検出
        if os.path.exists('_internal') and os.path.exists('README.txt'):
            return True
            
        return False
    
    def _get_config_dir(self) -> Path:
        """設定ディレクトリのパスを取得"""
        if self.is_desktop_app:
            # デスクトップアプリの場合：実行ファイルと同じディレクトリの config
            return Path('.') / 'config'
        else:
            # 開発環境の場合：プロジェクトルートの config
            return Path(__file__).parent.parent.parent / 'config'
    
    def _get_streamlit_dir(self) -> Path:
        """Streamlit設定ディレクトリのパスを取得"""
        if self.is_desktop_app:
            # デスクトップアプリの場合：実行ファイルと同じディレクトリの .streamlit
            return Path('.') / '.streamlit'
        else:
            # 開発環境の場合：プロジェクトルートの .streamlit
            return Path(__file__).parent.parent.parent / '.streamlit'
    
    def get_mcp_config_path(self) -> Path:
        """MCP設定ファイルのパスを取得"""
        return self.config_dir / 'mcp_config.json'
    
    def get_secrets_path(self) -> Path:
        """Streamlit secrets.toml のパスを取得"""
        return self.streamlit_dir / 'secrets.toml'
    
    def get_secrets_example_path(self) -> Path:
        """Streamlit secrets.toml.example のパスを取得"""
        return self.streamlit_dir / 'secrets.toml.example'
    
    def ensure_config_directories(self):
        """設定ディレクトリが存在することを確認"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.streamlit_dir.mkdir(parents=True, exist_ok=True)
    
    def copy_default_configs_if_missing(self):
        """デフォルト設定ファイルが存在しない場合にコピー"""
        # MCP設定ファイルのコピー
        mcp_config_path = self.get_mcp_config_path()
        if not mcp_config_path.exists():
            self._copy_default_mcp_config()
        
        # secrets.toml.example のコピー
        secrets_example_path = self.get_secrets_example_path()
        if not secrets_example_path.exists():
            self._copy_default_secrets_example()
    
    def _copy_default_mcp_config(self):
        """デフォルトMCP設定をコピー"""
        if self.is_desktop_app:
            # デスクトップアプリ：dist_config からコピー
            default_config = Path('./dist_config/mcp_config.json')
        else:
            # 開発環境：プロジェクトルートからコピー
            default_config = Path(__file__).parent.parent.parent / 'config' / 'mcp_config.json'
        
        if default_config.exists():
            self.ensure_config_directories()
            shutil.copy2(default_config, self.get_mcp_config_path())
            self.logger.info(f"デフォルトMCP設定をコピーしました: {default_config}")
    
    def _copy_default_secrets_example(self):
        """デフォルトsecrets.toml.example をコピー"""
        if self.is_desktop_app:
            # デスクトップアプリ：dist_config からコピー
            default_secrets = Path('./dist_config/.streamlit/secrets.toml.example')
        else:
            # 開発環境：プロジェクトルートからコピー
            default_secrets = Path(__file__).parent.parent.parent / '.streamlit' / 'secrets.toml.example'
        
        if default_secrets.exists():
            self.ensure_config_directories()
            shutil.copy2(default_secrets, self.get_secrets_example_path())
            self.logger.info(f"デフォルトsecrets.toml.example をコピーしました: {default_secrets}")
    
    def get_config_status(self) -> Dict[str, Any]:
        """設定ファイルの状態を取得"""
        return {
            "is_desktop_app": self.is_desktop_app,
            "config_dir": str(self.config_dir),
            "streamlit_dir": str(self.streamlit_dir),
            "mcp_config_exists": self.get_mcp_config_path().exists(),
            "secrets_exists": self.get_secrets_path().exists(),
            "secrets_example_exists": self.get_secrets_example_path().exists()
        }
    
    def load_mcp_config(self) -> Optional[Dict[str, Any]]:
        """MCP設定を読み込み"""
        config_path = self.get_mcp_config_path()
        
        if not config_path.exists():
            self.logger.warning(f"MCP設定ファイルが見つかりません: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"MCP設定の読み込みエラー: {e}")
            return None


# シングルトンインスタンス
_config_manager = None


def get_config_manager() -> ConfigManager:
    """ConfigManagerのシングルトンインスタンスを取得"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager