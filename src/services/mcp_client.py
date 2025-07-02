"""
AWS MCP (Model Context Protocol) クライアントサービス

このモジュールは、AWS MCP サーバーとの統合を提供し、
Windows、Mac、Linux環境での動作をサポートします。
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import hashlib
import time
from datetime import datetime, timedelta

import streamlit as st
import asyncio

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MultiServerMCPClient = None


class MCPRequestCache:
    """MCPリクエストのキャッシュ機構"""
    
    def __init__(self, default_ttl: int = 300):  # デフォルト5分
        """
        キャッシュを初期化
        
        Args:
            default_ttl: デフォルトのTTL（秒）
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
            "cache_size": 0
        }
        self.logger = logging.getLogger(__name__ + ".cache")
        
    def _generate_cache_key(self, method: str, *args, **kwargs) -> str:
        """
        リクエストパラメータからキャッシュキーを生成
        
        Args:
            method: 呼び出しメソッド名
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            ハッシュ化されたキャッシュキー
        """
        # リクエストパラメータを文字列に変換
        params_str = f"{method}:{str(args)}:{str(sorted(kwargs.items()))}"
        
        # SHA256でハッシュ化
        cache_key = hashlib.sha256(params_str.encode('utf-8')).hexdigest()
        
        return cache_key
    
    def get(self, method: str, *args, **kwargs) -> Optional[Any]:
        """
        キャッシュから値を取得
        
        Args:
            method: 呼び出しメソッド名
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            キャッシュされた値、または None
        """
        cache_key = self._generate_cache_key(method, *args, **kwargs)
        self.stats["total_requests"] += 1
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            
            # TTL チェック
            if time.time() < cache_entry["expires_at"]:
                self.stats["hits"] += 1
                self.logger.debug(f"キャッシュヒット: {method} - キー: {cache_key[:8]}...")
                return cache_entry["value"]
            else:
                # 期限切れのエントリを削除
                del self.cache[cache_key]
                self.stats["cache_size"] = len(self.cache)
                self.logger.debug(f"キャッシュ期限切れ: {method} - キー: {cache_key[:8]}...")
        
        self.stats["misses"] += 1
        self.logger.debug(f"キャッシュミス: {method} - キー: {cache_key[:8]}...")
        return None
    
    def set(self, method: str, value: Any, ttl: Optional[int] = None, *args, **kwargs) -> None:
        """
        値をキャッシュに保存
        
        Args:
            method: 呼び出しメソッド名
            value: 保存する値
            ttl: TTL（秒）、Noneの場合はデフォルトTTLを使用
            *args: 位置引数
            **kwargs: キーワード引数
        """
        cache_key = self._generate_cache_key(method, *args, **kwargs)
        expires_at = time.time() + (ttl or self.default_ttl)
        
        self.cache[cache_key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
            "method": method
        }
        
        self.stats["cache_size"] = len(self.cache)
        self.logger.debug(f"キャッシュ保存: {method} - キー: {cache_key[:8]}... - TTL: {ttl or self.default_ttl}秒")
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        self.cache.clear()
        self.stats["cache_size"] = 0
        self.logger.info("キャッシュをクリアしました")
    
    def cleanup_expired(self) -> int:
        """期限切れのキャッシュエントリを削除"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time >= entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        self.stats["cache_size"] = len(self.cache)
        
        if expired_keys:
            self.logger.info(f"期限切れキャッシュエントリを {len(expired_keys)} 個削除しました")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        total_requests = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            "hit_rate": round(hit_rate, 2),
            "cache_entries": len(self.cache)
        }


class MCPClientService:
    """AWS MCP サーバーとの統合を管理するクライアントサービス"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        MCP クライアントサービスを初期化
        
        Args:
            config_path: MCP設定ファイルのパス（デフォルト: config/mcp_config.json）
        """
        self.logger = logging.getLogger(__name__)
        self.platform = platform.system().lower()
        self.config_path = config_path or self._get_default_config_path()
        self.mcp_client = None
        self.mcp_tools = {}
        self.config = self._load_config()
        
        # リクエストキャッシュを初期化
        self.request_cache = MCPRequestCache(default_ttl=300)  # 5分のデフォルトTTL
        
    def _get_default_config_path(self) -> str:
        """デフォルトの設定ファイルパスを取得"""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "config" / "mcp_config.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """MCP設定ファイルを読み込み"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # プラットフォーム固有の設定を適用
            if "platform_overrides" in config:
                platform_config = config["platform_overrides"].get(self.platform, {})
                if "mcpServers" in platform_config:
                    # プラットフォーム固有の設定でオーバーライド
                    for server_name, server_config in platform_config["mcpServers"].items():
                        if server_name in config["mcpServers"]:
                            config["mcpServers"][server_name].update(server_config)
                            
            return config
            
        except FileNotFoundError:
            self.logger.error(f"MCP設定ファイルが見つかりません: {self.config_path}")
            return {"mcpServers": {}}
        except json.JSONDecodeError as e:
            self.logger.error(f"MCP設定ファイルの解析に失敗しました: {e}")
            return {"mcpServers": {}}
    
    def _check_uvx_installation(self) -> bool:
        """uvxがインストールされているかチェック"""
        try:
            command = "uvx.exe" if self.platform == "windows" else "uvx"
            result = subprocess.run([command, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _install_uvx_if_needed(self) -> bool:
        """必要に応じてuvxをインストール"""
        if self._check_uvx_installation():
            return True
            
        self.logger.info("uvxが見つかりません。インストールを試行します...")
        
        try:
            if self.platform == "windows":
                # Windows: pipx経由でuvxをインストール
                subprocess.run(["pip", "install", "uvx"], check=True, timeout=60)
            else:
                # Mac/Linux: curl経由でインストール
                subprocess.run(["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"], 
                             shell=True, check=True, timeout=60)
                
            return self._check_uvx_installation()
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"uvxのインストールに失敗しました: {e}")
            return False
    
    def initialize_mcp_servers(self) -> bool:
        """MCP サーバーを初期化"""
        # MCP ライブラリが利用できない場合はフォールバックモードで動作
        if not MCP_AVAILABLE:
            self.logger.warning("langchain-mcp-adaptersライブラリが利用できません。フォールバックモードで動作します。")
            # 設定は読み込んでおく（フォールバック機能で使用）
            for server_name, server_config in self.config.get("mcpServers", {}).items():
                if not server_config.get("disabled", False):
                    self.mcp_tools[server_name] = {
                        "config": server_config,
                        "initialized": True,
                        "fallback_mode": True
                    }
            return len(self.mcp_tools) > 0
        
        if not self._install_uvx_if_needed():
            self.logger.warning("uvxのインストールに失敗しました。フォールバックモードで動作します。")
            return False
            
        try:
            # langchain-mcp-adaptersのMultiServerMCPClient用の設定を作成
            server_configs = {}
            
            for server_name, server_config in self.config.get("mcpServers", {}).items():
                if server_config.get("disabled", False):
                    continue
                    
                command = server_config.get("command", "uvx")
                args = server_config.get("args", [])
                env = server_config.get("env", {})
                
                if not command or not args:
                    self.logger.warning(f"不完全な設定: {server_name}")
                    continue
                    
                # MultiServerMCPClient用の設定形式に変換
                server_configs[server_name] = {
                    "command": command,
                    "args": args,
                    "env": env,
                    "transport": "stdio"
                }
                
                # 設定を保存（後で実際の接続時に使用）
                self.mcp_tools[server_name] = {
                    "config": server_config,
                    "initialized": True,
                    "fallback_mode": False
                }
            
            if server_configs:
                # MultiServerMCPClientを初期化（実際の接続は後で行う）
                self.mcp_client = MultiServerMCPClient(server_configs)
                self.logger.info(f"{len(server_configs)} のMCPサーバー設定が準備されました")
                return True
            else:
                self.logger.warning("有効なMCPサーバー設定が見つかりませんでした")
                return False
                
        except Exception as e:
            self.logger.error(f"MCPサーバー初期化エラー: {e}")
            return False
    
    def get_available_tools(self) -> List[str]:
        """利用可能なMCPツールのリストを取得"""
        tools = []
        for server_name, server_info in self.mcp_tools.items():
            if server_info.get("initialized", False):
                tools.append(server_name)
        return tools
    
    async def call_mcp_tool_async(self, server_name: str, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        指定されたMCPサーバーのツールを非同期で呼び出し
        
        Args:
            server_name: MCPサーバー名
            tool_name: ツール名
            **kwargs: ツールに渡すパラメータ
            
        Returns:
            ツールの実行結果、またはエラー時はNone
        """
        if not self.mcp_client:
            self.logger.error("MCPクライアントが初期化されていません")
            return None
            
        if server_name not in self.mcp_tools:
            self.logger.error(f"未知のMCPサーバー: {server_name}")
            return None
            
        try:
            # MCPクライアントからツールを取得
            tools = await self.mcp_client.get_tools()
            
            # 指定されたサーバーのツールを検索
            target_tool = None
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    target_tool = tool
                    break
            
            if not target_tool:
                self.logger.error(f"ツールが見つかりません: {tool_name}")
                return None
            
            # ツールを実行
            result = await target_tool.ainvoke(kwargs)
            return result
            
        except Exception as e:
            self.logger.error(f"MCPツール呼び出しエラー: {e}")
            return None
    
    def call_mcp_tool(self, server_name: str, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        指定されたMCPサーバーのツールを呼び出し（同期版）
        
        Args:
            server_name: MCPサーバー名
            tool_name: ツール名
            **kwargs: ツールに渡すパラメータ
            
        Returns:
            ツールの実行結果、またはエラー時はNone
        """
        try:
            # 新しいイベントループを作成して実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.call_mcp_tool_async(server_name, tool_name, **kwargs)
                )
            finally:
                loop.close()
        except Exception as e:
            self.logger.error(f"同期MCPツール呼び出しエラー: {e}")
            return None
    
    def get_core_mcp_guidance(self, prompt: str) -> Optional[str]:
        """
        Core MCPサーバーからプロンプトの理解とガイダンスを取得
        
        Args:
            prompt: 分析対象のプロンプト
            
        Returns:
            ガイダンス内容、またはエラー時はNone
        """
        # キャッシュから確認
        cached_result = self.request_cache.get("get_core_mcp_guidance", prompt)
        if cached_result is not None:
            return cached_result
        
        # MCP統合が完全に動作するまでは、静的なガイダンスを返す
        try:
            # 将来的にはMCPサーバーから動的に取得
            # result = self.call_mcp_tool("awslabs.core-mcp-server", "prompt_understanding", prompt=prompt)
            
            # 現在は基本的なガイダンスを提供
            result = None
            if any(keyword in prompt.lower() for keyword in ["vpc", "network", "subnet"]):
                result = "VPC設計では、パブリック/プライベートサブネットの分離、マルチAZ構成、適切なルーティング設定を考慮してください。"
            elif any(keyword in prompt.lower() for keyword in ["lambda", "serverless"]):
                result = "サーバーレス構成では、イベント駆動設計、適切な権限設定、コールドスタート対策を考慮してください。"
            elif any(keyword in prompt.lower() for keyword in ["rds", "database"]):
                result = "データベース設計では、マルチAZ、バックアップ戦略、セキュリティグループ、暗号化を考慮してください。"
            else:
                result = "AWS Well-Architected Frameworkに基づき、信頼性、セキュリティ、コスト効率、パフォーマンスを考慮した設計を心がけてください。"
            
            # 結果をキャッシュに保存（ガイダンスは比較的長期間有効）
            if result:
                self.request_cache.set("get_core_mcp_guidance", result, 600, prompt)  # 10分キャッシュ
            
            return result
                
        except Exception as e:
            self.logger.error(f"Core MCPガイダンス取得エラー: {e}")
            return None
    
    def get_aws_documentation(self, query: str) -> Optional[Dict[str, Any]]:
        """
        AWS Documentation MCPサーバーから情報を取得
        
        Args:
            query: 検索クエリ
            
        Returns:
            ドキュメント情報、またはエラー時はNone
        """
        # キャッシュから確認
        cached_result = self.request_cache.get("get_aws_documentation", query)
        if cached_result is not None:
            return cached_result
        
        # MCP統合が完全に動作するまでは、基本的な情報を返す
        try:
            # 将来的にはMCPサーバーから動的に取得
            # return self.call_mcp_tool("awslabs.aws-documentation-mcp-server", "search_documentation", query=query)
            
            # 現在は基本的なドキュメント情報を提供
            common_services = {
                "ec2": "Amazon EC2は、クラウド内で安全でサイズ変更可能な仮想サーバーを提供します。",
                "s3": "Amazon S3は、業界トップクラスのスケーラビリティ、データ可用性、セキュリティ、パフォーマンスを提供するオブジェクトストレージサービスです。",
                "rds": "Amazon RDSは、クラウド内でリレーショナルデータベースの設定、運用、スケーリングを簡単に行えるWebサービスです。",
                "lambda": "AWS Lambdaは、サーバーのプロビジョニングや管理なしにコードを実行できるコンピューティングサービスです。"
            }
            
            result = None
            for service, description in common_services.items():
                if service in query.lower():
                    result = {"service": service, "description": description, "source": "local_cache"}
                    break
            
            if result is None:
                result = {"general": "AWS公式ドキュメントを参照することをお勧めします。", "source": "local_cache"}
            
            # 結果をキャッシュに保存（ドキュメント情報は長期間有効）
            if result:
                self.request_cache.set("get_aws_documentation", result, 1800, query)  # 30分キャッシュ
            
            return result
            
        except Exception as e:
            self.logger.error(f"AWS ドキュメント取得エラー: {e}")
            return None
    
    def generate_terraform_code(self, requirements: str) -> Optional[str]:
        """
        Terraform MCPサーバーからコード生成
        
        Args:
            requirements: Terraformコード生成要件
            
        Returns:
            生成されたTerraformコード、またはエラー時はNone
        """
        # キャッシュから確認
        cached_result = self.request_cache.get("generate_terraform_code", requirements)
        if cached_result is not None:
            return cached_result
        
        # MCP統合が完全に動作するまでは、基本的なテンプレートを返す
        try:
            # 将来的にはMCPサーバーから動的に取得
            # result = self.call_mcp_tool("awslabs.terraform-mcp-server", "generate_terraform", requirements=requirements)
            
            # 現在は基本的なTerraformテンプレートを提供
            result = None
            if "vpc" in requirements.lower():
                result = '''
# VPC基本構成テンプレート
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "main-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "public-subnet"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = {
    Name = "main-igw"
  }
}
'''
            elif "lambda" in requirements.lower():
                result = '''
# Lambda基本構成テンプレート
resource "aws_lambda_function" "main" {
  filename         = "lambda.zip"
  function_name    = "main-function"
  role            = aws_iam_role.lambda_role.arn
  handler         = "index.handler"
  source_code_hash = filebase64sha256("lambda.zip")
  runtime         = "python3.9"
  
  tags = {
    Name = "main-lambda"
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "lambda-execution-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}
'''
            else:
                result = "# 詳細な要件を指定してください。MCP統合により、より具体的なTerraformコードが生成されます。"
            
            # 結果をキャッシュに保存（Terraformコードは短期間有効）
            if result:
                self.request_cache.set("generate_terraform_code", result, 180, requirements)  # 3分キャッシュ
            
            return result
                
        except Exception as e:
            self.logger.error(f"Terraform コード生成エラー: {e}")
            return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        return self.request_cache.get_stats()
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self.request_cache.clear()
        
    def cleanup_expired_cache(self) -> int:
        """期限切れキャッシュを削除"""
        return self.request_cache.cleanup_expired()


# Streamlit用のセッション管理
def get_mcp_client() -> MCPClientService:
    """StreamlitセッションでMCPクライアントを取得/初期化"""
    if "mcp_client" not in st.session_state:
        try:
            st.session_state.mcp_client = MCPClientService()
            
            # 初回のみ初期化を実行
            if "mcp_initialized" not in st.session_state:
                # UIの通知は最小限にし、エラーが発生しても続行
                try:
                    success = st.session_state.mcp_client.initialize_mcp_servers()
                    st.session_state.mcp_initialized = success
                    
                    if success:
                        # 成功メッセージは最初だけ表示
                        if not st.session_state.get("mcp_success_shown", False):
                            st.sidebar.success("✅ MCP統合が利用可能です")
                            st.session_state.mcp_success_shown = True
                    else:
                        # 失敗時は警告のみ（フォールバック機能で動作継続）
                        if not st.session_state.get("mcp_warning_shown", False):
                            # より詳細なデバッグ情報を表示
                            debug_info = f"MCP_AVAILABLE: {MCP_AVAILABLE}"
                            if not MCP_AVAILABLE:
                                debug_info += " (langchain-mcp-adaptersが見つかりません)"
                            st.sidebar.warning(f"⚠️ MCP統合は利用できません\n\nデバッグ情報: {debug_info}")
                            st.session_state.mcp_warning_shown = True
                except Exception as e:
                    # 初期化エラーでも続行
                    st.session_state.mcp_initialized = False
                    if not st.session_state.get("mcp_error_shown", False):
                        st.sidebar.info("ℹ️ MCP統合なしで動作しています")
                        st.session_state.mcp_error_shown = True
        except Exception as e:
            # クライアント作成エラーでも最低限の機能を提供
            st.session_state.mcp_client = None
            st.session_state.mcp_initialized = False
            # デバッグ用：エラー情報を保存
            st.session_state.mcp_client_error = str(e)
    
    # MCPクライアントがNoneの場合はダミークライアントを返す
    if st.session_state.mcp_client is None:
        # 基本的な機能のみ提供するダミークライアント
        class DummyMCPClient:
            def get_available_tools(self):
                return []
            def get_core_mcp_guidance(self, prompt):
                return None
            def get_aws_documentation(self, query):
                return None
            def generate_terraform_code(self, requirements):
                return None
        
        return DummyMCPClient()
    
    return st.session_state.mcp_client