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

# 使用するモデルID (Claude 3.7 Sonnet)
# Inference Profileを利用する場合、モデルIDの先頭に 'us.' を付与する
MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

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
SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "solution_architect_system_prompt.txt")
SYSTEM_PROMPT = load_system_prompt(SYSTEM_PROMPT_FILE)

# --- Bedrock呼び出し関数 (ストリーミング対応) ---

def invoke_bedrock_streaming(prompt: str):
    """BedrockのClaude 3.7 Sonnetモデルをストリーミングで呼び出す関数"""
    try:
        # メッセージリストの作成
        messages = [
            {
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": prompt
                }]
            }
        ]

        # リクエストボディの作成
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": messages
        })

        # Bedrock APIのストリーミング呼び出し
        response = bedrock_client.invoke_model_with_response_stream(
            body=body,
            modelId=MODEL_ID,
            accept="application/json",
            contentType="application/json"
        )

        # ストリームからチャンクを読み込み、逐次yieldする
        for event in response.get("body"):
            chunk = json.loads(event["chunk"]["bytes"])
            if chunk["type"] == "content_block_delta":
                if chunk["delta"]["type"] == "text_delta":
                    yield chunk["delta"]["text"]

    except Exception as e:
        st.error(f"Bedrockのストリーミング呼び出し中にエラーが発生しました: {e}")
        yield "申し訳ありませんが、応答を生成できませんでした。"

# --- Streamlit UI ---

st.title("💬 Simple Architect Assistant")

# セッション状態でチャット履歴を管理
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "どのようなAWS構成に関心がありますか？"}]

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
            for chunk in invoke_bedrock_streaming(prompt):
                full_response += chunk
                message_placeholder.write(full_response + "▌") # カーソル表示
            message_placeholder.write(full_response) # 最終的な応答を表示
    
    # AIの応答を履歴に追加
    st.session_state.messages.append({"role": "assistant", "content": full_response})
