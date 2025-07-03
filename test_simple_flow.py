#!/usr/bin/env python3
"""
サービスコード変換の基本機能テスト（Streamlit依存なし）
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from src.services.aws_service_code_helper import get_service_code_helper

def test_service_code_helper():
    """AWSServiceCodeHelperの基本機能テスト"""
    print('=== AWSServiceCodeHelper テスト ===')
    
    # ログレベルを設定
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # ヘルパーインスタンス取得
        print('1. ヘルパーインスタンス取得...')
        helper = get_service_code_helper()
        print(f'   ✅ 成功: {type(helper).__name__}')
        
        # サービスコード辞書の確認
        print('2. サービスコード辞書の確認...')
        if helper.service_codes:
            print(f'   ✅ 辞書サイズ: {len(helper.service_codes)}')
            
            # 最初の5つのサービスコードを表示
            sample_items = list(helper.service_codes.items())[:5]
            print('   サンプルサービスコード:')
            for name, code in sample_items:
                print(f'     {name} -> {code}')
        else:
            print('   ❌ サービスコード辞書が空です')
            return False
        
        # サービスコード変換テスト
        print('3. サービスコード変換テスト...')
        test_services = [
            "EC2", "S3", "RDS", "Lambda", "DynamoDB",
            "ec2", "s3", "amazon ec2", "aws lambda"
        ]
        
        successful_conversions = 0
        for service in test_services:
            code = helper.find_service_code(service)
            if code:
                print(f'   ✅ {service} -> {code}')
                successful_conversions += 1
            else:
                print(f'   ❌ {service} -> 見つからず')
        
        print(f'   変換成功率: {successful_conversions}/{len(test_services)} ({(successful_conversions/len(test_services)*100):.1f}%)')
        
        # サービス検索テスト
        print('4. サービス検索テスト...')
        search_results = helper.search_services("ec2")
        print(f'   "ec2"の検索結果: {len(search_results)}件')
        for result in search_results[:3]:  # 最初の3件を表示
            print(f'     {result["service_name"]} ({result["service_code"]})')
        
        return True
        
    except Exception as e:
        print(f'❌ エラー: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_service_code_mapping():
    """特定のサービスコードマッピングをテスト"""
    print('\n=== サービスコードマッピング詳細テスト ===')
    
    # 重要なサービスの変換確認
    critical_services = {
        "EC2": "AmazonEC2",
        "S3": "AmazonS3", 
        "RDS": "AmazonRDS",
        "Lambda": "AWSLambda",
        "DynamoDB": "AmazonDynamoDB"
    }
    
    helper = get_service_code_helper()
    all_correct = True
    
    for service_name, expected_code in critical_services.items():
        actual_code = helper.find_service_code(service_name)
        if actual_code == expected_code:
            print(f'   ✅ {service_name}: {actual_code} (正解)')
        else:
            print(f'   ❌ {service_name}: {actual_code} (期待値: {expected_code})')
            all_correct = False
    
    return all_correct

def main():
    print('サービスコード変換フロー検証テスト開始\n')
    
    # 基本機能テスト
    basic_test_passed = test_service_code_helper()
    
    # マッピングテスト
    mapping_test_passed = test_service_code_mapping()
    
    # 結果サマリ
    print('\n=== テスト結果サマリ ===')
    print(f'基本機能テスト: {"✅ 成功" if basic_test_passed else "❌ 失敗"}')
    print(f'マッピングテスト: {"✅ 成功" if mapping_test_passed else "❌ 失敗"}')
    
    if basic_test_passed and mapping_test_passed:
        print('\n🎉 全テスト成功! サービスコード変換機能は正常に動作しています。')
        return 0
    else:
        print('\n⚠️  一部テストに失敗しました。')
        return 1

if __name__ == "__main__":
    exit(main())