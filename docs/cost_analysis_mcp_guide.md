# Cost Analysis MCP 利用ガイド

## 目次
1. [概要](#概要)
2. [サービスコードの取得方法](#サービスコードの取得方法)
3. [Cost Analysis MCPツールの詳細](#cost-analysis-mcpツールの詳細)
4. [LangChainエージェントでの実装](#langchainエージェントでの実装)
5. [トラブルシューティング](#トラブルシューティング)
6. [実用的な使用例](#実用的な使用例)

---

## 概要

Cost Analysis MCPは、AWS料金情報を取得・分析するためのModel Context Protocol (MCP) サーバーです。このガイドでは、正しいサービスコードの取得方法と、LangChainエージェントからの適切な利用方法について説明します。

### 主な機能
- AWS Price List APIからの詳細料金データ取得
- AWS公式サイトからの料金情報取得
- コスト分析レポートの自動生成
- CDK/Terraformプロジェクトの分析

---

## サービスコードの取得方法

### 1. AWS Price List API 直接呼び出し

最も確実な方法は、AWS Price List APIから直接サービスコード一覧を取得することです。

#### cURLを使用した場合
```bash
curl 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json' | jq -r '.offers | .[] | .offerCode'
```

#### Pythonスクリプト
```python
import requests
import json

def get_all_service_codes():
    """すべてのAWSサービスコードを取得"""
    url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        service_codes = {}
        for offer in data.get('offers', {}).values():
            service_name = offer.get('serviceName', '')
            service_code = offer.get('offerCode', '')
            if service_name and service_code:
                service_codes[service_name] = service_code
        
        return service_codes
    except Exception as e:
        print(f"Error fetching service codes: {e}")
        return {}

# 使用例
codes = get_all_service_codes()
for name, code in codes.items():
    print(f"{name}: {code}")
```

### 2. 主要サービスコード一覧

#### コンピューティングサービス
| サービス名 | サービスコード | 用途 |
|------------|----------------|------|
| Amazon EC2 | `AmazonEC2` | 仮想サーバー |
| AWS Lambda | `AWSLambda` | サーバーレス |
| Amazon Lightsail | `AmazonLightsail` | VPS |
| Amazon ECS | `AmazonECS` | コンテナ |
| Amazon EKS | `AmazonEKS` | Kubernetes |

#### ストレージサービス
| サービス名 | サービスコード | 用途 |
|------------|----------------|------|
| Amazon S3 | `AmazonS3` | オブジェクトストレージ |
| Amazon EBS | `AmazonEC2` | ブロックストレージ※ |
| Amazon EFS | `AmazonEFS` | ファイルシステム |
| Amazon FSx | `AmazonFSx` | 高性能ファイルシステム |

> ※ 注意: EBSの料金はEC2サービスコードに含まれます

#### データベースサービス
| サービス名 | サービスコード | 用途 |
|------------|----------------|------|
| Amazon RDS | `AmazonRDS` | リレーショナルDB |
| Amazon DynamoDB | `AmazonDynamoDB` | NoSQL |
| Amazon Redshift | `AmazonRedshift` | データウェアハウス |
| Amazon ElastiCache | `AmazonElastiCache` | インメモリキャッシュ |

#### AI・機械学習
| サービス名 | サービスコード | 用途 |
|------------|----------------|------|
| Amazon Bedrock | `AmazonBedrock` | 生成AI |
| Amazon SageMaker | `AmazonSageMaker` | 機械学習 |
| Amazon Rekognition | `AmazonRekognition` | 画像・動画分析 |
| Amazon Comprehend | `AmazonComprehend` | 自然言語処理 |

### 3. サービスコード検索ヘルパークラス

```python
import requests
from typing import List, Dict, Optional

class AWSServiceCodeHelper:
    def __init__(self):
        self.service_codes = None
        self._load_service_codes()
    
    def _load_service_codes(self):
        """AWS Price List APIからサービスコードを取得"""
        try:
            url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.service_codes = {}
            
            for offer in data.get('offers', {}).values():
                service_name = offer.get('serviceName', '').lower()
                service_code = offer.get('offerCode', '')
                if service_name and service_code:
                    self.service_codes[service_name] = service_code
                    
        except Exception as e:
            print(f"Failed to load service codes: {e}")
            # フォールバック用の主要サービスコード
            self._load_fallback_codes()
    
    def _load_fallback_codes(self):
        """フォールバック用の主要サービスコード"""
        self.service_codes = {
            "amazon ec2": "AmazonEC2",
            "amazon s3": "AmazonS3",
            "amazon rds": "AmazonRDS",
            "amazon lightsail": "AmazonLightsail",
            "aws lambda": "AWSLambda",
            "amazon bedrock": "AmazonBedrock",
            "amazon sagemaker": "AmazonSageMaker",
            "amazon dynamodb": "AmazonDynamoDB",
            "amazon cloudfront": "AmazonCloudFront",
            "amazon route 53": "AmazonRoute53"
        }
    
    def find_service_code(self, service_name: str) -> Optional[str]:
        """サービス名からサービスコードを検索"""
        if not self.service_codes:
            return None
            
        service_name = service_name.lower().strip()
        
        # 完全一致チェック
        if service_name in self.service_codes:
            return self.service_codes[service_name]
        
        # 部分一致チェック
        for name, code in self.service_codes.items():
            if service_name in name or name in service_name:
                return code
        
        # 別名チェック
        aliases = {
            "ec2": "amazon ec2",
            "s3": "amazon s3",
            "rds": "amazon rds",
            "lambda": "aws lambda",
            "lightsail": "amazon lightsail",
            "bedrock": "amazon bedrock",
            "sagemaker": "amazon sagemaker",
            "dynamo": "amazon dynamodb",
            "dynamodb": "amazon dynamodb"
        }
        
        if service_name in aliases:
            return self.service_codes.get(aliases[service_name])
        
        return None
    
    def search_services(self, keyword: str) -> List[Dict[str, str]]:
        """キーワードでサービスを検索"""
        if not self.service_codes:
            return []
            
        keyword = keyword.lower()
        results = []
        
        for name, code in self.service_codes.items():
            if keyword in name:
                results.append({
                    "service_name": name.title(),
                    "service_code": code
                })
        
        return sorted(results, key=lambda x: x['service_name'])
    
    def list_all_services(self) -> Dict[str, str]:
        """全サービスの一覧を取得"""
        return dict(self.service_codes) if self.service_codes else {}

# 使用例
helper = AWSServiceCodeHelper()

# 単一サービスコード検索
print(helper.find_service_code("EC2"))  # -> "AmazonEC2"
print(helper.find_service_code("Amazon S3"))  # -> "AmazonS3"

# キーワード検索
storage_services = helper.search_services("storage")
for service in storage_services:
    print(f"{service['service_name']}: {service['service_code']}")
```

---

## Cost Analysis MCPツールの詳細

### 利用可能なツール

#### 1. `get_pricing_from_api`
AWS Price List APIから詳細な料金データを取得します。

**必須パラメータ:**
- `service_code`: AWSサービスコード（例: "AmazonEC2"）
- `region`: AWSリージョン（例: "us-east-1"）

**オプションパラメータ:**
- `filters`: 価格データをフィルタリングするための条件

**基本的な使用例:**
```python
request = {
    "service_code": "AmazonEC2",
    "region": "us-east-1"
}
```

**フィルタ付きの使用例:**
```python
request = {
    "service_code": "AmazonEC2",
    "region": "us-east-1",
    "filters": {
        "filters": [
            {
                "Field": "instanceType",
                "Value": "t3.micro",
                "Type": "TERM_MATCH"
            }
        ]
    }
}
```

#### 2. `get_pricing_from_web`
AWS公式サイトから料金情報を取得します。

**パラメータ:**
- `service_code`: Webサイト用のサービスコード（小文字、ハイフン区切り）

**使用例:**
```python
request = {
    "service_code": "ec2"  # Webサイト用は小文字
}
```

#### 3. `generate_cost_report`
取得した料金データから詳細なコスト分析レポートを生成します。

**必須パラメータ:**
- `pricing_data`: 前段階で取得した料金データ
- `service_name`: サービス名

**オプションパラメータ:**
- `assumptions`: 前提条件のリスト
- `exclusions`: 除外項目のリスト
- `detailed_cost_data`: 詳細なコストデータ
- `recommendations`: 推奨事項

### 有効なリージョン一覧

```python
VALID_REGIONS = [
    "us-east-1",        # 米国東部（バージニア北部）
    "us-east-2",        # 米国東部（オハイオ）
    "us-west-1",        # 米国西部（北カリフォルニア）
    "us-west-2",        # 米国西部（オレゴン）
    "eu-west-1",        # 欧州（アイルランド）
    "eu-west-2",        # 欧州（ロンドン）
    "eu-west-3",        # 欧州（パリ）
    "eu-central-1",     # 欧州（フランクフルト）
    "ap-northeast-1",   # アジアパシフィック（東京）
    "ap-northeast-2",   # アジアパシフィック（ソウル）
    "ap-southeast-1",   # アジアパシフィック（シンガポール）
    "ap-southeast-2",   # アジアパシフィック（シドニー）
    "ap-south-1",       # アジアパシフィック（ムンバイ）
    "ca-central-1",     # カナダ（中部）
    "sa-east-1"         # 南米（サンパウロ）
]
```

---

## LangChainエージェントでの実装

### 1. 基本的なツールクラス

```python
from langchain.tools import BaseTool
from typing import Dict, Any, Optional
import json

class CostAnalysisTool(BaseTool):
    name = "aws_cost_analysis"
    description = """AWS料金情報を取得・分析するツール。
    サービス名またはサービスコードとリージョンを指定して料金データを取得できます。
    例: get_pricing('EC2', 'us-east-1') または get_pricing('AmazonEC2', 'us-east-1')
    """
    
    def __init__(self):
        super().__init__()
        self.helper = AWSServiceCodeHelper()
    
    def _run(
        self, 
        service_name: str, 
        region: str = "us-east-1",
        use_filters: bool = False,
        filters: Optional[Dict] = None
    ) -> str:
        """料金データを取得"""
        
        # 1. サービスコードを取得
        service_code = self.helper.find_service_code(service_name)
        if not service_code:
            suggestions = self.helper.search_services(service_name[:5])
            return json.dumps({
                "error": f"Service code not found for: {service_name}",
                "suggestions": suggestions
            }, indent=2)
        
        # 2. リクエストを構築
        request = {
            "service_code": service_code,
            "region": region
        }
        
        if use_filters and filters:
            request["filters"] = filters
        
        # 3. MCPツールを呼び出し
        try:
            result = self._call_mcp_tool(
                "awslabs.cost-analysis-mcp-server:get_pricing_from_api",
                request
            )
            
            if result.get("status") == "success":
                return json.dumps({
                    "success": True,
                    "service_code": service_code,
                    "region": region,
                    "data_count": len(result.get("data", [])),
                    "message": result.get("message", ""),
                    "sample_data": result.get("data", [])[:3]  # 最初の3件のみ表示
                }, indent=2)
            else:
                return json.dumps({
                    "error": "Failed to retrieve pricing data",
                    "details": result
                }, indent=2)
                
        except Exception as e:
            return json.dumps({
                "error": f"MCP call failed: {str(e)}",
                "service_code": service_code,
                "region": region
            }, indent=2)
    
    def _call_mcp_tool(self, tool_name: str, params: Dict) -> Dict:
        """MCPツールを呼び出す（実装は環境に依存）"""
        # ここは実際のMCP呼び出し実装に置き換えてください
        # 例: return mcp_client.call_tool(tool_name, params)
        raise NotImplementedError("MCP client implementation required")

class ServiceCodeSearchTool(BaseTool):
    name = "aws_service_search"
    description = """AWSサービスのサービスコードを検索するツール。
    サービス名やキーワードから正しいサービスコードを見つけることができます。
    例: search_service('storage') または search_service('EC2')
    """
    
    def __init__(self):
        super().__init__()
        self.helper = AWSServiceCodeHelper()
    
    def _run(self, keyword: str) -> str:
        """サービスを検索"""
        
        # 1. 完全一致検索
        exact_match = self.helper.find_service_code(keyword)
        if exact_match:
            return json.dumps({
                "exact_match": {
                    "service_name": keyword,
                    "service_code": exact_match
                }
            }, indent=2)
        
        # 2. 部分一致検索
        results = self.helper.search_services(keyword)
        
        if results:
            return json.dumps({
                "search_results": results,
                "total_found": len(results)
            }, indent=2)
        else:
            return json.dumps({
                "message": f"No services found for keyword: {keyword}",
                "suggestion": "Try using broader keywords like 'compute', 'storage', 'database'"
            }, indent=2)
```

### 2. 安全な呼び出し関数

```python
def safe_cost_analysis(
    service_name: str, 
    region: str = "us-east-1",
    timeout: int = 30
) -> Dict[str, Any]:
    """安全にCost Analysis MCPを呼び出す"""
    
    helper = AWSServiceCodeHelper()
    
    # 入力値検証
    if not service_name or not service_name.strip():
        return {"error": "Service name is required"}
    
    if region not in VALID_REGIONS:
        return {
            "error": f"Invalid region: {region}",
            "valid_regions": VALID_REGIONS
        }
    
    # サービスコード取得
    service_code = helper.find_service_code(service_name.strip())
    if not service_code:
        suggestions = helper.search_services(service_name[:5])
        return {
            "error": f"Service code not found for: {service_name}",
            "suggestions": suggestions[:5]  # 上位5件のみ
        }
    
    # リクエスト構築
    request = {
        "service_code": service_code,
        "region": region
    }
    
    # タイムアウト付きMCP呼び出し
    try:
        result = call_mcp_with_timeout(
            "awslabs.cost-analysis-mcp-server:get_pricing_from_api",
            request,
            timeout=timeout
        )
        
        # レスポンス検証
        if isinstance(result, dict) and result.get("status") == "success":
            return {
                "success": True,
                "service_code": service_code,
                "region": region,
                "data": result.get("data", []),
                "message": result.get("message", "")
            }
        else:
            return {
                "error": "Failed to retrieve pricing data",
                "service_code": service_code,
                "details": result
            }
            
    except TimeoutError:
        return {
            "error": f"Request timed out after {timeout} seconds",
            "service_code": service_code
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "service_code": service_code
        }

def call_mcp_with_timeout(tool_name: str, params: Dict, timeout: int = 30):
    """タイムアウト付きでMCPツールを呼び出す"""
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("MCP call timed out")
    
    # タイムアウト設定
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        # 実際のMCP呼び出し（実装は環境に依存）
        result = your_mcp_client.call_tool(tool_name, params)
        return result
    finally:
        signal.alarm(0)  # タイムアウト解除
```

### 3. エージェント設定例

```python
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

# ツールを初期化
tools = [
    CostAnalysisTool(),
    ServiceCodeSearchTool()
]

# LLMを初期化
llm = OpenAI(temperature=0)

# エージェントを初期化
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    max_iterations=3
)

# 使用例
response = agent.run(
    "EC2 t3.microインスタンスの東京リージョンでの料金を調べてください"
)
print(response)
```

---

## トラブルシューティング

### よくある問題と解決策

#### 1. レスポンスが返らない

**症状:**
- MCPツール呼び出しが応答しない
- タイムアウトエラーが発生

**原因と対策:**

```python
# ❌ 避けるべきパターン
{
    "service_code": "EC2",      # 不正: 正しくは "AmazonEC2"
    "region": "tokyo"           # 不正: 正しくは "ap-northeast-1"
}

# ✅ 正しいパターン  
{
    "service_code": "AmazonEC2",
    "region": "ap-northeast-1"
}
```

#### 2. サービスコードが見つからない

**症状:**
- "Service code not found" エラー

**対策:**
```python
# サービスコード検索を活用
helper = AWSServiceCodeHelper()
suggestions = helper.search_services("storage")
print("候補サービス:", suggestions)

# 別名での検索も試行
aliases = ["EC2", "Amazon EC2", "Elastic Compute Cloud"]
for alias in aliases:
    code = helper.find_service_code(alias)
    if code:
        print(f"Found: {alias} -> {code}")
        break
```

#### 3. フィルターエラー

**症状:**
- フィルター指定時にエラーが発生

**対策:**
```python
# ❌ 間違ったフィルター構造
{
    "filters": {
        "instanceType": "t3.micro"  # 不正な構造
    }
}

# ✅ 正しいフィルター構造
{
    "filters": {
        "filters": [
            {
                "Field": "instanceType",
                "Value": "t3.micro", 
                "Type": "TERM_MATCH"
            }
        ]
    }
}
```

#### 4. タイムアウト問題

**対策:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError

async def async_cost_analysis(service_name: str, region: str, timeout: int = 30):
    """非同期でCost Analysis MCPを呼び出し"""
    
    loop = asyncio.get_event_loop()
    
    try:
        with ThreadPoolExecutor() as executor:
            future = loop.run_in_executor(
                executor,
                safe_cost_analysis,
                service_name,
                region
            )
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
    except asyncio.TimeoutError:
        return {"error": f"Request timed out after {timeout} seconds"}

# 使用例
result = await async_cost_analysis("EC2", "us-east-1", timeout=30)
```

### デバッグのためのチェックリスト

1. **サービスコード確認**
   ```python
   # サービスコードが正しいかチェック
   helper = AWSServiceCodeHelper()
   code = helper.find_service_code(service_name)
   print(f"Service code for {service_name}: {code}")
   ```

2. **リージョン確認**
   ```python
   # リージョンが有効かチェック
   if region not in VALID_REGIONS:
       print(f"Invalid region: {region}")
       print(f"Valid regions: {VALID_REGIONS}")
   ```

3. **リクエスト構造確認**
   ```python
   # リクエスト構造をログ出力
   import json
   print("Request structure:")
   print(json.dumps(request, indent=2))
   ```

4. **段階的テスト**
   ```python
   # 最もシンプルなリクエストから開始
   simple_request = {
       "service_code": "AmazonS3",
       "region": "us-east-1"
   }
   
   # 徐々に複雑なリクエストに移行
   complex_request = {
       "service_code": "AmazonEC2",
       "region": "us-east-1", 
       "filters": {
           "filters": [
               {
                   "Field": "tenancy",
                   "Value": "Shared",
                   "Type": "TERM_MATCH"
               }
           ]
       }
   }
   ```

---

## 実用的な使用例

### 1. 基本的な料金取得

```python
# EC2料金の取得
def get_ec2_pricing():
    result = safe_cost_analysis("EC2", "us-east-1")
    
    if result.get("success"):
        print(f"Found {len(result['data'])} pricing entries for EC2")
        return result['data']
    else:
        print(f"Error: {result.get('error')}")
        return None

# 使用例
ec2_pricing = get_ec2_pricing()
```

### 2. 複数サービスの料金比較

```python
def compare_service_pricing(services: list, region: str = "us-east-1"):
    """複数サービスの料金を比較"""
    
    results = {}
    
    for service in services:
        print(f"Getting pricing for {service}...")
        result = safe_cost_analysis(service, region)
        
        if result.get("success"):
            results[service] = {
                "service_code": result["service_code"],
                "data_count": len(result["data"]),
                "sample_pricing": result["data"][:3]
            }
        else:
            results[service] = {"error": result.get("error")}
    
    return results

# 使用例
services = ["EC2", "RDS", "S3", "Lambda"]
comparison = compare_service_pricing(services)

for service, data in comparison.items():
    if "error" in data:
        print(f"{service}: Error - {data['error']}")
    else:
        print(f"{service}: {data['data_count']} pricing entries found")
```

### 3. 特定インスタンスタイプの料金取得

```python
def get_specific_instance_pricing(instance_type: str, region: str = "us-east-1"):
    """特定のEC2インスタンスタイプの料金を取得"""
    
    filters = {
        "filters": [
            {
                "Field": "instanceType",
                "Value": instance_type,
                "Type": "TERM_MATCH"
            },
            {
                "Field": "tenancy", 
                "Value": "Shared",
                "Type": "TERM_MATCH"
            },
            {
                "Field": "operating-system",
                "Value": "Linux",
                "Type": "TERM_MATCH"
            }
        ]
    }
    
    # フィルター付きでリクエスト
    helper = AWSServiceCodeHelper()
    service_code = helper.find_service_code("EC2")
    
    request = {
        "service_code": service_code,
        "region": region,
        "filters": filters
    }
    
    try:
        result = call_mcp_tool(
            "awslabs.cost-analysis-mcp-server:get_pricing_from_api",
            request
        )
        return result
    except Exception as e:
        return {"error": str(e)}

# 使用例
t3_micro_pricing = get_specific_instance_pricing("t3.micro", "ap-northeast-1")
```

### 4. コスト分析レポートの生成

```python
def generate_comprehensive_report(service_name: str, region: str = "us-east-1"):
    """包括的なコスト分析レポートを生成"""
    
    # 1. 料金データを取得
    pricing_result = safe_cost_analysis(service_name, region)
    
    if not pricing_result.get("success"):
        return {"error": f"Failed to get pricing data: {pricing_result.get('error')}"}
    
    # 2. レポート生成用のパラメータを準備
    report_params = {
        "pricing_data": pricing_result,
        "service_name": service_name,
        "assumptions": [
            f"Pricing data from {region} region",
            "On-demand pricing model",
            "USD currency",
            "Standard usage patterns"
        ],
        "exclusions": [
            "Reserved instance discounts",
            "Spot instance pricing", 
            "Volume discounts",
            "Enterprise support costs"
        ],
        "pricing_model": "ON DEMAND",
        "related_services": get_related_services(service_name)
    }
    
    # 3. レポートを生成
    try:
        report = call_mcp_tool(
            "awslabs.cost-analysis-mcp-server:generate_cost_report",
            report_params
        )
        return report
    except Exception as e:
        return {"error": f"Failed to generate report: {str(e)}"}

def get_related_services(service_name: str) -> list:
    """関連サービスを取得"""
    related_map = {
        "EC2": ["EBS", "VPC", "ELB", "CloudWatch"],
        "RDS": ["EC2", "VPC", "CloudWatch", "S3"],
        "S3": ["CloudFront", "Lambda", "EC2"],
        "Lambda": ["S3", "API Gateway", "DynamoDB", "CloudWatch"],
        "DynamoDB": ["Lambda", "API Gateway", "CloudWatch"],
        "S3": ["CloudFront", "Lambda", "EC2", "Glacier"]
    }
    return related_map.get(service_name.upper(), [])

# 使用例
report = generate_comprehensive_report("EC2", "us-east-1")
if "error" not in report:
    print("Report generated successfully!")
else:
    print(f"Error: {report['error']}")
```

### 5. バッチ処理での料金データ収集

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_pricing_analysis(services_regions: list, max_workers: int = 3):
    """複数のサービス・リージョンの料金を並行取得"""
    
    def fetch_pricing(service, region):
        """単一のサービス・リージョンの料金を取得"""
        try:
            result = safe_cost_analysis(service, region)
            return {
                "service": service,
                "region": region, 
                "result": result,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "service": service,
                "region": region,
                "error": str(e),
                "timestamp": time.time()
            }
    
    results = []
    
    # 並行処理で料金データを取得
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # タスクを投入
        future_to_service = {
            executor.submit(fetch_pricing, service, region): (service, region)
            for service, region in services_regions
        }
        
        # 結果を収集
        for future in as_completed(future_to_service):
            service, region = future_to_service[future]
            try:
                result = future.result(timeout=60)
                results.append(result)
                print(f"✓ Completed: {service} in {region}")
            except Exception as e:
                results.append({
                    "service": service,
                    "region": region,
                    "error": str(e),
                    "timestamp": time.time()
                })
                print(f"✗ Failed: {service} in {region} - {e}")
            
            # API制限を考慮して少し待機
            time.sleep(0.5)
    
    return results

# 使用例
services_regions = [
    ("EC2", "us-east-1"),
    ("EC2", "ap-northeast-1"),
    ("RDS", "us-east-1"),
    ("S3", "us-east-1"),
    ("Lambda", "us-east-1")
]

batch_results = batch_pricing_analysis(services_regions)

# 結果の集計
success_count = sum(1 for r in batch_results if "error" not in r)
print(f"成功: {success_count}/{len(batch_results)}")
```

### 6. 料金データのキャッシュ機能

```python
import json
import os
from datetime import datetime, timedelta
from hashlib import md5

class PricingCache:
    """料金データのキャッシュクラス"""
    
    def __init__(self, cache_dir: str = "./pricing_cache", cache_duration: int = 24):
        self.cache_dir = cache_dir
        self.cache_duration = cache_duration  # hours
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, service_code: str, region: str) -> str:
        """キャッシュキーを生成"""
        key_string = f"{service_code}_{region}"
        return md5(key_string.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """キャッシュファイルパスを取得"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get_cached_data(self, service_code: str, region: str) -> dict:
        """キャッシュからデータを取得"""
        cache_key = self._get_cache_key(service_code, region)
        cache_path = self._get_cache_path(cache_key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # キャッシュの有効期限をチェック
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            expiry_time = cached_time + timedelta(hours=self.cache_duration)
            
            if datetime.now() > expiry_time:
                os.remove(cache_path)
                return None
            
            return cached_data['data']
            
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def save_to_cache(self, service_code: str, region: str, data: dict):
        """データをキャッシュに保存"""
        cache_key = self._get_cache_key(service_code, region)
        cache_path = self._get_cache_path(cache_key)
        
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "service_code": service_code,
            "region": region,
            "data": data
        }
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Cache write error: {e}")

def cached_cost_analysis(
    service_name: str, 
    region: str = "us-east-1",
    use_cache: bool = True
) -> dict:
    """キャッシュ機能付きのコスト分析"""
    
    helper = AWSServiceCodeHelper()
    cache = PricingCache()
    
    # サービスコードを取得
    service_code = helper.find_service_code(service_name)
    if not service_code:
        return {"error": f"Service code not found for: {service_name}"}
    
    # キャッシュをチェック
    if use_cache:
        cached_data = cache.get_cached_data(service_code, region)
        if cached_data:
            print(f"Using cached data for {service_code} in {region}")
            return {
                "success": True,
                "service_code": service_code,
                "region": region,
                "data": cached_data,
                "from_cache": True
            }
    
    # 新しいデータを取得
    print(f"Fetching fresh data for {service_code} in {region}")
    result = safe_cost_analysis(service_name, region)
    
    # 成功した場合はキャッシュに保存
    if result.get("success") and use_cache:
        cache.save_to_cache(service_code, region, result.get("data", []))
        result["from_cache"] = False
    
    return result

# 使用例
result = cached_cost_analysis("EC2", "us-east-1", use_cache=True)
if result.get("from_cache"):
    print("Data retrieved from cache")
else:
    print("Data retrieved from API")
```

---

## まとめ

### 重要なポイント

1. **正しいサービスコードの使用**
   - AWS Price List APIの正式なサービスコードを使用
   - サービス名の曖昧性を避けるため、AWSServiceCodeHelperクラスを活用

2. **適切なエラーハンドリング**
   - タイムアウト、ネットワークエラー、不正なパラメータに対する適切な処理
   - 段階的なフォールバック戦略

3. **パフォーマンス最適化**
   - キャッシュ機能の活用
   - 並行処理による効率的なデータ取得
   - API制限の考慮

4. **実用的な機能**
   - フィルター機能を使った詳細な料金検索
   - 複数サービス・リージョンの一括処理
   - 包括的なコスト分析レポート生成

### 推奨ワークフロー

1. **サービスコード確認** → `AWSServiceCodeHelper`でサービスコードを取得
2. **基本テスト** → 最もシンプルなリクエストでMCP接続を確認
3. **段階的拡張** → フィルターや複数サービスに徐々に拡張
4. **エラーハンドリング** → 本番環境向けの堅牢な実装
5. **最適化** → キャッシュ・並行処理の導入

### トラブル時のチェックポイント

- [ ] サービスコードが正しい（大文字小文字含む）
- [ ] リージョンが有効な値
- [ ] MCPサーバーが正常に動作している
- [ ] ネットワーク接続に問題がない
- [ ] タイムアウト設定が適切
- [ ] リクエスト構造が正しい

この ガイドに従って実装することで、LangChainエージェントからCost Analysis MCPツールを安全かつ効率的に利用できるようになります。