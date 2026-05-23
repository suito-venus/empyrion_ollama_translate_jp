import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def validate_tags(text: str, line_no: Optional[int] = None) -> list[str]:
    """翻訳テキストのタグ対応をチェック"""
    errors = []

    # 検証するタグパターン（ブラケット形式）
    tag_patterns = [
        (r'\[u\]', r'\[/u\]', 'underline'),
        (r'\[i\]', r'\[/i\]', 'italic'),
        (r'\[b\]', r'\[/b\]', 'bold'),
        (r'\[sup\]', r'\[/sup\]', 'sup'),
        (r'\[c\]\[[0-9A-Fa-f]{6}\]', r'\[-\]\[/c\]', 'color'),
        (r'<size=\d+>', r'</size>', 'size')
    ]

    for start_pattern, end_pattern, tag_name in tag_patterns:
        start_matches = list(re.finditer(start_pattern, text))
        end_matches = list(re.finditer(end_pattern, text))

        start_count = len(start_matches)
        end_count = len(end_matches)

        if start_count != end_count:
            line_info = f"行{line_no}: " if line_no else ""
            errors.append(
                f"{line_info}{tag_name}タグの開始({start_count})と"
                f"終了({end_count})の数が一致しません"
            )

        # ネストチェック（簡易版）
        if start_count > 0 and end_count > 0:
            positions = []
            for match in start_matches:
                positions.append((match.start(), 'start', tag_name))
            for match in end_matches:
                positions.append((match.start(), 'end', tag_name))

            positions.sort()
            stack = []

            for pos, tag_type, name in positions:
                if tag_type == 'start':
                    stack.append(name)
                elif tag_type == 'end':
                    if not stack or stack[-1] != name:
                        line_info = f"行{line_no}: " if line_no else ""
                        errors.append(
                            f"{line_info}{name}タグの対応が正しくありません"
                        )
                    else:
                        stack.pop()

    # HTMLタグのチェック
    html_errors = validate_html_tags(text, line_no)
    errors.extend(html_errors)

    return errors


def validate_html_tags(text: str, line_no: Optional[int] = None) -> list[str]:
    """HTMLタグ(<b>, <i>, <color=...>)の構文と対応をチェック"""
    errors = []
    line_info = f"行{line_no}: " if line_no else ""

    # 壊れたタグの検出: < の後にタグ名があるが > で閉じられていないパターン
    # 例: <b が > なしで次の文字が来る、<color=#ffffff が > なしで来る
    broken_tag_pattern = r'<(/?(?:b|i|u|color(?:=[^>]*)?|size(?:=[^>]*)?))\b(?!>)(?![^<]*>)'
    broken_matches = re.finditer(broken_tag_pattern, text)
    for match in broken_matches:
        # マッチした位置の後に > があるか確認
        after_match = text[match.end():]
        # タグの閉じ > が次の < より前にあるか確認
        next_lt = after_match.find('<')
        next_gt = after_match.find('>')
        if next_gt == -1 or (next_lt != -1 and next_lt < next_gt):
            errors.append(
                f"{line_info}壊れたHTMLタグを検出: '{match.group()}' "
                f"(位置{match.start()}) - '>'が欠落しています"
            )

    # HTMLタグの開始/終了数の一致チェック
    html_tag_pairs = [
        (r'<b>', r'</b>', 'HTML bold (<b>)'),
        (r'<i>', r'</i>', 'HTML italic (<i>)'),
        (r'<u>', r'</u>', 'HTML underline (<u>)'),
        (r'<color=#[A-Fa-f0-9]{6}>', r'</color>', 'HTML color (<color>)'),
        (r'<size=\d+>', r'</size>', 'HTML size (<size>)'),
    ]

    for start_pattern, end_pattern, tag_name in html_tag_pairs:
        start_count = len(re.findall(start_pattern, text))
        end_count = len(re.findall(end_pattern, text))

        if start_count != end_count:
            errors.append(
                f"{line_info}{tag_name}の開始({start_count})と"
                f"終了({end_count})の数が一致しません"
            )

    return errors


def check_translation_tags(text: str, line_no: Optional[int] = None):
    """翻訳結果のタグをチェックしてWARNINGを出力"""
    errors = validate_tags(text, line_no)

    for error in errors:
        logger.warning(f"タグ検証: {error}")
        logger.warning(f"対象テキスト: {text.strip()[:100]}...")

    return len(errors) == 0


if __name__ == "__main__":
    # テスト用
    test_cases = [
        "[u]下線テキスト[/u]",  # 正常
        "[u]下線テキスト",  # 終了タグなし
        "[i]イタリック[/i] [b]太字[/b]",  # 正常
        "[c][FF0000]赤色テキスト[-][/c]",  # 正常
        "[c][FF0000]赤色テキスト[/c]",  # 終了タグ不正
        "<size=14>大きな文字</size>",  # 正常
        "<size=14>大きな文字",  # 終了タグなし
        "<b>太字テスト</b>",  # 正常
        "<b太字テスト</b>",  # 壊れたタグ（>が欠落）
        "<b><color=#ffffff>テスト</color></b>",  # 正常
        "<b<color=#ffffff>テスト</color></b>",  # 壊れたタグ
        "<b>テスト1</b><b>テスト2",  # 開始2、終了1で不一致
        "<color=#ffffff>テスト</color> <color=#00fbff>テスト2",  # color終了タグ不足
    ]

    logging.basicConfig(level=logging.WARNING,
                        format='[%(levelname)s]: %(message)s')

    for i, test in enumerate(test_cases, 1):
        print(f"\nテスト{i}: {test}")
        result = check_translation_tags(test, i)
        print(f"  結果: {'OK' if result else 'NG'}")
