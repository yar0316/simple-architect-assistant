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
    
    async def initialize(self, server_configs: Dict[str, Dict[str, Any]]) -> bool:
        """MCP クライアントを初期化"""
        if not self.mcp_available:
            st.warning("⚠️ LangChain MCP Adapters が利用できません。")
            return False
        
        try:
            # MultiServerMCPClientを初期化
            self.client = MultiServerMCPClient(server_configs)
            
            # サーバーに接続してツールを取得
            self.tools = await self.client.get_tools()
            
            # 接続済みサーバーリストを更新
            self.connected_servers = list(server_configs.keys())
            
            logging.info(f"LangChain MCP: {len(self.tools)} tools loaded from {len(self.connected_servers)} servers")
            return True
            
        except Exception as e:
            logging.error(f"LangChain MCP initialization failed: {e}")
            st.warning(f"MCP初期化エラー: {e}")
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
        return {
            "aws_documentation": {
                "command": "npx",
                "args": ["@aws/mcp-server-aws-documentation"],
                "transport": "stdio"
            }
        }
    
    @staticmethod  
    def create_terraform_config() -> Dict[str, Any]:
        """AWS Terraform MCP設定を作成"""
        return {
            "aws_terraform": {
                "command": "npx", 
                "args": ["@aws/mcp-server-terraform"],
                "transport": "stdio"
            }
        }
    
    @staticmethod
    def create_cost_calculator_config() -> Dict[str, Any]:
        """Cost Calculator MCP設定を作成"""
        return {
            "cost_calculator": {
                "command": "npx",
                "args": ["@aws/mcp-server-cost-calculator"], 
                "transport": "stdio"
            }
        }
    
    @staticmethod
    def create_full_config() -> Dict[str, Any]:
        """全てのMCP設定を作成"""
        config = {}
        config.update(MCPToolFactory.create_aws_documentation_config())
        config.update(MCPToolFactory.create_terraform_config())
        config.update(MCPToolFactory.create_cost_calculator_config())
        return config

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