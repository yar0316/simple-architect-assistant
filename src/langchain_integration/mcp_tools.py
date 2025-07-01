"""LangChain MCP Adapters統合"""
import asyncio
import streamlit as st
from typing import List, Dict, Any, Optional
import logging

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_core.tools import BaseTool
    LANGCHAIN_MCP_AVAILABLE = True
except ImportError as e:
    st.warning(f"LangChain MCP Adapters が利用できません: {e}")
    LANGCHAIN_MCP_AVAILABLE = False
    # ImportError時のダミークラス定義
    class MultiServerMCPClient:
        pass
    class BaseTool:
        pass

class LangChainMCPManager:
    """LangChain MCP Adapters管理クラス"""
    
    def __init__(self):
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: List[BaseTool] = []
        self.connected_servers: List[str] = []
        self.mcp_available = LANGCHAIN_MCP_AVAILABLE
    
    def initialize_with_existing_mcp(self, mcp_client_service) -> bool:
        """既存のMCPClientServiceを使用して初期化"""
        try:
            logging.info("既存のMCPClientServiceとの統合を開始")
            
            # 既存のMCPクライアントからツールを作成
            available_tools = mcp_client_service.get_available_tools()
            logging.info(f"既存MCPから利用可能なツール: {available_tools}")
            
            if not available_tools:
                logging.warning("既存MCPクライアントにツールがありません - フォールバック機能を提供")
                # ツールが無くても基本的なフォールバック機能を提供
                self.tools = self._create_tools_from_mcp_client(mcp_client_service)
                self.connected_servers = []
                return len(self.tools) > 0
            
            # MCPClientServiceをラップしてLangChainツールを作成
            self.tools = self._create_tools_from_mcp_client(mcp_client_service)
            self.connected_servers = available_tools
            
            logging.info(f"既存MCP統合成功: {len(self.tools)}個のツール, {len(self.connected_servers)}個のサーバー")
            return True
            
        except Exception as e:
            logging.error(f"既存MCP統合エラー: {e}")
            return False
    
    def _create_tools_from_mcp_client(self, mcp_client_service):
        """MCPClientServiceをラップしてLangChainツールを作成"""
        from langchain_core.tools import Tool
        
        tools = []
        
        try:
            # AWS Documentation検索ツール
            def aws_docs_search(query: str) -> str:
                """AWS公式ドキュメントを検索"""
                result = mcp_client_service.get_aws_documentation(query)
                if result:
                    return f"検索結果: {result.get('description', 'N/A')} (出典: {result.get('source', 'AWS公式')})"
                return f"AWS {query} に関する基本的な情報を参照してください。"
            
            # Core MCP ガイダンスツール
            def core_guidance(prompt: str) -> str:
                """AWS構成に関するガイダンスを取得"""
                guidance = mcp_client_service.get_core_mcp_guidance(prompt)
                if guidance:
                    return f"推奨事項: {guidance}"
                return "AWS Well-Architected Frameworkに基づいた設計を推奨します。"
            
            # Terraformコード生成ツール
            def terraform_generate(requirements: str) -> str:
                """Terraformコードを生成"""
                code = mcp_client_service.generate_terraform_code(requirements)
                if code:
                    return f"生成されたTerraformコード:\n```hcl\n{code}\n```"
                return "Terraformコード生成には詳細な要件指定が必要です。"
            
            # ツールを作成
            tools.append(Tool(
                name="aws_documentation_search",
                description="AWS公式ドキュメントからサービス情報を検索します。引数: query (検索するAWSサービス名)",
                func=aws_docs_search
            ))
            
            tools.append(Tool(
                name="aws_guidance",
                description="AWS構成に関する専門的なガイダンスを提供します。引数: prompt (相談内容)",
                func=core_guidance
            ))
            
            tools.append(Tool(
                name="terraform_code_generator",
                description="AWS構成のTerraformコードを生成します。引数: requirements (実装要件)",
                func=terraform_generate
            ))
            
            logging.info(f"MCPClientService統合ツール作成完了: {len(tools)}個")
            
        except Exception as e:
            logging.error(f"MCPツール作成エラー: {e}")
        
        return tools

    async def initialize(self, server_configs: Dict[str, Dict[str, Any]]) -> bool:
        """MCP クライアントを初期化"""
        if not self.mcp_available:
            logging.warning("LangChain MCP Adapters が利用できません")
            return False
        
        try:
            logging.info(f"MCPクライアント初期化開始: {len(server_configs)}個のサーバー設定")
            
            # MCPサーバーの事前チェック
            available_configs = await self._check_mcp_servers(server_configs)
            if not available_configs:
                logging.warning("利用可能なMCPサーバーがありません")
                return False
            
            # MultiServerMCPClientを初期化（利用可能なサーバーのみ）
            self.client = MultiServerMCPClient(available_configs)
            logging.info("MultiServerMCPClient作成完了")
            
            # サーバーに接続してツールを取得（TaskGroupエラーが発生しやすい箇所）
            try:
                self.tools = await self.client.get_tools()
                logging.info(f"ツール取得完了: {len(self.tools)}個")
            except Exception as tool_error:
                logging.error(f"ツール取得エラー: {tool_error}")
                
                # 特定のエラーパターンをチェック
                if "Connection closed" in str(tool_error):
                    logging.error("MCPサーバーとの接続が閉じられました - サーバーが起動していない可能性があります")
                elif "TaskGroup" in str(tool_error):
                    logging.error("TaskGroupエラー - 複数のMCPサーバーで問題が発生しています")
                
                # フォールバック: 個別サーバーを順次試行
                return await self._fallback_individual_servers(available_configs)
            
            # 接続済みサーバーリストを更新
            self.connected_servers = list(available_configs.keys())
            
            logging.info(f"LangChain MCP初期化成功: {len(self.tools)} tools loaded from {len(self.connected_servers)} servers")
            return True
            
        except Exception as e:
            error_msg = f"LangChain MCP initialization failed: {e}"
            logging.error(error_msg)
            
            # TaskGroupエラーの場合の特別な処理
            if "TaskGroup" in str(e):
                logging.error("TaskGroupエラー検出 - MCP サーバーとの接続に問題がある可能性があります")
                logging.error("考えられる原因: 1) MCPサーバーが起動していない 2) ネットワーク接続の問題 3) 設定エラー")
            
            import traceback
            logging.error(f"詳細なトレースバック: {traceback.format_exc()}")
            return False
    
    async def _check_mcp_servers(self, server_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """MCPサーバーの利用可能性をチェック"""
        import subprocess
        import asyncio
        available_configs = {}
        
        for server_name, config in server_configs.items():
            try:
                command = config.get("command", "")
                args = config.get("args", [])
                
                # npxコマンドの存在確認
                if command == "npx":
                    # npxのバージョン確認で利用可能性をチェック
                    try:
                        result = await asyncio.create_subprocess_exec(
                            "npx", "--version",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await result.communicate()
                        
                        if result.returncode == 0:
                            logging.info(f"npx利用可能: バージョン {stdout.decode().strip()}")
                            
                            # MCPパッケージの存在確認（簡易版）
                            package_name = args[0] if args else ""
                            if package_name:
                                available_configs[server_name] = config
                                logging.info(f"MCPサーバー設定追加: {server_name} -> {package_name}")
                        else:
                            logging.warning(f"npx利用不可: {stderr.decode()}")
                    
                    except Exception as npx_error:
                        logging.warning(f"npxチェックエラー: {npx_error}")
                else:
                    # npx以外のコマンドの場合は設定をそのまま追加
                    available_configs[server_name] = config
                    logging.info(f"非npxサーバー設定追加: {server_name}")
                    
            except Exception as check_error:
                logging.warning(f"サーバーチェックエラー {server_name}: {check_error}")
        
        logging.info(f"利用可能なMCPサーバー: {len(available_configs)}/{len(server_configs)}")
        return available_configs
    
    async def _fallback_individual_servers(self, server_configs: Dict[str, Dict[str, Any]]) -> bool:
        """個別サーバーを順次試行するフォールバック処理"""
        logging.info("個別サーバー試行モードに切り替え")
        
        working_tools = []
        working_servers = []
        
        for server_name, config in server_configs.items():
            try:
                logging.info(f"個別試行: {server_name}")
                
                # 単一サーバー設定でクライアント作成
                single_config = {server_name: config}
                temp_client = MultiServerMCPClient(single_config)
                
                # タイムアウト付きでツール取得
                tools = await asyncio.wait_for(
                    temp_client.get_tools(), 
                    timeout=10.0
                )
                
                if tools:
                    working_tools.extend(tools)
                    working_servers.append(server_name)
                    logging.info(f"成功: {server_name} -> {len(tools)}個のツール")
                else:
                    logging.warning(f"ツールなし: {server_name}")
                
                # 成功したクライアントを保持
                if not self.client and tools:
                    self.client = temp_client
                
            except asyncio.TimeoutError:
                logging.warning(f"タイムアウト: {server_name}")
            except Exception as individual_error:
                logging.warning(f"個別試行失敗 {server_name}: {individual_error}")
        
        if working_tools:
            self.tools = working_tools
            self.connected_servers = working_servers
            logging.info(f"フォールバック成功: {len(working_tools)}個のツール, {len(working_servers)}個のサーバー")
            return True
        else:
            logging.error("全てのMCPサーバーとの接続に失敗しました")
            return False
    
    def get_aws_documentation_tools(self) -> List[BaseTool]:
        """AWS Documentation関連ツールを取得"""
        return [tool for tool in self.tools if "documentation" in tool.name.lower() or "docs" in tool.name.lower()]
    
    def get_terraform_tools(self) -> List[BaseTool]:
        """Terraform関連ツールを取得"""
        return [tool for tool in self.tools if "terraform" in tool.name.lower() or "iac" in tool.name.lower()]
    
    def get_cost_calculation_tools(self) -> List[BaseTool]:
        """コスト計算関連ツールを取得"""
        return [tool for tool in self.tools if "cost" in tool.name.lower() or "price" in tool.name.lower()]
    
    def get_all_tools(self) -> List[BaseTool]:
        """全てのツールを取得"""
        return self.tools
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """カテゴリ別にツールを取得"""
        category_mapping = {
            "documentation": self.get_aws_documentation_tools,
            "terraform": self.get_terraform_tools,
            "cost": self.get_cost_calculation_tools
        }
        
        return category_mapping.get(category, lambda: [])()
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """指定されたツールを実行"""
        try:
            # ツール名でツールを検索
            target_tool = None
            for tool in self.tools:
                if tool.name == tool_name:
                    target_tool = tool
                    break
            
            if not target_tool:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            # ツールを実行
            result = await target_tool.arun(**kwargs)
            return result
            
        except Exception as e:
            logging.error(f"Tool execution failed: {e}")
            raise e
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """全ツールの説明を取得"""
        return {tool.name: tool.description for tool in self.tools}
    
    def is_available(self) -> bool:
        """MCPが利用可能かチェック"""
        return self.mcp_available and self.client is not None
    
    async def close(self):
        """MCP接続を閉じる"""
        if self.client:
            try:
                await self.client.close()
                logging.info("LangChain MCP connections closed")
            except Exception as e:
                logging.error(f"Error closing MCP connections: {e}")

class MCPToolFactory:
    """MCPツールのファクトリークラス"""
    
    @staticmethod
    def create_aws_documentation_config() -> Dict[str, Any]:
        """AWS Documentation MCP設定を作成"""
        # 注意: @aws/mcp-server-aws-documentationは架空のパッケージ
        # 実際の利用時は実在するMCPサーバーパッケージに置き換える必要がある
        return {
            "aws_documentation": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-everything"],  # 実在する汎用MCPサーバー
                "transport": "stdio"
            }
        }
    
    @staticmethod  
    def create_terraform_config() -> Dict[str, Any]:
        """AWS Terraform MCP設定を作成"""
        # 注意: 架空のパッケージのため、実用時は置き換えが必要
        return {}  # 実在しないため無効化
    
    @staticmethod
    def create_cost_calculator_config() -> Dict[str, Any]:
        """Cost Calculator MCP設定を作成"""
        # 注意: 架空のパッケージのため、実用時は置き換えが必要
        return {}  # 実在しないため無効化
    
    @staticmethod
    def create_minimal_config() -> Dict[str, Any]:
        """最小限のMCP設定を作成（デバッグ用）"""
        return {
            "echo_server": {
                "command": "node",
                "args": ["-e", "console.log('MCP Echo Server'); process.stdin.pipe(process.stdout);"],
                "transport": "stdio"
            }
        }
    
    @staticmethod
    def create_full_config() -> Dict[str, Any]:
        """全てのMCP設定を作成"""
        # 現在は実用的なAWS MCPサーバーが利用できないため
        # フォールバックツールに依存する空の設定を返す
        logging.info("MCP設定: 実用的なAWS MCPサーバーが利用できないため、フォールバックモードで動作")
        return {}  # 空の設定でフォールバックツールを使用

# シングルトンインスタンス
_mcp_manager_instance = None

def get_langchain_mcp_manager() -> LangChainMCPManager:
    """LangChain MCP Managerのシングルトンインスタンスを取得"""
    global _mcp_manager_instance
    if _mcp_manager_instance is None:
        _mcp_manager_instance = LangChainMCPManager()
    return _mcp_manager_instance

def is_langchain_mcp_available() -> bool:
    """LangChain MCP Adaptersが利用可能かチェック"""
    return LANGCHAIN_MCP_AVAILABLE