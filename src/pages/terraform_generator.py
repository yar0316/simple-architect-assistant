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
    from ui.streamlit_ui import display_chat_history
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {e}")
    st.stop()

# ページ設定
st.set_page_config(
    page_title="Terraform コード生成 - Simple Architect Assistant",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

        # AIレスポンスを生成
        with st.chat_message("assistant"):
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

                    full_response = ""
                    message_placeholder = st.empty()

                    # BedrockServiceを使用してストリーミング応答を取得
                    for chunk in bedrock_service.invoke_streaming(
                        prompt=context_info,
                        system_prompt=terraform_system_prompt,
                        enable_cache=enable_cache,
                        use_langchain=use_langchain
                    ):
                        full_response += chunk
                        message_placeholder.write(full_response + "▌")

                    # 最終応答を表示
                    message_placeholder.write(full_response)

                    # AIメッセージを履歴に追加
                    st.session_state.terraform_messages.append({
                        "role": "assistant",
                        "content": full_response
                    })

                    # キャッシュヒット統計（簡易推定）
                    if enable_cache and st.session_state.terraform_cache_stats["total_requests"] > 1:
                        st.session_state.terraform_cache_stats["cache_hits"] += 1
                        # 推定値
                        st.session_state.terraform_cache_stats["total_tokens_saved"] += 800

                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
                    st.session_state.terraform_messages.append({
                        "role": "assistant",
                        "content": f"申し訳ありませんが、エラーが発生しました: {str(e)}"
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
