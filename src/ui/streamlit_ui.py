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
                for chunk in bedrock_service.invoke_streaming(prompt, enable_cache, use_langchain):
                    full_response += chunk
                    message_placeholder.write(full_response + "▌")
                
                message_placeholder.write(full_response)
        
        # AI応答を履歴に追加
        add_message_to_history("assistant", full_response)
        
        # メモリ管理にも追加
        if memory_manager and memory_manager.is_available():
            memory_manager.add_ai_message(full_response)

def display_cost_analysis_button():
    """コスト分析ボタンを表示"""
    # 最新のAI応答にAWSサービスが含まれているかチェック
    auto_suggest = False
    if st.session_state.messages:
        latest_response = ""
        for message in reversed(st.session_state.messages):
            if message["role"] == "assistant":
                latest_response = message["content"].lower()
                break
        
        # AWSサービスのキーワードをチェック
        aws_keywords = ["ec2", "s3", "rds", "lambda", "cloudfront", "dynamodb", 
                       "vpc", "ecs", "eks", "load balancer", "elasticache"]
        auto_suggest = any(keyword in latest_response for keyword in aws_keywords)
    
    # ボタンの表示
    button_type = "primary" if auto_suggest else "secondary"
    button_text = "💰 この構成のコスト概算を確認" + (" (推奨)" if auto_suggest else "")
    
    if auto_suggest:
        st.info("💡 AWS構成が提案されました。コスト分析を実行することをお勧めします。")
    
    if st.button(button_text, type=button_type, use_container_width=True):
        st.session_state.show_cost_analysis = True
        st.rerun()

def display_cost_analysis_ui(mcp_client):
    """コスト分析UIを表示"""
    if not st.session_state.get("show_cost_analysis", False):
        return
    
    st.subheader("💰 コスト分析")
    
    # 最新のAI応答からAWSサービスを抽出
    latest_response = ""
    for message in reversed(st.session_state.messages):
        if message["role"] == "assistant":
            latest_response = message["content"]
            break
    
    if not latest_response:
        st.warning("コスト分析対象の構成が見つかりません。")
        return
    
    # AWSサービス候補を表示
    aws_services = [
        "Amazon EC2", "Amazon S3", "Amazon RDS", "Amazon CloudFront",
        "AWS Lambda", "Amazon DynamoDB", "Amazon VPC", "Amazon ECS",
        "Amazon EKS", "Application Load Balancer", "Network Load Balancer",
        "Amazon ElastiCache", "Amazon SQS", "Amazon SNS", "Amazon CloudWatch"
    ]
    
    st.write("**分析対象のAWSサービスを選択してください：**")
    selected_services = st.multiselect(
        "サービス選択",
        aws_services,
        default=[],
        help="コスト分析を実行したいAWSサービスを選択してください"
    )
    
    if selected_services:
        st.write("**利用規模を入力してください：**")
        
        usage_params = {}
        for service in selected_services:
            with st.expander(f"📊 {service} の利用規模"):
                if "EC2" in service:
                    usage_params[service] = {
                        "instance_type": st.selectbox(f"{service} インスタンスタイプ", ["t3.micro", "t3.small", "t3.medium", "t3.large", "m5.large", "m5.xlarge"], key=f"{service}_type"),
                        "instance_count": st.number_input(f"{service} インスタンス数", min_value=1, max_value=100, value=1, key=f"{service}_count"),
                        "hours_per_month": st.number_input(f"{service} 月間稼働時間", min_value=1, max_value=744, value=744, key=f"{service}_hours")
                    }
                elif "S3" in service:
                    usage_params[service] = {
                        "storage_gb": st.number_input(f"{service} ストレージ容量 (GB)", min_value=1, max_value=10000, value=100, key=f"{service}_storage"),
                        "requests_per_month": st.number_input(f"{service} 月間リクエスト数", min_value=1000, max_value=10000000, value=100000, key=f"{service}_requests")
                    }
                elif "RDS" in service:
                    usage_params[service] = {
                        "instance_type": st.selectbox(f"{service} インスタンスタイプ", ["db.t3.micro", "db.t3.small", "db.t3.medium", "db.m5.large"], key=f"{service}_db_type"),
                        "storage_gb": st.number_input(f"{service} ストレージ容量 (GB)", min_value=20, max_value=1000, value=100, key=f"{service}_db_storage"),
                        "multi_az": st.checkbox(f"{service} マルチAZ構成", key=f"{service}_multi_az")
                    }
                elif "Lambda" in service:
                    usage_params[service] = {
                        "executions_per_month": st.number_input(f"{service} 月間実行回数", min_value=1000, max_value=100000000, value=1000000, key=f"{service}_executions"),
                        "memory_mb": st.selectbox(f"{service} メモリ割り当て (MB)", [128, 256, 512, 1024, 2048, 3008], key=f"{service}_memory"),
                        "duration_ms": st.number_input(f"{service} 平均実行時間 (ms)", min_value=100, max_value=15000, value=1000, key=f"{service}_duration")
                    }
                else:
                    # その他のサービス用の汎用パラメータ
                    usage_params[service] = {
                        "usage_scale": st.selectbox(f"{service} 利用規模", ["小規模", "中規模", "大規模"], key=f"{service}_scale")
                    }
        
        # コスト計算実行ボタン
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💸 コスト計算を実行", type="primary", use_container_width=True):
                return perform_cost_analysis(selected_services, usage_params, latest_response, mcp_client)
    
    # 閉じるボタン
    if st.button("❌ コスト分析を閉じる"):
        st.session_state.show_cost_analysis = False
        st.rerun()
    
    return None

def perform_cost_analysis(selected_services, usage_params, architecture_context, mcp_client):
    """コスト分析を実行"""
    st.info("🔄 コスト分析を実行中...")
    
    # BedrockServiceの取得
    if "bedrock_service" not in st.session_state:
        st.error("BedrockServiceが初期化されていません")
        return None
    
    bedrock_service = st.session_state.bedrock_service
    
    # コスト計算プロンプトの読み込み
    try:
        import os
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(current_dir, "prompts", "cost_calculation_prompt.txt")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            cost_calculation_prompt = f.read()
    except Exception as e:
        st.error(f"コスト計算プロンプトの読み込みに失敗しました: {str(e)}")
        return None
    
    # 料金情報の収集
    pricing_data = {}
    with st.spinner("AWS料金情報を収集中..."):
        for service in selected_services:
            try:
                # MCP経由でAWS料金情報を取得
                pricing_info = mcp_client.get_aws_documentation(f"{service} pricing ap-northeast-1 tokyo region cost calculator")
                pricing_data[service] = pricing_info
            except Exception as e:
                st.warning(f"{service}の料金情報取得でエラー: {str(e)}")
                pricing_data[service] = {"error": str(e)}
    
    # プロンプトの構築
    services_info = []
    for service in selected_services:
        params = usage_params.get(service, {})
        service_info = f"- **{service}**: {params}"
        if service in pricing_data:
            service_info += f"\n  料金情報: {pricing_data[service]}"
        services_info.append(service_info)
    
    full_prompt = f"""
{cost_calculation_prompt}

## 分析対象

### AWSアーキテクチャコンテキスト
{architecture_context}

### 選択されたサービスと利用規模
{chr(10).join(services_info)}

### 要求事項
上記の情報に基づいて、詳細なコスト分析を実行し、指定された出力形式で結果を提示してください。
特に以下の点を重視してください：
1. 東京リージョン（ap-northeast-1）の料金を基準とする
2. 実際の利用パターンを考慮した現実的な見積もり
3. コスト最適化の具体的な提案
4. 計算根拠の明確な説明
"""

    # Bedrockでコスト分析を実行
    with st.spinner("AI によるコスト分析を実行中..."):
        try:
            full_response = ""
            response_placeholder = st.empty()
            
            # ストリーミングレスポンスでコスト分析結果を取得
            for chunk in bedrock_service.invoke_streaming(
                full_prompt,
                enable_cache=st.session_state.get("enable_cache", True),
                use_langchain=st.session_state.get("use_langchain", True)
            ):
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            
            # 分析結果をセッションに保存
            st.session_state.latest_cost_analysis = {
                "services": selected_services,
                "params": usage_params,
                "result": full_response,
                "timestamp": st.session_state.get("timestamp", "不明")
            }
            
            return {"analysis": full_response, "services": selected_services}
            
        except Exception as e:
            st.error(f"コスト分析の実行に失敗しました: {str(e)}")
            return None

def calculate_service_cost(service_name, usage_params, pricing_info):
    """サービスのコストを計算（簡易版）"""
    # 実際のMCP統合時はより詳細な計算ロジックを実装
    base_costs = {
        "Amazon EC2": {"t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416, "t3.large": 0.0832, "m5.large": 0.096, "m5.xlarge": 0.192},
        "Amazon S3": {"storage": 0.023, "requests": 0.0004},
        "Amazon RDS": {"db.t3.micro": 0.017, "db.t3.small": 0.034, "db.t3.medium": 0.068, "db.m5.large": 0.192},
        "AWS Lambda": {"execution": 0.0000002, "memory": 0.0000166667}
    }
    
    try:
        if "EC2" in service_name:
            instance_type = usage_params.get("instance_type", "t3.micro")
            instance_count = usage_params.get("instance_count", 1)
            hours = usage_params.get("hours_per_month", 744)
            hourly_rate = base_costs["Amazon EC2"].get(instance_type, 0.0104)
            return hourly_rate * instance_count * hours
            
        elif "S3" in service_name:
            storage_gb = usage_params.get("storage_gb", 100)
            requests = usage_params.get("requests_per_month", 100000)
            storage_cost = storage_gb * base_costs["Amazon S3"]["storage"]
            request_cost = requests * base_costs["Amazon S3"]["requests"] / 1000
            return storage_cost + request_cost
            
        elif "RDS" in service_name:
            instance_type = usage_params.get("instance_type", "db.t3.micro")
            storage_gb = usage_params.get("storage_gb", 100)
            multi_az = usage_params.get("multi_az", False)
            hourly_rate = base_costs["Amazon RDS"].get(instance_type, 0.017)
            instance_cost = hourly_rate * 744 * (2 if multi_az else 1)
            storage_cost = storage_gb * 0.115  # GP2 storage cost
            return instance_cost + storage_cost
            
        elif "Lambda" in service_name:
            executions = usage_params.get("executions_per_month", 1000000)
            memory_mb = usage_params.get("memory_mb", 128)
            duration_ms = usage_params.get("duration_ms", 1000)
            
            execution_cost = executions * base_costs["AWS Lambda"]["execution"]
            compute_cost = executions * (memory_mb / 1024) * (duration_ms / 1000) * base_costs["AWS Lambda"]["memory"]
            return execution_cost + compute_cost
            
        else:
            # その他のサービスの簡易計算
            scale = usage_params.get("usage_scale", "小規模")
            scale_multiplier = {"小規模": 10, "中規模": 50, "大規模": 200}
            return scale_multiplier.get(scale, 10)
            
    except Exception:
        return 10.0  # デフォルト値
