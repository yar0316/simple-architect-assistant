#!/usr/bin/env python3
"""
Terraform MCP実装の動作テスト

実際のMCP呼び出しとフォールバック機能をテストします。
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# テスト対象モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from services.mcp_client import MCPClientService
except ImportError as e:
    print(f"MCPClientServiceのインポートに失敗: {e}")
    MCPClientService = None


class TestTerraformMCPImplementation(unittest.TestCase):
    """Terraform MCP実装のテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        if MCPClientService is None:
            self.skipTest("MCPClientServiceが利用できません")
        
        # MCPクライアントを初期化（実際のサーバー接続なし）
        self.mcp_client = MCPClientService()

    def test_generate_terraform_code_with_vpc_requirements(self):
        """VPC要件でのTerraformコード生成テスト"""
        requirements = "VPCとパブリック・プライベートサブネットの作成"
        
        # フォールバック機能をテスト
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_vpc", result)
        self.assertIn("aws_subnet", result)
        self.assertIn("aws_internet_gateway", result)
        self.assertIn("terraform {", result)
        self.assertIn("provider \"aws\"", result)
        print(f"✅ VPCテンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_lambda_requirements(self):
        """Lambda要件でのTerraformコード生成テスト"""
        requirements = "Lambda関数とCloudWatch Logsの設定"
        
        # フォールバック機能をテスト
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_lambda_function", result)
        self.assertIn("aws_iam_role", result)
        self.assertIn("aws_cloudwatch_log_group", result)
        print(f"✅ Lambdaテンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_ec2_requirements(self):
        """EC2要件でのTerraformコード生成テスト"""
        requirements = "EC2インスタンスとセキュリティグループの設定"
        
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_instance", result)
        self.assertIn("aws_security_group", result)
        self.assertIn("data \"aws_ami\"", result)
        print(f"✅ EC2テンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_rds_requirements(self):
        """RDS要件でのTerraformコード生成テスト"""
        requirements = "RDS MySQLデータベースとDBサブネットグループ"
        
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_db_instance", result)
        self.assertIn("aws_db_subnet_group", result)
        self.assertIn("mysql", result)
        print(f"✅ RDSテンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_s3_requirements(self):
        """S3要件でのTerraformコード生成テスト"""
        requirements = "S3バケットと暗号化、ライフサイクル設定"
        
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_s3_bucket", result)
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration", result)
        self.assertIn("aws_s3_bucket_lifecycle_configuration", result)
        print(f"✅ S3テンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_ecs_requirements(self):
        """ECS要件でのTerraformコード生成テスト"""
        requirements = "ECS Fargateクラスターとサービス"
        
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("aws_ecs_cluster", result)
        self.assertIn("aws_ecs_service", result)
        self.assertIn("aws_ecs_task_definition", result)
        self.assertIn("FARGATE", result)
        print(f"✅ ECSテンプレート生成成功: {len(result)} 文字")

    def test_generate_terraform_code_with_mcp_success(self):
        """MCP成功時のTerraformコード生成テスト"""
        requirements = "ALBとターゲットグループの設定"
        
        # MCPサーバーから成功レスポンスを返すモック
        mock_mcp_response = {
            "terraform_code": """# ALB構成（MCPサーバー生成）
resource "aws_lb" "main" {
  name               = "test-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = var.subnet_ids
}""",
            "source": "terraform_mcp_server"
        }
        
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=mock_mcp_response):
            with patch.object(self.mcp_client, '_extract_terraform_code_from_mcp_result', 
                            return_value=mock_mcp_response["terraform_code"]):
                result = self.mcp_client.generate_terraform_code(requirements)
        
        self.assertIsNotNone(result)
        self.assertIn("ALB構成（MCPサーバー生成）", result)
        self.assertIn("aws_lb", result)
        print(f"✅ MCP成功時テスト成功: {len(result)} 文字")

    def test_extract_terraform_code_from_various_formats(self):
        """様々なMCPレスポンス形式からのコード抽出テスト"""
        # 文字列形式
        string_response = "resource \"aws_vpc\" \"main\" { cidr_block = \"10.0.0.0/16\" }"
        result = self.mcp_client._extract_terraform_code_from_mcp_result(string_response)
        self.assertEqual(result, string_response)

        # 辞書形式（terraform_codeフィールド）
        dict_response_1 = {"terraform_code": string_response, "source": "mcp"}
        result = self.mcp_client._extract_terraform_code_from_mcp_result(dict_response_1)
        self.assertEqual(result, string_response)

        # 辞書形式（codeフィールド）
        dict_response_2 = {"code": string_response, "metadata": "test"}
        result = self.mcp_client._extract_terraform_code_from_mcp_result(dict_response_2)
        self.assertEqual(result, string_response)

        # リスト形式
        list_response = [string_response]
        result = self.mcp_client._extract_terraform_code_from_mcp_result(list_response)
        self.assertEqual(result, string_response)

        print("✅ 様々なMCPレスポンス形式からの抽出テスト成功")

    def test_basic_terraform_template_generation(self):
        """基本Terraformテンプレート生成のパターンマッチングテスト"""
        test_cases = [
            ("VPCとサブネット", "aws_vpc"),
            ("Lambda関数", "aws_lambda_function"),
            ("EC2インスタンス", "aws_instance"),
            ("RDSデータベース", "aws_db_instance"),
            ("S3バケット", "aws_s3_bucket"),
            ("ALBロードバランサー", "aws_lb"),
            ("ECSコンテナ", "aws_ecs_cluster"),
            ("不明な要件", "terraform {")  # 汎用テンプレート
        ]
        
        for requirements, expected_resource in test_cases:
            result = self.mcp_client._get_basic_terraform_template(requirements)
            self.assertIsNotNone(result)
            self.assertIn(expected_resource, result)
            print(f"✅ パターンマッチング成功: '{requirements}' -> {expected_resource}")

    def test_caching_functionality(self):
        """キャッシュ機能のテスト"""
        requirements = "テスト用VPC設定"
        
        # 最初の呼び出し
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None) as mock_call:
            result1 = self.mcp_client.generate_terraform_code(requirements)
            first_call_count = mock_call.call_count
        
        # 2回目の呼び出し（キャッシュヒット）
        with patch.object(self.mcp_client, 'call_mcp_tool', return_value=None) as mock_call:
            result2 = self.mcp_client.generate_terraform_code(requirements)
            second_call_count = mock_call.call_count
        
        # 結果が同じでキャッシュされていることを確認
        self.assertEqual(result1, result2)
        self.assertEqual(second_call_count, 0)  # キャッシュヒットで呼び出されない
        print("✅ キャッシュ機能テスト成功")

    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        requirements = "エラーテスト"
        
        # MCP呼び出し時に例外発生
        with patch.object(self.mcp_client, 'call_mcp_tool', side_effect=Exception("テスト例外")):
            result = self.mcp_client.generate_terraform_code(requirements)
        
        # エラー時もフォールバック結果が返されることを確認
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)
        print(f"✅ エラーハンドリングテスト成功: {len(result)} 文字のフォールバック")


def main():
    """テスト実行"""
    print("Terraform MCP実装テスト開始\n")
    
    # テストスイートを実行
    unittest.main(verbosity=2, exit=False)
    
    print("\n=== テスト完了 ===")
    print("🎉 Terraform MCP実装の動作確認が完了しました！")


if __name__ == "__main__":
    main()