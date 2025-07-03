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
    
    def get_cost_estimation(self, service_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        AWS構成のコスト見積もりをCost Analysis MCP Serverから取得
        
        Args:
            service_config: サービス構成情報 {
                "service_name": str,    # EC2, S3, RDS等
                "region": str,          # us-east-1等
                "instance_type": str,   # t3.medium等 (EC2の場合)
                "usage_details": dict   # 使用量詳細
            }
            
        Returns:
            コスト見積もり結果、またはエラー時はNone {
                "cost": float,              # 月額コスト
                "detail": str,              # 構成詳細
                "optimization": str,        # 最適化提案
                "current_state": str,       # 現在の状態
                "reduction_rate": float     # 削減率 (0.0-1.0)
            }
        """
        # キャッシュから確認
        cache_key_data = f"{service_config.get('service_name')}_{service_config.get('instance_type', 'default')}_{service_config.get('region', 'us-east-1')}"
        cached_result = self.request_cache.get("get_cost_estimation", cache_key_data)
        if cached_result is not None:
            return cached_result
        
        try:
            # 実際のCost Analysis MCP Serverを呼び出し
            service_name = service_config.get("service_name", "").upper()
            region = service_config.get("region", "us-east-1")
            instance_type = service_config.get("instance_type")
            
            # Cost Analysis MCP Serverに送信する自然言語クエリを作成
            query = f"Provide cost estimate for AWS {service_name}"
            if instance_type:
                query += f" using {instance_type} instance"
            query += f" in {region} region"
            if service_config.get("usage_details"):
                query += f" with usage: {service_config['usage_details']}"
            
            # 実際のMCPサーバー呼び出し
            mcp_result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_cost", query=query)
            
            if mcp_result and isinstance(mcp_result, dict):
                # MCPサーバーの結果を既存の形式に変換
                result = self._convert_mcp_result_to_standard_format(mcp_result, service_name, instance_type, region)
                
                # 結果をキャッシュに保存（コスト見積もりは短期間有効）
                if result:
                    self.request_cache.set("get_cost_estimation", result, 300, cache_key_data)  # 5分キャッシュ
                
                return result
            else:
                # MCPサーバーからの応答が無効な場合はフォールバック
                self.logger.warning(f"MCPサーバーからの無効な応答、フォールバック使用: {service_name}")
                return self._calculate_fallback_cost_estimate(service_name, region, instance_type)
                
        except Exception as e:
            self.logger.error(f"Cost Analysis MCP Server呼び出しエラー: {e}")
            # エラー時はフォールバック計算を使用
            return self._calculate_fallback_cost_estimate(
                service_config.get("service_name", "").upper(), 
                service_config.get("region", "us-east-1"), 
                service_config.get("instance_type")
            )
    
    def _convert_mcp_result_to_standard_format(self, mcp_result: Dict[str, Any], service_name: str, instance_type: Optional[str], region: str) -> Optional[Dict[str, Any]]:
        """
        Cost Analysis MCP Serverの結果を標準形式に変換
        
        Args:
            mcp_result: MCPサーバーからの生の結果
            service_name: AWSサービス名
            instance_type: インスタンスタイプ
            region: AWSリージョン
            
        Returns:
            標準形式のコスト見積もり
        """
        try:
            # MCPサーバーの結果から必要な情報を抽出
            # 実際のMCPサーバーのレスポンス形式に応じて調整が必要
            
            # レスポンスが文字列の場合
            if isinstance(mcp_result, str):
                return self._parse_text_cost_result(mcp_result, service_name, instance_type, region)
            
            # レスポンスが辞書の場合
            monthly_cost = 0
            detail = f"{service_name}"
            if instance_type:
                detail += f" {instance_type}"
            detail += f" ({region})"
                
            # MCPサーバーから価格情報を抽出（一般的なフィールド名で試行）
            if "cost" in mcp_result:
                monthly_cost = float(mcp_result["cost"])
            elif "price" in mcp_result:
                monthly_cost = float(mcp_result["price"])
            elif "monthly_cost" in mcp_result:
                monthly_cost = float(mcp_result["monthly_cost"])
            else:
                # 数値を含む文字列から価格を抽出
                import re
                text = str(mcp_result)
                price_matches = re.findall(r'\$?(\d+\.?\d*)', text)
                if price_matches:
                    monthly_cost = float(price_matches[0])
            
            # 最適化提案を抽出
            optimization = mcp_result.get("optimization", "Reserved Instance検討")
            if "recommendation" in mcp_result:
                optimization = mcp_result["recommendation"]
            
            return {
                "cost": monthly_cost,
                "detail": detail,
                "optimization": optimization,
                "current_state": "オンデマンド",
                "reduction_rate": 0.25  # デフォルト削減率
            }
            
        except Exception as e:
            self.logger.error(f"MCP結果変換エラー: {e}")
            return None
    
    def _parse_text_cost_result(self, text_result: str, service_name: str, instance_type: Optional[str], region: str) -> Dict[str, Any]:
        """
        テキスト形式のMCP結果から価格情報を抽出
        
        Args:
            text_result: MCPサーバーからのテキスト結果
            service_name: AWSサービス名
            instance_type: インスタンスタイプ
            region: AWSリージョン
            
        Returns:
            標準形式のコスト見積もり
        """
        import re
        
        # 価格パターンを検索（$記号付きまたは数値のみ）
        price_patterns = [
            r'\$(\d+\.?\d*)\s*(?:per\s+month|monthly|\/month)',
            r'(\d+\.?\d*)\s*USD\s*(?:per\s+month|monthly|\/month)',
            r'\$(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*USD'
        ]
        
        monthly_cost = 0
        for pattern in price_patterns:
            match = re.search(pattern, text_result, re.IGNORECASE)
            if match:
                monthly_cost = float(match.group(1))
                break
        
        # 詳細情報を構築
        detail = f"{service_name}"
        if instance_type:
            detail += f" {instance_type}"
        detail += f" ({region})"
        
        # 最適化提案をテキストから抽出
        optimization = "Reserved Instance検討"
        if "reserved" in text_result.lower():
            optimization = "Reserved Instance利用"
        elif "spot" in text_result.lower():
            optimization = "Spot Instance検討"
        elif "saving" in text_result.lower():
            optimization = "Savings Plans検討"
        
        return {
            "cost": monthly_cost,
            "detail": detail,
            "optimization": optimization,
            "current_state": "オンデマンド",
            "reduction_rate": 0.25
        }
    
    def _calculate_fallback_cost_estimate(self, service_name: str, region: str, instance_type: Optional[str]) -> Dict[str, Any]:
        """
        MCP呼び出し失敗時のフォールバック計算
        
        Args:
            service_name: AWSサービス名
            region: AWSリージョン
            instance_type: インスタンスタイプ
            
        Returns:
            フォールバック計算されたコスト見積もり
        """
        # 既存の動的計算ロジックを簡略化して使用
        region_multiplier = {
            "us-east-1": 1.0, "us-west-2": 1.05, "eu-west-1": 1.1,
            "ap-northeast-1": 1.15, "ap-southeast-1": 1.12
        }.get(region, 1.0)
        
        instance_multiplier = {
            "t3.nano": 0.5, "t3.micro": 0.75, "t3.small": 1.0,
            "t3.medium": 1.5, "t3.large": 2.0, "t3.xlarge": 3.0
        }.get(instance_type, 1.0) if instance_type else 1.0
        
        base_costs = {
            "EC2": 25, "S3": 20, "RDS": 70, "LAMBDA": 12, 
            "CLOUDFRONT": 18, "VPC": 8
        }
        
        base_cost = base_costs.get(service_name, 30)
        final_cost = base_cost * region_multiplier * instance_multiplier
        
        return {
            "cost": final_cost,
            "detail": f"{service_name} {instance_type or '標準'} ({region}) [フォールバック]",
            "optimization": "詳細分析が必要",
            "current_state": "デフォルト構成",
            "reduction_rate": 0.15
        }
    
    
    def analyze_cost_with_natural_language(self, query: str) -> Optional[str]:
        """
        自然言語でのコスト問い合わせ（Cost Analysis MCP Server）
        
        Args:
            query: 自然言語でのコスト関連質問
            
        Returns:
            コスト分析結果、またはエラー時はNone
        """
        # キャッシュから確認
        cached_result = self.request_cache.get("analyze_cost_with_natural_language", query)
        if cached_result is not None:
            return cached_result
        
        try:
            # Cost Analysis MCP Serverの自然言語クエリ機能を呼び出し
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_cost", query=query)
            
            if result:
                # 結果をキャッシュに保存（長期間有効）
                self.request_cache.set("analyze_cost_with_natural_language", result, 600, query)  # 10分キャッシュ
                return str(result)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"自然言語コスト分析エラー: {e}")
            return None
    
    def analyze_infrastructure_project_cost(self, project_path: str, project_type: str = "terraform") -> Optional[Dict[str, Any]]:
        """
        CDK/Terraformプロジェクトのコスト分析
        
        Args:
            project_path: プロジェクトファイルパス
            project_type: プロジェクトタイプ ("terraform", "cdk")
            
        Returns:
            プロジェクトコスト分析結果、またはエラー時はNone
        """
        # キャッシュから確認
        cache_key = f"{project_path}_{project_type}"
        cached_result = self.request_cache.get("analyze_infrastructure_project_cost", cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Cost Analysis MCP ServerのIaCプロジェクト分析機能を呼び出し
            if project_type.lower() == "terraform":
                result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_terraform", project_path=project_path)
            elif project_type.lower() == "cdk":
                result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_cdk", project_path=project_path)
            else:
                self.logger.error(f"サポートされていないプロジェクトタイプ: {project_type}")
                return None
            
            if result:
                # 結果をキャッシュに保存（中期間有効）
                self.request_cache.set("analyze_infrastructure_project_cost", result, 900, cache_key)  # 15分キャッシュ
                return result
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"IaCプロジェクトコスト分析エラー: {e}")
            return None
    
    def generate_comprehensive_cost_report(self, services: List[str], region: str = "us-east-1") -> Optional[str]:
        """
        包括的なコストレポート生成
        
        Args:
            services: 分析対象AWSサービスリスト
            region: 対象リージョン
            
        Returns:
            包括的なコストレポート、またはエラー時はNone
        """
        # キャッシュから確認
        cache_key = f"{'-'.join(sorted(services))}_{region}"
        cached_result = self.request_cache.get("generate_comprehensive_cost_report", cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # サービスリストとリージョンを含むクエリを構築
            query = f"Generate comprehensive cost report for AWS services: {', '.join(services)} in {region} region with optimization recommendations"
            
            # Cost Analysis MCP Serverの包括的レポート生成機能を呼び出し
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "generate_report", 
                                      services=services, region=region, query=query)
            
            if result:
                # 結果をキャッシュに保存（短期間有効）
                self.request_cache.set("generate_comprehensive_cost_report", result, 300, cache_key)  # 5分キャッシュ
                return str(result)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"包括的コストレポート生成エラー: {e}")
            return None
    
    def get_cost_optimization_recommendations(self, current_setup: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        コスト最適化推奨事項の取得
        
        Args:
            current_setup: 現在のAWS構成情報
            
        Returns:
            最適化推奨事項リスト、またはエラー時はNone
        """
        # キャッシュから確認
        cache_key = str(sorted(current_setup.items()))
        cached_result = self.request_cache.get("get_cost_optimization_recommendations", cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Cost Analysis MCP Serverの最適化推奨機能を呼び出し
            query = f"Provide cost optimization recommendations for current AWS setup: {current_setup}"
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "optimize_cost", 
                                      current_setup=current_setup, query=query)
            
            if result:
                # 結果をリスト形式に変換
                if isinstance(result, str):
                    # テキスト結果を構造化データに変換
                    recommendations = self._parse_optimization_recommendations(result)
                elif isinstance(result, list):
                    recommendations = result
                else:
                    recommendations = [{"recommendation": str(result), "priority": "medium"}]
                
                # 結果をキャッシュに保存（中期間有効）
                self.request_cache.set("get_cost_optimization_recommendations", recommendations, 600, cache_key)  # 10分キャッシュ
                return recommendations
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"コスト最適化推奨事項取得エラー: {e}")
            return None
    
    def _parse_optimization_recommendations(self, text_result: str) -> List[Dict[str, Any]]:
        """
        テキスト形式の最適化推奨事項を構造化データに変換
        
        Args:
            text_result: テキスト形式の推奨事項
            
        Returns:
            構造化された推奨事項リスト
        """
        import re
        
        recommendations = []
        
        # 推奨事項のパターンを検索
        lines = text_result.split('\n')
        current_recommendation = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 推奨事項の開始を検出
            if re.match(r'^\d+\.', line) or line.startswith('-') or line.startswith('•'):
                if current_recommendation:
                    recommendations.append(current_recommendation)
                
                current_recommendation = {
                    "recommendation": line,
                    "priority": "medium",
                    "estimated_savings": None
                }
            
            # 節約額を抽出
            savings_match = re.search(r'\$(\d+\.?\d*)', line)
            if savings_match and current_recommendation:
                current_recommendation["estimated_savings"] = float(savings_match.group(1))
            
            # 優先度を推定
            if any(keyword in line.lower() for keyword in ["critical", "high", "urgent"]):
                current_recommendation["priority"] = "high"
            elif any(keyword in line.lower() for keyword in ["low", "minor", "optional"]):
                current_recommendation["priority"] = "low"
        
        # 最後の推奨事項を追加
        if current_recommendation:
            recommendations.append(current_recommendation)
        
        # 推奨事項が見つからない場合は汎用的な推奨事項を返す
        if not recommendations:
            recommendations = [
                {
                    "recommendation": "Reserved Instancesの検討",
                    "priority": "medium",
                    "estimated_savings": None
                }
            ]
        
        return recommendations

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