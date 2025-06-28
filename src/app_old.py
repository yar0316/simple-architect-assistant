import streamlit as st
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(__file__))

# モジュールをインポート
from services.bedrock_service import BedrockService
from ui.streamlit_ui import (
    initialize_session_state,
    display_chat_history,
    display_performance_stats,
    display_langchain_stats,
    display_memory_stats,
    display_settings_tab,
    add_message_to_history
)

# LangChain統合の確認
try:
    from langchain_integration.bedrock_llm import create_bedrock_llm
    from langchain_integration.memory_manager import StreamlitMemoryManager
    from langchain_integration.mcp_tools import is_langchain_mcp_available
    LANGCHAIN_INTEGRATION_AVAILABLE = True
except ImportError:
    LANGCHAIN_INTEGRATION_AVAILABLE = False

# --- Streamlit UI ---

st.title("💬 Simple Architect Assistant")

# セッション状態を初期化
initialize_session_state()

# BedrockServiceを初期化（セッション状態で管理）
if "bedrock_service" not in st.session_state:
    st.session_state.bedrock_service = BedrockService()

bedrock_service = st.session_state.bedrock_service


# システムプロンプトのパス
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(
    __file__), "prompts", "solution_architect_system_prompt.txt")
SYSTEM_PROMPT = load_system_prompt(SYSTEM_PROMPT_FILE)

# LangChain Bedrock LLM初期化
langchain_llm = None
memory_manager = None
if LANGCHAIN_INTEGRATION_AVAILABLE:
    langchain_llm = create_bedrock_llm(aws_profile, aws_region, MODEL_ID)
    memory_manager = get_memory_manager(window_size=10)

# --- Bedrock呼び出し関数 (ストリーミング対応) ---


def invoke_bedrock_streaming(prompt: str, enable_cache: bool = True, use_langchain: bool = True):
    """BedrockのClaude 4 SonnetモデルをConverse APIまたはLangChainでストリーミング呼び出し"""
    
    # LangChainを使用する場合
    if use_langchain and LANGCHAIN_INTEGRATION_AVAILABLE and langchain_llm:
        return invoke_with_langchain(prompt)
    
    # 従来のConverse APIを使用する場合
    return invoke_with_converse_api(prompt, enable_cache)

def invoke_with_langchain(prompt: str):
    """LangChainを使用したBedrock呼び出し（メモリ管理付き）"""
    try:
        # 統計更新
        st.session_state["cache_stats"]["total_requests"] += 1
        
        # メモリ管理を使用してチャット履歴を取得
        if memory_manager and memory_manager.is_available():
            chat_history = memory_manager.get_chat_history()[:-1]  # 最新のユーザーメッセージを除く
        else:
            chat_history = st.session_state.get("messages", [])[:-1]  # フォールバック
        
        # LangChainでストリーミング実行
        for chunk in langchain_llm.invoke_with_memory(prompt, SYSTEM_PROMPT, chat_history):
            yield chunk
            
        # LangChain使用統計を更新
        if "langchain_stats" not in st.session_state:
            st.session_state["langchain_stats"] = {
                "total_requests": 0,
                "successful_requests": 0
            }
        
        st.session_state["langchain_stats"]["total_requests"] += 1
        st.session_state["langchain_stats"]["successful_requests"] += 1
        
    except Exception as e:
        st.error(f"LangChain Bedrockストリーミング呼び出しエラー: {e}")
        yield "申し訳ありませんが、LangChainでの応答生成に失敗しました。"

def invoke_with_converse_api(prompt: str, enable_cache: bool = True):
    """従来のConverse APIを使用したBedrock呼び出し"""
    try:
        # 統計更新
        st.session_state["cache_stats"]["total_requests"] += 1
        
        # メッセージ作成（シンプル形式）
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": f"{SYSTEM_PROMPT}\n\nユーザーからの質問: {prompt}"
                    }
                ]
            }
        ]

        # システムプロンプトとキャッシュを分離
        if enable_cache:
            # システムプロンプトとキャッシュポイントを使用
            system_prompts = [
                {
                    "text": SYSTEM_PROMPT
                },
                {
                    "cachePoint": {"type": "default"}
                }
            ]
            
            # ユーザーメッセージはシンプルに
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
            
            # Converse APIでストリーミング呼び出し（システムプロンプト付き）
            response = bedrock_client.converse_stream(
                modelId=MODEL_ID,
                messages=messages,
                system=system_prompts,
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.7
                }
            )
        else:
            # キャッシュなしの場合
            response = bedrock_client.converse_stream(
                modelId=MODEL_ID,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.7
                }
            )

        # キャッシュヒット推定（2回目以降のリクエストでキャッシュ有効時）
        if enable_cache and st.session_state["cache_stats"]["total_requests"] > 1:
            st.session_state["cache_stats"]["cache_hits"] += 1
            # システムプロンプトのトークン数を推定（約600トークン）
            st.session_state["cache_stats"]["total_tokens_saved"] += 600

        # ストリームからチャンクを読み込み、逐次yieldする
        if response and "stream" in response:
            for event in response["stream"]:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        yield delta["text"]
                elif "messageStop" in event:
                    break
        else:
            st.error("ストリーミングレスポンスを取得できませんでした。")
            yield "申し訳ありませんが、応答を取得できませんでした。"

    except Exception as e:
        st.error(f"Converse APIストリーミング呼び出し中にエラーが発生しました: {e}")
        yield "申し訳ありませんが、応答を生成できませんでした。"

# --- Streamlit UI ---


st.title("💬 Simple Architect Assistant")

# サイドバーでキャッシュ統計を表示
with st.sidebar:
    st.header("📊 パフォーマンス統計")
    
    # セッション状態の初期化
    if "cache_stats" not in st.session_state:
        st.session_state["cache_stats"] = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens_saved": 0
        }
    
    stats = st.session_state["cache_stats"]
    
    # 統計表示
    col1, col2 = st.columns(2)
    with col1:
        st.metric("総リクエスト数", stats["total_requests"])
        st.metric("キャッシュヒット数", stats["cache_hits"])
    
    with col2:
        cache_hit_rate = (stats["cache_hits"] / max(stats["total_requests"], 1)) * 100
        st.metric("キャッシュヒット率", f"{cache_hit_rate:.1f}%")
        st.metric("節約トークン数(推定)", stats["total_tokens_saved"])
    
    # LangChain統計表示
    if LANGCHAIN_INTEGRATION_AVAILABLE and langchain_llm:
        st.header("🦜 LangChain統計")
        
        if "langchain_stats" not in st.session_state:
            st.session_state["langchain_stats"] = {
                "total_requests": 0,
                "successful_requests": 0
            }
        
        lc_stats = st.session_state["langchain_stats"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("LangChain総リクエスト", lc_stats["total_requests"])
        with col2:
            success_rate = (lc_stats["successful_requests"] / max(lc_stats["total_requests"], 1)) * 100
            st.metric("成功率", f"{success_rate:.1f}%")
        
        # メモリ統計表示
        if memory_manager and memory_manager.is_available():
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
                    if memory_manager:
                        memory_manager.clear_history()
                    st.session_state["messages"] = [
                        {"role": "assistant", "content": "どのようなAWS構成に関心がありますか？"}
                    ]
                    st.rerun()
            with col2:
                if st.button("会話履歴をエクスポート"):
                    if memory_manager:
                        history = memory_manager.export_history()
                        st.download_button(
                            "履歴をダウンロード",
                            data=json.dumps(history, ensure_ascii=False, indent=2),
                            file_name="chat_history.json",
                            mime="application/json"
                        )

    # 設定
    st.header("⚙️ 設定")
    enable_cache = st.checkbox("プロンプトキャッシュを有効にする", value=True)
    
    if LANGCHAIN_INTEGRATION_AVAILABLE and langchain_llm:
        use_langchain = st.checkbox("LangChainを使用する", value=True)
        
        with st.expander("LangChain詳細設定"):
            st.write("**利用可能な機能:**")
            st.write("✅ AWS Bedrock統合")
            st.write("✅ チャット履歴管理")
            st.write("✅ ストリーミングレスポンス")
            if is_langchain_mcp_available():
                st.write("✅ MCP Tools統合")
            else:
                st.write("❌ MCP Tools統合（パッケージ未インストール）")
    else:
        use_langchain = False
        st.info("💡 LangChain統合が利用できません。依存関係をインストールしてください。")
    
    if st.button("統計をリセット"):
        st.session_state["cache_stats"] = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens_saved": 0
        }
        if "langchain_stats" in st.session_state:
            st.session_state["langchain_stats"] = {
                "total_requests": 0,
                "successful_requests": 0
            }
        st.rerun()

# セッション状態でチャット履歴を管理
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "どのようなAWS構成に関心がありますか？"}]

# チャット履歴の表示
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# ユーザーからの入力
if prompt := st.chat_input():
    # ユーザーのメッセージを履歴に追加
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # LangChainメモリ管理にも追加
    if memory_manager and memory_manager.is_available():
        memory_manager.add_user_message(prompt)
    
    st.chat_message("user").write(prompt)

    # Bedrockからの応答をストリーミングで取得し表示
    with st.chat_message("assistant"):
        with st.spinner("AIが応答を生成中です..."):
            full_response = ""
            # プレースホルダーを作成し、逐次更新する
            message_placeholder = st.empty()
            for chunk in invoke_bedrock_streaming(prompt, enable_cache, use_langchain if 'use_langchain' in locals() else False):
                full_response += chunk
                message_placeholder.write(full_response + "▌")  # カーソル表示
            message_placeholder.write(full_response)  # 最終的な応答を表示

    # AIの応答を履歴に追加
    st.session_state.messages.append(
        {"role": "assistant", "content": full_response})
    
    # LangChainメモリ管理にも追加
    if memory_manager and memory_manager.is_available():
        memory_manager.add_ai_message(full_response)
