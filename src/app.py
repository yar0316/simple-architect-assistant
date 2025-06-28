import streamlit as st

# ページ設定
st.set_page_config(
    page_title="Simple Architect Assistant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# メインページ
st.title("🏗️ Simple Architect Assistant")

st.markdown("""
## AWS インフラ設計支援アプリケーション

このアプリケーションは、AWS Bedrock (Claude 3.7 Sonnet) を活用したAWSインフラ設計支援ツールです。

### 利用可能な機能

- **AWS構成提案チャット**: チャット形式でAWSアーキテクチャの提案を受けられます
- **Terraform コード生成**: AWSインフラのTerraformコードを自動生成できます

### 使い方

1. 左側のナビゲーションから使用したい機能を選択してください
2. AWS構成提案では、要件を自然言語で入力するとAWSアーキテクチャを提案します
3. Terraformコード生成では、インフラ要件からTerraformコードを生成します
""")

st.sidebar.success("👈 上のメニューからページを選択してください")

# 技術情報
with st.expander("📋 技術情報"):
    st.markdown("""
    **使用技術:**
    - Frontend: Streamlit
    - AI Model: AWS Bedrock Claude 3.7 Sonnet
    - Infrastructure: AWS
    - Language: Python
    
    **主な特徴:**
    - ストリーミングレスポンス
    - プロンプトキャッシュによるコスト最適化
    - LangChain統合（オプション）
    - セッション管理
    """)

# フッター
st.markdown("---")
st.markdown("🚀 **AWS Well-Architected Framework** に基づいた設計提案を行います")
