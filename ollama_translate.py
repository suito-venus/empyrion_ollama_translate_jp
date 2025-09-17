import ollama
import json
import re
import argparse
from datetime import datetime as dt
import time
import logging
import os
import subprocess
from tag_validator import check_translation_tags
from content_filter_detector import detect_content_filter
from color_tag_fixer import fix_color_tags
from text_preview import generate_html_preview
from punctuation_formatter import format_punctuation


logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

# モデル名を一箇所で管理

# MODEL_NAME = 'gemma-2-llama-swallow-27b-it-v01-q5_0'
# MODEL_NAME = 'gemma2:27b-instruct-q5_0'
MODEL_NAME = 'gpt-oss:120b'


def ollama_translate_line(text: str, glossary: dict) -> str:
    """Ollama を使用して翻訳（リトライ機能付き）"""

    def translate_attempt(text: str, glossary: dict) -> str:
        # 翻訳ルールを含むプロンプト
        translation_rules = f"""英語を日本語に翻訳してください。必ず日本語で回答してください。

ルール:
1. 装飾タグ([u][/u], [i][/i], [b][/b], [sup][/sup])は元テキストにある場合のみ保持
2. カラータグ: [c][色コード]...テキスト...[-][/c] の形式で、[-][/c]で終了します
3. サイズタグ: <size=数字>...テキスト...</size> の形式です
4. "\\n"は改行コードですが変更しないでください
5. "@p9"等は読み上げ記号として前後に空白
6. 結果は１行で出力してください。

用語集:
{', '.join([f"{en}→{ja}" for en, ja in glossary.items()])}

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
        import re
        # タグを除去してテキスト部分のみを抽出
        clean_text = re.sub(r'\[[^\]]*\]|<[^>]*>', '', text)
        # 英語の単語を検出
        english_words = re.findall(r'\b[A-Za-z]+\b', clean_text)
        # 日本語文字を検出
        japanese_chars = re.findall(r'[ひらがなカタカナ漢字]', clean_text)

        # 英語の単語が多く、日本語文字が少ない場合は英語と判定
        return (len(english_words) > 3 and
                len(japanese_chars) < len(english_words))

    try:
        logger.debug(f"使用モデル: {MODEL_NAME}")

        # 初回翻訳
        translated_text = translate_attempt(text, glossary)

        # 英語のままの場合はリトライ
        if is_mostly_english(translated_text):
            logger.warning(f"英語のまま翻訳されました。リトライします: {translated_text[:50]}...")
            translated_text = translate_attempt(text, glossary)

        return translated_text

    except Exception as e:
        logger.error("翻訳エラー詳細:")
        logger.error(f"  エラータイプ: {type(e).__name__}")
        logger.error(f"  エラーメッセージ: {str(e)}")
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
    import re
    filtered_glossary = {}

    # テキストを単語に分割
    words_in_text = set(re.findall(r'\b[A-Za-z]+\b', text.lower()))

    for en_term, ja_term in full_glossary.items():
        # 用語が翻訳対象テキストに含まれているかチェック
        if (en_term.lower() in words_in_text or
                any(word in en_term.lower() for word in words_in_text)):
            filtered_glossary[en_term] = ja_term

    return filtered_glossary


def read_processor_words(filename: str) -> list[str]:
    """preprocessor/postprocessor文字列を読み込み"""
    try:
        with open(filename, 'r', encoding='utf_8') as f:
            return [s.rstrip() for s in f.readlines()]
    except FileNotFoundError:
        logger.warning(f"プロセッサファイル {filename} が見つかりません")
        return []


def processor_words(src_str: str, processor_words: list[str]) -> str:
    """プリ/ポストプロセッサ"""
    dest_str = src_str
    for processor_word in processor_words:
        parts = processor_word.split('\t')
        if len(parts) >= 2:
            dest_str = re.sub(parts[0], parts[1], dest_str)
    return dest_str


def get_model_size_gb(model_name):
    """モデルのサイズをGB単位で取得"""
    try:
        models = ollama.list()
        logger.debug(f"モデル情報: {models}")

        for model in models['models']:
            logger.debug(f"モデル詳細: {model}")
            # 様々なキーを試す
            name = model.get('name') or model.get('model') or model.get('id', '')
            if name == model_name:
                size_bytes = model.get('size', 0)
                size_gb = size_bytes / (1024**3)
                logger.info(f"モデルサイズ: {size_gb:.1f}GB")
                return size_gb
        logger.error(f"モデル {model_name} が見つかりません")
        return None
    except Exception as e:
        logger.error(f"モデルサイズ取得エラー: {e}")
        logger.error(f"モデル情報の構造: {models if 'models' in locals() else 'N/A'}")
        exit(1)


def get_available_vram_gb():
    """利用可能なVRAMをGB単位で取得"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.free',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True)
        if result.returncode == 0:
            vram_mb = int(result.stdout.strip().split('\n')[0])
            vram_gb = vram_mb / 1024
            logger.info(f"利用可能VRAM: {vram_gb:.1f}GB")
            return vram_gb
        else:
            logger.warning("nvidia-smiコマンドが失敗しました")
            return 0
    except Exception as e:
        logger.error(f"VRAM取得エラー: {e}")
        exit(1)


def setup_cpu_only_if_needed(model_name):
    """VRAM不足時にCPU実行を設定"""
    model_size = get_model_size_gb(model_name)
    available_vram = get_available_vram_gb()

    if model_size and available_vram > 0:
        required_vram = model_size * 0.8  # 80%のマージン
        logger.info(f"必要VRAM(推定): {required_vram:.1f}GB")

        if available_vram < required_vram:
            logger.warning("VRAM不足のためCPU実行に切り替えます")
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
            os.environ['OLLAMA_NUM_GPU'] = '0'
            os.environ['NUM_GPU'] = '0'
        else:
            logger.info("GPU使用可能です")


def check_ollama_connection():
    """Ollama接続確認"""
    try:
        models = ollama.list()
        # モデル構造を確認してから処理
        if 'models' in models:
            available_models = []
            for model in models['models']:
                # nameキーまたはmodelキーを確認
                model_name = model.get('name') or model.get('model', 'unknown')
                available_models.append(model_name)

            if any(MODEL_NAME in model for model in available_models):
                logger.info(f"{MODEL_NAME}モデルが利用可能です")
                # VRAM不足チェック
                setup_cpu_only_if_needed(MODEL_NAME)
            else:
                logger.warning(f"{MODEL_NAME}モデルが見つかりません")
                logger.info(f"利用可能なモデル: {available_models}")
        else:
            logger.warning("モデル一覧の取得に失敗しました")

    except Exception as e:
        logger.error(f"Ollama接続エラー: {e}")
        logger.error("ollama serveが起動していることを確認してください")


def main(args):
    """メイン処理"""

    # Ollama接続確認
    check_ollama_connection()

    glossary = load_glossary("deepl_glossary_empyrion.json")
    preprocessor_words = read_processor_words("preprocessor_words.tsv")
    postprocessor_words = read_processor_words("postprocessor_words.tsv")

    # 入力ファイルを読み込み、最後の行の改行情報を保持
    with open(args.input, 'r', encoding='utf_8') as inputfile:
        lines = inputfile.readlines()

    with open(args.output, 'w', encoding='utf_8') as outputfile:
        for line_no, raw_line in enumerate(lines, 1):
            line = processor_words(raw_line, preprocessor_words)

            logger.info(f"翻訳中: {line_no}行目")

            try:
                # 翻訳対象テキストに関連する用語のみを抽出
                filtered_glossary = filter_glossary_for_text(line, glossary)
                logger.debug(
                    f"用語数: {len(glossary)} → {len(filtered_glossary)}")

                translated_line = ollama_translate_line(
                    line, filtered_glossary)

                # 一時コード数をカウント（postprocessor適用前）
                original_newline_count = line.count('[NLINE]')
                translated_newline_count = translated_line.count('[NLINE]')

                # 改行コード数が一致しない場合は警告
                if original_newline_count != translated_newline_count:
                    logger.warning(
                        f"行{line_no}: 改行コード数が不一致 - "
                        f"元:{original_newline_count}, "
                        f"翻訳後:{translated_newline_count}")

                translated_line = processor_words(
                    translated_line, postprocessor_words)

                # カラータグ補完
                translated_line = fix_color_tags(
                    translated_line.strip(), line_no)

                # 句読点整形
                translated_line = format_punctuation(translated_line, line_no)

                # コンテンツフィルタ検出
                detect_content_filter(translated_line.strip(), line_no)

                # タグ検証（カラータグ補完後に再実行）
                check_translation_tags(translated_line.strip(), line_no)

                translated_line_striped = translated_line.strip()
                outputfile.write(translated_line_striped + '\n')
                time.sleep(0.5)  # Ollamaは高速なので短縮
            except Exception as e:
                logger.error(
                    f"{line_no}行目でエラーが発生しました。"
                    "処理を中断します。")
                raise e

    # 翻訳完了後にHTMLプレビューを自動生成
    logger.info("翻訳完了。HTMLプレビューを生成中...")

    # 翻訳結果を読み込み
    with open(args.output, 'r', encoding='utf-8') as f:
        translated_lines = f.readlines()

    # HTMLプレビューファイル名を生成
    base_name = os.path.splitext(args.output)[0]
    preview_file = f"{base_name}_preview.html"

    # HTMLプレビューを生成
    generate_html_preview(translated_lines, preview_file)

    logger.info(f"HTMLプレビューを生成しました: {preview_file}")
    logger.info("ブラウザで開いて確認してください。")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Ollama を使って翻訳")
    parser.add_argument('-i', '--input', required=True, help='入力ファイル')
    parser.add_argument('-o', '--output', help='出力ファイル')

    args = parser.parse_args()

    if args.output is None:
        tdatetime = dt.now()
        date_time_str = tdatetime.strftime('%Y%m%d_%H%M%S')

        # 入力ファイル名と拡張子を分離
        base_name = os.path.splitext(args.input)[0]
        extension = os.path.splitext(args.input)[1]

        args.output = f"{base_name}_ollama_{date_time_str}{extension}"

    main(args)
