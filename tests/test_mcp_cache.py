"""
MCPリクエストキャッシュのテスト
"""

import unittest
import time
import sys
import os

# テスト対象モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from services.mcp_client import MCPRequestCache
except ImportError:
    # Streamlit依存関係を回避するため、テストをスキップ
    MCPRequestCache = None


class TestMCPRequestCache(unittest.TestCase):
    """MCPリクエストキャッシュのテスト"""

    def setUp(self):
        """テストセットアップ"""
        if MCPRequestCache is None:
            self.skipTest("Streamlit依存関係のため、単体テスト環境では実行できません")
        
        self.cache = MCPRequestCache(default_ttl=1)  # 1秒のTTLでテスト
        
    def test_cache_key_generation(self):
        """キャッシュキー生成のテスト"""
        # 同じパラメータで同じキーが生成されることを確認
        key1 = self.cache._generate_cache_key("test_method", "arg1", param="value")
        key2 = self.cache._generate_cache_key("test_method", "arg1", param="value")
        self.assertEqual(key1, key2)
        
        # 異なるパラメータで異なるキーが生成されることを確認
        key3 = self.cache._generate_cache_key("test_method", "arg2", param="value")
        self.assertNotEqual(key1, key3)
        
        # キーが文字列であることを確認
        self.assertIsInstance(key1, str)
        self.assertGreater(len(key1), 10)  # 妥当な長さのハッシュ

    def test_cache_set_and_get(self):
        """キャッシュの保存と取得のテスト"""
        # キャッシュミス
        result = self.cache.get("test_method", "query")
        self.assertIsNone(result)
        
        # キャッシュ保存
        test_value = {"test": "data"}
        self.cache.set("test_method", test_value, None, "query")
        
        # キャッシュヒット
        cached_result = self.cache.get("test_method", "query")
        self.assertEqual(cached_result, test_value)

    def test_cache_ttl_expiration(self):
        """TTL期限切れのテスト"""
        # 短いTTLでキャッシュ保存
        test_value = "test_data"
        self.cache.set("test_method", test_value, 0.1, "query")  # 0.1秒TTL
        
        # 即座にアクセス - ヒットするはず
        result = self.cache.get("test_method", "query")
        self.assertEqual(result, test_value)
        
        # TTL期限切れ後にアクセス - ミスするはず
        time.sleep(0.2)
        expired_result = self.cache.get("test_method", "query")
        self.assertIsNone(expired_result)

    def test_cache_stats(self):
        """キャッシュ統計のテスト"""
        # 初期統計
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["total_requests"], 0)
        
        # キャッシュミス
        self.cache.get("test_method", "query")
        stats = self.cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["total_requests"], 1)
        
        # キャッシュ保存とヒット
        self.cache.set("test_method", "value", None, "query")
        self.cache.get("test_method", "query")
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["total_requests"], 2)
        
        # ヒット率計算
        self.assertEqual(stats["hit_rate"], 50.0)

    def test_cache_clear(self):
        """キャッシュクリアのテスト"""
        # キャッシュに値を保存
        self.cache.set("test_method", "value", None, "query")
        
        # キャッシュされていることを確認
        result = self.cache.get("test_method", "query")
        self.assertEqual(result, "value")
        
        # キャッシュクリア
        self.cache.clear()
        
        # キャッシュがクリアされていることを確認
        result = self.cache.get("test_method", "query")
        self.assertIsNone(result)
        
        # 統計もリセットされていることを確認
        stats = self.cache.get_stats()
        self.assertEqual(stats["cache_size"], 0)

    def test_different_method_names(self):
        """異なるメソッド名でのキャッシュ分離テスト"""
        # 同じパラメータでも異なるメソッド名では別キャッシュ
        self.cache.set("method1", "value1", None, "query")
        self.cache.set("method2", "value2", None, "query")
        
        result1 = self.cache.get("method1", "query")
        result2 = self.cache.get("method2", "query")
        
        self.assertEqual(result1, "value1")
        self.assertEqual(result2, "value2")
        self.assertNotEqual(result1, result2)


class TestMCPCacheIntegration(unittest.TestCase):
    """MCPキャッシュ統合のテスト"""

    def test_cache_parameter_normalization(self):
        """キャッシュパラメータ正規化のテスト"""
        if MCPRequestCache is None:
            self.skipTest("Streamlit依存関係のため、単体テスト環境では実行できません")
            
        cache = MCPRequestCache()
        
        # 同じ辞書パラメータでも順序が異なる場合のテスト
        key1 = cache._generate_cache_key("test", param1="a", param2="b")
        key2 = cache._generate_cache_key("test", param2="b", param1="a")
        
        # 辞書は内部でソートされるため、同じキーになるはず
        self.assertEqual(key1, key2)


if __name__ == '__main__':
    # テスト実行設定
    unittest.main(verbosity=2)