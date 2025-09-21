import ollama
import json
import re
import argparse
import difflib
from datetime import datetime as dt
import time
import logging
import os
from tag_validator import check_translation_tags
from content_filter_detector import detect_content_filter
from color_tag_fixer import fix_color_tags
from punctuation_formatter import format_punctuation

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

MODEL_NAME = 'gpt-oss:120b'


def ollama_translate_line(text: str, glossary: dict,
                          casual_mode: bool = False) -> str:
    """Ollama を使用して翻訳（リトライ機能付き）"""
    
    def translate_attempt(text: str, glossary: dict,
                          casual_mode: bool) -> str:
        if casual_mode:
            style_instruction = """ゲームのセリフや会話として、口語的で自然な日本語に翻訳してください。
翻訳スタイル:
- キャラクターの感情や性格が伝わるような表現を選択
- 丁寧語よりも親しみやすい表現を優先"""
        else:
            style_instruction = "標準的な日本語に翻訳してください。"

        glossary_str = ', '.join([f"{en}→{ja}" for en, ja in glossary.items()])
        translation_rules = f"""英語を日本語に翻訳してください。必ず日本語で回答してください。

{style_instruction}

ルール:
1. 装飾タグ([u][/u], [i][/i], [b][/b], [sup][/sup])は元テキストにある場合のみ保持
2. カラータグ: [c][色コード]...テキスト...[-][/c] の形式で、[-][/c]で終了します
3. サイズタグ: <size=数字>...テキスト...</size> の形式です
4. "\\n"は改行コードですが変更しないでください
5. "@p9"等は読み上げ記号として前後に空白
6. 結果は１行で出力してください。

用語集:
{glossary_str}

テキスト: {text}

日本語翻訳:"""

        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    'role': 'user',
                    'content': translation_rules
                }
            ]
        )

        return response['message']['content'].strip()

    def is_mostly_english(text: str) -> bool:
        """テキストが主に英語かどうかを判定"""
        clean_text = re.sub(r'\[[^\]]*\]|<[^>]*>', '', text)
        english_words = re.findall(r'\b[A-Za-z]+\b', clean_text)
        japanese_chars = re.findall(r'[ひらがなカタカナ漢字]', clean_text)
        
        return (len(english_words) > 3 and
                len(japanese_chars) < len(english_words))

    try:
        translated_text = translate_attempt(text, glossary, casual_mode)
        
        if is_mostly_english(translated_text):
            logger.warning(f"英語のまま翻訳されました。リトライします: {translated_text[:50]}...")
            translated_text = translate_attempt(text, glossary, casual_mode)
        
        return translated_text

    except Exception as e:
        logger.error(f"翻訳エラー: {type(e).__name__}: {str(e)}")
        raise e


def load_glossary(filename: str) -> dict:
    """用語集を読み込む"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            glossary_data = json.load(f)
            glossary_dict = {}
            entries = glossary_data.get('entries', '')
            for line in entries.strip().split('\n'):
                if '\t' in line:
                    en, ja = line.split('\t', 1)
                    glossary_dict[en] = ja
            return glossary_dict
    except FileNotFoundError:
        logger.warning(f"用語集ファイル {filename} が見つかりません")
        return {}


def filter_glossary_for_text(text: str, full_glossary: dict) -> dict:
    """翻訳対象テキストに含まれる単語のみを抽出"""
    filtered_glossary = {}
    words_in_text = set(re.findall(r'\b[A-Za-z]+\b', text.lower()))
    
    for en_term, ja_term in full_glossary.items():
        if (en_term.lower() in words_in_text or
                any(word in en_term.lower() for word in words_in_text)):
            filtered_glossary[en_term] = ja_term
    
    return filtered_glossary


def get_diff_changes(old_text: str, new_text: str) -> list:
    """2つのテキスト間の差分を取得"""
    old_words = old_text.split()
    new_words = new_text.split()
    
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    changes = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            changes.append({
                'type': 'replace',
                'old': ' '.join(old_words[i1:i2]),
                'new': ' '.join(new_words[j1:j2])
            })
        elif tag == 'insert':
            changes.append({
                'type': 'insert',
                'new': ' '.join(new_words[j1:j2])
            })
        elif tag == 'delete':
            changes.append({
                'type': 'delete',
                'old': ' '.join(old_words[i1:i2])
            })
    
    return changes


def apply_diff_to_translation(old_english: str, new_english: str,
                              old_japanese: str, glossary: dict,
                              casual_mode: bool = False) -> str:
    """差分を日本語翻訳に適用（シンプルな置換ベース）"""
    # 変更が小さい場合は、新しい英語全体を翻訳して返す
    # これにより文脈を保持しつつ、変更部分を正確に反映
    filtered_glossary = filter_glossary_for_text(new_english, glossary)
    return ollama_translate_line(new_english, filtered_glossary, casual_mode)


def process_tsv_file(input_file: str, output_file: str, glossary: dict,
                     casual_mode: bool = False):
    """TSVファイルを処理して差分翻訳を実行"""
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # ヘッダー行をスキップ
    header = lines[0].strip()
    data_lines = lines[1:]
    
    results = []
    
    for line_no, line in enumerate(data_lines, 2):
        parts = line.strip().split('\t')
        if len(parts) < 3:
            logger.warning(f"行{line_no}: 列数が不足しています")
            continue
        
        old_english = parts[0]
        new_english = parts[1]
        old_japanese = parts[2]
        
        logger.info(f"処理中: {line_no}行目")
        
        # 英語テキストに変更がない場合はそのまま
        if old_english == new_english:
            results.append(old_japanese)
            continue
        
        # 差分を取得
        changes = get_diff_changes(old_english, new_english)
        
        if not changes:
            results.append(old_japanese)
            continue
        
        # 変更が大きい場合は全体を再翻訳
        similarity = difflib.SequenceMatcher(None, old_english, new_english).ratio()
        
        # 70%未満の類似度の場合は全体を再翻訳
        if similarity < 0.7:
            logger.info(f"行{line_no}: 変更が大きいため全体を再翻訳 "
                       f"(類似度: {similarity:.2f})")
            filtered_glossary = filter_glossary_for_text(new_english, glossary)
            new_japanese = ollama_translate_line(new_english,
                                               filtered_glossary,
                                               casual_mode)
        else:
            logger.info(f"行{line_no}: 差分翻訳を適用 "
                       f"(類似度: {similarity:.2f})")
            new_japanese = apply_diff_to_translation(old_english,
                                                   new_english,
                                                   old_japanese,
                                                   glossary,
                                                   casual_mode)
        
        # 品質チェック
        new_japanese = fix_color_tags(new_japanese, line_no)
        new_japanese = format_punctuation(new_japanese, line_no)
        detect_content_filter(new_japanese, line_no)
        check_translation_tags(new_japanese, line_no)
        
        results.append(new_japanese)
        time.sleep(0.5)
    
    # 結果を出力
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for i, result in enumerate(results):
            parts = data_lines[i].strip().split('\t')
            f.write(f"{parts[0]}\t{parts[1]}\t{result}\n")


def main():
    parser = argparse.ArgumentParser(description="差分翻訳スクリプト")
    parser.add_argument('-i', '--input', required=True, help='入力TSVファイル')
    parser.add_argument('-o', '--output', help='出力TSVファイル')
    parser.add_argument('-c', '--casual', action='store_true', help='口語体モード')
    
    args = parser.parse_args()
    
    if args.output is None:
        tdatetime = dt.now()
        date_time_str = tdatetime.strftime('%Y%m%d_%H%M%S')
        base_name = os.path.splitext(args.input)[0]
        extension = os.path.splitext(args.input)[1]
        args.output = f"{base_name}_diff_{date_time_str}{extension}"
    
    glossary = load_glossary("deepl_glossary_empyrion.json")
    
    logger.info(f"入力ファイル: {args.input}")
    logger.info(f"出力ファイル: {args.output}")
    
    process_tsv_file(args.input, args.output, glossary, args.casual)
    
    logger.info("差分翻訳完了")


if __name__ == '__main__':
    main()