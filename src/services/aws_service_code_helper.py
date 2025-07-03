"""
AWSサービスコードヘルパークラス

AWS Price List APIから正しいサービスコードを取得・管理するためのヘルパークラス。
Cost Analysis MCPとの統合において適切なサービスコードを使用するために必要。
"""

import requests
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class AWSServiceCodeHelper:
    """AWSサービスコードの取得と検索を行うヘルパークラス"""
    
    def __init__(self, cache_duration: int = 24):
        """
        初期化
        
        Args:
            cache_duration: キャッシュの有効期間（時間）
        """
        self.service_codes = None
        self.cache_duration = cache_duration
        self.last_updated = None
        self.logger = logging.getLogger(__name__)
        self._load_service_codes()
    
    def _load_service_codes(self):
        """AWS Price List APIからサービスコードを取得"""
        try:
            # キャッシュの有効性をチェック
            if self._is_cache_valid():
                self.logger.debug("Service codes cache is still valid")
                return
                
            self.logger.info("Loading AWS service codes from Price List API...")
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
            
            self.last_updated = datetime.now()
            self.logger.info(f"Loaded {len(self.service_codes)} AWS service codes")
                    
        except Exception as e:
            self.logger.warning(f"Failed to load service codes from API: {e}")
            # フォールバック用の主要サービスコード
            self._load_fallback_codes()
    
    def _is_cache_valid(self) -> bool:
        """キャッシュが有効かチェック"""
        if not self.last_updated or not self.service_codes:
            return False
            
        expiry_time = self.last_updated + timedelta(hours=self.cache_duration)
        return datetime.now() < expiry_time
    
    def _load_fallback_codes(self):
        """フォールバック用の主要サービスコード"""
        self.service_codes = {
            # コンピューティング
            "amazon ec2": "AmazonEC2",
            "aws lambda": "AWSLambda",
            "amazon lightsail": "AmazonLightsail",
            "amazon ecs": "AmazonECS",
            "amazon eks": "AmazonEKS",
            
            # ストレージ
            "amazon s3": "AmazonS3",
            "amazon efs": "AmazonEFS",
            "amazon fsx": "AmazonFSx",
            
            # データベース
            "amazon rds": "AmazonRDS",
            "amazon dynamodb": "AmazonDynamoDB",
            "amazon redshift": "AmazonRedshift",
            "amazon elasticache": "AmazonElastiCache",
            
            # AI・機械学習
            "amazon bedrock": "AmazonBedrock",
            "amazon sagemaker": "AmazonSageMaker",
            "amazon rekognition": "AmazonRekognition",
            "amazon comprehend": "AmazonComprehend",
            
            # ネットワーキング
            "amazon cloudfront": "AmazonCloudFront",
            "amazon route 53": "AmazonRoute53",
            "amazon vpc": "AmazonVPC",
            "elastic load balancing": "AWSELB",
            
            # その他の主要サービス
            "amazon sns": "AmazonSNS",
            "amazon sqs": "AmazonSQS",
            "amazon cloudwatch": "AmazonCloudWatch",
            "aws iam": "AmazonIdentityManagement",
            "aws config": "AWSConfig",
            "aws cloudtrail": "AWSCloudTrail"
        }
        
        self.last_updated = datetime.now()
        self.logger.info(f"Loaded {len(self.service_codes)} fallback service codes")
    
    def find_service_code(self, service_name: str) -> Optional[str]:
        """
        サービス名からサービスコードを検索
        
        Args:
            service_name: 検索するサービス名
            
        Returns:
            サービスコード、見つからない場合はNone
        """
        if not self.service_codes:
            self._load_service_codes()
            
        if not self.service_codes:
            return None
            
        service_name = service_name.lower().strip()
        
        # 完全一致チェック
        if service_name in self.service_codes:
            return self.service_codes[service_name]
        
        # 部分一致チェック（双方向）
        for name, code in self.service_codes.items():
            if service_name in name or name in service_name:
                return code
        
        # 別名・略称チェック
        aliases = self._get_service_aliases()
        normalized_name = aliases.get(service_name)
        if normalized_name and normalized_name in self.service_codes:
            return self.service_codes[normalized_name]
        
        return None
    
    def _get_service_aliases(self) -> Dict[str, str]:
        """サービスの別名・略称マッピング"""
        return {
            # コンピューティング
            "ec2": "amazon ec2",
            "lambda": "aws lambda",
            "lightsail": "amazon lightsail",
            "ecs": "amazon ecs",
            "eks": "amazon eks",
            "fargate": "amazon ecs",  # Fargateは実際にはECSの一部
            
            # ストレージ
            "s3": "amazon s3",
            "simple storage service": "amazon s3",
            "efs": "amazon efs",
            "fsx": "amazon fsx",
            "ebs": "amazon ec2",  # EBSはEC2サービスに含まれる
            "elastic block store": "amazon ec2",
            
            # データベース
            "rds": "amazon rds",
            "relational database service": "amazon rds",
            "dynamo": "amazon dynamodb",
            "dynamodb": "amazon dynamodb",
            "redshift": "amazon redshift",
            "elasticache": "amazon elasticache",
            
            # AI・機械学習
            "bedrock": "amazon bedrock",
            "sagemaker": "amazon sagemaker",
            "rekognition": "amazon rekognition",
            "comprehend": "amazon comprehend",
            
            # ネットワーキング
            "cloudfront": "amazon cloudfront",
            "cdn": "amazon cloudfront",
            "route53": "amazon route 53",
            "route 53": "amazon route 53",
            "dns": "amazon route 53",
            "vpc": "amazon vpc",
            "elb": "elastic load balancing",
            "load balancer": "elastic load balancing",
            "alb": "elastic load balancing",
            "nlb": "elastic load balancing",
            
            # その他
            "sns": "amazon sns",
            "sqs": "amazon sqs",
            "cloudwatch": "amazon cloudwatch",
            "iam": "aws iam",
            "config": "aws config",
            "cloudtrail": "aws cloudtrail"
        }
    
    def search_services(self, keyword: str) -> List[Dict[str, str]]:
        """
        キーワードでサービスを検索
        
        Args:
            keyword: 検索キーワード
            
        Returns:
            検索結果のリスト
        """
        if not self.service_codes:
            self._load_service_codes()
            
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
        """
        全サービスの一覧を取得
        
        Returns:
            サービス名をキー、サービスコードを値とする辞書
        """
        if not self.service_codes:
            self._load_service_codes()
            
        return dict(self.service_codes) if self.service_codes else {}
    
    def refresh_service_codes(self) -> bool:
        """
        サービスコードを強制的に再取得
        
        Returns:
            成功した場合True
        """
        self.last_updated = None
        self.service_codes = None
        
        try:
            self._load_service_codes()
            return self.service_codes is not None
        except Exception as e:
            self.logger.error(f"Failed to refresh service codes: {e}")
            return False
    
    def get_service_info(self, service_name: str) -> Optional[Dict[str, str]]:
        """
        サービスの詳細情報を取得
        
        Args:
            service_name: サービス名
            
        Returns:
            サービス情報の辞書
        """
        service_code = self.find_service_code(service_name)
        if not service_code:
            return None
            
        # サービス名を正規化して取得
        normalized_name = None
        for name, code in self.service_codes.items():
            if code == service_code:
                normalized_name = name.title()
                break
        
        return {
            "service_name": normalized_name or service_name.title(),
            "service_code": service_code,
            "search_term": service_name
        }
    
    def validate_service_code(self, service_code: str) -> bool:
        """
        サービスコードが有効かチェック
        
        Args:
            service_code: チェックするサービスコード
            
        Returns:
            有効な場合True
        """
        if not self.service_codes:
            self._load_service_codes()
            
        if not self.service_codes:
            return False
            
        return service_code in self.service_codes.values()


# グローバルインスタンス（シングルトンパターン）
_service_code_helper = None

def get_service_code_helper() -> AWSServiceCodeHelper:
    """
    AWSServiceCodeHelperのグローバルインスタンスを取得
    
    Returns:
        AWSServiceCodeHelperのインスタンス
    """
    global _service_code_helper
    if _service_code_helper is None:
        _service_code_helper = AWSServiceCodeHelper()
    return _service_code_helper


# 便利関数
def find_aws_service_code(service_name: str) -> Optional[str]:
    """
    サービス名からAWSサービスコードを検索する便利関数
    
    Args:
        service_name: 検索するサービス名
        
    Returns:
        サービスコード、見つからない場合はNone
    """
    helper = get_service_code_helper()
    return helper.find_service_code(service_name)


def search_aws_services(keyword: str) -> List[Dict[str, str]]:
    """
    キーワードでAWSサービスを検索する便利関数
    
    Args:
        keyword: 検索キーワード
        
    Returns:
        検索結果のリスト
    """
    helper = get_service_code_helper()
    return helper.search_services(keyword)