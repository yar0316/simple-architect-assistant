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
import streamlit as st
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(__file__))

# モジュールをインポート

# --- Streamlit UI ---

st.title("💬 Simple Architect Assistant")

# セッション状態を初期化
initialize_session_state()

# BedrockServiceを初期化（セッション状態で管理）
if "bedrock_service" not in st.session_state:
    st.session_state.bedrock_service = BedrockService()

bedrock_service = st.session_state.bedrock_service

# タブの定義
tab_chat, tab_stats, tab_settings = st.tabs([
    "💬 チャット",
    "📊 統計",
    "⚙️ 設定"
])

with tab_chat:
    # チャット履歴の表示
    display_chat_history()

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

with tab_settings:
    # 設定タブ表示
    display_settings_tab(bedrock_service.is_langchain_available())
