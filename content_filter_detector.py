import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def detect_content_filter(text: str, line_no: Optional[int] = None) -> bool:
    """コンテンツフィルタに引っかかった出力を検出"""

    # コンテンツフィルタのパターン
    filter_patterns = [
        r"The generated text has been blocked by our content filters",
        r"I cannot provide",
        r"I'm not able to",
        r"I can't assist with",
        r"content policy",
        r"safety guidelines",
        r"inappropriate content",
        r"blocked.*content.*filter",
        r"violates.*policy"
    ]

    text_lower = text.lower()

    for pattern in filter_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            line_info = f"行{line_no}: " if line_no else ""
            logger.warning(
                f"コンテンツフィルタ検出: {line_info}翻訳がブロックされました"
            )
            logger.warning(f"検出パターン: {pattern}")
            logger.warning(f"対象テキスト: {text.strip()}")
            return True

    return False


if __name__ == "__main__":
    # テスト用
    test_cases = [
        "This is normal text",  # 正常
        "The generated text has been blocked by our content filters.",  # フィルタ
        "I cannot provide that information",  # フィルタ
        "Hello world",  # 正常
        "This violates our policy",  # フィルタ
    ]

    logging.basicConfig(level=logging.WARNING,
                        format='[%(levelname)s]: %(message)s')

    for i, test in enumerate(test_cases, 1):
        print(f"\nテスト{i}: {test}")
        detect_content_filter(test, i)
