import re
import argparse
from typing import List

def parse_game_text(text: str) -> str:
    """ゲーム内ルールに従ってテキストを解析・表示"""

    # HTMLエスケープ
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 1. 下線装飾 [u]...[/u]
    text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text)

    # 2. イタリック装飾 [i]...[/i]
    text = re.sub(r'\[i\](.*?)\[/i\]', r'<i>\1</i>', text)

    # 3. 太字装飾 [b]...[/b]
    text = re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text)

    # 3.5. 上付き文字（60%サイズ） [sup]...[/sup]
    text = re.sub(r'\[sup\](.*?)\[/sup\]', r'<span style="font-size: 0.6em;">\1</span>', text)

    # 4. 改行コード \n
    text = text.replace('\\n', '<br>')

    # 8. カラーコード [c][HHHHHH]...[-][/c]
    def color_replace(match):
        color = match.group(1)
        content = match.group(2)
        return f'<span style="color: #{color};">{content}</span>'

    text = re.sub(r'\[c\]\[([0-9A-Fa-f]{6})\](.*?)\[-\]\[/c\]', color_replace, text)

    # 9. フォントサイズ <size=NN>...</size>
    def size_replace(match):
        size = match.group(1)
        content = match.group(2)
        return f'<span style="font-size: {size}px;">{content}</span>'

    text = re.sub(r'<size=(\d+)>(.*?)</size>', size_replace, text)

    return text

def generate_html_preview(lines: List[str], output_file: str):
    """HTMLプレビューファイルを生成"""

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Empyrion翻訳プレビュー</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1a1a1a;
            color: #ffffff;
            margin: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .line {{
            background-color: #2d2d2d;
            border: 1px solid #444;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
            position: relative;
        }}
        .line-number {{
            position: absolute;
            top: 5px;
            right: 10px;
            background-color: #444;
            color: #ccc;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
        }}
        .text-content {{
            margin-right: 60px;
        }}
        h1 {{
            color: #4CAF50;
            text-align: center;
        }}
        .stats {{
            background-color: #333;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Empyrion翻訳プレビュー</h1>
        <div class="stats">
            <strong>総行数:</strong> {len(lines)}行
        </div>
"""

    for i, line in enumerate(lines, 1):
        parsed_line = parse_game_text(line.strip())
        html_content += f"""
        <div class="line">
            <div class="line-number">{i}</div>
            <div class="text-content">{parsed_line}</div>
        </div>
"""

    html_content += """
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="翻訳結果をゲーム内表示でプレビュー")
    parser.add_argument('-i', '--input', required=True, help='翻訳結果ファイル')
    parser.add_argument('-o', '--output', help='HTMLプレビューファイル')

    args = parser.parse_args()

    if args.output is None:
        import os
        base_name = os.path.splitext(args.input)[0]
        args.output = f"{base_name}_preview.html"

    # 翻訳結果を読み込み
    with open(args.input, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # HTMLプレビューを生成
    generate_html_preview(lines, args.output)

    print(f"プレビューファイルを生成しました: {args.output}")
    print("ブラウザで開いて確認してください。")


if __name__ == "__main__":
    main()
