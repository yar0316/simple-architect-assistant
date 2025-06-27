import streamlit as st
import boto3
import json
import os

# --- AWS Bedrockの設定 ---

# StreamlitのSecretsからAWS設定を読み込む
try:
    aws_profile = st.secrets.aws.profile
    aws_region = st.secrets.aws.region
except (AttributeError, KeyError):
    st.error("AWSの設定が.streamlit/secrets.tomlに見つかりません。")
    st.stop()

# boto3セッションとBedrockクライアントを初期化
session = boto3.Session(profile_name=aws_profile)
bedrock_client = session.client("bedrock-runtime", region_name=aws_region)

# 使用するモデルID (Claude 4 Sonnet)
# Inference Profileを利用する場合、モデルIDの先頭に 'us.' を付与する
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"

# --- システムプロンプトの読み込み ---


def load_system_prompt(file_path: str) -> str:
    """指定されたファイルからシステムプロンプトを読み込む関数"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"システムプロンプトファイルが見つかりません: {file_path}")
        st.stop()


# システムプロンプトのパス
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(
    __file__), "prompts", "solution_architect_system_prompt.txt")
SYSTEM_PROMPT = load_system_prompt(SYSTEM_PROMPT_FILE)

# --- Bedrock呼び出し関数 (ストリーミング対応) ---


def invoke_bedrock_streaming(prompt: str, enable_cache: bool = True):
    """BedrockのClaude 4 SonnetモデルをConverse APIとプロンプトキャッシュでストリーミング呼び出し"""
    try:
        # 統計更新
        st.session_state["cache_stats"]["total_requests"] += 1
        
        if enable_cache:
            # キャッシュ対応のメッセージ作成
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                        },
                        {
                            "type": "cacheControl",
                            "cacheType": "ephemeral"
                        },
                        {
                            "type": "text", 
                            "text": f"\n\nユーザーからの質問: {prompt}"
                        }
                    ]
                }
            ]
        else:
            # キャッシュなしのメッセージ作成
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{SYSTEM_PROMPT}\n\nユーザーからの質問: {prompt}"
                        }
                    ]
                }
            ]

        # Converse APIでストリーミング呼び出し
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
        for event in response.get("stream", []):
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    yield delta["text"]
            elif "messageStop" in event:
                break

    except Exception as e:
        st.error(f"Bedrockのストリーミング呼び出し中にエラーが発生しました: {e}")
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
    
    # プロンプトキャッシュ設定
    st.header("⚙️ 設定")
    enable_cache = st.checkbox("プロンプトキャッシュを有効にする", value=True)
    
    if st.button("統計をリセット"):
        st.session_state["cache_stats"] = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_tokens_saved": 0
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
    # ユーザーのメッセージを履歴に追加して表示
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # Bedrockからの応答をストリーミングで取得し表示
    with st.chat_message("assistant"):
        with st.spinner("AIが応答を生成中です..."):
            full_response = ""
            # プレースホルダーを作成し、逐次更新する
            message_placeholder = st.empty()
            for chunk in invoke_bedrock_streaming(prompt, enable_cache):
                full_response += chunk
                message_placeholder.write(full_response + "▌")  # カーソル表示
            message_placeholder.write(full_response)  # 最終的な応答を表示

    # AIの応答を履歴に追加
    st.session_state.messages.append(
        {"role": "assistant", "content": full_response})
