"""LangChain AWS Bedrock LLM統合"""
import streamlit as st
from typing import Iterator, Optional, Dict, Any
import boto3
import warnings
import logging

# urllib3警告を抑制（HTTPResponse close時のI/Oエラー警告）
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="I/O operation on closed file")
    warnings.filterwarnings("ignore", category=ResourceWarning)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HTTPResponseのログレベルを下げて詳細なエラーを抑制
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("urllib3.response").setLevel(logging.WARNING)

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
        self._is_closed = False
        
        # boto3セッション作成（HTTP接続設定を改善）
        from botocore.config import Config
        
        # HTTP接続設定を最適化
        config = Config(
            region_name=aws_region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=5,   # エージェント用に接続数を制限
            read_timeout=60,
            connect_timeout=10
        )
        
        self.session = boto3.Session(profile_name=aws_profile)
        
        # LangChain ChatBedrock初期化（リソース管理を改善）
        self.llm = ChatBedrock(
            model_id=model_id,
            model_kwargs={
                "max_tokens": 4096,
                "temperature": 0.7
            },
            streaming=True,
            credentials_profile_name=aws_profile,
            region_name=aws_region,
            # boto3設定を適用
            config=config
        )
        
        # アウトプットパーサー
        self.output_parser = StrOutputParser()
    
    def __enter__(self):
        """コンテキストマネージャー開始"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了時のクリーンアップ"""
        self.close()
    
    def close(self):
        """リソースの明示的な解放"""
        if not self._is_closed:
            try:
                # ChatBedrockの内部クライアントを安全に閉じる
                if hasattr(self.llm, 'client') and hasattr(self.llm.client, 'close'):
                    self.llm.client.close()
            except Exception:
                # クローズ時のエラーは無視（既に閉じられている可能性）
                pass
            finally:
                self._is_closed = True
    
    def __del__(self):
        """デストラクタでの安全なクリーンアップ"""
        try:
            self.close()
        except Exception:
            # デストラクタ内でのエラーは無視
            pass
    
    def create_chat_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """チャットプロンプトテンプレートを作成"""
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{user_input}")
        ])
    
    def _cleanup_stream_iterator(self, stream_iterator):
        """ストリームイテレータの適切なクリーンアップを実行"""
        if stream_iterator:
            try:
                # ストリームの残りを消費して接続をクリーンに閉じる
                for _ in stream_iterator:
                    pass
            except (StopIteration, GeneratorExit):
                pass
            except Exception:
                # クリーンアップ時のエラーは抑制
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    pass
    
    def invoke_streaming(self, prompt: str, system_prompt: str) -> Iterator[str]:
        """ストリーミングでLLMを呼び出し"""
        if self._is_closed:
            yield "エラー: LLMクライアントが閉じられています"
            return
            
        stream_iterator = None
        try:
            # チャットプロンプトを作成
            chat_prompt = self.create_chat_prompt(system_prompt)
            
            # チェーンを構築
            chain = chat_prompt | self.llm | self.output_parser
            
            # ストリーミング実行（リソース管理を強化）
            stream_iterator = chain.stream({"user_input": prompt})
            
            for chunk in stream_iterator:
                if chunk:
                    yield chunk
                    
        except Exception as e:
            # ストリーミングエラーの詳細ログを抑制
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                st.error(f"LangChain Bedrock呼び出しエラー: {e}")
            yield "申し訳ありませんが、応答を生成できませんでした。"
        finally:
            # ストリームの適切なクリーンアップ
            self._cleanup_stream_iterator(stream_iterator)
    
    def invoke_with_memory(self, prompt: str, system_prompt: str, chat_history: list) -> Iterator[str]:
        """メモリ付きでLLMを呼び出し"""
        stream_iterator = None
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
            
            # LLM呼び出し（リソース管理を強化）
            stream_iterator = self.llm.stream(messages)
            
            for chunk in stream_iterator:
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            # エラーログを抑制
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                st.error(f"LangChain Bedrock メモリ付き呼び出しエラー: {e}")
            yield "申し訳ありませんが、応答を生成できませんでした。"
        finally:
            # ストリームの適切なクリーンアップ
            self._cleanup_stream_iterator(stream_iterator)
    
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