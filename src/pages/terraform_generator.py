import streamlit as st
import os
import sys

# 絶対パスでモジュールのパスを追加
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from services.bedrock_service import BedrockService
    from services.mcp_client import get_mcp_client
    from ui.streamlit_ui import display_chat_history
    from langchain_integration.agent_executor import create_aws_agent_executor
    from langchain_integration.mcp_tools import LangChainMCPManager, PAGE_TYPE_TERRAFORM_GENERATOR
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {e}")
    st.stop()

# ページ設定はメインのapp.pyで設定済み

# ページタイトル
st.title("🔧 Terraform コード生成")
st.markdown("AWS Terraformコードの自動生成を支援するチャットです。")

# AWS構成検討からの引き継ぎ状態を表示
if "shared_aws_config" in st.session_state:
    st.success("✅ AWS構成検討チャットから構成情報が引き継がれました。チャット履歴を確認してください。")

# Terraformシステムプロンプトのパス
TERRAFORM_PROMPT_FILE = os.path.join(
    parent_dir,
    "prompts",
    "terraform_system_prompt.txt"
)

# BedrockServiceの初期化


@st.cache_resource
def init_bedrock_service():
    return BedrockService()


bedrock_service = init_bedrock_service()

# MCPクライアントを初期化
mcp_client = get_mcp_client()

# セッション状態の初期化
if "terraform_messages" not in st.session_state:
    st.session_state.terraform_messages = [
        {
            "role": "assistant",
            "content": "こんにちは！Terraformコード生成アシスタントです。\n\nどのようなAWSインフラのTerraformコードを生成しますか？\n例：\n- ALB + ECS Fargate + RDS構成\n- S3 + CloudFront構成\n- VPC + EC2 + ELB構成"
        }
    ]

# AWS構成検討チャットからの引き継ぎデータを処理
if "shared_aws_config" in st.session_state and st.session_state.get("navigate_to_terraform", False):
    # 引き継ぎメッセージを追加（初回のみ）
    if not any(msg.get("from_aws_chat", False) for msg in st.session_state.terraform_messages):
        shared_config = st.session_state.shared_aws_config
        
        # AWS構成検討の結果をTerraform生成チャットに引き継ぎ
        handover_message = f"""
AWS構成検討チャットから以下の構成が引き継がれました：

---
**引き継がれた構成:**
{shared_config['content']}
---

この構成をもとにTerraformコードを生成いたします。
設定を確認して、必要に応じて追加の要件をお聞かせください。
        """
        
        st.session_state.terraform_messages.append({
            "role": "assistant",
            "content": handover_message,
            "from_aws_chat": True,
            "shared_config": shared_config
        })
    
    # ナビゲーションフラグをリセット
    st.session_state.navigate_to_terraform = False

if "terraform_cache_stats" not in st.session_state:
    st.session_state.terraform_cache_stats = {
        "total_requests": 0,
        "cache_hits": 0,
        "total_tokens_saved": 0
    }

# サイドバーに設定
with st.sidebar:
    st.header("🔧 Terraform設定")
    
    # AWS構成検討からの引き継ぎ情報を表示
    if "shared_aws_config" in st.session_state:
        with st.expander("📋 引き継がれた構成", expanded=True):
            shared_config = st.session_state.shared_aws_config
            st.write(f"**取得元:** {shared_config['source']}")
            st.write(f"**取得時刻:** {shared_config['timestamp']}")
            if st.button("引き継ぎデータをクリア", key="clear_shared"):
                del st.session_state.shared_aws_config
                st.rerun()
        st.markdown("---")

    # 環境選択
    environment = st.selectbox(
        "対象環境",
        ["development", "production", "staging"],
        index=0
    )

    # AWS リージョン選択
    aws_region = st.selectbox(
        "AWSリージョン",
        ["us-east-1", "us-west-2", "ap-northeast-1", "eu-west-1"],
        index=2  # ap-northeast-1をデフォルト
    )

    # コード出力形式
    output_format = st.selectbox(
        "出力形式",
        ["モジュール化構造", "単一ファイル", "ディレクトリ構造のみ"],
        index=0
    )

    st.markdown("---")

    # MCP統合設定
    st.header("🔧 MCP統合設定")
    
    # MCP統合の有効/無効
    enable_mcp = st.toggle(
        "MCP統合を有効化",
        value=st.session_state.get("enable_terraform_mcp", True),
        help="Terraform MCP サーバーとの統合を有効化します。より高品質なTerraformコードが生成されます。"
    )
    st.session_state.enable_terraform_mcp = enable_mcp
    
    if enable_mcp:
        # 利用可能なMCPツールを表示
        available_tools = mcp_client.get_available_tools()
        if "awslabs.terraform-mcp-server" in available_tools:
            st.success("✅ Terraform MCPサーバーが利用可能")
        else:
            st.warning("⚠️ Terraform MCPサーバーが初期化されていません")

    st.markdown("---")
    
    # エージェントモード設定
    st.header("🤖 AI エージェントモード")
    
    # 既存設定の移行処理: enable_terraform_agent_mode -> enable_agent_mode
    if "enable_terraform_agent_mode" in st.session_state and "enable_agent_mode" not in st.session_state:
        st.session_state.enable_agent_mode = st.session_state.enable_terraform_agent_mode
    
    # エージェントモードの有効/無効
    enable_agent_mode = st.toggle(
        "エージェントモードを有効化 (Beta)",
        value=st.session_state.get("enable_agent_mode", True),
        help="LangChainエージェントが自律的にツールを選択・実行してTerraformコード生成を支援します。複雑な構成の場合に適していますが、応答時間が長くなる場合があります。"
    )
    st.session_state.enable_agent_mode = enable_agent_mode
    
    if enable_agent_mode:
        # エージェント初期化
        if "terraform_agent_executor" not in st.session_state:
            try:
                # LangChain MCP Manager初期化
                if "terraform_langchain_mcp_manager" not in st.session_state:
                    st.session_state.terraform_langchain_mcp_manager = LangChainMCPManager()
                
                mcp_manager = st.session_state.terraform_langchain_mcp_manager
                
                # 既存のMCPクライアントを使用して初期化
                if not mcp_manager.is_available():
                    st.info("🔄 既存のMCPクライアントと統合中...")
                    
                    try:
                        # 既存のMCPClientServiceを取得
                        existing_mcp_client = get_mcp_client()
                        
                        # 既存MCPクライアントとの統合を試行（terraform_generatorページ特化）
                        mcp_init_success = mcp_manager.initialize_with_existing_mcp(existing_mcp_client, PAGE_TYPE_TERRAFORM_GENERATOR)
                        
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
                        st.session_state.terraform_agent_executor = agent_executor
                        st.success("✅ Terraform AIエージェントが初期化されました")
                        
                        # エージェント統計表示
                        stats = agent_executor.get_execution_stats()
                        with st.expander("エージェント詳細情報"):
                            st.json(stats)
                    else:
                        st.warning("⚠️ エージェント初期化に失敗しました。手動モードで動作します。")
                        st.session_state.terraform_agent_executor = None
                else:
                    st.error("❌ エージェントエグゼキューター作成に失敗しました")
                    st.session_state.terraform_agent_executor = None
            except ImportError:
                st.warning("⚠️ LangChain Agent機能が利用できません。手動モードで動作します。")
                st.session_state.terraform_agent_executor = None
            except Exception as e:
                st.error(f"❌ エージェント初期化エラー: {str(e)}")
                st.session_state.terraform_agent_executor = None
        
        # エージェント状態表示
        if st.session_state.get("terraform_agent_executor"):
            agent_stats = st.session_state.terraform_agent_executor.get_execution_stats()
            if agent_stats.get("status") == "初期化済み":
                st.info(f"🤖 Terraform エージェント ready | ツール数: {agent_stats.get('available_tools', 0)}")
            
            # メモリクリアボタン
            if st.button("🧹 エージェントメモリをクリア", key="terraform_clear_agent_memory"):
                st.session_state.terraform_agent_executor.clear_memory()
                st.success("エージェントメモリをクリアしました")
                st.rerun()
    else:
        # エージェントモード無効時は手動モード
        if "terraform_agent_executor" in st.session_state:
            del st.session_state.terraform_agent_executor
        st.info("📋 手動モード: 事前定義されたMCPツール呼び出しを使用")
    
    st.markdown("---")

    # キャッシュ設定
    enable_cache = st.checkbox("プロンプトキャッシュを有効にする", value=True)
    use_langchain = st.checkbox(
        "LangChainを使用する",
        value=bedrock_service.is_langchain_available()
    )

    st.markdown("---")

    # 統計表示
    st.subheader("📊 統計")
    stats = st.session_state.terraform_cache_stats
    st.metric("総リクエスト数", stats["total_requests"])
    cache_hit_rate = (stats["cache_hits"] /
                      max(stats["total_requests"], 1)) * 100
    st.metric("キャッシュヒット率", f"{cache_hit_rate:.1f}%")

    # 履歴クリア
    if st.button("チャット履歴をクリア", use_container_width=True):
        st.session_state.terraform_messages = [
            {
                "role": "assistant",
                "content": "チャット履歴がクリアされました。新しいTerraformコード生成を開始できます。"
            }
        ]
        st.rerun()

# メインチャットエリア
col1, col2 = st.columns([3, 1])

with col1:
    # チャット履歴の表示
    display_chat_history(st.session_state.terraform_messages)

    # チャット入力
    if user_input := st.chat_input("Terraformコード生成のリクエストを入力してください..."):
        # ユーザーメッセージを追加
        st.session_state.terraform_messages.append({
            "role": "user",
            "content": user_input
        })

        # ユーザーメッセージを表示
        with st.chat_message("user"):
            st.write(user_input)

        # コンテキスト情報を追加
        context_info = f"""
        対象環境: {environment}
        AWSリージョン: {aws_region}
        出力形式: {output_format}
        """
        
        # AWS構成検討からの引き継ぎデータがある場合は追加
        if "shared_aws_config" in st.session_state:
            shared_config = st.session_state.shared_aws_config
            context_info += f"""
        
        【引き継がれたAWS構成】:
        {shared_config['content']}
        
        【現在のリクエスト】: {user_input}
        
        上記の引き継がれたAWS構成を基にTerraformコードを生成してください。
        """
        else:
            context_info += f"""
        
        ユーザーリクエスト: {user_input}
        """

        # エージェントモードと手動モードで処理を分岐
        with st.chat_message("assistant"):
            full_response = ""
            
            # エージェントモードが有効で、エージェントが利用可能な場合
            if (st.session_state.get("enable_agent_mode", False) and 
                st.session_state.get("terraform_agent_executor") and 
                st.session_state.terraform_agent_executor.is_initialized):
                
                st.info("🤖 Terraform AIエージェントが自律的に最適なコード生成を行います...")
                
                # エージェント思考プロセス可視化用コンテナ
                agent_process_container = st.container()
                
                # エージェント用のコンテキスト作成
                agent_context = f"""
                【Terraformコード生成リクエスト】
                {context_info}
                
                対象環境: {environment}
                AWSリージョン: {aws_region}
                出力形式: {output_format}
                
                ユーザーリクエスト: {user_input}
                
                Terraformのベストプラクティスに従い、実用的で保守しやすいコードを生成してください。
                """
                
                # エージェントでストリーミング実行
                full_response = st.write_stream(
                    st.session_state.terraform_agent_executor.invoke_streaming(agent_context, agent_process_container)
                )
                        
            else:
                # 手動モード（従来の処理）
                if st.session_state.get("enable_agent_mode", False):
                    st.warning("⚠️ エージェントが利用できないため、手動モードで処理します")
                
                with st.spinner("Terraformコードを生成中です..."):
                    try:
                        # 統計更新
                        st.session_state.terraform_cache_stats["total_requests"] += 1

                        # Terraformシステムプロンプトを読み込み
                        try:
                            with open(TERRAFORM_PROMPT_FILE, "r", encoding="utf-8") as f:
                                terraform_system_prompt = f.read()
                        except FileNotFoundError:
                            terraform_system_prompt = "あなたはTerraformエキスパートです。AWSのTerraformコードを生成してください。"

                        enhanced_context = context_info
                        
                        # MCP統合が有効な場合、Terraform MCPサーバーからコード生成
                        if st.session_state.get("enable_terraform_mcp", True):
                            with st.spinner("Terraform MCPサーバーから高品質コードを生成中..."):
                                try:
                                    # 手動モード専用のLangChainMCPManagerを初期化
                                    if "manual_langchain_mcp_manager" not in st.session_state:
                                        st.session_state.manual_langchain_mcp_manager = LangChainMCPManager()
                                        
                                        # 既存のMCPクライアントと統合
                                        existing_mcp_client = get_mcp_client()
                                        mcp_init_success = st.session_state.manual_langchain_mcp_manager.initialize_with_existing_mcp(
                                            existing_mcp_client, PAGE_TYPE_TERRAFORM_GENERATOR
                                        )
                                        
                                        if not mcp_init_success:
                                            st.warning("手動モード用MCP統合に失敗しました。フォールバックモードで動作します。")
                                    
                                    manual_mcp_manager = st.session_state.manual_langchain_mcp_manager
                                    
                                    # Core MCPからガイダンスを取得
                                    core_guidance = mcp_client.get_core_mcp_guidance(context_info)
                                    
                                    # LangChainMCPManagerのterraform_code_generatorツールを使用
                                    terraform_code = None
                                    available_tools = manual_mcp_manager.get_all_tools()
                                    
                                    # terraform_code_generatorツールを検索
                                    terraform_tool = None
                                    for tool in available_tools:
                                        if tool.name == "terraform_code_generator":
                                            terraform_tool = tool
                                            break
                                    
                                    if terraform_tool:
                                        terraform_code = terraform_tool.func(context_info)
                                    else:
                                        # フォールバック: 従来のMCPクライアント呼び出し
                                        terraform_code = mcp_client.generate_terraform_code(context_info)
                                    
                                    # プロンプトを拡張
                                    if core_guidance or terraform_code:
                                        enhanced_context = f"""ユーザーリクエスト: {context_info}

【MCP統合情報】"""
                                        
                                        if core_guidance:
                                            enhanced_context += f"""

■ Core MCPガイダンス:
{core_guidance}"""
                                        
                                        if terraform_code:
                                            enhanced_context += f"""

■ Terraform MCPサーバー生成コード:
```terraform
{terraform_code}
```"""
                                        
                                        enhanced_context += f"""

上記のMCP情報を参考に、ユーザーのリクエストに対して最適化されたTerraformコードを生成してください。
MCPサーバーが提供した情報を基に、さらに詳細で実用的なコードを提供してください。"""
                                
                                except Exception as e:
                                    st.warning(f"MCP情報の取得中にエラーが発生しました: {str(e)}")
                                    # エラーが発生してもオリジナルのコンテキストで続行

                        message_placeholder = st.empty()

                        # BedrockServiceのシステムプロンプトを一時的に上書き
                        with bedrock_service.override_system_prompt(terraform_system_prompt):
                            # BedrockServiceを使用してストリーミング応答を取得
                            for chunk in bedrock_service.invoke_streaming(
                                prompt=enhanced_context,
                                enable_cache=enable_cache,
                                use_langchain=use_langchain
                            ):
                                full_response += chunk
                                message_placeholder.write(full_response + "▌")

                            # 最終応答を表示
                            message_placeholder.write(full_response)

                        # キャッシュヒット統計（簡易推定）
                        if enable_cache and st.session_state.terraform_cache_stats["total_requests"] > 1:
                            st.session_state.terraform_cache_stats["cache_hits"] += 1
                            # 推定値
                            st.session_state.terraform_cache_stats["total_tokens_saved"] += 800

                    except Exception as e:
                        st.error(f"エラーが発生しました: {str(e)}")
                        full_response = f"申し訳ありませんが、エラーが発生しました: {str(e)}"

        # AIメッセージを履歴に追加（エージェントモード・手動モード共通）
        st.session_state.terraform_messages.append({
            "role": "assistant",
            "content": full_response
        })

with col2:
    # 右側のサンプル・ヘルプエリア
    st.subheader("💡 Terraformコード例")

    with st.expander("よく使用される構成パターン"):
        st.markdown("""
        **Webアプリケーション構成:**
        - VPC + Subnet
        - ALB + ECS Fargate
        - RDS + ElastiCache
        
        **静的サイト構成:**
        - S3 + CloudFront
        - Route53 + ACM
        
        **API構成:**
        - API Gateway + Lambda
        - DynamoDB
        
        **データ分析構成:**
        - Kinesis + S3
        - Athena + QuickSight
        """)

    with st.expander("Terraformベストプラクティス"):
        st.markdown("""
        - モジュール化
        - 状態ファイルのリモート管理
        - 変数とoutputの適切な定義
        - タグ付けの統一
        - セキュリティベストプラクティス
        - 環境別設定の分離
        """)

    st.subheader("📁 サンプルリクエスト")

    sample_requests = [
        "VPCとパブリック・プライベートサブネットの作成",
        "ALBとECS Fargateサービスの構成",
        "RDS PostgreSQLのマルチAZ構成",
        "S3とCloudFrontによるCDN構成",
        "Lambda関数とAPI Gatewayの統合"
    ]

    for i, sample in enumerate(sample_requests):
        if st.button(sample, key=f"sample_{i}", use_container_width=True):
            # サンプルリクエストをチャット入力に設定
            st.session_state.sample_input = sample
            st.rerun()

# フッター
st.markdown("---")
st.markdown(
    "💡 **ヒント**: 具体的な要件（インスタンスタイプ、ストレージ容量、ネットワーク設定など）を含めると、"
    "より詳細で実用的なTerraformコードが生成されます。"
)
