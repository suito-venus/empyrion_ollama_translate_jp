#!/usr/bin/env python3
"""
全セキュリティテストの実行
"""
import subprocess
import sys

def run_test(test_file):
    """個別テストを実行"""
    print(f"\n{'='*60}")
    print(f"実行中: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, cwd='test')
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"エラー: {e}")
        return False

def main():
    """全テストを実行"""
    print("セキュリティ脆弱性テストスイート")
    print("修正前の現在の動作を確認します")
    
    tests = [
        "test_path_traversal.py",
        "test_log_injection.py", 
        "test_xss_vulnerability.py"
    ]
    
    results = {}
    
    for test in tests:
        success = run_test(test)
        results[test] = success
    
    print(f"\n{'='*60}")
    print("テスト結果サマリー")
    print('='*60)
    
    for test, success in results.items():
        status = "✅ 完了" if success else "❌ エラー"
        print(f"{test:25} {status}")
    
    print(f"\n修正前の脆弱性確認が完了しました。")
    print("次に各モジュールのセキュリティ修正を行ってください。")

if __name__ == "__main__":
    main()