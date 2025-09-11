import re
import logging

logger = logging.getLogger(__name__)


def format_punctuation(text: str, line_no: int) -> str:
    """句読点の後に半角空白を追加する整形処理"""

    # original_text = text

    # ".", ",", ":" の後に半角空白を追加
    # 連続する場合や既に空白がある場合は除外
    # 桁区切りのカンマ（数字に囲まれた場合）は除外
    patterns = [
        (r'\.(?![\.\s])', '. '),  # . の後が . や空白でない場合
        (r'(?<!\d),(?!\d)(?![\,\s])', ', '),   # 桁区切りでない , の後が , や空白でない場合
        (r':(?![\:\s])', ': ')    # : の後が : や空白でない場合
    ]

    formatted_text = text
    changes_made = 0

    for pattern, replacement in patterns:
        new_text = re.sub(pattern, replacement, formatted_text)
        if new_text != formatted_text:
            changes_made += len(re.findall(pattern, formatted_text))
            formatted_text = new_text

    if changes_made > 0:
        line_info = f"行{line_no}: " if line_no else ""
        logger.info(f"句読点整形: {line_info}{changes_made}箇所に半角空白を追加")

    return formatted_text


if __name__ == "__main__":
    # テスト用
    test_cases = [
        "これはテスト.次の文章です,そして:最後です.",
        "連続する...場合や::場合はそのまま.",
        "既に空白がある. 場合や, 場合: 場合はそのまま.",
        "価格は1,000円,重量は2,500kgです.",
        "通常のテキスト",
    ]

    logging.basicConfig(level=logging.INFO, format='[%(levelname)s]: %(message)s')

    for i, test in enumerate(test_cases, 1):
        print(f"\nテスト{i}: {test}")
        result = format_punctuation(test, i)
        print(f"結果: {result}")
