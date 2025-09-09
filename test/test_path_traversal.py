#!/usr/bin/env python3
"""
Path Traversal脆弱性のテスト
"""
import os
import sys
sys.path.append('..')

def test_path_traversal():
    """Path Traversal攻撃のテストケース"""
    
    # 危険なパス例
    dangerous_paths = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\SAM",
        "test/../../../etc/passwd",
        "normal_file.txt/../../../etc/passwd"
    ]
    
    print("=== Path Traversal脆弱性テスト ===")
    
    for path in dangerous_paths:
        print(f"\n危険なパス: {path}")
        
        # 現在のコードでの動作確認
        try:
            # ollama_translate.pyの処理を模擬
            resolved_path = os.path.abspath(path)
            print(f"  解決されたパス: {resolved_path}")
            
            # ファイルが存在するかチェック
            if os.path.exists(resolved_path):
                print(f"  ⚠️  ファイルが存在します: {resolved_path}")
            else:
                print(f"  ✅ ファイルは存在しません")
                
        except Exception as e:
            print(f"  エラー: {e}")

def test_safe_path_validation():
    """安全なパス検証のテスト"""
    
    print("\n=== 安全なパス検証テスト ===")
    
    def is_safe_path(path, base_dir="."):
        """安全なパスかどうかチェック"""
        try:
            # 絶対パスに変換
            abs_path = os.path.abspath(path)
            abs_base = os.path.abspath(base_dir)
            
            # ベースディレクトリ内かチェック
            return abs_path.startswith(abs_base + os.sep) or abs_path == abs_base
        except:
            return False
    
    test_paths = [
        "test.txt",
        "./test.txt", 
        "../test.txt",
        "../../etc/passwd",
        "/etc/passwd"
    ]
    
    for path in test_paths:
        safe = is_safe_path(path)
        print(f"パス: {path:20} -> {'✅ 安全' if safe else '❌ 危険'}")

if __name__ == "__main__":
    test_path_traversal()
    test_safe_path_validation()