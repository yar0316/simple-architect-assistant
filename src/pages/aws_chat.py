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
        add_message_to_history
    )
    from services.bedrock_service import BedrockService
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {e}")
    st.stop()

# ページ設定
st.set_page_config(
    page_title="AWS構成提案 - Simple Architect Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💬 AWS構成提案チャット")

# セッション状態を初期化
initialize_session_state()

# BedrockServiceを初期化（セッション状態で管理）
if "bedrock_service" not in st.session_state:
    st.session_state.bedrock_service = BedrockService()

bedrock_service = st.session_state.bedrock_service

# サイドバーにページ情報と設定を表示
with st.sidebar:
    st.header("📄 ページ情報")
    st.markdown("**現在のページ:** AWS構成提案")
    st.markdown("---")

    display_settings_tab(bedrock_service)

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

    # Terraform生成への連携ボタン（チャット履歴がある場合のみ表示）
    if st.session_state.messages and len(st.session_state.messages) > 0:
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

        # Bedrockからの応答をストリーミングで取得し表示
        with st.chat_message("assistant"):
            with st.spinner("AIが応答を生成中です..."):
                full_response = ""
                # プレースホルダーを作成し、逐次更新する
                message_placeholder = st.empty()

                # 設定から取得
                enable_cache = st.session_state.get("enable_cache", True)
                use_langchain = st.session_state.get("use_langchain", True)

                # BedrockServiceを使用してストリーミング応答を取得
                for chunk in bedrock_service.invoke_streaming(prompt, enable_cache, use_langchain):
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
