#!/usr/bin/env python3
"""
Celery + FastAPI 統合テストスクリプト
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_health_check():
    """ヘルスチェック"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health Check失敗: {e}")
        return False

def test_celery_status():
    """Celery状態確認"""
    try:
        response = requests.get(f"{BASE_URL}/api/celery/status")
        print(f"Celery Status: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Celery状態確認失敗: {e}")
        return False

def test_openapi_schema():
    """OpenAPI スキーマ取得"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        print(f"OpenAPI Docs: {response.status_code}")
        
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            schema = response.json()
            print(f"OpenAPI Schema取得成功:")
            print(f"  - title: {schema.get('info', {}).get('title')}")
            print(f"  - version: {schema.get('info', {}).get('version')}")
            print(f"  - endpoints: {len(schema.get('paths', {}))}")
            return True
    except Exception as e:
        print(f"OpenAPI Schema取得失敗: {e}")
        return False

def test_redis_connection():
    """Redis接続テスト"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("Redis接続成功")
        return True
    except Exception as e:
        print(f"Redis接続失敗: {e}")
        return False

def main():
    print("=== Celery + FastAPI 統合テスト ===")
    
    tests = [
        ("Health Check", test_health_check),
        ("Redis接続", test_redis_connection),
        ("Celery状態", test_celery_status),
        ("OpenAPI Schema", test_openapi_schema),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n=== テスト結果 ===")
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print(f"\n全体結果: {'✅ 全てPASS' if all_passed else '❌ 一部FAIL'}")

if __name__ == "__main__":
    main()