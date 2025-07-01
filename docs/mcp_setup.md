# MCP (Model Context Protocol) セットアップガイド

このドキュメントでは、AWS MCP サーバーの設定方法について説明します。

## 概要

Simple Architect Assistant は AWS の公式 MCP サーバーと統合して、以下の機能を提供します：

- **Core MCP Server**: プロンプト理解とAWSソリューション構築ガイダンス
- **AWS Documentation MCP Server**: AWS公式ドキュメント検索
- **Terraform MCP Server**: 高品質なTerraformコード生成

## 前提条件

### 1. uvx のインストール

MCPサーバーは `uvx` を使用して実行されます。まず `uvx` をインストールしてください：

```bash
# Python pipを使用してuvxをインストール
pip install uvx

# または、公式インストーラーを使用（Linux/Mac）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. AWS認証情報の設定

AWS MCP サーバーが AWS サービスにアクセスするため、適切な認証情報が必要です：

```bash
# AWS CLIの設定
aws configure

# または環境変数での設定
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-northeast-1
```

## MCP設定ファイル

MCPサーバーの設定は `config/mcp_config.json` で管理されています。

### デフォルト設定（Windows対応）

Windows環境での動作を優先し、以下の設定をデフォルトとしています：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "awslabs-core-mcp-server", 
        "awslabs.core-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    },
    "awslabs.aws-documentation-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "awslabs-aws-documentation-mcp-server",
        "awslabs.aws-documentation-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    },
    "awslabs.terraform-mcp-server": {
      "command": "uvx",
      "args": [
        "--from", 
        "awslabs-terraform-mcp-server",
        "awslabs.terraform-mcp-server.exe"
      ],
      "env": {"FASTMCP_LOG_LEVEL": "ERROR"},
      "autoApprove": [],
      "disabled": false
    }
  }
}
```

**重要**: Windows環境では `--from` オプションと `.exe` 拡張子が必要です。これは[こちらの記事](https://qiita.com/revsystem/items/911999b174dc5f3cf29d)で説明されているWindows固有の要件です。

### プラットフォーム固有設定

Mac/Linux環境では、より簡潔な設定を使用できます。`platform_overrides` セクションで自動的に適用されます：

```json
{
  "platform_overrides": {
    "darwin": {
      "mcpServers": {
        "awslabs.core-mcp-server": {
          "command": "uvx",
          "args": ["awslabs.core-mcp-server@latest"]
        }
      }
    },
    "linux": {
      "mcpServers": {
        "awslabs.core-mcp-server": {
          "command": "uvx", 
          "args": ["awslabs.core-mcp-server@latest"]
        }
      }
    }
  }
}
```

## 設定のカスタマイズ

### MCPサーバーの無効化

特定のサーバーを無効にするには、`disabled` を `true` に設定します：

```json
{
  "mcpServers": {
    "awslabs.terraform-mcp-server": {
      "disabled": true
    }
  }
}
```

### ログレベルの変更

より詳細なログが必要な場合は、ログレベルを変更します：

```json
{
  "env": {
    "FASTMCP_LOG_LEVEL": "DEBUG"
  }
}
```

### Windows環境での調整

現在の設定は既にWindows環境に最適化されています。問題が発生する場合の代替設定例：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "python",
      "args": ["-m", "uvx", "--from", "awslabs-core-mcp-server", "awslabs.core-mcp-server.exe"]
    }
  }
}
```

または、uvxを直接指定する場合：

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "uvx.exe",
      "args": ["--from", "awslabs-core-mcp-server", "awslabs.core-mcp-server.exe"]
    }
  }
}
```

## トラブルシューティング

### 1. 404 Not Found エラー

MCPサーバーが見つからない場合：

1. uvxが正しくインストールされているか確認
2. ネットワーク接続を確認
3. パッケージ名が正しいか確認

```bash
# uvxの動作確認
uvx --version

# MCPサーバーパッケージの確認
uvx run awslabs.core-mcp-server@latest --help
```

### 2. 権限エラー

AWS関連の権限エラーが発生する場合：

1. AWS認証情報が正しく設定されているか確認
2. 必要なIAM権限があるか確認
3. リージョン設定を確認

### 3. フォールバックモード

MCPサーバーが利用できない場合、アプリケーションは自動的にフォールバックモードで動作します：

- 基本的なAWSガイダンス機能は継続
- 静的なTerraformテンプレート提供
- エラーメッセージは最小限

## 開発者向け情報

### MCP統合の実装

`src/services/mcp_client.py` でMCP統合が実装されています：

- `MCPClientService`: メインのMCPクライアント
- `get_mcp_client()`: Streamlitセッション管理
- フォールバック機能付きエラーハンドリング

### 新しいMCPサーバーの追加

1. `config/mcp_config.json` に新しいサーバー設定を追加
2. `src/services/mcp_client.py` に対応するメソッドを実装
3. 必要に応じてUIコンポーネントを更新

### テスト

MCPサーバーの動作を個別にテストする場合：

```bash
# Core MCPサーバーのテスト
uvx run awslabs.core-mcp-server@latest

# AWS Documentation MCPサーバーのテスト
uvx run awslabs.aws-documentation-mcp-server@latest
```

## LangChain エージェントでのMCP利用（一般的な方法）

### 概要

**LangChain MCP Adapters** (`langchain-mcp-adapters`) は、Model Context Protocol (MCP) をLangChainエコシステムと統合するための公式ライブラリです。MCPは、AIモデルが外部ツールと対話するための標準化されたプロトコルで、このアダプターを使用することで、MCPサーバーが提供するツールをLangChain Agentで簡単に利用できます。

### MCP統合の基本アーキテクチャ

```
LangChain Agent
    ↓
langchain-mcp-adapters (McpClient)
    ↓
MCP Protocol (JSON-RPC)
    ↓
MCPサーバー群 (様々な機能提供)
```

### 基本的な実装方法

#### 1. インストール

```bash
pip install langchain-mcp-adapters
```

#### 2. 基本的なコード例

```python
from langchain_mcp_adapters import McpClient
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 1. MCPクライアントの初期化
# portはMCPサーバーがリッスンしているポート番号
mcp_client = McpClient(port=8080) 

# 2. MCPサーバーからツールを取得
# get_tools()はLangChainのToolオブジェクトのリストを返す
mcp_tools = mcp_client.get_tools()

# 3. LangChain Agentの設定
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, mcp_tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=mcp_tools, 
    verbose=True
)

# Agentの実行
result = agent_executor.invoke({
    "input": "MCPツールを使って何かをしてください"
})
```

#### 3. 複数MCPサーバーとの連携

```python
from langchain_mcp_adapters import McpClient
from langchain.tools import tool

# 複数のMCPクライアントを作成
documentation_client = McpClient(port=8080)  # ドキュメント検索
database_client = McpClient(port=8081)       # データベース操作

# 各クライアントからツールを取得
doc_tools = documentation_client.get_tools()
db_tools = database_client.get_tools()

# ローカルツールも定義可能
@tool
def local_calculator(expression: str) -> str:
    """数式を計算します。"""
    try:
        result = eval(expression)  # 注意: 本番では安全な評価を使用
        return str(result)
    except:
        return "計算エラー"

# すべてのツールを結合
all_tools = doc_tools + db_tools + [local_calculator]

# Agentに統合
agent = create_openai_tools_agent(llm, all_tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=all_tools)
```

### 統合パターンとベストプラクティス

#### 1. エラーハンドリング

```python
def get_mcp_tools_safely(port: int, backup_tools=None):
    """安全にMCPツールを取得"""
    try:
        client = McpClient(port=port)
        tools = client.get_tools()
        print(f"MCPサーバー（ポート{port}）から{len(tools)}個のツール取得")
        return tools
    except ConnectionError:
        print(f"MCPサーバー（ポート{port}）に接続できません")
        return backup_tools or []
    except Exception as e:
        print(f"ツール取得エラー: {e}")
        return backup_tools or []

# 使用例
mcp_tools = get_mcp_tools_safely(8080, backup_tools=[local_calculator])
```

#### 2. 動的ツール更新

```python
class DynamicMCPAgent:
    def __init__(self, llm, prompt):
        self.llm = llm
        self.prompt = prompt
        self.mcp_clients = {}
        
    def add_mcp_server(self, name: str, port: int):
        """MCPサーバーを動的に追加"""
        try:
            self.mcp_clients[name] = McpClient(port=port)
            print(f"MCPサーバー '{name}' を追加しました")
        except Exception as e:
            print(f"サーバー追加エラー: {e}")
    
    def get_all_tools(self):
        """すべてのMCPサーバーからツールを収集"""
        all_tools = []
        for name, client in self.mcp_clients.items():
            try:
                tools = client.get_tools()
                all_tools.extend(tools)
                print(f"'{name}' から {len(tools)} 個のツール取得")
            except Exception as e:
                print(f"'{name}' からのツール取得失敗: {e}")
        return all_tools
    
    def create_agent(self):
        """現在のツールセットでAgentを作成"""
        tools = self.get_all_tools()
        agent = create_openai_tools_agent(self.llm, tools, self.prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)

# 使用例
dynamic_agent = DynamicMCPAgent(llm, prompt)
dynamic_agent.add_mcp_server("docs", 8080)
dynamic_agent.add_mcp_server("database", 8081)

agent_executor = dynamic_agent.create_agent()
```

#### 3. MCPサーバー設定管理

```python
import json
from typing import Dict, List

class MCPServerConfig:
    def __init__(self, config_file: str):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
    
    def get_mcp_tools(self) -> List:
        """設定ファイルからMCPツールを取得"""
        tools = []
        
        for server_name, server_config in self.config.get("mcp_servers", {}).items():
            if server_config.get("disabled", False):
                continue
                
            try:
                port = server_config["port"]
                client = McpClient(port=port)
                server_tools = client.get_tools()
                tools.extend(server_tools)
                print(f"{server_name}: {len(server_tools)}個のツール追加")
                
            except Exception as e:
                print(f"{server_name} 接続エラー: {e}")
                
        return tools

# 設定ファイル例 (mcp_config.json)
"""
{
  "mcp_servers": {
    "documentation": {
      "port": 8080,
      "description": "ドキュメント検索サーバー",
      "disabled": false
    },
    "database": {
      "port": 8081, 
      "description": "データベース操作サーバー",
      "disabled": false
    }
  }
}
"""

# 使用例
config = MCPServerConfig("mcp_config.json")
mcp_tools = config.get_mcp_tools()
```

### セキュリティ考慮事項

#### 1. 信頼できるMCPサーバーのみ使用

```python
# 許可されたサーバーのホワイトリスト
ALLOWED_MCP_SERVERS = {
    "localhost:8080": "internal_docs",
    "internal-server:8081": "database_tools"
}

def validate_mcp_server(host: str, port: int) -> bool:
    """MCPサーバーの妥当性確認"""
    server_key = f"{host}:{port}"
    return server_key in ALLOWED_MCP_SERVERS
```

#### 2. ツール実行権限の制御

```python
from langchain.tools import BaseTool

class SecureMCPTool(BaseTool):
    """セキュリティ制御付きMCPツール"""
    
    def __init__(self, mcp_tool, allowed_operations=None):
        self.mcp_tool = mcp_tool
        self.allowed_operations = allowed_operations or []
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description
        )
    
    def _run(self, *args, **kwargs):
        # 実行前にセキュリティチェック
        if not self._is_operation_allowed(kwargs):
            return "この操作は許可されていません"
        
        return self.mcp_tool._run(*args, **kwargs)
    
    def _is_operation_allowed(self, kwargs) -> bool:
        # 実装依存のセキュリティロジック
        return True
```

### LangGraphとの統合

```python
from langgraph.graph import Graph
from langgraph.prebuilt import ToolNode

# MCPツールを取得
mcp_tools = get_mcp_tools_safely(8080)

# LangGraphでのワークフロー定義
def create_mcp_workflow():
    workflow = Graph()
    
    # ツールノードの追加
    tool_node = ToolNode(mcp_tools)
    workflow.add_node("tools", tool_node)
    
    # エージェントノードの追加
    workflow.add_node("agent", agent_function)
    
    # エッジの定義
    workflow.add_edge("agent", "tools")
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

### このプロジェクトでの具体的な実装

Simple Architect Assistant では、上記の一般的なパターンを AWS 特化で実装：

- **既存MCP統合**: `MCPClientService` との連携
- **フォールバック機能**: MCP利用不可時の代替処理  
- **AWS特化ツール**: ドキュメント検索、Terraform生成、コスト計算

実装詳細は `src/langchain_integration/mcp_tools.py` を参照。

## 参考資料

### 基本資料
- [AWS MCP Servers 公式ドキュメント](https://awslabs.github.io/mcp/)
- [Model Context Protocol 仕様](https://modelcontextprotocol.io/)
- [uvx 公式ドキュメント](https://docs.astral.sh/uv/)

### LangChain エージェント関連
- [langchain-mcp-adapters GitHub](https://github.com/model-context-protocol/langchain-mcp-adapters)
- [LangChain Agents ドキュメント](https://python.langchain.com/docs/modules/agents/)
- [LangChain Tools ガイド](https://python.langchain.com/docs/modules/tools/)
- [awesome-mcp-servers](https://github.com/mcp-protocol/awesome-mcp-servers) - 公開MCPサーバーリスト

### 技術詳細
- [Model Context Protocol 開発者ガイド](https://mcp.dev/)
- [asyncio と TaskGroup](https://docs.python.org/3/library/asyncio-task.html#task-groups)
- [AWS Bedrock + LangChain 統合](https://python.langchain.com/docs/integrations/llms/bedrock/)