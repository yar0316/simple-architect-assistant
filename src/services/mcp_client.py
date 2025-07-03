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

# 新しいAWSServiceCodeHelperをインポート
try:
    from .aws_service_code_helper import get_service_code_helper
    # インポート成功は通常のINFOレベルでログ出力（モジュール初期化時のため、ここではloggingモジュール使用）
    logging.info("💼 [AWSServiceCodeHelper] インポート成功")
except ImportError as import_error:
    logging.warning(f"💼 [AWSServiceCodeHelper] インポート失敗: {import_error}")
    
    # フォールバック関数を定義
    def get_service_code_helper():
        class FallbackHelper:
            def find_service_code(self, service_name):
                return None
            def search_services(self, keyword):
                return []
            def get_service_info(self, service_name):
                return None
        return FallbackHelper()

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
        self.logger.setLevel(logging.INFO)  # INFOレベル以上のログを表示
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
                
            # platform_overridesは削除されたため、基本設定のみを使用
                            
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
                    "initialized": False,  # 実際の接続確認後にTrue
                    "fallback_mode": False,
                    "connection_status": "configured",  # configured, connecting, connected, failed
                    "last_connection_attempt": None,
                    "connection_error": None,
                    "available_tools": []
                }
            
            if server_configs:
                # MultiServerMCPClientを初期化
                self.mcp_client = MultiServerMCPClient(server_configs)
                self.logger.info(f"{len(server_configs)} のMCPサーバー設定が準備されました")
                
                # 非同期で接続確認を実行
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success_count = loop.run_until_complete(self._verify_mcp_connections())
                    self.logger.info(f"MCP接続確認完了: {success_count}/{len(server_configs)} サーバーが利用可能")
                    return success_count > 0
                finally:
                    loop.close()
            else:
                self.logger.warning("有効なMCPサーバー設定が見つかりませんでした")
                return False
                
        except Exception as e:
            self.logger.error(f"MCPサーバー初期化エラー: {e}")
            return False
    
    async def _verify_mcp_connections(self) -> int:
        """MCPサーバーへの接続を確認し、状態を更新"""
        success_count = 0
        
        for server_name in self.mcp_tools.keys():
            try:
                self.logger.info(f"🔍 MCP接続確認開始: {server_name}")
                self.mcp_tools[server_name]["connection_status"] = "connecting"
                self.mcp_tools[server_name]["last_connection_attempt"] = datetime.now()
                
                # タイムアウト付きでツール一覧を取得
                tools = await asyncio.wait_for(
                    self.mcp_client.get_tools(), 
                    timeout=10.0
                )
                
                if tools:
                    # サーバー固有のツールを抽出
                    server_tools = []
                    for tool in tools:
                        tool_info = f"{getattr(tool, 'name', 'unknown')}"
                        if hasattr(tool, 'server_name') and tool.server_name == server_name:
                            server_tools.append(tool_info)
                        elif not hasattr(tool, 'server_name'):
                            # サーバー名情報がない場合は候補として記録
                            server_tools.append(f"{tool_info}?")
                    
                    self.mcp_tools[server_name]["available_tools"] = server_tools
                    self.mcp_tools[server_name]["connection_status"] = "connected"
                    self.mcp_tools[server_name]["initialized"] = True
                    self.mcp_tools[server_name]["connection_error"] = None
                    
                    self.logger.info(f"✅ MCP接続成功: {server_name} -> {len(server_tools)}個のツール")
                    success_count += 1
                    
                else:
                    self.logger.warning(f"⚠️  MCP接続はできたがツールが見つからない: {server_name}")
                    self.mcp_tools[server_name]["connection_status"] = "connected_no_tools"
                    self.mcp_tools[server_name]["initialized"] = False
                    
            except asyncio.TimeoutError:
                error_msg = f"接続タイムアウト（10秒）: {server_name}"
                self.logger.warning(f"⏰ {error_msg}")
                self.mcp_tools[server_name]["connection_status"] = "timeout"
                self.mcp_tools[server_name]["connection_error"] = error_msg
                self.mcp_tools[server_name]["initialized"] = False
                
            except Exception as e:
                error_msg = f"接続エラー: {str(e)}"
                self.logger.error(f"❌ MCP接続失敗: {server_name} -> {error_msg}")
                self.mcp_tools[server_name]["connection_status"] = "failed"
                self.mcp_tools[server_name]["connection_error"] = error_msg
                self.mcp_tools[server_name]["initialized"] = False
        
        return success_count
    
    def get_available_tools(self) -> List[str]:
        """利用可能なMCPツールのリストを取得"""
        tools = []
        for server_name, server_info in self.mcp_tools.items():
            if server_info.get("initialized", False):
                tools.append(server_name)
        return tools
    
    def get_mcp_server_status(self) -> Dict[str, Dict[str, Any]]:
        """MCPサーバーの詳細状態を取得"""
        status = {}
        for server_name, server_info in self.mcp_tools.items():
            status[server_name] = {
                "connection_status": server_info.get("connection_status", "unknown"),
                "initialized": server_info.get("initialized", False),
                "fallback_mode": server_info.get("fallback_mode", False),
                "available_tools": server_info.get("available_tools", []),
                "last_connection_attempt": server_info.get("last_connection_attempt"),
                "connection_error": server_info.get("connection_error")
            }
        return status
    
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
        self.logger.info(f"🔄 [MCP] ツール呼び出し開始: サーバー='{server_name}', ツール='{tool_name}'")
        self.logger.debug(f"   - パラメータ: {kwargs}")
        
        # MCPクライアントの初期化状態確認
        if not self.mcp_client:
            self.logger.error(f"❌ MCPクライアントが初期化されていません（サーバー: {server_name}）")
            return None
        
        # フォールバックモードの場合は静的結果を返す
        if server_name in self.mcp_tools and self.mcp_tools[server_name].get("fallback_mode", False):
            self.logger.info(f"🔄 フォールバックモード: {server_name}.{tool_name}")
            return self._handle_fallback_tool_call(server_name, tool_name, **kwargs)
        
        # サーバー設定の確認
        if server_name not in self.mcp_tools:
            self.logger.warning(f"⚠️  未知のMCPサーバー: {server_name}")
            self.logger.info(f"   - 利用可能サーバー: {list(self.mcp_tools.keys())}")
            return None
            
        try:
            # MCPクライアントからツールを取得
            self.logger.debug(f"   🔍 MCPクライアントからツール一覧取得中...")
            tools = await self.mcp_client.get_tools()
            self.logger.info(f"   - 取得されたツール数: {len(tools)}")
            
            # デバッグ用：利用可能なツール一覧を表示
            available_tools = []
            for tool in tools:
                tool_info = f"{getattr(tool, 'name', 'NO_NAME')}"
                if hasattr(tool, 'server_name'):
                    tool_info += f"@{tool.server_name}"
                available_tools.append(tool_info)
            
            self.logger.debug(f"   - 利用可能ツール: {available_tools}")
            
            # サーバー固有のツールを検索
            target_tool = None
            matching_tools = []
            
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    matching_tools.append(tool)
                    
                    # サーバー名が一致するツールを優先
                    if hasattr(tool, 'server_name') and tool.server_name == server_name:
                        target_tool = tool
                        self.logger.info(f"   ✅ サーバー固有ツール発見: {server_name}.{tool_name}")
                        break
                    # サーバー名情報がない場合は、とりあえず候補として保持
                    elif not target_tool:
                        target_tool = tool
            
            if not target_tool:
                self.logger.error(f"❌ ツールが見つかりません: {tool_name}")
                self.logger.info(f"   - 一致するツール: {len(matching_tools)}個")
                if matching_tools:
                    for i, tool in enumerate(matching_tools):
                        server_info = getattr(tool, 'server_name', 'unknown_server')
                        self.logger.info(f"     {i+1}. {tool.name}@{server_info}")
                return None
            
            # ツールが見つからない場合でも、フォールバック処理を試行
            if not target_tool and tool_name in ["get_pricing_from_api", "get_pricing_from_web"]:
                self.logger.info(f"🔄 Cost Analysis MCP未利用、フォールバック処理を実行")
                return self._handle_fallback_tool_call(server_name, tool_name, **kwargs)
            
            # ツールを実行
            self.logger.info(f"   🚀 MCPツール実行: {tool_name}")
            result = await target_tool.ainvoke(kwargs)
            
            if result:
                self.logger.info(f"   ✅ MCPツール実行成功: {tool_name}")
                self.logger.debug(f"   - 結果タイプ: {type(result)}")
                self.logger.debug(f"   - 結果サイズ: {len(str(result))} 文字")
            else:
                self.logger.warning(f"   ❌ MCPツール実行結果が空: {tool_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ MCPツール呼び出し例外: {tool_name} -> {e}")
            import traceback
            self.logger.debug(f"   - 詳細トレースバック: {traceback.format_exc()}")
            
            # 例外が発生した場合もフォールバックを試行
            if tool_name in ["get_pricing_from_api", "get_pricing_from_web"]:
                self.logger.info(f"🔄 例外後フォールバック処理実行: {tool_name}")
                return self._handle_fallback_tool_call(server_name, tool_name, **kwargs)
            
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
            # AWSServiceCodeHelperを使用して正しいサービスコードを取得
            service_name_input = service_config.get("service_name", "")
            region = service_config.get("region", "us-east-1")
            instance_type = service_config.get("instance_type")
            
            # サービスコードヘルパーからサービスコードを取得
            self.logger.info(f"💼 サービス名入力: '{service_name_input}'")
            
            try:
                service_code_helper = get_service_code_helper()
                self.logger.debug(f"サービスコードヘルパー取得成功: {type(service_code_helper)}")
                
            except Exception as helper_error:
                self.logger.error(f"サービスコードヘルパー取得失敗: {helper_error}")
                return self._calculate_fallback_cost_estimate(service_name_input.upper(), region, instance_type)
            
            # AWSServiceCodeHelperの状況確認
            self.logger.debug(f"サービスコード辞書の状況: {bool(service_code_helper.service_codes)}")
            
            if service_code_helper.service_codes:
                self.logger.debug(f"辞書サイズ: {len(service_code_helper.service_codes)}")
            else:
                self.logger.warning("サービスコード辞書が空または未初期化")
            
            # find_service_codeメソッド呼び出し
            try:
                service_code = service_code_helper.find_service_code(service_name_input)
                self.logger.info(f"💼 [サービスコード変換] '{service_name_input}' → '{service_code}'")
            except Exception as find_error:
                self.logger.error(f"find_service_code呼び出し例外: {find_error}")
                service_code = None
            
            if not service_code:
                # サービスコードが見つからない場合、候補を提案
                suggestions = service_code_helper.search_services(service_name_input[:5])
                self.logger.warning(f"サービスコードが見つかりません: {service_name_input}")
                if suggestions:
                    self.logger.info(f"候補サービス: {[s['service_name'] for s in suggestions[:3]]}")
                
                # フォールバック処理
                self.logger.info(f"サービスコード未発見のため最終フォールバックを使用: {service_name_input.upper()}")
                return self._calculate_fallback_cost_estimate(service_name_input.upper(), region, instance_type)
            
            # 有効なリージョンをチェック
            valid_regions = [
                "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
                "ap-northeast-1", "ap-northeast-2", "ap-southeast-1", "ap-southeast-2",
                "ap-south-1", "ca-central-1", "sa-east-1"
            ]
            
            if region not in valid_regions:
                self.logger.warning(f"無効なリージョン: {region}, デフォルトのus-east-1を使用")
                region = "us-east-1"
            
            self.logger.info(f"使用リージョン: {region}")
            
            # Cost Analysis MCP Serverに送信する自然言語クエリを作成
            service_info = service_code_helper.get_service_info(service_name_input)
            display_name = service_info['service_name'] if service_info else service_name_input
            
            query = f"Provide cost estimate for AWS {display_name}"
            if instance_type:
                query += f" using {instance_type} instance"
            query += f" in {region} region"
            if service_config.get("usage_details"):
                query += f" with usage: {service_config['usage_details']}"
            
            # 実際のMCPサーバー呼び出し（まずAPIから、失敗時はWebから）
            mcp_result = None
            
            # 最初にAPI経由で価格情報を取得
            try:
                self.logger.info(f"🔄 [Cost Analysis MCP] API呼び出し開始")
                self.logger.info(f"   - サーバー: awslabs.cost-analysis-mcp-server")
                self.logger.info(f"   - ツール: get_pricing_from_api")
                self.logger.debug(f"   - パラメータ: service_code='{service_code}', region='{region}'")
                
                mcp_result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "get_pricing_from_api", 
                                              service_code=service_code, region=region)
                
                if mcp_result:
                    self.logger.info(f"   ✅ Cost Analysis MCP API呼び出し成功")
                    self.logger.debug(f"   - 結果タイプ: {type(mcp_result)}")
                    self.logger.debug(f"   - 結果サイズ: {len(str(mcp_result))} 文字")
                else:
                    self.logger.warning(f"   ❌ Cost Analysis MCP API呼び出し失敗: 結果がNone")
            except Exception as api_error:
                self.logger.warning(f"❌ Cost Analysis MCP API呼び出し例外: {api_error}")
                
                # API失敗時はWeb検索にフォールバック
                try:
                    self.logger.info(f"   🔄 Cost Analysis MCP Server Web検索にフォールバック")
                    self.logger.info(f"   - サーバー: awslabs.cost-analysis-mcp-server")
                    self.logger.info(f"   - ツール: get_pricing_from_web")
                    self.logger.debug(f"   - パラメータ: query='{query}'")
                    
                    mcp_result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "get_pricing_from_web", query=query)
                    
                    if mcp_result:
                        self.logger.info(f"   ✅ Cost Analysis MCP Web検索成功")
                        self.logger.debug(f"   - 結果タイプ: {type(mcp_result)}")
                        self.logger.debug(f"   - 結果サイズ: {len(str(mcp_result))} 文字")
                    else:
                        self.logger.warning(f"   ❌ Cost Analysis MCP Web検索失敗: 結果がNone")
                        
                except Exception as web_error:
                    self.logger.error(f"❌ Cost Analysis MCP Web検索例外: {web_error}")
                    mcp_result = None
            
            if mcp_result:
                self.logger.info(f"   ✅ Cost Analysis MCP Server成功、結果変換中")
                # MCPサーバーの結果を既存の形式に変換
                result = self._convert_mcp_result_to_standard_format(mcp_result, service_code, instance_type, region)
                
                if result:
                    self.logger.info(f"   ✅ Cost Analysis結果変換成功: {result['cost']}USD/月")
                    # 結果をキャッシュに保存（コスト見積もりは短期間有効）
                    self.request_cache.set("get_cost_estimation", result, 300, cache_key_data)  # 5分キャッシュ
                    return result
                else:
                    self.logger.warning(f"   ❌ Cost Analysis結果変換失敗")
            
            # Cost Analysis MCPが失敗した場合、AWS Documentation MCPから価格情報を取得
            self.logger.info(f"   🔄 AWS Documentation MCPにフォールバック: {service_code}")
            doc_result = self._get_pricing_from_aws_documentation(service_code, region, instance_type, display_name)
            
            if doc_result:
                self.logger.info(f"   ✅ AWS Documentation MCP成功: {doc_result['cost']}USD/月")
                # AWS Documentation MCPからの結果をキャッシュに保存
                self.request_cache.set("get_cost_estimation", doc_result, 300, cache_key_data)
                return doc_result
            else:
                # AWS Documentation MCPも失敗した場合、最終フォールバック
                self.logger.info(f"   🔄 最終フォールバック（静的計算）使用: {service_code}")
                fallback_result = self._calculate_fallback_cost_estimate(service_code, region, instance_type)
                self.logger.info(f"   ✅ 最終フォールバック成功: {fallback_result['cost']}USD/月")
                return fallback_result
                
        except Exception as e:
            self.logger.error(f"❌ Cost Analysis MCP Server呼び出し例外: {e}")
            # エラー時もAWS Documentation MCPを試行
            service_name_input = service_config.get("service_name", "")
            region = service_config.get("region", "us-east-1")
            instance_type = service_config.get("instance_type")
            
            service_code_helper = get_service_code_helper()
            service_code = service_code_helper.find_service_code(service_name_input) or service_name_input.upper()
            service_info = service_code_helper.get_service_info(service_name_input)
            display_name = service_info['service_name'] if service_info else service_name_input
            
            self.logger.info(f"🔄 例外後AWS Documentation MCPを試行: {service_code}")
            
            # AWS Documentation MCPを試行
            doc_result = self._get_pricing_from_aws_documentation(service_code, region, instance_type, display_name)
            
            if doc_result:
                self.logger.info(f"✅ 例外後AWS Documentation MCP成功: {doc_result['cost']}USD/月")
                return doc_result
            else:
                # 最終フォールバック
                self.logger.info(f"🔄 例外後最終フォールバック使用: {service_code}")
                fallback_result = self._calculate_fallback_cost_estimate(service_code, region, instance_type)
                self.logger.info(f"✅ 例外後最終フォールバック成功: {fallback_result['cost']}USD/月")
                return fallback_result
    
    def _convert_mcp_result_to_standard_format(self, mcp_result: Any, service_name: str, instance_type: Optional[str], region: str) -> Optional[Dict[str, Any]]:
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
            if isinstance(mcp_result, dict):
                monthly_cost = 0
                detail = f"{service_name}"
                if instance_type:
                    detail += f" {instance_type}"
                detail += f" ({region})"
                source_info = ""
                
                # フォールバック結果の場合の特別処理
                if mcp_result.get("source") == "fallback_calculation":
                    self.logger.info(f"🔄 フォールバック結果を標準形式に変換")
                    pricing_info = mcp_result.get("pricing", {})
                    monthly_cost = pricing_info.get("monthly_estimate", 0)
                    detail += f" [フォールバック推定値]"
                    source_info = " (フォールバック)"
                    
                elif mcp_result.get("source") == "fallback_analysis":
                    self.logger.info(f"🔄 フォールバック分析結果を標準形式に変換")
                    # Web検索フォールバックの場合は基本コストを推定
                    monthly_cost = 75  # デフォルト値
                    detail += f" [フォールバック分析]"
                    source_info = " (フォールバック分析)"
                    
                else:
                    # 通常のMCPサーバー結果の処理
                    # MCPサーバーから価格情報を抽出（一般的なフィールド名で試行）
                    if "cost" in mcp_result:
                        monthly_cost = float(mcp_result["cost"])
                    elif "price" in mcp_result:
                        monthly_cost = float(mcp_result["price"])
                    elif "monthly_cost" in mcp_result:
                        monthly_cost = float(mcp_result["monthly_cost"])
                    elif "pricing" in mcp_result and isinstance(mcp_result["pricing"], dict):
                        pricing = mcp_result["pricing"]
                        monthly_cost = pricing.get("monthly_estimate", pricing.get("monthly", 0))
                    else:
                        # 数値を含む文字列から価格を抽出
                        import re
                        text = str(mcp_result)
                        price_matches = re.findall(r'\$?(\d+\.?\d*)', text)
                        if price_matches:
                            monthly_cost = float(price_matches[0])
                
                # 最適化提案を抽出
                optimization = "Reserved Instance検討"
                if mcp_result.get("source") == "fallback_analysis":
                    recommendations = mcp_result.get("recommendations", [])
                    if recommendations:
                        optimization = "; ".join(recommendations[:2])  # 最初の2つを結合
                elif "optimization" in mcp_result:
                    optimization = mcp_result["optimization"]
                elif "recommendation" in mcp_result:
                    optimization = mcp_result["recommendation"]
                elif "recommendations" in mcp_result and isinstance(mcp_result["recommendations"], list):
                    optimization = "; ".join(mcp_result["recommendations"][:2])
                
                # 注記情報を追加
                note_info = mcp_result.get("note", "")
                if note_info:
                    optimization += f" {source_info}"
                
                return {
                    "cost": monthly_cost,
                    "detail": detail,
                    "optimization": optimization,
                    "current_state": "オンデマンド" + source_info,
                    "reduction_rate": 0.25  # デフォルト削減率
                }
            
            # その他の型（リスト、None等）の場合は文字列に変換してテキスト解析
            return self._parse_text_cost_result(str(mcp_result), service_name, instance_type, region)
            
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
            service_name: AWSサービス名またはサービスコード
            region: AWSリージョン
            instance_type: インスタンスタイプ
            
        Returns:
            フォールバック計算されたコスト見積もり
        """
        # サービスコードを正規化（既に正しいサービスコードの場合はそのまま使用）
        service_code_helper = get_service_code_helper()
        normalized_service_code = service_code_helper.find_service_code(service_name) or service_name
        
        # リージョン別料金倍率（us-east-1を基準）
        region_multiplier = {
            "us-east-1": 1.0, "us-east-2": 1.02, "us-west-1": 1.08, "us-west-2": 1.05,
            "eu-west-1": 1.1, "eu-west-2": 1.12, "eu-west-3": 1.15, "eu-central-1": 1.13,
            "ap-northeast-1": 1.15, "ap-northeast-2": 1.12, "ap-southeast-1": 1.12, 
            "ap-southeast-2": 1.14, "ap-south-1": 1.08, "ca-central-1": 1.06, "sa-east-1": 1.18
        }.get(region, 1.0)
        
        # インスタンスタイプ別倍率
        instance_multiplier = {
            # T3 系（バーストable）
            "t3.nano": 0.3, "t3.micro": 0.5, "t3.small": 1.0, "t3.medium": 1.8,
            "t3.large": 3.6, "t3.xlarge": 7.2, "t3.2xlarge": 14.4,
            # T4g 系（ARM）
            "t4g.nano": 0.25, "t4g.micro": 0.45, "t4g.small": 0.9, "t4g.medium": 1.6,
            "t4g.large": 3.2, "t4g.xlarge": 6.4, "t4g.2xlarge": 12.8,
            # M5 系（汎用）
            "m5.large": 4.0, "m5.xlarge": 8.0, "m5.2xlarge": 16.0, "m5.4xlarge": 32.0,
            # C5 系（コンピューティング最適化）
            "c5.large": 3.8, "c5.xlarge": 7.6, "c5.2xlarge": 15.2, "c5.4xlarge": 30.4,
            # R5 系（メモリ最適化）
            "r5.large": 5.2, "r5.xlarge": 10.4, "r5.2xlarge": 20.8, "r5.4xlarge": 41.6
        }.get(instance_type, 1.0) if instance_type else 1.0
        
        # サービス別基本料金（月額USD、us-east-1の標準構成）
        base_costs = {
            "AmazonEC2": 25, "AmazonS3": 8, "AmazonRDS": 85, "AWSLambda": 12,
            "AmazonCloudFront": 15, "AmazonVPC": 5, "AmazonDynamoDB": 18,
            "AmazonECS": 30, "AmazonEKS": 75, "AmazonLightsail": 20,
            "AmazonEFS": 35, "AmazonFSx": 120, "AmazonRedshift": 180,
            "AmazonElastiCache": 95, "AmazonBedrock": 45, "AmazonSageMaker": 150,
            "AmazonSNS": 2, "AmazonSQS": 3, "AmazonCloudWatch": 12,
            "AmazonRoute53": 8, "AWSELB": 25
        }
        
        # 正規化されたサービスコードから基本料金を取得
        base_cost = base_costs.get(normalized_service_code, 30)
        
        # 最終料金を計算
        final_cost = base_cost * region_multiplier * instance_multiplier
        
        # サービス表示名を取得
        service_info = service_code_helper.get_service_info(service_name)
        display_name = service_info['service_name'] if service_info else service_name
        
        # 最適化提案を生成
        optimization_suggestions = []
        
        # インスタンスタイプ固有の最適化
        if instance_type and instance_type.startswith('t3.'):
            optimization_suggestions.append("Reserved Instanceで20-75%の削減可能")
        elif instance_type and 'xlarge' in instance_type:
            optimization_suggestions.append("Savings Plansで最大72%の削減可能")
        
        # サービス固有の最適化
        if normalized_service_code == "AmazonEC2":
            optimization_suggestions.append("Spot Instanceで最大90%の削減可能")
        elif normalized_service_code == "AmazonS3":
            optimization_suggestions.append("Intelligent Tieringで自動コスト最適化")
        elif normalized_service_code == "AmazonRDS":
            optimization_suggestions.append("Aurora Serverlessで使用量ベース課金")
        
        optimization = "; ".join(optimization_suggestions) if optimization_suggestions else "詳細分析が必要"
        
        # 削減率を推定
        reduction_rate = 0.15  # デフォルト
        if any("Reserved" in s for s in optimization_suggestions):
            reduction_rate = 0.35
        elif any("Savings" in s for s in optimization_suggestions):
            reduction_rate = 0.45
        elif any("Spot" in s for s in optimization_suggestions):
            reduction_rate = 0.65
        
        return {
            "cost": round(final_cost, 2),
            "detail": f"{display_name} {instance_type or '標準構成'} ({region}) [推定値]",
            "optimization": optimization,
            "current_state": "オンデマンド料金",
            "reduction_rate": reduction_rate,
            "note": "MCPサーバー未利用のため推定値です。正確な料金は AWS料金計算ツールをご利用ください。"
        }
    
    def _get_pricing_from_aws_documentation(self, service_code: str, region: str, instance_type: Optional[str], display_name: str) -> Optional[Dict[str, Any]]:
        """
        AWS Documentation MCPから価格情報を取得
        
        Args:
            service_code: AWSサービスコード
            region: AWSリージョン
            instance_type: インスタンスタイプ
            display_name: サービス表示名
            
        Returns:
            価格情報、または取得失敗時はNone
        """
        try:
            # AWS Documentation MCPに送信するクエリを構築
            pricing_query = f"{display_name} pricing"
            if instance_type:
                pricing_query += f" {instance_type}"
            pricing_query += f" {region} cost per hour monthly"
            
            self.logger.info(f"🔄 AWS Documentation MCP呼び出し開始")
            self.logger.info(f"   - サーバー: awslabs.aws-documentation-mcp-server")
            self.logger.info(f"   - ツール: search_documentation")
            self.logger.info(f"   - クエリ: '{pricing_query}'")
            
            # AWS Documentation MCPを呼び出し
            doc_result = self.call_mcp_tool("awslabs.aws-documentation-mcp-server", "search_documentation", query=pricing_query)
            
            if doc_result and isinstance(doc_result, dict):
                self.logger.info(f"✅ AWS Documentation MCP応答受信")
                self.logger.debug(f"   - 結果タイプ: {type(doc_result)}")
                self.logger.debug(f"   - 結果サイズ: {len(str(doc_result))} 文字")
                
                # ドキュメント検索結果から価格情報を抽出
                extracted_cost = self._extract_pricing_from_documentation(doc_result, service_code, instance_type, region, display_name)
                if extracted_cost:
                    self.logger.info(f"✅ AWS Documentation価格抽出成功: {extracted_cost['cost']}USD/月")
                    return extracted_cost
                else:
                    self.logger.warning(f"❌ AWS Documentation価格抽出失敗")
            else:
                self.logger.warning(f"❌ AWS Documentation MCP応答無効または空")
            
            # 汎用的な価格クエリも試行
            if instance_type:
                generic_query = f"AWS {display_name} {instance_type} pricing cost"
                self.logger.info(f"🔄 AWS Documentation MCP汎用クエリ試行: '{generic_query}'")
                
                doc_result = self.call_mcp_tool("awslabs.aws-documentation-mcp-server", "search_documentation", query=generic_query)
                
                if doc_result and isinstance(doc_result, dict):
                    self.logger.info(f"✅ AWS Documentation MCP汎用クエリ応答受信")
                    extracted_cost = self._extract_pricing_from_documentation(doc_result, service_code, instance_type, region, display_name)
                    if extracted_cost:
                        self.logger.info(f"✅ AWS Documentation汎用クエリ価格抽出成功: {extracted_cost['cost']}USD/月")
                        return extracted_cost
                    else:
                        self.logger.warning(f"❌ AWS Documentation汎用クエリ価格抽出失敗")
                else:
                    self.logger.warning(f"❌ AWS Documentation MCP汎用クエリ応答無効")
            
            self.logger.info(f"❌ AWS Documentation MCPから有用な価格情報を取得できませんでした: {service_code}")
            return None
            
        except Exception as e:
            self.logger.warning(f"AWS Documentation MCP呼び出しエラー: {e}")
            return None
    
    def _extract_pricing_from_documentation(self, doc_result: Dict[str, Any], service_code: str, instance_type: Optional[str], region: str, display_name: str) -> Optional[Dict[str, Any]]:
        """
        AWS Documentation MCPの結果から価格情報を抽出
        
        Args:
            doc_result: AWS Documentation MCPの検索結果
            service_code: AWSサービスコード
            instance_type: インスタンスタイプ
            region: AWSリージョン
            display_name: サービス表示名
            
        Returns:
            抽出された価格情報、または抽出失敗時はNone
        """
        try:
            import re
            
            # ドキュメント内容を取得
            content = ""
            if "content" in doc_result:
                content = str(doc_result["content"])
            elif "description" in doc_result:
                content = str(doc_result["description"])
            elif "text" in doc_result:
                content = str(doc_result["text"])
            else:
                # 辞書全体を文字列として検索
                content = str(doc_result)
            
            if not content:
                return None
            
            # 価格パターンを検索
            price_patterns = [
                # 時間単価（$0.0464 per hour等）
                r'\$(\d+\.?\d*)\s*(?:per\s+hour|/hour|hourly)',
                # 月額（$33.55 per month等）
                r'\$(\d+\.?\d*)\s*(?:per\s+month|/month|monthly)',
                # GB単価（$0.023 per GB等）
                r'\$(\d+\.?\d*)\s*(?:per\s+GB|/GB)',
                # 一般的な価格（$XX.XX）
                r'\$(\d+\.?\d*)',
            ]
            
            extracted_prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    try:
                        price = float(match)
                        if 0.001 <= price <= 10000:  # 現実的な価格範囲
                            extracted_prices.append(price)
                    except ValueError:
                        continue
            
            if not extracted_prices:
                return None
            
            # 最も妥当な価格を選択（中央値を使用）
            extracted_prices.sort()
            if len(extracted_prices) == 1:
                hourly_price = extracted_prices[0]
            else:
                # 中央値を取得
                mid = len(extracted_prices) // 2
                hourly_price = extracted_prices[mid]
            
            # 時間単価から月額を計算（730時間/月で計算）
            monthly_cost = hourly_price * 730
            
            # 価格が異常に高い場合は調整
            if monthly_cost > 5000:
                monthly_cost = hourly_price  # 既に月額の可能性
            
            # 最適化提案を生成
            optimization_suggestions = []
            
            if service_code == "AmazonEC2":
                optimization_suggestions.append("Reserved Instanceで最大75%削減")
                optimization_suggestions.append("Spot Instanceで最大90%削減")
            elif service_code == "AmazonRDS":
                optimization_suggestions.append("Reserved Instanceで最大69%削減")
            elif service_code == "AmazonS3":
                optimization_suggestions.append("Intelligent Tieringで自動最適化")
            else:
                optimization_suggestions.append("Reserved pricing optionsで削減可能")
            
            optimization = "; ".join(optimization_suggestions)
            
            return {
                "cost": round(monthly_cost, 2),
                "detail": f"{display_name} {instance_type or '標準構成'} ({region}) [AWS Docs]",
                "optimization": optimization,
                "current_state": "オンデマンド料金",
                "reduction_rate": 0.35,  # AWS Documentation情報に基づく削減率
                "source": "AWS Documentation MCP",
                "note": f"AWS公式ドキュメントから抽出した価格情報です（時間単価: ${hourly_price:.4f}）"
            }
            
        except Exception as e:
            self.logger.error(f"Documentation価格抽出エラー: {e}")
            return None
    
    
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
            # Cost Analysis MCP ServerのWeb検索機能を呼び出し（自然言語クエリに最適）
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "get_pricing_from_web", query=query)
            
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
                result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_terraform_project", project_path=project_path)
            elif project_type.lower() == "cdk":
                result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "analyze_cdk_project", project_path=project_path)
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
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "generate_cost_report", 
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
            # Cost Analysis MCP Serverの価格情報取得機能を使用して最適化推奨を取得
            query = f"Provide cost optimization recommendations for current AWS setup: {current_setup}"
            result = self.call_mcp_tool("awslabs.cost-analysis-mcp-server", "get_pricing_from_web", query=query)
            
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
    
    def _handle_fallback_tool_call(self, server_name: str, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        MCPサーバーが利用できない場合のフォールバック処理
        
        Args:
            server_name: MCPサーバー名
            tool_name: ツール名
            **kwargs: ツールパラメータ
            
        Returns:
            フォールバック結果またはNone
        """
        self.logger.info(f"🔄 フォールバック処理実行: {server_name}.{tool_name}")
        
        try:
            if server_name == "awslabs.cost-analysis-mcp-server":
                if tool_name == "get_pricing_from_api":
                    return self._fallback_cost_analysis_api(**kwargs)
                elif tool_name == "get_pricing_from_web":
                    return self._fallback_cost_analysis_web(**kwargs)
                elif tool_name == "generate_cost_report":
                    return self._fallback_generate_cost_report(**kwargs)
                
            elif server_name == "awslabs.aws-documentation-mcp-server":
                if tool_name == "search_documentation":
                    return self._fallback_aws_documentation(**kwargs)
                    
            elif server_name == "awslabs.terraform-mcp-server":
                if tool_name == "generate_terraform":
                    return self._fallback_terraform_generation(**kwargs)
                    
            self.logger.warning(f"⚠️  未対応のフォールバック: {server_name}.{tool_name}")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ フォールバック処理エラー: {e}")
            return None
    
    def _fallback_cost_analysis_api(self, service_code: str, region: str, **kwargs) -> Dict[str, Any]:
        """Cost Analysis API フォールバック"""
        self.logger.info(f"💰 Cost Analysis APIフォールバック: {service_code} ({region})")
        
        # 基本的なコスト情報を返す（実際のAPIデータの代替）
        base_costs = {
            "AmazonEC2": {"hourly": 0.0464, "monthly": 33.5},
            "AmazonS3": {"gb_month": 0.023, "monthly": 15.0},
            "AmazonRDS": {"hourly": 0.115, "monthly": 83.0},
            "AWSLambda": {"million_requests": 0.20, "monthly": 12.0},
            "AmazonDynamoDB": {"wcu_month": 0.00065, "monthly": 25.0}
        }
        
        cost_info = base_costs.get(service_code, {"hourly": 0.05, "monthly": 36.0})
        
        return {
            "service_code": service_code,
            "region": region,
            "pricing": {
                "monthly_estimate": cost_info["monthly"],
                "currency": "USD",
                "pricing_model": "On-Demand"
            },
            "note": "フォールバック値（実際のAPIデータではありません）",
            "source": "fallback_calculation"
        }
    
    def _fallback_cost_analysis_web(self, query: str, **kwargs) -> Dict[str, Any]:
        """Cost Analysis Web検索 フォールバック"""
        self.logger.info(f"🌐 Cost Analysis Web検索フォールバック: {query}")
        
        # 基本的なコスト分析結果を返す
        return {
            "query": query,
            "analysis": f"'{query}' に関するコスト分析：基本構成での月額は約$50-200の範囲と推定されます。正確な料金は使用量、リージョン、インスタンスタイプによって大きく変動します。AWS料金計算ツールでの詳細見積もりをお勧めします。",
            "recommendations": [
                "Reserved Instancesで20-75%の節約が可能",
                "Savings Plansによる柔軟な割引適用",
                "適切なインスタンスサイズの選択"
            ],
            "note": "フォールバック情報（実際のWeb検索結果ではありません）",
            "source": "fallback_analysis"
        }
    
    def _fallback_generate_cost_report(self, services: List[str], region: str, **kwargs) -> Dict[str, Any]:
        """コストレポート生成 フォールバック"""
        self.logger.info(f"📊 コストレポート生成フォールバック: {services} ({region})")
        
        total_cost = 0
        service_costs = {}
        
        for service in services:
            # 簡単なコスト推定
            if "EC2" in service.upper():
                cost = 85
            elif "S3" in service.upper():
                cost = 20
            elif "RDS" in service.upper():
                cost = 150
            elif "LAMBDA" in service.upper():
                cost = 25
            else:
                cost = 50
                
            service_costs[service] = cost
            total_cost += cost
        
        return {
            "services": services,
            "region": region,
            "total_monthly_cost": total_cost,
            "service_breakdown": service_costs,
            "currency": "USD",
            "report_summary": f"総月額コスト: ${total_cost} USD ({region})",
            "note": "フォールバック推定値",
            "source": "fallback_report"
        }
    
    def _fallback_aws_documentation(self, query: str, **kwargs) -> Dict[str, Any]:
        """AWS Documentation フォールバック"""
        self.logger.info(f"📚 AWS Documentation フォールバック: {query}")
        
        common_docs = {
            "ec2": "Amazon EC2は、AWS クラウドでスケーラブルなコンピューティング容量を提供します。",
            "s3": "Amazon S3は、業界をリードするスケーラビリティ、データ可用性、セキュリティ、パフォーマンスを提供するオブジェクトストレージサービスです。",
            "rds": "Amazon RDSでは、クラウドでリレーショナルデータベースを簡単にセットアップ、運用、スケールできます。",
            "lambda": "AWS Lambdaは、サーバーをプロビジョニングまたは管理することなく、コードを実行できるコンピューティングサービスです。"
        }
        
        description = "AWS公式ドキュメントを参照してください。"
        for key, desc in common_docs.items():
            if key in query.lower():
                description = desc
                break
        
        return {
            "query": query,
            "description": description,
            "source": "fallback_documentation",
            "note": "フォールバック情報"
        }
    
    def _fallback_terraform_generation(self, requirements: str, **kwargs) -> Dict[str, Any]:
        """Terraform生成 フォールバック"""
        self.logger.info(f"🏗️ Terraform生成フォールバック: {requirements}")
        
        # 基本的なTerraformテンプレートを返す
        if "vpc" in requirements.lower():
            code = '''
# VPC基本構成
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
  map_public_ip_on_launch = true
  
  tags = {
    Name = "public-subnet"
  }
}
'''
        else:
            code = "# 詳細な要件を指定してください。"
        
        return {
            "requirements": requirements,
            "terraform_code": code,
            "note": "フォールバックテンプレート",
            "source": "fallback_terraform"
        }


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