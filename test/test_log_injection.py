#!/usr/bin/env python3
"""
Log Injection脆弱性のテスト
"""
import sys
sys.path.append('..')

def test_log_injection():
    """Log Injection攻撃のテストケース"""
    
    # 危険なログ入力例
    malicious_inputs = [
        "Normal text",
        "Text with\nnewline",
        "Text with\r\nCRLF",
        "Fake log entry\n[ERROR] Fake error message",
        "User input\n[INFO] Admin logged in successfully",
        "Text\x00with\x00null\x00bytes",
        "Text with\ttab\tcharacters",
        "\x1b[31mRed text\x1b[0m",  # ANSI escape codes
    ]
    
    print("=== Log Injection脆弱性テスト ===")
    
    for input_text in malicious_inputs:
        print(f"\n入力: {repr(input_text)}")
        
        # 現在のログ出力（脆弱）
        print("脆弱なログ出力:")
        print(f"[INFO]: 翻訳中: {input_text}")
        
        # 安全なログ出力
        safe_text = sanitize_log_input(input_text)
        print("安全なログ出力:")
        print(f"[INFO]: 翻訳中: {safe_text}")

def sanitize_log_input(text):
    """ログ入力をサニタイズ"""
    if not isinstance(text, str):
        text = str(text)
    
    # 危険な文字を置換
    sanitized = (text
                .replace('\n', '\\n')
                .replace('\r', '\\r')
                .replace('\t', '\\t')
                .replace('\x00', '\\x00'))
    
    # ANSI エスケープシーケンスを除去
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    sanitized = ansi_escape.sub('', sanitized)
    
    # 長すぎる場合は切り詰め
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + "..."
    
    return sanitized

def test_logging_safety():
    """ログ出力の安全性テスト"""
    
    print("\n=== ログ安全性比較テスト ===")
    
    dangerous_log = "User: admin\nPassword: secret\n[ADMIN] Logged in"
    
    print("危険なログ:")
    print(f"[INFO] {dangerous_log}")
    
    print("\n安全なログ:")
    safe_log = sanitize_log_input(dangerous_log)
    print(f"[INFO] {safe_log}")

if __name__ == "__main__":
    test_log_injection()
    test_logging_safety()