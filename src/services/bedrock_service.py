"""AWS Bedrock サービス統合モジュール"""
import streamlit as st
import boto3
import json
import os
import warnings
from typing import Iterator, Optional
from contextlib import contextmanager

# urllib3警告を抑制（HTTPResponse close時のI/Oエラー警告）
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="I/O operation on closed file")
    warnings.filterwarnings("ignore", category=ResourceWarning)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# LangChain統合のインポート
try:
    from langchain_integration.bedrock_llm import create_bedrock_llm, LANGCHAIN_AVAILABLE
    from langchain_integration.memory_manager import get_memory_manager
    LANGCHAIN_INTEGRATION_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_INTEGRATION_AVAILABLE = False


class BedrockService:
    """AWS Bedrock サービスクラス"""
    
    def __init__(self):
        self.aws_profile = None
        self.aws_region = None
        self.model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
        self.bedrock_client = None
        self.langchain_llm = None
        self.memory_manager = None
        self.system_prompt = None
        
        self._initialize_aws_config()
        self._initialize_bedrock_client()
        self._load_system_prompt()
        self._initialize_langchain()
    
    def _initialize_aws_config(self):
        """AWS設定を初期化"""
        try:
            self.aws_profile = st.secrets.aws.profile
            self.aws_region = st.secrets.aws.region
        except (AttributeError, KeyError):
            st.error("AWSの設定が.streamlit/secrets.tomlに見つかりません。")
            st.stop()
    
    def _initialize_bedrock_client(self):
        """Bedrockクライアントを初期化"""
        from botocore.config import Config
        
        # HTTP接続設定を最適化
        config = Config(
            region_name=self.aws_region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=10,  # 接続プール数を制限
            read_timeout=60,          # 読み取りタイムアウト
            connect_timeout=10        # 接続タイムアウト
        )
        
        session = boto3.Session(profile_name=self.aws_profile)
        self.bedrock_client = session.client(
            "bedrock-runtime", 
            region_name=self.aws_region,
            config=config
        )
    
    def _load_system_prompt(self):
        """システムプロンプトを読み込み"""
        system_prompt_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "prompts", 
            "solution_architect_system_prompt.txt"
        )
        try:
            with open(system_prompt_file, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            st.error(f"システムプロンプトファイルが見つかりません: {system_prompt_file}")
            st.stop()
    
    def _initialize_langchain(self):
        """LangChain統合を初期化"""
        if LANGCHAIN_INTEGRATION_AVAILABLE:
            self.langchain_llm = create_bedrock_llm(self.aws_profile, self.aws_region, self.model_id)
            self.memory_manager = get_memory_manager(window_size=10)
    
    def invoke_streaming(self, prompt: str, enable_cache: bool = True, use_langchain: bool = True) -> Iterator[str]:
        """BedrockをストリーミングAPI経由で呼び出し"""
        if use_langchain and self.langchain_llm:
            yield from self._invoke_with_langchain(prompt)
        else:
            yield from self._invoke_with_converse_api(prompt, enable_cache)
    
    def _invoke_with_langchain(self, prompt: str) -> Iterator[str]:
        """LangChainを使用した呼び出し"""
        try:
            # 統計更新
            if "cache_stats" in st.session_state:
                st.session_state["cache_stats"]["total_requests"] += 1
            
            # メモリ管理でチャット履歴を取得
            chat_history = []
            if self.memory_manager and self.memory_manager.is_available():
                chat_history = self.memory_manager.get_chat_history()[:-1]
            elif "messages" in st.session_state:
                chat_history = st.session_state.get("messages", [])[:-1]
            
            # LangChainでストリーミング実行
            for chunk in self.langchain_llm.invoke_with_memory(prompt, self.system_prompt, chat_history):
                yield chunk
            
            # 統計更新
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
    
    def _invoke_with_converse_api(self, prompt: str, enable_cache: bool = True) -> Iterator[str]:
        """Converse APIを使用した呼び出し"""
        response = None
        try:
            # 統計更新
            if "cache_stats" in st.session_state:
                st.session_state["cache_stats"]["total_requests"] += 1
            
            if enable_cache:
                # キャッシュ有効時の処理
                system_prompts = [
                    {"text": self.system_prompt},
                    {"cachePoint": {"type": "default"}}
                ]
                messages = [{
                    "role": "user",
                    "content": [{"text": prompt}]
                }]
                
                response = self.bedrock_client.converse_stream(
                    modelId=self.model_id,
                    messages=messages,
                    system=system_prompts,
                    inferenceConfig={
                        "maxTokens": 4096,
                        "temperature": 0.7
                    }
                )
                
                # キャッシュヒット推定
                if st.session_state.get("cache_stats", {}).get("total_requests", 0) > 1:
                    st.session_state["cache_stats"]["cache_hits"] += 1
                    st.session_state["cache_stats"]["total_tokens_saved"] += 600
            else:
                # キャッシュ無効時の処理
                messages = [{
                    "role": "user",
                    "content": [{"text": f"{self.system_prompt}\n\nユーザーからの質問: {prompt}"}]
                }]
                
                response = self.bedrock_client.converse_stream(
                    modelId=self.model_id,
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": 4096,
                        "temperature": 0.7
                    }
                )
            
            # ストリーミングレスポンスの処理（try-finallyで安全性確保）
            stream_started = False
            try:
                if response and "stream" in response:
                    for event in response["stream"]:
                        stream_started = True
                        if "contentBlockDelta" in event:
                            delta = event["contentBlockDelta"]["delta"]
                            if "text" in delta:
                                yield delta["text"]
                        elif "messageStop" in event:
                            break
                else:
                    yield "申し訳ありませんが、応答を取得できませんでした。"
            finally:
                # ストリーミング完了後のクリーンアップ
                if stream_started and response:
                    try:
                        # ストリームが完全に消費されていない場合のクリーンアップ
                        if "stream" in response:
                            # 残りのイベントを消費して接続をクリーンに閉じる
                            for _ in response["stream"]:
                                pass
                    except (StopIteration, GeneratorExit):
                        # 正常終了
                        pass
                    except Exception:
                        # クリーンアップ時のエラーは無視
                        pass
                
        except Exception as e:
            st.error(f"Converse APIストリーミング呼び出し中にエラーが発生しました: {e}")
            yield "申し訳ありませんが、応答を生成できませんでした。"
    
    def is_langchain_available(self) -> bool:
        """LangChain統合が利用可能かチェック"""
        return LANGCHAIN_INTEGRATION_AVAILABLE and self.langchain_llm is not None
    
    @contextmanager
    def override_system_prompt(self, new_prompt: str):
        """
        システムプロンプトを一時的に上書きするコンテキストマネージャー
        
        Args:
            new_prompt: 一時的に使用するシステムプロンプト
            
        Usage:
            with bedrock_service.override_system_prompt("新しいプロンプト"):
                # この範囲内でsystem_promptが上書きされる
                response = bedrock_service.invoke_streaming(
                    prompt=prompt,
                    enable_cache=enable_cache,
                    use_langchain=use_langchain
                )
            # withブロックを抜けると自動的に元のプロンプトに戻る
        """
        original_prompt = self.system_prompt
        try:
            self.system_prompt = new_prompt
            yield
        finally:
            self.system_prompt = original_prompt
