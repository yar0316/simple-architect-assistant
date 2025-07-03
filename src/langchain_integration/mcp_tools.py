"""LangChain MCP Adapters統合"""
import asyncio
import logging
import os
import re
import streamlit as st
from typing import List, Dict, Any, Optional

# Page type constants
PAGE_TYPE_AWS_CHAT = "aws_chat"
PAGE_TYPE_TERRAFORM_GENERATOR = "terraform_generator" 
PAGE_TYPE_GENERAL = "general"

# テンプレートキャッシュ（モジュールレベル）
_COST_ANALYSIS_TEMPLATE = None

def get_cost_analysis_template():
    """コスト分析テンプレートをキャッシュして返す"""
    global _COST_ANALYSIS_TEMPLATE
    if _COST_ANALYSIS_TEMPLATE is None:
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "cost_analysis_template.md")
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                _COST_ANALYSIS_TEMPLATE = f.read()
        except FileNotFoundError:
            _COST_ANALYSIS_TEMPLATE = "# エラー: テンプレートファイルが見つかりません\n\nコスト分析テンプレートの読み込みに失敗しました。"
        except Exception as e:
            _COST_ANALYSIS_TEMPLATE = f"# エラー: テンプレート読み込み失敗\n\n{str(e)}"
    return _COST_ANALYSIS_TEMPLATE


def generate_cost_analysis_report(detected_services, cost_estimates, cost_guidance, cost_docs):
    """テンプレートベースでコスト分析レポートを生成
    
    Args:
        detected_services (list): 検出されたAWSサービス名のリスト (例: ["EC2", "S3", "RDS"])
        cost_estimates (dict): サービス別コスト見積もり辞書。各サービスは以下の構造:
            {
                "cost": float,  # 月額コスト
                "detail": str,  # 構成詳細
                "optimization": str,  # 最適化提案
                "current_state": str,  # 現在の状態
                "reduction_rate": float  # 削減率 (0.0-1.0)
            }
        cost_guidance (str): MCP Core からのコスト最適化ガイダンス文字列
        cost_docs (dict): AWS ドキュメントからの料金情報辞書 (description キーを含む)
    
    Returns:
        str: 生成されたMarkdown形式のコスト分析レポート。以下を含む:
            - サービス別月額・年額コスト表
            - 最適化提案と削減効果表
            - 専門的ガイダンス
            - 実装推奨事項
    """
    
    # キャッシュされたテンプレートを取得
    template = get_cost_analysis_template()
    
    # エラーテンプレートの場合は早期リターン
    if template.startswith("# エラー:"):
        return template
    
    # サービス別コスト表を動的生成
    service_rows = []
    total_monthly = 0
    optimization_data = []
    
    for service in detected_services:
        if service in cost_estimates:
            estimate = cost_estimates[service]
            monthly_cost = estimate["cost"]
            total_monthly += monthly_cost
            yearly_cost = monthly_cost * 12
            
            # サービス行を追加
            service_rows.append(f"| {service} | {estimate['detail']} | ${monthly_cost:.2f} | ${yearly_cost:.2f} | {estimate['optimization']} |")
            
            # 最適化データを追加
            if estimate.get('reduction_rate', 0) > 0:
                reduction_amount = monthly_cost * estimate['reduction_rate']
                optimization_data.append({
                    'name': f"{service}最適化",
                    'current': estimate['current_state'],
                    'optimized': estimate['optimization'],
                    'savings': reduction_amount,
                    'percentage': int(estimate['reduction_rate'] * 100)
                })
        else:
            # 未知サービスの汎用対応
            service_rows.append(f"| {service} | 詳細分析が必要です | 見積もり要 | 見積もり要 | 詳細な要件確認が必要 |")
    
    # 空テーブルのフォールバック処理
    if not service_rows:
        service_rows.append("| 該当サービスなし | 要件に基づくサービスを検出できませんでした | $0.00 | $0.00 | より具体的な要件をお聞かせください |")
    
    service_cost_table = "\n".join(service_rows)
    total_yearly = total_monthly * 12
    
    # 最適化提案表を動的生成
    optimization_rows = []
    total_savings = 0
    
    for opt in optimization_data:
        optimization_rows.append(f"| {opt['name']} | {opt['current']} | {opt['optimized']} | ${opt['savings']:.2f} | {opt['percentage']}% |")
        total_savings += opt['savings']
    
    # 最適化提案表の空テーブル対応
    if not optimization_rows:
        optimization_rows.append("| 最適化提案なし | 現在の構成 | 詳細分析後に提案 | $0.00 | 0% |")
    
    optimization_table = "\n".join(optimization_rows)
    optimized_monthly = total_monthly - total_savings
    savings_percentage = int((total_savings / total_monthly * 100) if total_monthly > 0 else 0)
    
    # ガイダンス情報の処理
    guidance_text = cost_guidance if cost_guidance else "現在利用可能なガイダンスはありません。"
    docs_text = cost_docs.get('description', '料金情報は現在利用できません。') if cost_docs and cost_docs.get('description') != 'N/A' else "料金情報は現在利用できません。"
    
    # テンプレートに値を注入
    report = template.format(
        service_cost_table=service_cost_table,
        total_monthly=total_monthly,
        total_yearly=total_yearly,
        optimization_table=optimization_table,
        optimized_monthly=optimized_monthly,
        total_savings=total_savings,
        savings_percentage=savings_percentage,
        cost_guidance=guidance_text,
        cost_docs=docs_text
    )
    
    return report

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
    
    def initialize_with_existing_mcp(self, mcp_client_service, page_type: str = PAGE_TYPE_GENERAL) -> bool:
        """既存のMCPClientServiceを使用して初期化
        
        Args:
            mcp_client_service: MCPクライアントサービス
            page_type: ページタイプ (PAGE_TYPE_AWS_CHAT, PAGE_TYPE_TERRAFORM_GENERATOR, PAGE_TYPE_GENERAL)
        """
        try:
            logging.info(f"既存のMCPClientServiceとの統合を開始 (ページタイプ: {page_type})")
            
            # 既存のMCPクライアントからツールを作成
            available_tools = mcp_client_service.get_available_tools()
            logging.info(f"既存MCPから利用可能なツール: {available_tools}")
            
            if not available_tools:
                logging.warning("既存MCPクライアントにツールがありません - フォールバック機能を提供")
                # ツールが無くても基本的なフォールバック機能を提供
                self.tools = self._create_tools_from_mcp_client(mcp_client_service, page_type)
                self.connected_servers = []
                return len(self.tools) > 0
            
            # MCPClientServiceをラップしてLangChainツールを作成（ページ特化）
            self.tools = self._create_tools_from_mcp_client(mcp_client_service, page_type)
            self.connected_servers = available_tools
            
            logging.info(f"既存MCP統合成功: {len(self.tools)}個のツール, {len(self.connected_servers)}個のサーバー (ページタイプ: {page_type})")
            return True
            
        except Exception as e:
            logging.error(f"既存MCP統合エラー: {e}")
            return False
    
    def _create_tools_from_mcp_client(self, mcp_client_service, page_type: str = PAGE_TYPE_GENERAL):
        """MCPClientServiceをラップしてLangChainツールを作成
        
        Args:
            mcp_client_service: MCPクライアントサービス
            page_type: ページタイプ (PAGE_TYPE_AWS_CHAT, PAGE_TYPE_TERRAFORM_GENERATOR, PAGE_TYPE_GENERAL)
        """
        from langchain_core.tools import Tool
        
        tools = []
        
        try:
            # AWS Documentation検索ツール（共通）
            def aws_docs_search(query: str) -> str:
                """AWS公式ドキュメントを検索"""
                result = mcp_client_service.get_aws_documentation(query)
                if result and result.get('description') and result.get('description') != 'N/A':
                    return f"検索結果: {result.get('description', 'N/A')} (出典: {result.get('source', 'AWS公式')})"
                
                # より具体的で次の行動を促すメッセージを返す
                return f"'{query}' に関する詳細なドキュメントが見つかりませんでした。代わりに別のキーワードで検索するか、aws_guidanceツールを使用して一般的な推奨事項を取得してください。これまでに収集した情報で十分な場合は、最終回答を作成してください。"
            
            # Core MCP ガイダンスツール（共通）
            def core_guidance(prompt: str) -> str:
                """AWS構成に関するガイダンスを取得"""
                guidance = mcp_client_service.get_core_mcp_guidance(prompt)
                if guidance:
                    return f"推奨事項: {guidance}"
                return "AWS Well-Architected Frameworkに基づいた設計を推奨します。"
            
            # コスト分析ツール（aws_chatページ特化）
            def cost_analysis(service_requirements: str) -> str:
                """AWS構成のコスト分析を実行"""
                try:
                    # Core MCPからコスト関連ガイダンスを取得
                    cost_guidance = mcp_client_service.get_core_mcp_guidance(f"コスト最適化 {service_requirements}")
                    
                    # AWS Documentationからコスト情報を検索
                    cost_docs = mcp_client_service.get_aws_documentation(f"pricing cost calculator {service_requirements}")
                    
                    # 要件からAWSサービスを抽出してコスト概算表を作成
                    aws_services = []
                    service_patterns = {
                        "EC2": r"(?i)ec2|インスタンス|仮想マシン|サーバー",
                        "S3": r"(?i)s3|ストレージ|オブジェクト",
                        "RDS": r"(?i)rds|データベース|mysql|postgres",
                        "Lambda": r"(?i)lambda|サーバーレス|関数",
                        "CloudFront": r"(?i)cloudfront|cdn|配信",
                        "VPC": r"(?i)vpc|ネットワーク|プライベート"
                    }
                    
                    for service, pattern in service_patterns.items():
                        if re.search(pattern, service_requirements):
                            aws_services.append(service)
                    
                    # デフォルトでよく使われるサービスを追加
                    if not aws_services:
                        aws_services = ["EC2", "S3", "VPC"]
                    
                    # MCPサーバーから動的にコスト見積もりを取得
                    cost_estimates = {}
                    
                    # 各サービスについてMCPクライアントから見積もりを取得
                    for service in aws_services:
                        try:
                            # サービス構成情報を準備
                            service_config = {
                                "service_name": service,
                                "region": "us-east-1",  # デフォルトリージョン
                                "usage_details": {}
                            }
                            
                            # 要件文字列からインスタンスタイプを推定
                            if service in ["EC2", "RDS"]:
                                if "small" in service_requirements.lower():
                                    service_config["instance_type"] = "t3.small" if service == "EC2" else "db.t3.small"
                                elif "large" in service_requirements.lower():
                                    service_config["instance_type"] = "t3.large" if service == "EC2" else "db.t3.large"
                                else:
                                    service_config["instance_type"] = "t3.medium" if service == "EC2" else "db.t3.small"
                            
                            # MCPクライアントからコスト見積もりを取得
                            estimate = mcp_client_service.get_cost_estimation(service_config)
                            
                            if estimate:
                                cost_estimates[service] = estimate
                            else:
                                # フォールバック: 基本的な見積もり
                                cost_estimates[service] = {
                                    "cost": 30,
                                    "detail": f"{service} 基本構成",
                                    "optimization": "詳細分析が必要",
                                    "current_state": "デフォルト",
                                    "reduction_rate": 0.15
                                }
                                
                        except Exception as service_error:
                            # 個別サービスエラーでも処理を継続
                            cost_estimates[service] = {
                                "cost": 25,
                                "detail": f"{service} 見積もり要",
                                "optimization": "詳細な要件確認が必要",
                                "current_state": "不明",
                                "reduction_rate": 0.10
                            }
                    
                    # テンプレートベースでレポートを生成
                    result = generate_cost_analysis_report(aws_services, cost_estimates, cost_guidance, cost_docs)
                    
                    # 結果のエラーハンドリング
                    if not result:
                        result = "コスト分析レポートの生成に失敗しました。"
                    
                    return result
                except Exception as e:
                    return f"コスト分析エラー: {str(e)}。基本的なコスト最適化手法を検討してください。"
            
            # Terraformコード生成ツール（terraform_generatorページ特化）
            def terraform_code_generator(requirements: str) -> str:
                """Terraformコードを生成"""
                code = mcp_client_service.generate_terraform_code(requirements)
                if code:
                    return f"生成されたTerraformコード:\n```hcl\n{code}\n```"
                return "Terraformコード生成には詳細な要件指定が必要です。"
            
            # 共通ツールを追加
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
            
            # ページ特化ツールを追加
            if page_type == PAGE_TYPE_AWS_CHAT:
                # aws_chatページ: コスト分析に特化
                tools.append(Tool(
                    name="aws_cost_analysis",
                    description="AWS構成のコスト分析と最適化提案を行います。引数: service_requirements (対象サービスと要件)",
                    func=cost_analysis
                ))
                logging.info("aws_chatページ特化: コスト分析ツールを追加")
                
            elif page_type == PAGE_TYPE_TERRAFORM_GENERATOR:
                # terraform_generatorページ: Terraformコード生成に特化
                tools.append(Tool(
                    name="terraform_code_generator",
                    description="AWS構成のTerraformコードを生成します。引数: requirements (実装要件)",
                    func=terraform_code_generator
                ))
                logging.info("terraform_generatorページ特化: Terraformコード生成ツールを追加")
                
            else:
                # 汎用ページ: 全ツールを追加
                tools.append(Tool(
                    name="aws_cost_analysis",
                    description="AWS構成のコスト分析と最適化提案を行います。引数: service_requirements (対象サービスと要件)",
                    func=cost_analysis
                ))
                tools.append(Tool(
                    name="terraform_code_generator",
                    description="AWS構成のTerraformコードを生成します。引数: requirements (実装要件)",
                    func=terraform_code_generator
                ))
                logging.info("汎用ページ: 全ツールを追加")
            
            logging.info(f"MCPClientService統合ツール作成完了: {len(tools)}個 (ページタイプ: {page_type})")
            
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