# 公開MCPサーバー連携ガイド

このドキュメントでは、AIエージェント（ClaudeやLangChainなど）が、インターネット上で公開されている既存のMCP（Model Context Protocol）サーバーと連携する方法について解説します。この方法では、自身でサーバーを実装・ホストする必要はありません。

## 1. MCP (Model Context Protocol) とは

MCPは、AIモデル（LLM）が外部のツールやデータソースと安全かつ標準化された方法でやり取りするためのオープンソースプロトコルです。これにより、AIエージェントは、標準化されたインターフェースを通じて、多種多様な外部ツール（API、データベース、検索エンジンなど）の機能を利用できます。

## 2. 公開MCPサーバーとは

サードパーティの開発者や企業によって、特定の機能を持つMCPサーバーがインターネット上に公開されています。これらを利用することで、AIエージェントは即座に高度な機能を手に入れることができます。

公開サーバーのリストは、以下のリポジトリでコミュニティによって管理されています。

- **[awesome-mcp-servers](https://github.com/mcp-protocol/awesome-mcp-servers)**

このリストには、以下のような多様なツールが含まれています。

- **検索エンジン**: Brave Search, Kagi Search
- **開発ツール**: GitHub, Docker, OpenAPI
- **データベース**: MongoDB, PostgreSQL, Redis
- **その他**: AWS S3, Puppeteer (ブラウザ操作)

## 3. 連携方法 (設定ファイル利用)

最も簡単な連携方法は、エージェントのツール設定ファイルに、利用したい公開MCPサーバーの情報を記述することです。コードを書く必要はありません。

### 設定例: GitHub と Brave Search の利用

以下は、エージェント（例: Claude）に、GitHubリポジトリの情報取得と、Brave Searchでのウェブ検索を許可するための設定ファイル（JSON形式）の例です。

```json
{
  "tools": {
    "github": {
      "uri": "https://mcp.github.com"
    },
    "search": {
      "uri": "https://mcp.brave.com"
    }
  }
}
```

#### 設定の解説

- `"tools"`: 利用するツールを定義するセクションです。
- `"github"`, `"search"`: エージェントがツールを認識するための名前（任意）です。
- `"uri"`: **利用したい公開MCPサーバーのエンドポイントURI**を指定します。

エージェントは、この設定を読み込むことで、`github` や `search` というツールが利用可能であることを認識します。ユーザーから「〇〇というリポジトリの最新のコミットを教えて」や「〇〇についてウェブで調べて」といった指示を受けると、エージェントは自動的に指定されたURIのMCPサーバーにリクエストを送り、結果をユーザーに返します。

## 4. LangChainからの利用

Pythonアプリケーション内で、より動的にMCPサーバーを扱いたい場合は、`langchain-mcp-adapters` ライブラリを利用して、公開サーバーに接続することも可能です。

```python
from langchain_mcp_adapters import MCPToolLoader

# Brave Searchの公開MCPサーバーからツールをロード
mcp_loader = MCPToolLoader(mcp_server_url="https://mcp.brave.com")
tools = mcp_loader.load_tools()

# これで `tools` にはBrave Searchの機能が入っており、
# LangChainのエージェントに渡して利用できる

# (エージェントのセットアップと実行部分は省略)
```

このアプローチにより、アプリケーションのロジックに応じて、利用するMCPサーバーを切り替えるなど、柔軟な制御が可能になります。