"""Streamlit UI関連のユーティリティ"""
import streamlit as st
import json
from typing import Dict, Any, Optional

def initialize_session_state():
    """セッション状態を初期化"""
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "どのようなAWS構成に関心がありますか？"}
        ]
    
    if "cache_stats" not in st.session_state:
        st.session_state["cache_stats"] = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens_saved": 0
        }
    
    if "langchain_stats" not in st.session_state:
        st.session_state["langchain_stats"] = {
            "total_requests": 0,
            "successful_requests": 0
        }

def display_chat_history(messages=None):
    """チャット履歴を表示"""
    if messages is None:
        messages = st.session_state.messages
    for msg in messages:
        st.chat_message(msg["role"]).write(msg["content"])

def add_message_to_history(role: str, content: str):
    """メッセージを履歴に追加"""
    st.session_state.messages.append({"role": role, "content": content})

def display_performance_stats():
    """パフォーマンス統計を表示"""
    st.header("📊 パフォーマンス統計")
    stats = st.session_state["cache_stats"]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("総リクエスト数", stats["total_requests"])
        st.metric("キャッシュヒット数", stats["cache_hits"])
    
    with col2:
        cache_hit_rate = (stats["cache_hits"] / max(stats["total_requests"], 1)) * 100
        st.metric("キャッシュヒット率", f"{cache_hit_rate:.1f}%")
        st.metric("節約トークン数(推定)", stats["total_tokens_saved"])

def display_langchain_stats():
    """LangChain統計を表示"""
    if "langchain_stats" in st.session_state:
        st.header("🦜 LangChain統計")
        lc_stats = st.session_state["langchain_stats"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("LangChain総リクエスト", lc_stats["total_requests"])
        with col2:
            success_rate = (lc_stats["successful_requests"] / max(lc_stats["total_requests"], 1)) * 100
            st.metric("成功率", f"{success_rate:.1f}%")

def display_memory_stats(memory_manager):
    """メモリ統計を表示"""
    if memory_manager and memory_manager.is_available():
        try:
            from langchain_integration.memory_manager import ConversationAnalyzer
            
            st.subheader("💭 会話メモリ統計")
            conversation_analysis = ConversationAnalyzer.analyze_conversation(
                memory_manager.get_chat_history()
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("会話ターン数", conversation_analysis.get("total_messages", 0))
                st.metric("ユーザーメッセージ", conversation_analysis.get("user_message_count", 0))
            with col2:
                st.metric("AIメッセージ", conversation_analysis.get("ai_message_count", 0))
                if conversation_analysis.get("topics"):
                    st.write("**検出トピック:**", ", ".join(conversation_analysis["topics"][:3]))
            
            # メモリ管理ボタン
            col1, col2 = st.columns(2)
            with col1:
                if st.button("会話履歴をクリア"):
                    memory_manager.clear_history()
                    st.session_state.messages = [
                        {"role": "assistant", "content": "どのようなAWS構成に関心がありますか？"}
                    ]
                    st.rerun()
            with col2:
                if st.button("会話履歴をエクスポート"):
                    history = memory_manager.export_history()
                    st.download_button(
                        "履歴をダウンロード",
                        data=json.dumps(history, ensure_ascii=False, indent=2),
                        file_name="chat_history.json",
                        mime="application/json"
                    )
        except ImportError:
            st.info("会話分析機能は利用できません。")

def display_settings_tab(bedrock_service):
    """設定タブを表示"""
    st.header("⚙️ 設定")
    
    # キャッシュ設定
    enable_cache = st.checkbox(
        "プロンプトキャッシュを有効にする",
        value=st.session_state.get("enable_cache", True)
    )
    st.session_state["enable_cache"] = enable_cache
    
    # LangChain設定
    if bedrock_service.is_langchain_available():
        use_langchain = st.checkbox(
            "LangChainを使用する",
            value=st.session_state.get("use_langchain", True)
        )
        st.session_state["use_langchain"] = use_langchain
        
        with st.expander("LangChain詳細設定"):
            st.write("**利用可能な機能:**")
            st.write("✅ AWS Bedrock統合")
            st.write("✅ チャット履歴管理")
            st.write("✅ ストリーミングレスポンス")
            
            try:
                from langchain_integration.mcp_tools import is_langchain_mcp_available
                if is_langchain_mcp_available():
                    st.write("✅ MCP Tools統合")
                else:
                    st.write("❌ MCP Tools統合（パッケージ未インストール）")
            except ImportError:
                st.write("❌ MCP Tools統合（パッケージ未インストール）")
    else:
        st.session_state["use_langchain"] = False
        st.info("💡 LangChain統合が利用できません。依存関係をインストールしてください。")
    
    # 統計リセット
    if st.button("統計をリセット"):
        st.session_state["cache_stats"] = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens_saved": 0
        }
        st.session_state["langchain_stats"] = {
            "total_requests": 0,
            "successful_requests": 0
        }
        st.rerun()

def handle_chat_input(bedrock_service, memory_manager=None):
    """チャット入力を処理"""
    if prompt := st.chat_input():
        # ユーザーメッセージを追加
        add_message_to_history("user", prompt)
        
        # メモリ管理にも追加
        if memory_manager and memory_manager.is_available():
            memory_manager.add_user_message(prompt)
        
        st.chat_message("user").write(prompt)
        
        # AI応答を取得
        with st.chat_message("assistant"):
            with st.spinner("AIが応答を生成中です..."):
                full_response = ""
                message_placeholder = st.empty()
                
                # 設定値を取得
                enable_cache = st.session_state.get("enable_cache", True)
                use_langchain = st.session_state.get("use_langchain", True)
                
                # ストリーミング応答を処理
                for chunk in bedrock_service.invoke_streaming(
                    prompt=prompt,
                    enable_cache=enable_cache,
                    use_langchain=use_langchain
                ):
                    full_response += chunk
                    message_placeholder.write(full_response + "▌")
                
                message_placeholder.write(full_response)
        
        # AI応答を履歴に追加
        add_message_to_history("assistant", full_response)
        
        # メモリ管理にも追加
        if memory_manager and memory_manager.is_available():
            memory_manager.add_ai_message(full_response)

# コスト分析関連の機能は削除されました。
# エージェントモードのcost_analysisツールが自動的にコスト計算を実行します。