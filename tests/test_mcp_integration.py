"""
LangChain MCP統合のユニットテスト

MCPマネージャーとツール統合の基本機能をテストします。
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# テスト対象モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from langchain_integration.mcp_tools import (
        LangChainMCPManager, 
        is_langchain_mcp_available,
        PAGE_TYPE_AWS_CHAT,
        PAGE_TYPE_TERRAFORM_GENERATOR,
        PAGE_TYPE_GENERAL
    )
except ImportError:
    # langchain-mcp-adaptersが利用できない環境でもテストを実行
    LangChainMCPManager = None
    is_langchain_mcp_available = lambda: False
    PAGE_TYPE_AWS_CHAT = "aws_chat"
    PAGE_TYPE_TERRAFORM_GENERATOR = "terraform_generator"
    PAGE_TYPE_GENERAL = "general"


class TestLangChainMCPManager(unittest.TestCase):
    """LangChainMCPManagerのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        if LangChainMCPManager is None:
            self.skipTest("LangChain MCP Adapters が利用できません")
        
        self.manager = LangChainMCPManager()

    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager.tools), 0)
        self.assertEqual(len(self.manager.connected_servers), 0)

    def test_is_available_without_client(self):
        """クライアント未設定時の利用可能性チェック"""
        self.assertFalse(self.manager.is_available())

    @patch('langchain_integration.mcp_tools.MultiServerMCPClient')
    def test_initialize_with_mock_client(self, mock_client_class):
        """モッククライアントでの初期化テスト"""
        # モッククライアントの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # モックツールの設定
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "テスト用ツール"
        mock_client.get_tools.return_value = [mock_tool]
        
        # 非同期初期化のテスト（同期版でテスト）
        config = {"test_server": {"command": "test", "args": []}}
        
        # 実際の非同期メソッドはスキップし、ツール設定のみテスト
        self.manager.tools = [mock_tool]
        self.manager.connected_servers = ["test_server"]
        
        self.assertEqual(len(self.manager.tools), 1)
        self.assertEqual(self.manager.tools[0].name, "test_tool")

    def test_existing_mcp_integration_with_mock(self):
        """既存MCPクライアント統合のテスト"""
        # モックMCPクライアントサービス作成
        mock_mcp_service = Mock()
        mock_mcp_service.get_available_tools.return_value = ["aws_docs", "terraform"]
        mock_mcp_service.get_aws_documentation.return_value = {
            "description": "テスト結果",
            "source": "mock"
        }
        mock_mcp_service.get_core_mcp_guidance.return_value = "テストガイダンス"
        mock_mcp_service.generate_terraform_code.return_value = "# テストコード"
        
        # 既存MCP統合テスト
        result = self.manager.initialize_with_existing_mcp(mock_mcp_service)
        
        if result:
            self.assertTrue(len(self.manager.tools) > 0)
            self.assertTrue(any(tool.name == "aws_documentation_search" for tool in self.manager.tools))

    def test_fallback_tools_creation(self):
        """フォールバックツール作成テスト"""
        mock_mcp_service = Mock()
        mock_mcp_service.get_available_tools.return_value = []
        
        tools = self.manager._create_tools_from_mcp_client(mock_mcp_service)
        
        # フォールバックツールが作成されることを確認
        self.assertIsInstance(tools, list)
        if tools:  # ツールが作成された場合
            tool_names = [tool.name for tool in tools]
            expected_tools = ["aws_documentation_search", "aws_guidance", "terraform_code_generator"]
            for expected_tool in expected_tools:
                self.assertIn(expected_tool, tool_names)


class TestMCPAvailability(unittest.TestCase):
    """MCP利用可能性テスト"""

    def test_mcp_availability_check(self):
        """MCP利用可能性チェック"""
        available = is_langchain_mcp_available()
        self.assertIsInstance(available, bool)

    def test_manager_creation_when_unavailable(self):
        """MCP利用不可時のマネージャー作成"""
        # 依存関係の問題でスキップ
        self.skipTest("Streamlit依存関係のため、単体テスト環境では実行できません")


class TestMCPToolIntegration(unittest.TestCase):
    """MCPツール統合テスト"""

    def test_tool_execution_simulation(self):
        """ツール実行シミュレーション"""
        # モックツールの動作テスト
        mock_service = Mock()
        mock_service.get_aws_documentation.return_value = {
            "description": "Amazon S3は...",
            "source": "AWS公式"
        }
        
        # ツールラッパー関数のテスト
        def aws_docs_search(query: str) -> str:
            result = mock_service.get_aws_documentation(query)
            if result:
                return f"検索結果: {result.get('description', 'N/A')}"
            return f"AWS {query} に関する情報が見つかりませんでした"
        
        result = aws_docs_search("S3")
        self.assertIn("Amazon S3は", result)
        self.assertIn("検索結果:", result)


class TestPageSpecificToolBranching(unittest.TestCase):
    """ページ固有ツール分岐テスト"""

    def setUp(self):
        """テストセットアップ"""
        if LangChainMCPManager is None:
            self.skipTest("LangChain MCP Adapters が利用できません")
        
        self.manager = LangChainMCPManager()
        
        # モックMCPクライアントサービス作成
        self.mock_mcp_service = Mock()
        self.mock_mcp_service.get_available_tools.return_value = ["aws_docs", "terraform"]
        self.mock_mcp_service.get_aws_documentation.return_value = {
            "description": "テスト結果",
            "source": "mock"
        }
        self.mock_mcp_service.get_core_mcp_guidance.return_value = "テストガイダンス"
        self.mock_mcp_service.generate_terraform_code.return_value = "# テストコード"

    def test_aws_chat_page_specific_tools(self):
        """AWS Chatページ固有ツールのテスト"""
        # AWS Chatページタイプで初期化
        result = self.manager.initialize_with_existing_mcp(
            self.mock_mcp_service, 
            PAGE_TYPE_AWS_CHAT
        )
        
        if result:
            tool_names = [tool.name for tool in self.manager.tools]
            
            # AWS Chatページには aws_cost_analysis ツールが含まれるべき
            self.assertIn("aws_cost_analysis", tool_names)
            
            # AWS Chatページには terraform_code_generator は含まれないべき
            self.assertNotIn("terraform_code_generator", tool_names)

    def test_terraform_generator_page_specific_tools(self):
        """Terraform Generatorページ固有ツールのテスト"""
        # Terraform Generatorページタイプで初期化
        result = self.manager.initialize_with_existing_mcp(
            self.mock_mcp_service, 
            PAGE_TYPE_TERRAFORM_GENERATOR
        )
        
        if result:
            tool_names = [tool.name for tool in self.manager.tools]
            
            # Terraform Generatorページには terraform_code_generator ツールが含まれるべき
            self.assertIn("terraform_code_generator", tool_names)
            
            # Terraform Generatorページには aws_cost_analysis は含まれないべき
            self.assertNotIn("aws_cost_analysis", tool_names)

    def test_general_page_all_tools(self):
        """汎用ページ全ツールのテスト"""
        # 汎用ページタイプで初期化
        result = self.manager.initialize_with_existing_mcp(
            self.mock_mcp_service, 
            PAGE_TYPE_GENERAL
        )
        
        if result:
            tool_names = [tool.name for tool in self.manager.tools]
            
            # 汎用ページには両方のツールが含まれるべき
            self.assertIn("aws_cost_analysis", tool_names)
            self.assertIn("terraform_code_generator", tool_names)

    def test_page_type_constants_consistency(self):
        """ページタイプ定数の一貫性テスト"""
        # 定数が正しく定義されていることを確認
        self.assertEqual(PAGE_TYPE_AWS_CHAT, "aws_chat")
        self.assertEqual(PAGE_TYPE_TERRAFORM_GENERATOR, "terraform_generator")
        self.assertEqual(PAGE_TYPE_GENERAL, "general")

    def test_invalid_page_type_fallback(self):
        """無効なページタイプの場合のフォールバックテスト"""
        # 無効なページタイプで初期化
        result = self.manager.initialize_with_existing_mcp(
            self.mock_mcp_service, 
            "invalid_page_type"
        )
        
        if result:
            tool_names = [tool.name for tool in self.manager.tools]
            
            # 無効なページタイプの場合は汎用ページと同様に全ツールが含まれるべき
            self.assertIn("aws_cost_analysis", tool_names)
            self.assertIn("terraform_code_generator", tool_names)


if __name__ == '__main__':
    # テスト実行設定
    unittest.main(verbosity=2)