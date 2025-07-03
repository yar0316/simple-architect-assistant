#!/usr/bin/env python3
"""
サービスコード変換からMCPサーバー呼び出しまでのフロー検証テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.aws_service_code_helper import get_service_code_helper
from src.services.mcp_client import MCPClientService
import logging

def main():
    # ログレベルを設定
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print('=== AWSServiceCodeHelper テスト ===')
    try:
        helper = get_service_code_helper()
        print(f'サービスコード辞書サイズ: {len(helper.service_codes) if helper.service_codes else 0}')
        
        # 主要サービスのテスト
        test_services = ["EC2", "S3", "RDS", "Lambda"]
        for service in test_services:
            code = helper.find_service_code(service)
            print(f'{service}サービスコード: {code}')
            
    except Exception as e:
        print(f'AWSServiceCodeHelper エラー: {e}')
    
    print('\n=== MCPClient テスト ===')
    try:
        mcp_client = MCPClientService()
        print(f'MCP設定数: {len(mcp_client.config.get("mcpServers", {}))}')
        print(f'MCPツール数: {len(mcp_client.mcp_tools)}')
        
        # MCPサーバー状態を取得
        server_status = mcp_client.get_mcp_server_status()
        print(f'MCPサーバー状態:')
        for server, status in server_status.items():
            print(f'  - {server}: {status["connection_status"]} (initialized: {status["initialized"]})')
            
    except Exception as e:
        print(f'MCPClient エラー: {e}')
    
    print('\n=== サービスコード変換→コスト見積もりフロー テスト ===')
    try:
        test_configs = [
            {'service_name': 'EC2', 'region': 'us-east-1', 'instance_type': 't3.small'},
            {'service_name': 'S3', 'region': 'us-east-1'},
            {'service_name': 'RDS', 'region': 'us-east-1', 'instance_type': 'db.t3.small'}
        ]
        
        for config in test_configs:
            print(f'\n--- {config["service_name"]} テスト ---')
            cost_result = mcp_client.get_cost_estimation(config)
            
            if cost_result:
                print(f'✅ コスト見積もり成功:')
                print(f'  - コスト: ${cost_result.get("cost", "N/A")}/月')
                print(f'  - 詳細: {cost_result.get("detail", "N/A")}')
                print(f'  - 最適化: {cost_result.get("optimization", "N/A")}')
                print(f'  - 状態: {cost_result.get("current_state", "N/A")}')
            else:
                print(f'❌ コスト見積もり失敗')
                
    except Exception as e:
        print(f'コスト見積もりフロー エラー: {e}')
    
    print('\n=== テスト完了 ===')

if __name__ == "__main__":
    main()