"""
LangChain ReActエージェントの実行エンジン

AWS構成提案を自律的に行うエージェントシステムを提供します。
"""

import streamlit as st
import asyncio
import os
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime
import logging

try:
    from langchain.agents import create_react_agent, AgentExecutor
    from langchain_core.prompts import PromptTemplate
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.tools import BaseTool
    from langchain.memory import ConversationBufferWindowMemory
    from langchain_aws import ChatBedrock
    LANGCHAIN_AGENT_AVAILABLE = True
except ImportError as e:
    st.warning(f"LangChain Agent機能が利用できません: {e}")
    LANGCHAIN_AGENT_AVAILABLE = False


class StreamlitAgentCallbackHandler(BaseCallbackHandler):
    """Streamlitでのエージェント実行過程を可視化するコールバックハンドラー"""
    
    def __init__(self, container):
        super().__init__()
        self.container = container
        self.step_count = 0
        self.current_step_container = None
        self.steps_history = []
        
    def on_agent_action(self, action, **kwargs):
        """エージェントがアクションを実行する前に呼ばれる"""
        self.step_count += 1
        
        with self.container:
            step_expander = st.expander(
                f"🤖 ステップ {self.step_count}: {action.tool} を実行中...", 
                expanded=True
            )
            
            with step_expander:
                st.write("**思考過程:**")
                st.write(action.log)
                st.write("**使用ツール:**", action.tool)
                st.write("**入力データ:**", action.tool_input)
                
                # 実行中を示すプレースホルダー
                self.current_step_container = st.empty()
                self.current_step_container.info("🔄 実行中...")
        
        self.steps_history.append({
            "step": self.step_count,
            "action": action.tool,
            "input": action.tool_input,
            "log": action.log,
            "timestamp": datetime.now()
        })
    
    def on_agent_finish(self, finish, **kwargs):
        """エージェントが完了した時に呼ばれる"""
        if self.current_step_container:
            self.current_step_container.success("✅ 全ステップ完了")
        
        with self.container:
            st.success("🎉 エージェント実行が完了しました")
    
    def on_tool_end(self, output, **kwargs):
        """ツール実行が完了した時に呼ばれる"""
        if self.current_step_container:
            self.current_step_container.success("✅ 実行完了")
            
        # 最新ステップに結果を追加
        if self.steps_history:
            self.steps_history[-1]["output"] = str(output)[:500] + "..." if len(str(output)) > 500 else str(output)
    
    def on_tool_error(self, error, **kwargs):
        """ツール実行でエラーが発生した時に呼ばれる"""
        if self.current_step_container:
            self.current_step_container.error(f"❌ エラー: {error}")


class AWSAgentExecutor:
    """AWS構成提案を行うLangChainエージェントのエグゼキューター"""
    
    def __init__(self, bedrock_service):
        self.bedrock_service = bedrock_service
        self.agent_executor = None
        self.memory = None
        self.tools = []
        self.logger = logging.getLogger(__name__)
        self.is_initialized = False
        
    def initialize(self, mcp_manager) -> bool:
        """エージェントを初期化"""
        if not LANGCHAIN_AGENT_AVAILABLE:
            self.logger.error("LangChain Agent機能が利用できません")
            return False
            
        try:
            # デバッグ: MCPマネージャーの状態を詳細に確認
            self.logger.info(f"MCPマネージャー初期化開始: {type(mcp_manager).__name__}")
            self.logger.info(f"MCPマネージャー利用可能: {getattr(mcp_manager, 'mcp_available', 'N/A')}")
            self.logger.info(f"MCPクライアント: {getattr(mcp_manager, 'client', 'N/A')}")
            self.logger.info(f"MCPマネージャーのツール数: {len(getattr(mcp_manager, 'tools', []))}")
            
            # MCPツールを取得
            if hasattr(mcp_manager, 'get_all_tools'):
                self.tools = mcp_manager.get_all_tools()
                self.logger.info(f"get_all_tools()から取得: {len(self.tools)}個のツール")
            else:
                self.logger.warning("mcp_managerにget_all_toolsメソッドがありません")
                # フォールバック: 基本的なツールセットを手動で作成
                self.tools = self._create_fallback_tools(mcp_manager)
                self.logger.info(f"フォールバックツールを作成: {len(self.tools)}個のツール")
            
            # ツールの詳細情報をログ出力
            for i, tool in enumerate(self.tools):
                self.logger.info(f"ツール{i+1}: {getattr(tool, 'name', 'NO_NAME')} - {getattr(tool, 'description', 'NO_DESCRIPTION')[:100]}")
            
            if not self.tools:
                self.logger.warning("MCPツールが利用できません - フォールバックツールのみで動作します")
                self.logger.info(f"MCPマネージャー状態: mcp_available={getattr(mcp_manager, 'mcp_available', 'N/A')}, client={getattr(mcp_manager, 'client', 'N/A')}")
                
                # フォールバックツールが作成されていない場合は作成
                if not self.tools:
                    self.tools = self._create_fallback_tools(mcp_manager)
                    self.logger.info(f"フォールバックツール作成完了: {len(self.tools)}個")
                
                # フォールバックツールもない場合は失敗
                if not self.tools:
                    self.logger.error("フォールバックツールの作成にも失敗しました")
                    return False
            
            # Claude 4 Sonnet用のLLM設定
            llm = ChatBedrock(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                model_kwargs={
                    "max_tokens": 4096,
                    "temperature": 0.1,
                    "top_p": 0.9
                },
                # BedrockServiceからセッション情報を取得
                region_name=self.bedrock_service.aws_region
            )
            
            # システムプロンプトを読み込み
            prompt_template = self._load_agent_prompt()
            
            # メモリ初期化
            self.memory = ConversationBufferWindowMemory(
                k=5,  # 直近5つの対話を保持
                memory_key="chat_history",
                return_messages=True
            )
            
            # ReActエージェント作成
            agent = create_react_agent(
                llm=llm,
                tools=self.tools,
                prompt=prompt_template
            )
            
            # エージェントエグゼキューター作成
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=self.memory,
                verbose=True,
                max_iterations=10,
                early_stopping_method="generate",
                handle_parsing_errors=True
            )
            
            self.is_initialized = True
            self.logger.info(f"エージェント初期化完了: {len(self.tools)}個のツールが利用可能")
            return True
            
        except Exception as e:
            self.logger.error(f"エージェント初期化エラー: {e}")
            return False
    
    def _load_agent_prompt(self) -> PromptTemplate:
        """エージェント用プロンプトテンプレートを読み込み"""
        try:
            # プロンプトファイルパス
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            prompt_path = os.path.join(current_dir, "prompts", "agent_system_prompt.txt")
            
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    template = f.read()
            else:
                # デフォルトプロンプト
                template = self._get_default_agent_prompt()
            
            return PromptTemplate(
                template=template,
                input_variables=["tools", "tool_names", "input", "agent_scratchpad", "chat_history"]
            )
            
        except Exception as e:
            self.logger.warning(f"プロンプト読み込みエラー: {e}, デフォルトプロンプトを使用")
            return PromptTemplate(
                template=self._get_default_agent_prompt(),
                input_variables=["tools", "tool_names", "input", "agent_scratchpad", "chat_history"]
            )
    
    def _get_default_agent_prompt(self) -> str:
        """デフォルトのエージェントプロンプト"""
        return """あなたは経験豊富なAWSソリューションアーキテクトです。ユーザーの要件に基づいて、最適なAWS構成を提案し、必要に応じて関連するツールを使用してください。

利用可能なツール:
{tools}

ツール名: {tool_names}

以下の形式で思考し、行動してください:

Question: 入力された質問
Thought: 何をすべきかを考える
Action: 使用するツール名
Action Input: ツールへの入力
Observation: ツールからの結果
... (必要に応じてThought/Action/Action Input/Observationを繰り返し)
Thought: 最終的な答えがわかりました
Final Answer: ユーザーへの最終回答

過去の会話履歴:
{chat_history}

Question: {input}
Thought: {agent_scratchpad}"""
    
    def _create_fallback_tools(self, mcp_manager) -> List[BaseTool]:
        """フォールバック用の基本ツールセットを作成"""
        from langchain_core.tools import Tool
        
        tools = []
        
        # 基本的なAWS情報提供ツール
        def aws_service_info(query: str) -> str:
            """AWS サービス情報を提供する基本ツール"""
            return f"AWS サービス '{query}' についての基本情報を提供します。より詳細な情報はMCPサーバーが必要です。"
        
        # 基本的なコスト情報ツール
        def basic_cost_info(service: str) -> str:
            """基本的なAWSコスト情報を提供"""
            return f"AWS {service} の基本的な料金体系についての情報を提供します。正確な見積りはMCPサーバーが必要です。"
        
        # フォールバックツールを作成
        try:
            aws_info_tool = Tool(
                name="aws_service_info",
                description="AWSサービスの基本情報を提供",
                func=aws_service_info
            )
            tools.append(aws_info_tool)
            
            cost_info_tool = Tool(
                name="basic_cost_info", 
                description="AWSサービスの基本的なコスト情報を提供",
                func=basic_cost_info
            )
            tools.append(cost_info_tool)
            
            self.logger.info(f"フォールバックツールセットを作成: {len(tools)}個のツール")
            
        except Exception as e:
            self.logger.error(f"フォールバックツール作成エラー: {e}")
        
        return tools
    
    def invoke_streaming(self, user_input: str, callback_container, streaming_delay: float = 0.001):
        """エージェントをストリーミング実行
        
        Args:
            user_input: ユーザーからの入力
            callback_container: Streamlitコンテナ（進行状況表示用）
            streaming_delay: 文字ごとの遅延時間（秒）。0で遅延なし、デフォルト0.001秒
        """
        if not self.is_initialized:
            yield "エラー: エージェントが初期化されていません"
            return
            
        try:
            # コールバックハンドラー作成
            callback_handler = StreamlitAgentCallbackHandler(callback_container)
            
            # エージェント実行（同期）
            result = self.agent_executor.invoke(
                {"input": user_input},
                config={"callbacks": [callback_handler]}
            )
            
            # 結果を段階的に返す（疑似ストリーミング）
            final_answer = result.get("output", "回答を生成できませんでした")
            
            # 文字単位で少しずつ返す（遅延設定可能）
            import time
            for char in final_answer:
                yield char
                if streaming_delay > 0:  # 遅延が0以上の場合のみ適用
                    time.sleep(streaming_delay)
                
        except Exception as e:
            self.logger.error(f"エージェント実行エラー: {e}")
            yield f"エラーが発生しました: {str(e)}"
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """エージェント実行統計を取得"""
        if not self.is_initialized:
            return {"status": "未初期化"}
            
        return {
            "status": "初期化済み",
            "available_tools": len(self.tools),
            "tool_names": [tool.name for tool in self.tools],
            "memory_messages": len(self.memory.chat_memory.messages) if self.memory else 0
        }
    
    def clear_memory(self):
        """エージェントメモリをクリア"""
        if self.memory:
            self.memory.clear()
            self.logger.info("エージェントメモリをクリアしました")


def create_aws_agent_executor(bedrock_service) -> Optional[AWSAgentExecutor]:
    """AWS Agent Executorのファクトリー関数"""
    try:
        executor = AWSAgentExecutor(bedrock_service)
        return executor
    except Exception as e:
        logging.error(f"AWSAgentExecutor作成エラー: {e}")
        return None