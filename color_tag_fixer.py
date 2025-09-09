import re
import logging

logger = logging.getLogger(__name__)


def fix_color_tags(text: str, line_no: int = None) -> str:
    """カラータグの終了を [-][/c] に修正"""
    
    # [c][HHHHHH] で始まるカラータグを検出
    color_start_pattern = r'\[c\]\[[0-9A-Fa-f]{6}\]'
    
    # [/c] で終わるが [-][/c] ではない箇所を検出
    incorrect_end_pattern = r'(?<!\[-\])\[/c\]'
    
    original_text = text
    
    # カラータグの開始数をカウント
    color_starts = len(re.findall(color_start_pattern, text))
    
    # 正しい終了タグ [-][/c] の数をカウント
    correct_ends = len(re.findall(r'\[-\]\[/c\]', text))
    
    # 不正な終了タグ [/c] ([-][/c]ではない) の数をカウント
    incorrect_ends = len(re.findall(incorrect_end_pattern, text))
    
    if color_starts > correct_ends and incorrect_ends > 0:
        # 不正な [/c] を [-][/c] に置換
        fixed_text = re.sub(incorrect_end_pattern, '[-][/c]', text)
        
        line_info = f"行{line_no}: " if line_no else ""
        logger.info(f"カラータグ修正: {line_info}[/c] → [-][/c] を {incorrect_ends}箇所修正")
        
        return fixed_text
    
    return text


if __name__ == "__main__":
    # テスト用
    test_cases = [
        "[c][FF0000]赤いテキスト[/c]",  # 修正対象
        "[c][00FF00]緑のテキスト[-][/c]",  # 正常
        "[c][0000FF]青いテキスト[/c] と [c][FFFF00]黄色[/c]",  # 複数修正対象
        "通常のテキスト",  # 修正不要
    ]
    
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s]: %(message)s')
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nテスト{i}: {test}")
        result = fix_color_tags(test, i)
        print(f"結果: {result}")