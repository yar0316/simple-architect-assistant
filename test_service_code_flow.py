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

def test_aws_service_code_helper():
    helper = get_service_code_helper()
    assert helper.service_codes is not None, "Service codes should not be None"
    assert len(helper.service_codes) > 0, "Service codes dictionary should not be empty"
    
    test_services = ["EC2", "S3", "RDS", "Lambda"]
    for service in test_services:
        code = helper.find_service_code(service)
        assert code is not None, f"Service code for {service} should not be None"

def test_mcp_client_service():
    mcp_client = MCPClientService()
    assert len(mcp_client.config.get("mcpServers", {})) > 0, "MCP servers should not be empty"
    assert len(mcp_client.mcp_tools) > 0, "MCP tools should not be empty"
    
    server_status = mcp_client.get_mcp_server_status()
    assert server_status, "Server status should not be empty"
    for server, status in server_status.items():
        assert "connection_status" in status, f"{server} should have a connection_status"
        assert "initialized" in status, f"{server} should have an initialized status"

def test_cost_estimation_flow():
    mcp_client = MCPClientService()
    test_configs = [
        {'service_name': 'EC2', 'region': 'us-east-1', 'instance_type': 't3.small'},
        {'service_name': 'S3', 'region': 'us-east-1'},
        {'service_name': 'RDS', 'region': 'us-east-1', 'instance_type': 'db.t3.small'}
    ]
    
    for config in test_configs:
        cost_result = mcp_client.get_cost_estimation(config)
        assert cost_result is not None, f"Cost estimation for {config['service_name']} should not fail"
        assert "cost" in cost_result, "Cost result should include 'cost'"
        assert "detail" in cost_result, "Cost result should include 'detail'"
        assert "optimization" in cost_result, "Cost result should include 'optimization'"
        assert "current_state" in cost_result, "Cost result should include 'current_state'"

if __name__ == "__main__":
    main()