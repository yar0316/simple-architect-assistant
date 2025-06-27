"""LangChain Memory管理"""
import streamlit as st
from typing import List, Dict, Any, Optional

try:
    from langchain.memory import ConversationBufferWindowMemory
    from langchain_community.chat_message_histories import StreamlitChatMessageHistory
    from langchain_core.messages import HumanMessage, AIMessage
    LANGCHAIN_MEMORY_AVAILABLE = True
except ImportError as e:
    st.warning(f"LangChain Memory統合が利用できません: {e}")
    LANGCHAIN_MEMORY_AVAILABLE = False
    # ImportError時のダミークラス定義
    class ConversationBufferWindowMemory:
        pass
    class StreamlitChatMessageHistory:
        pass
    class HumanMessage:
        pass
    class AIMessage:
        pass

class StreamlitMemoryManager:
    """Streamlit専用のメモリ管理クラス"""
    
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.memory_available = LANGCHAIN_MEMORY_AVAILABLE
        
        if self.memory_available:
            # StreamlitChatMessageHistoryを初期化
            self.chat_history = StreamlitChatMessageHistory(key="chat_messages")
            
            # ConversationBufferWindowMemoryを初期化
            self.memory = ConversationBufferWindowMemory(
                k=window_size,
                chat_memory=self.chat_history,
                return_messages=True,
                memory_key="chat_history"
            )
    
    def add_user_message(self, message: str):
        """ユーザーメッセージを追加"""
        if self.memory_available:
            self.memory.chat_memory.add_user_message(message)
        
        # Streamlitセッション状態にも保存
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        st.session_state["messages"].append({"role": "user", "content": message})
    
    def add_ai_message(self, message: str):
        """AIメッセージを追加"""
        if self.memory_available:
            self.memory.chat_memory.add_ai_message(message)
        
        # Streamlitセッション状態にも保存
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        st.session_state["messages"].append({"role": "assistant", "content": message})
    
    def get_chat_history(self) -> List[Dict[str, str]]:
        """チャット履歴を取得"""
        if self.memory_available and self.memory.chat_memory:
            # LangChainメモリから取得
            messages = self.memory.chat_memory.messages
            history = []
            
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    history.append({"role": "assistant", "content": msg.content})
            
            return history
        else:
            # Streamlitセッション状態から取得
            return st.session_state.get("messages", [])
    
    def get_memory_variables(self) -> Dict[str, Any]:
        """メモリ変数を取得"""
        if self.memory_available:
            return self.memory.load_memory_variables({})
        return {"chat_history": []}
    
    def clear_history(self):
        """チャット履歴をクリア"""
        if self.memory_available:
            self.memory.clear()
        
        # Streamlitセッション状態もクリア
        if "messages" in st.session_state:
            st.session_state["messages"] = []
    
    def get_recent_messages(self, n: int = 5) -> List[Dict[str, str]]:
        """最近のn件のメッセージを取得"""
        history = self.get_chat_history()
        return history[-n:] if len(history) > n else history
    
    def get_conversation_summary(self) -> str:
        """会話のサマリーを取得"""
        history = self.get_chat_history()
        
        if not history:
            return "会話履歴がありません。"
        
        total_messages = len(history)
        user_messages = len([msg for msg in history if msg["role"] == "user"])
        ai_messages = len([msg for msg in history if msg["role"] == "assistant"])
        
        return f"総メッセージ数: {total_messages} (ユーザー: {user_messages}, AI: {ai_messages})"
    
    def export_history(self) -> List[Dict[str, str]]:
        """チャット履歴をエクスポート"""
        return self.get_chat_history()
    
    def import_history(self, history: List[Dict[str, str]]):
        """チャット履歴をインポート"""
        self.clear_history()
        
        for msg in history:
            if msg["role"] == "user":
                self.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                self.add_ai_message(msg["content"])
    
    def is_available(self) -> bool:
        """メモリ機能が利用可能かチェック"""
        return self.memory_available

class ConversationAnalyzer:
    """会話分析クラス"""
    
    @staticmethod
    def analyze_conversation(history: List[Dict[str, str]]) -> Dict[str, Any]:
        """会話を分析"""
        if not history:
            return {"total_messages": 0, "topics": [], "summary": "会話履歴がありません。"}
        
        # 基本統計
        total_messages = len(history)
        user_messages = [msg for msg in history if msg["role"] == "user"]
        ai_messages = [msg for msg in history if msg["role"] == "assistant"]
        
        # トピック抽出（簡易版）
        topics = ConversationAnalyzer.extract_topics(user_messages)
        
        # 平均メッセージ長
        avg_user_length = sum(len(msg["content"]) for msg in user_messages) / len(user_messages) if user_messages else 0
        avg_ai_length = sum(len(msg["content"]) for msg in ai_messages) / len(ai_messages) if ai_messages else 0
        
        return {
            "total_messages": total_messages,
            "user_message_count": len(user_messages),
            "ai_message_count": len(ai_messages),
            "avg_user_message_length": avg_user_length,
            "avg_ai_message_length": avg_ai_length,
            "topics": topics,
            "summary": f"{total_messages}件のメッセージ、主なトピック: {', '.join(topics[:3])}"
        }
    
    @staticmethod
    def extract_topics(user_messages: List[Dict[str, str]]) -> List[str]:
        """ユーザーメッセージからトピックを抽出"""
        topics = []
        aws_keywords = ["ec2", "rds", "s3", "lambda", "vpc", "iam", "cloudformation", "terraform"]
        
        for msg in user_messages:
            content = msg["content"].lower()
            for keyword in aws_keywords:
                if keyword in content and keyword not in topics:
                    topics.append(keyword.upper())
        
        return topics

# シングルトンインスタンス
_memory_manager_instance = None

def get_memory_manager(window_size: int = 10) -> StreamlitMemoryManager:
    """Memory Managerのシングルトンインスタンスを取得"""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = StreamlitMemoryManager(window_size)
    return _memory_manager_instance

def is_memory_available() -> bool:
    """LangChain Memory機能が利用可能かチェック"""
    return LANGCHAIN_MEMORY_AVAILABLE