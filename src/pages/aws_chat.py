import streamlit as st
import os
import sys

# 絶対パスでモジュールのパスを追加
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from ui.streamlit_ui import (
        initialize_session_state,
        display_chat_history,
        display_performance_stats,
        display_langchain_stats,
        display_memory_stats,
        display_settings_tab,
        add_message_to_history,
        display_cost_analysis_button,
        display_cost_analysis_ui
    )
    from services.bedrock_service import BedrockService
    from services.mcp_client import get_mcp_client
    from langchain_integration.agent_executor import create_aws_agent_executor
    from langchain_integration.mcp_tools import LangChainMCPManager
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {e}")
    st.stop()

# ページ設定はメインのapp.pyで設定済み

st.title("💬 AWS構成提案チャット")

# セッション状態を初期化
initialize_session_state()

# BedrockServiceを初期化（セッション状態で管理）
if "bedrock_service" not in st.session_state:
    st.session_state.bedrock_service = BedrockService()

bedrock_service = st.session_state.bedrock_service

# MCPクライアントを初期化
mcp_client = get_mcp_client()

# サイドバーにページ情報と設定を表示
with st.sidebar:
    st.header("📄 ページ情報")
    st.markdown("**現在のページ:** AWS構成提案")
    st.markdown("---")

    display_settings_tab(bedrock_service)

    st.markdown("---")
    
    # MCP統合設定
    st.header("🔧 MCP統合設定")
    
    # MCP統合の有効/無効
    enable_mcp = st.toggle(
        "MCP統合を有効化",
        value=st.session_state.get("enable_mcp", True),
        help="AWS MCP サーバーとの統合を有効化します。より詳細なAWS情報とガイダンスを提供します。"
    )
    st.session_state.enable_mcp = enable_mcp
    
    if enable_mcp:
        # 利用可能なMCPツールを表示
        available_tools = mcp_client.get_available_tools()
        if available_tools:
            st.success(f"✅ {len(available_tools)} 個のMCPサーバーが利用可能")
            with st.expander("利用可能なMCPサーバー"):
                for tool in available_tools:
                    st.write(f"• {tool}")
        else:
            # MCPライブラリの利用可能性をチェック
            try:
                from langchain_mcp_adapters.client import MultiServerMCPClient
                mcp_available = True
            except ImportError:
                mcp_available = False
            
            debug_info = f"MCP_AVAILABLE: {mcp_available}"
            if not mcp_available:
                debug_info += " (langchain-mcp-adaptersが見つかりません)"
            
            # MCPクライアントの詳細情報を追加
            debug_info += f"\nMCPクライアント状態: {type(mcp_client).__name__}"
            debug_info += f"\nMCP設定ファイル存在: {os.path.exists(mcp_client.config_path) if hasattr(mcp_client, 'config_path') else 'N/A'}"
            
            # 設定ファイルパスの詳細確認
            if hasattr(mcp_client, 'config_path'):
                debug_info += f"\nMCP設定ファイルパス: {mcp_client.config_path}"
            else:
                # 期待されるパスを計算
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                project_root = os.path.dirname(parent_dir)
                expected_config_path = os.path.join(project_root, "config", "mcp_config.json")
                debug_info += f"\nMCP期待される設定ファイルパス: {expected_config_path}"
                debug_info += f"\nMCP期待される設定ファイル存在: {os.path.exists(expected_config_path)}"
            
            # uvxの存在確認
            import subprocess
            import os
            try:
                uvx_result = subprocess.run(['uvx', '--version'], capture_output=True, text=True, timeout=5)
                debug_info += f"\nuvx利用可能: {uvx_result.returncode == 0}"
            except:
                debug_info += f"\nuvx利用可能: False"
            
            # MCPクライアント初期化エラー情報
            if hasattr(st.session_state, 'mcp_client_error'):
                debug_info += f"\nMCPクライアント初期化エラー: {st.session_state.mcp_client_error}"
            
            st.warning(f"⚠️ MCPサーバーが初期化されていません\n\nデバッグ情報: {debug_info}")
    
    st.markdown("---")
    
    # エージェントモード設定
    st.header("🤖 AI エージェントモード")
    
    # エージェントモードの有効/無効
    enable_agent_mode = st.toggle(
        "エージェントモードを有効化 (Beta)",
        value=st.session_state.get("enable_agent_mode", False),
        help="LangChainエージェントが自律的にツールを選択・実行します。複雑な問い合わせに適していますが、応答時間が長くなる場合があります。"
    )
    st.session_state.enable_agent_mode = enable_agent_mode
    
    if enable_agent_mode:
        # エージェント初期化
        if "aws_agent_executor" not in st.session_state:
            try:
                # LangChain MCP Manager初期化
                if "langchain_mcp_manager" not in st.session_state:
                    st.session_state.langchain_mcp_manager = LangChainMCPManager()
                
                mcp_manager = st.session_state.langchain_mcp_manager
                
                # 既存のMCPクライアントを使用して初期化
                if not mcp_manager.is_available():
                    st.info("🔄 既存のMCPクライアントと統合中...")
                    
                    try:
                        # 既存のMCPClientServiceを取得
                        existing_mcp_client = get_mcp_client()
                        
                        # 既存MCPクライアントとの統合を試行
                        mcp_init_success = mcp_manager.initialize_with_existing_mcp(existing_mcp_client)
                        
                        if mcp_init_success:
                            tools_count = len(mcp_manager.get_all_tools())
                            st.success(f"✅ 既存MCP統合成功: {tools_count}個のツールが利用可能")
                        else:
                            st.warning("⚠️ 既存MCPとの統合に失敗しました。フォールバックモードで動作します。")
                        
                    except Exception as mcp_error:
                        st.warning(f"⚠️ MCP統合エラー: {str(mcp_error)}")
                        st.info("フォールバック機能で動作します。")
                
                # エージェントエグゼキューター作成
                agent_executor = create_aws_agent_executor(bedrock_service)
                if agent_executor:
                    # MCPマネージャーでエージェント初期化を試行
                    if agent_executor.initialize(mcp_manager):
                        st.session_state.aws_agent_executor = agent_executor
                        st.success("✅ AIエージェントが初期化されました")
                        
                        # エージェント統計表示
                        stats = agent_executor.get_execution_stats()
                        with st.expander("エージェント詳細情報"):
                            st.json(stats)
                    else:
                        st.warning("⚠️ エージェント初期化に失敗しました。手動モードで動作します。")
                        st.session_state.aws_agent_executor = None
                else:
                    st.error("❌ エージェントエグゼキューター作成に失敗しました")
                    st.session_state.aws_agent_executor = None
            except ImportError:
                st.warning("⚠️ LangChain Agent機能が利用できません。手動モードで動作します。")
                st.session_state.aws_agent_executor = None
            except Exception as e:
                st.error(f"❌ エージェント初期化エラー: {str(e)}")
                st.session_state.aws_agent_executor = None
        
        # エージェント状態表示
        if st.session_state.get("aws_agent_executor"):
            agent_stats = st.session_state.aws_agent_executor.get_execution_stats()
            if agent_stats.get("status") == "初期化済み":
                st.info(f"🤖 エージェント ready | ツール数: {agent_stats.get('available_tools', 0)}")
            
            # メモリクリアボタン
            if st.button("🧹 エージェントメモリをクリア"):
                st.session_state.aws_agent_executor.clear_memory()
                st.success("エージェントメモリをクリアしました")
                st.rerun()
    else:
        # エージェントモード無効時は手動モード
        if "aws_agent_executor" in st.session_state:
            del st.session_state.aws_agent_executor
        st.info("📋 手動モード: 事前定義されたMCPツール呼び出しを使用")
    
    st.markdown("---")

    # パフォーマンス統計表示
    display_performance_stats()

    # LangChain統計表示
    if bedrock_service.is_langchain_available():
        display_langchain_stats()

# タブの定義
tab_chat, tab_stats = st.tabs([
    "💬 チャット",
    "📊 詳細統計"
])

with tab_chat:
    # チャット履歴の表示
    display_chat_history()

    # アクションボタン（チャット履歴がある場合のみ表示）
    if st.session_state.messages and len(st.session_state.messages) > 0:
        # コスト分析ボタン
        display_cost_analysis_button()
        
        # コスト分析UI表示
        display_cost_analysis_ui(mcp_client)
        
        # Terraform生成への連携ボタン
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔧 この構成でTerraformコード生成", use_container_width=True, type="primary"):
                # 最新のAI応答を共有データとして保存
                latest_assistant_message = None
                for message in reversed(st.session_state.messages):
                    if message["role"] == "assistant":
                        latest_assistant_message = message["content"]
                        break
                
                if latest_assistant_message:
                    # 共有セッション状態に保存
                    st.session_state.shared_aws_config = {
                        "content": latest_assistant_message,
                        "timestamp": st.session_state.get("timestamp", "不明"),
                        "source": "AWS構成検討チャット"
                    }
                    st.success("AWS構成をTerraform生成に引き継ぎました！")
                    st.balloons()
                    # ページ遷移のためのナビゲーション情報を設定
                    st.session_state.navigate_to_terraform = True
                    st.info("👆 左側のナビゲーションから「Terraform コード生成」を選択してください")
                else:
                    st.error("引き継ぎ可能なAWS構成が見つかりませんでした")

    # ユーザーからの入力
    if prompt := st.chat_input():
        # ユーザーのメッセージを履歴に追加して表示
        add_message_to_history("user", prompt)
        st.chat_message("user").write(prompt)

        # エージェントモードと手動モードで処理を分岐
        with st.chat_message("assistant"):
            full_response = ""
            
            # エージェントモードが有効で、エージェントが利用可能な場合
            if (st.session_state.get("enable_agent_mode", False) and 
                st.session_state.get("aws_agent_executor") and 
                st.session_state.aws_agent_executor.is_initialized):
                
                st.info("🤖 AIエージェントが自律的に応答を生成します...")
                
                # エージェント思考プロセス可視化用コンテナ
                agent_process_container = st.container()
                
                # エージェントでストリーミング実行（非同期対応）
                full_response = st.write_stream(
                    st.session_state.aws_agent_executor.invoke_streaming(prompt, agent_process_container)
                )
                        
            else:
                # 手動モード（従来の処理）
                if st.session_state.get("enable_agent_mode", False):
                    st.warning("⚠️ エージェントが利用できないため、手動モードで処理します")
                
                with st.spinner("AIが応答を生成中です..."):
                    enhanced_prompt = prompt
                    
                    # MCP統合が有効な場合、追加情報を取得
                    if st.session_state.get("enable_mcp", True):
                        with st.spinner("MCPサーバーから追加情報を取得中..."):
                            try:
                                # Core MCPからプロンプトの理解とガイダンスを取得
                                core_guidance = mcp_client.get_core_mcp_guidance(prompt)
                                
                                # AWS Documentation から関連情報を取得
                                # キーワード抽出（簡易版）
                                aws_keywords = []
                                aws_services = ["EC2", "S3", "RDS", "Lambda", "CloudFront", "VPC", "IAM", 
                                              "CloudWatch", "ELB", "Auto Scaling", "DynamoDB", "SNS", "SQS"]
                                for service in aws_services:
                                    if service.lower() in prompt.lower():
                                        aws_keywords.append(service)
                                
                                aws_docs = None
                                if aws_keywords:
                                    search_query = " ".join(aws_keywords[:3])  # 最初の3つのキーワードを使用
                                    aws_docs = mcp_client.get_aws_documentation(search_query)
                            
                                # プロンプトを拡張
                                if core_guidance or aws_docs:
                                    enhanced_prompt = f"""ユーザーの質問: {prompt}

【MCP統合情報】"""
                                
                                if core_guidance:
                                    enhanced_prompt += f"""

■ Core MCPガイダンス:
{core_guidance}"""
                                
                                if aws_docs:
                                    enhanced_prompt += f"""

■ AWS公式ドキュメント情報:
{str(aws_docs)[:500]}..."""  # 長すぎる場合は切り捨て
                                
                                enhanced_prompt += f"""

上記のMCP情報を参考に、ユーザーの質問に対して最適なAWS構成を提案してください。"""
                        
                            except Exception as e:
                                st.warning(f"MCP情報の取得中にエラーが発生しました: {str(e)}")
                                # エラーが発生してもオリジナルのプロンプトで続行
                    
                    # プレースホルダーを作成し、逐次更新する
                    message_placeholder = st.empty()

                    # 設定から取得
                    enable_cache = st.session_state.get("enable_cache", True)
                    use_langchain = st.session_state.get("use_langchain", True)

                    # BedrockServiceを使用してストリーミング応答を取得
                    for chunk in bedrock_service.invoke_streaming(
                        prompt=enhanced_prompt,
                        enable_cache=enable_cache,
                        use_langchain=use_langchain
                    ):
                        full_response += chunk
                        message_placeholder.write(full_response + "▌")  # カーソル表示

                    message_placeholder.write(full_response)  # 最終的な応答を表示

        # AIの応答を履歴に追加
        add_message_to_history("assistant", full_response)

        # メモリマネージャーにも追加（利用可能な場合）
        if bedrock_service.memory_manager and bedrock_service.memory_manager.is_available():
            bedrock_service.memory_manager.add_user_message(prompt)
            bedrock_service.memory_manager.add_ai_message(full_response)

with tab_stats:
    # パフォーマンス統計表示
    display_performance_stats()

    # LangChain統計表示
    if bedrock_service.is_langchain_available():
        display_langchain_stats()

        # メモリ統計表示
        if bedrock_service.memory_manager and bedrock_service.memory_manager.is_available():
            display_memory_stats(bedrock_service.memory_manager)
