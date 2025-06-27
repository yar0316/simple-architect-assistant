"""LangChain AWS Bedrock LLM統合"""
import streamlit as st
from typing import Iterator, Optional, Dict, Any
import boto3

try:
    from langchain_aws import ChatBedrock
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from langchain_core.callbacks import StreamingStdOutCallbackHandler
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    st.warning(f"LangChain AWS統合が利用できません: {e}")
    LANGCHAIN_AVAILABLE = False
    # ImportError時のダミークラス定義
    class ChatPromptTemplate:
        pass

class StreamlitCallbackHandler:
    """Streamlit用のストリーミングコールバックハンドラー"""
    
    def __init__(self, container):
        self.container = container
        self.text = ""
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """新しいトークンが生成されたときの処理"""
        self.text += token
        self.container.write(self.text + "▌")

class LangChainBedrockLLM:
    """LangChain統合のBedrock LLM"""
    
    def __init__(self, aws_profile: str, aws_region: str, model_id: str):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain AWS統合が利用できません")
        
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.model_id = model_id
        
        # boto3セッション作成
        self.session = boto3.Session(profile_name=aws_profile)
        
        # LangChain ChatBedrock初期化
        self.llm = ChatBedrock(
            model_id=model_id,
            model_kwargs={
                "max_tokens": 4096,
                "temperature": 0.7
            },
            streaming=True,
            credentials_profile_name=aws_profile,
            region_name=aws_region
        )
        
        # アウトプットパーサー
        self.output_parser = StrOutputParser()
    
    def create_chat_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """チャットプロンプトテンプレートを作成"""
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{user_input}")
        ])
    
    def invoke_streaming(self, prompt: str, system_prompt: str) -> Iterator[str]:
        """ストリーミングでLLMを呼び出し"""
        try:
            # チャットプロンプトを作成
            chat_prompt = self.create_chat_prompt(system_prompt)
            
            # チェーンを構築
            chain = chat_prompt | self.llm | self.output_parser
            
            # ストリーミング実行
            for chunk in chain.stream({"user_input": prompt}):
                if chunk:
                    yield chunk
                    
        except Exception as e:
            st.error(f"LangChain Bedrock呼び出しエラー: {e}")
            yield "申し訳ありませんが、応答を生成できませんでした。"
    
    def invoke_with_memory(self, prompt: str, system_prompt: str, chat_history: list) -> Iterator[str]:
        """メモリ付きでLLMを呼び出し"""
        try:
            # メッセージリストを構築
            messages = [SystemMessage(content=system_prompt)]
            
            # チャット履歴を追加
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
            
            # 現在のユーザーメッセージを追加
            messages.append(HumanMessage(content=prompt))
            
            # LLM呼び出し
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            st.error(f"LangChain Bedrock メモリ付き呼び出しエラー: {e}")
            yield "申し訳ありませんが、応答を生成できませんでした。"
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得（プレースホルダー）"""
        # LangChainでは使用統計の取得方法が異なる場合があります
        return {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0
        }

def create_bedrock_llm(aws_profile: str, aws_region: str, model_id: str) -> Optional[LangChainBedrockLLM]:
    """Bedrock LLMインスタンスを作成"""
    try:
        if not LANGCHAIN_AVAILABLE:
            return None
        return LangChainBedrockLLM(aws_profile, aws_region, model_id)
    except Exception as e:
        st.error(f"LangChain Bedrock LLM作成エラー: {e}")
        return None