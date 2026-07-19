import ollama
from openai import OpenAI
import json
import re
import argparse
from datetime import datetime as dt
import time
import logging
import os
import subprocess
from tag_validator import check_translation_tags, validate_html_tags
from content_filter_detector import detect_content_filter
from color_tag_fixer import fix_color_tags
from text_preview import generate_html_preview
from punctuation_formatter import format_punctuation


logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

# バックエンド設定: 'ollama' または 'llama'
BACKEND = 'ollama'
LLAMA_HOST = 'http://localhost:8080'

# モデル名を一箇所で管理
# Ollama用モデル名
# MODEL_NAME = 'gemma-2-llama-swallow-27b-it-v01-q5_0' - 改行が増えてしまう？
# MODEL_NAME = 'gemma2:27b-instruct-q5_0'  - 改行が増えてしまう？
# MODEL_NAME = 'gpt-oss:120b' - すごく重い
# MODEL_NAME = 'gpt-oss:20b' - 翻訳がちょっと硬いけど動作は良好
# MODEL_NAME = 'gemma3:27b' - good
OLLAMA_MODEL_NAME = 'gemma4:26b'

# llama-server用モデル名（自動検出するのでデフォルトは空）
LLAMA_MODEL_NAME = ''

MODEL_NAME = OLLAMA_MODEL_NAME


def get_llama_client():
    """llama-server用のOpenAIクライアントを取得"""
    return OpenAI(base_url=f"{LLAMA_HOST}/v1", api_key="no-key")


def detect_llama_model():
    """llama-serverからロード中のモデル名を自動検出"""
    try:
        client = get_llama_client()
        models = client.models.list()
        if models.data:
            model_id = models.data[0].id
            logger.info(f"llama-server モデル検出: {model_id}")
            return model_id
        logger.warning("llama-server にモデルが見つかりません")
        return None
    except Exception as e:
        logger.error(f"llama-server モデル検出エラー: {e}")
        return None


# def get_optimal_tokens(text: str) -> dict:
#     """入力テキストに基づいて最適なトークン数を計算"""
#     text_length = len(text)

#     if text_length < 100:
#         return {'num_predict': -1, 'num_ctx': 2048}      # 短文
#     elif text_length < 500:
#         return {'num_predict': -1, 'num_ctx': 4096}     # 中文
#     elif text_length < 1000:
#         return {'num_predict': -1, 'num_ctx': 4096}    # 長文
#     else:
#         return {'num_predict': -1, 'num_ctx': 8192}   # 超長文


def extract_decoration_tags(text: str) -> set:
    """テキストから装飾タグの種類を抽出"""
    tags = set()

    # 各タグタイプを個別にチェック
    tag_patterns = {
        'u': r'\[u\].*?\[/u\]',
        'i_bracket': r'\[i\].*?\[/i\]',
        'i_angle': r'<i>.*?</i>',
        'b_bracket': r'\[b\].*?\[/b\]',
        'b_angle': r'<b>.*?</b>',
        'sup': r'\[sup\].*?\[/sup\]',
        'sub': r'\[sub\].*?\[/sub\]',
        'color_bracket': r'\[c\]\[[A-Fa-f0-9]{6}\].*?(?:\[-\])?\[/c\]',
        'color_angle': r'<color=#[A-Fa-f0-9]{6}>.*?</color>',
        'size': r'<size=\d+>.*?</size>'
    }

    for tag_type, pattern in tag_patterns.items():
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            tags.add(tag_type)

    return tags


def validate_tag_preservation(original_text: str, translated_text: str) -> bool:
    """装飾タグが保持されているかチェック"""
    original_tags = extract_decoration_tags(original_text)
    translated_tags = extract_decoration_tags(translated_text)

    # 元テキストにあるタグが翻訳後にも存在するかチェック
    missing_tags = original_tags - translated_tags

    if missing_tags:
        logger.warning(f"装飾タグが欠落: {missing_tags}")
        return False

    # HTMLタグの開始/終了数の一致チェック
    html_tag_pairs = [
        (r'<b>', r'</b>', 'HTML bold (<b>)'),
        (r'<i>', r'</i>', 'HTML italic (<i>)'),
        (r'<u>', r'</u>', 'HTML underline (<u>)'),
        (r'<color=#[A-Fa-f0-9]{6}>', r'</color>', 'HTML color (<color>)'),
        (r'<size=\d+>', r'</size>', 'HTML size (<size>)'),
    ]

    for start_pattern, end_pattern, tag_name in html_tag_pairs:
        orig_start = len(re.findall(start_pattern, original_text))
        orig_end = len(re.findall(end_pattern, original_text))
        trans_start = len(re.findall(start_pattern, translated_text))
        trans_end = len(re.findall(end_pattern, translated_text))

        if orig_start != trans_start:
            logger.warning(
                f"{tag_name}開始タグ数が不一致: 元={orig_start}, 翻訳後={trans_start}")
            return False
        if orig_end != trans_end:
            logger.warning(
                f"{tag_name}終了タグ数が不一致: 元={orig_end}, 翻訳後={trans_end}")
            return False

    return True


def validate_newline_preservation(original_text: str, translated_text: str) -> bool:
    """改行コード(\n)が保持されているかチェック"""
    original_newlines = original_text.count('\\n')
    translated_newlines = translated_text.count('\\n')
    
    if original_newlines != translated_newlines:
        logger.warning(f"改行コード数が不一致: 元:{original_newlines}, 翻訳後:{translated_newlines}")
        return False
    
    return True


def restore_line_codes(original_text: str, translated_text: str) -> str:
    """行頭コード(@q0, @d0, @d0@q0)を翻訳後テキストに復元"""
    # 行頭コードのパターンを定義
    line_code_patterns = [r'^@d0@q0', r'^@q0', r'^@d0']
    
    for pattern in line_code_patterns:
        if re.match(pattern, original_text):
            # 元テキストから行頭コードを抽出
            match = re.match(pattern, original_text)
            if match:
                line_code = match.group(0)
                # 翻訳後テキストに行頭コードがない場合は追加
                if not translated_text.startswith(line_code):
                    translated_text = line_code + translated_text
                break
    
    return translated_text


def ollama_translate_line(text: str, glossary: dict, casual_mode: bool = False) -> str:
    """Ollama を使用して翻訳（リトライ機能付き）"""

    def translate_attempt(text: str, glossary: dict, casual_mode: bool,
                          retry_feedback: str = "") -> str:
        # IDA検出による丁寧語モード
        is_ida_mode = '[IDA]' in text

        # 翻訳スタイルを選択
        if is_ida_mode:
            style_instruction = """IDA（情報データアシスタント）として、丁寧語で翻訳してください。
翻訳スタイル:
- 「です・ます」調で統一
- 専門的で正確な情報提供を意識した表現"""
        elif casual_mode:
            style_instruction = """ゲームのセリフや会話として、口語的で自然な日本語に翻訳してください。
翻訳スタイル:
- キャラクターの感情や性格が伝わるような表現を選択
- 丁寧語よりも親しみやすい表現を優先"""
        else:
            style_instruction = "自然な日本語に翻訳してください。"

        # リトライ時のフィードバック指示
        feedback_section = ""
        if retry_feedback:
            feedback_section = f"""
【修正指示】前回の翻訳で以下の問題が検出されました。今回は必ず修正してください:
{retry_feedback}
"""

        # 翻訳ルールを含むプロンプト
        translation_rules = f"""英語を日本語に翻訳してください。必ず日本語で回答してください。

{style_instruction}
{feedback_section}
【重要】タグ保持ルール:
1. 装飾タグ([u][/u], [i][/i], <i></i>, [b][/b], <b></b>, [sup][/sup],[sub][/sub])は元テキストにある場合は必ず保持
2. 【最重要】カラータグの正しい位置を維持:
   - [c][色コード]で始まり[-][/c]で終わる形式
   - <color=#色コード>で始まり</color>で終わる形式
   - カラータグは元テキストと同じ単語を囲むように配置してください
   - 例1: [c][ffffbe]Enter the[-][/c] Bridge → ブリッジに[c][ffffbe]入る[-][/c]
   - 例2: [c][eeff00]bartender[-][/c] → [c][eeff00]バーテンダー[-][/c]
3. サイズタグ: <size=数字>...テキスト...</size> の形式も必ず保持
4. 【重要】"\\n"は改行コードです。元テキストの\\nの数と同じ数だけ翻訳結果に含めてください。絶対に削除しないでください
5. 【重要】"@p9", "@q0"等は読み上げ記号として前後に空白をいれてください。絶対に削除しないでください
6. 翻訳対象の文章が会話 XXをyyする のような短い文の場合、会話ではなくゲーム上での指示なので、 XXをyyする などのように動詞で終了するような表現してください
7. 結果は１行で出力してください


用語集:
{', '.join([f"{en}→{ja}" for en, ja in glossary.items()])}

テキスト: {text}

日本語翻訳:"""

        if BACKEND == 'llama':
            client = get_llama_client()
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        'role': 'user',
                        'content': translation_rules
                    }
                ]
            )
            return response.choices[0].message.content.replace('\n', '')
        else:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        'role': 'user',
                        'content': translation_rules
                    }
                ]
                # options={
                #     'num_predict': token_config['num_predict'],
                #     'num_ctx': token_config['num_ctx'],
                #     'temperature': 0.1,
                #     'top_p': 0.9,
                #     'repeat_penalty': 1.1
                # }
            )
            # 翻訳結果を取得して改行を削除
            return response['message']['content'].replace('\n', '')

    def is_mostly_english(text: str) -> bool:
        """テキストが主に英語かどうかを判定"""
        import re
        # タグを除去してテキスト部分のみを抽出
        clean_text = re.sub(r'\[[^\]]*\]|<[^>]*>', '', text)

        # 日本語文字を検出（正しいUnicode範囲を使用）
        hiragana = re.findall(r'[\u3041-\u309F]', clean_text)  # ひらがな
        katakana = re.findall(r'[\u30A1-\u30FF]', clean_text)  # カタカナ
        kanji = re.findall(r'[\u2E80-\u2FDF\u3005-\u3007\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]', clean_text)  # 漢字

        japanese_char_count = len(hiragana) + len(katakana) + len(kanji)

        # 日本語文字が含まれていない場合は英語と判定
        return japanese_char_count == 0

    try:
        logger.debug(f"使用モデル: {MODEL_NAME}")

        max_retries = 3
        retry_feedback = ""  # リトライ時にLLMに伝えるフィードバック

        for attempt in range(max_retries + 1):
            # 翻訳実行（リトライ時はフィードバック付き）
            translated_text = translate_attempt(
                text, glossary, casual_mode, retry_feedback)

            # エラー情報を収集（次のリトライ用）
            feedback_messages = []

            # 英語のままかチェック
            if is_mostly_english(translated_text):
                if attempt < max_retries:
                    logger.warning(f"英語のまま翻訳されました。リトライします({attempt + 1}/{max_retries}): {translated_text[:50]}...")
                    feedback_messages.append(
                        "- 翻訳結果が英語のままです。必ず日本語に翻訳してください。")
                    retry_feedback = "\n".join(feedback_messages)
                    continue
                else:
                    logger.warning(f"英語のまま翻訳されました。最大リトライ回数に達しました: {translated_text[:50]}...")

            # 装飾タグ保持チェック
            if not validate_tag_preservation(text, translated_text):
                if attempt < max_retries:
                    logger.warning(f"装飾タグが欠落しています。リトライします({attempt + 1}/{max_retries})")
                    feedback_messages.append(
                        "- HTMLタグの数が元テキストと一致しません。"
                        "<b>は必ず</b>で閉じ、<color=#XXXXXX>は必ず</color>で閉じてください。"
                        "タグの'>'を省略しないでください。")
                    retry_feedback = "\n".join(feedback_messages)
                    continue
                else:
                    logger.warning("装飾タグが欠落しています。最大リトライ回数に達しました。処理を続行します。")
            
            # HTMLタグの構文チェック（壊れたタグの検出）
            html_errors = validate_html_tags(translated_text)
            if html_errors:
                if attempt < max_retries:
                    for err in html_errors:
                        logger.warning(f"HTMLタグ検証エラー: {err}")
                    logger.warning(f"HTMLタグが壊れています。リトライします({attempt + 1}/{max_retries})")
                    # 具体的なエラー内容をフィードバックに含める
                    feedback_messages.append(
                        "- HTMLタグが壊れています。以下のエラーを修正してください:")
                    for err in html_errors:
                        feedback_messages.append(f"  {err}")
                    feedback_messages.append(
                        "- 全てのHTMLタグは正しく閉じてください: "
                        "<b>...</b>, <i>...</i>, <color=#XXXXXX>...</color>")
                    retry_feedback = "\n".join(feedback_messages)
                    continue
                else:
                    for err in html_errors:
                        logger.warning(f"HTMLタグ検証エラー: {err}")
                    logger.warning("HTMLタグが壊れています。最大リトライ回数に達しました。処理を続行します。")

            # 改行コード保持チェック
            if not validate_newline_preservation(text, translated_text):
                if attempt < max_retries:
                    logger.warning(f"改行コードが欠落しています。リトライします({attempt + 1}/{max_retries})")
                    original_count = text.count('\\n')
                    translated_count = translated_text.count('\\n')
                    feedback_messages.append(
                        f"- 改行コード(\\n)の数が不一致です。"
                        f"元テキストには{original_count}個の\\nがありますが、"
                        f"翻訳結果には{translated_count}個しかありません。"
                        f"必ず{original_count}個の\\nを含めてください。")
                    retry_feedback = "\n".join(feedback_messages)
                    continue
                else:
                    logger.warning("改行コードが欠落しています。最大リトライ回数に達しました。処理を続行します。")

            # 行頭コードを復元
            translated_text = restore_line_codes(text, translated_text)
            
            # 翻訳成功
            return translated_text

        # 最大リトライ回数に達した場合は最後の結果を返す
        translated_text = restore_line_codes(text, translated_text)
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
    """翻訳対象テキストに含まれる用語のみを抽出（部分文字列マッチ）"""
    filtered_glossary = {}
    text_lower = text.lower()

    for en_term, ja_term in full_glossary.items():
        en_lower = en_term.lower()
        # 短い用語（3文字以下）は単語境界でマッチ
        if len(en_term) <= 3:
            if re.search(r'\b' + re.escape(en_lower) + r'\b', text_lower):
                filtered_glossary[en_term] = ja_term
        else:
            # 4文字以上の用語はテキスト内に部分文字列として存在するかチェック
            if en_lower in text_lower:
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
    if BACKEND == 'llama':
        try:
            client = get_llama_client()
            models = client.models.list()
            for model in models.data:
                if model.id == model_name:
                    meta = getattr(model, 'meta', None)
                    if meta and hasattr(meta, 'size'):
                        size_gb = meta.size / (1024**3)
                        logger.info(f"モデルサイズ: {size_gb:.1f}GB")
                        return size_gb
            logger.warning(f"モデル {model_name} のサイズ情報が取得できません")
            return None
        except Exception as e:
            logger.error(f"モデルサイズ取得エラー: {e}")
            return None

    try:
        models = ollama.list()
        logger.debug(f"モデル情報: {models}")

        for model in models['models']:
            logger.debug(f"モデル詳細: {model}")
            # 様々なキーを試す
            name = (model.get('name') or model.get('model')
                    or model.get('id', ''))
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


# def setup_cpu_only_if_needed(model_name):
#     """VRAM不足時にCPU実行を設定"""
#     model_size = get_model_size_gb(model_name)
#     available_vram = get_available_vram_gb()

#     if model_size and available_vram > 0:
#         required_vram = model_size * 0.8  # 80%のマージン
#         logger.info(f"必要VRAM(推定): {required_vram:.1f}GB")

#         if available_vram < required_vram:
#             logger.warning("VRAM不足のためCPU実行に切り替えます")
#             os.environ['CUDA_VISIBLE_DEVICES'] = ''
#             os.environ['OLLAMA_NUM_GPU'] = '0'
#             os.environ['NUM_GPU'] = '0'
#         else:
#             logger.info("GPU使用可能です")


def check_ollama_connection():
    """LLMバックエンド接続確認"""
    try:
        # GPU使用状況を確認
        logger.info(f"OLLAMA_NUM_GPU: {os.environ.get('OLLAMA_NUM_GPU', '未設定')}")
        logger.info(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', '未設定')}")

        if BACKEND == 'llama':
            logger.info(f"バックエンド: llama-server ({LLAMA_HOST})")
            client = get_llama_client()
            models = client.models.list()
            available_models = [m.id for m in models.data]
            if available_models:
                logger.info(f"利用可能なモデル: {available_models}")
                if any(MODEL_NAME in model for model in available_models):
                    logger.info(f"{MODEL_NAME}モデルが利用可能です")
                else:
                    logger.warning(f"{MODEL_NAME}モデルが見つかりません")
            else:
                logger.warning("llama-server にモデルがロードされていません")
            return

        logger.info("バックエンド: Ollama")
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
                # # VRAM不足チェック
                # setup_cpu_only_if_needed(MODEL_NAME)
            else:
                logger.warning(f"{MODEL_NAME}モデルが見つかりません")
                logger.info(f"利用可能なモデル: {available_models}")
        else:
            logger.warning("モデル一覧の取得に失敗しました")

    except Exception as e:
        logger.error(f"LLMバックエンド接続エラー: {e}")
        if BACKEND == 'llama':
            logger.error(f"llama-server ({LLAMA_HOST}) が起動していることを確認してください")
        else:
            logger.error("ollama serveが起動していることを確認してください")


def setup_backend(backend, llama_host, model=None):
    """バックエンド設定をグローバルに反映"""
    global BACKEND, LLAMA_HOST, MODEL_NAME
    BACKEND = backend
    LLAMA_HOST = llama_host

    if model:
        MODEL_NAME = model
    elif backend == 'llama':
        detected = detect_llama_model()
        if detected:
            MODEL_NAME = detected
        elif LLAMA_MODEL_NAME:
            MODEL_NAME = LLAMA_MODEL_NAME
        else:
            logger.error("llama-server のモデル名を検出できませんでした。--model で指定してください。")
            exit(1)
    else:
        MODEL_NAME = OLLAMA_MODEL_NAME


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

    total_lines = len(lines)
    start_time = time.time()

    with open(args.output, 'w', encoding='utf_8') as outputfile:
        for line_no, raw_line in enumerate(lines, 1):
            line = processor_words(raw_line, preprocessor_words)

            elapsed = time.time() - start_time
            percent = (line_no / total_lines) * 100
            if line_no > 1:
                avg_per_line = elapsed / (line_no - 1)
                remaining = avg_per_line * (total_lines - line_no + 1)
            else:
                remaining = 0
            logger.info(
                f"翻訳中: {line_no}/{total_lines} 行目"
                f" ( {percent:.1f}% )"
                f"  経過時間: {elapsed:.0f} 秒"
                f"  予想残り時間: {remaining:.0f} 秒"
            )

            try:
                # 翻訳対象テキストに関連する用語のみを抽出
                filtered_glossary = filter_glossary_for_text(line, glossary)
                logger.debug(
                    f"用語数: {len(glossary)} → {len(filtered_glossary)}")

                translated_line = ollama_translate_line(
                    line, filtered_glossary, args.casual)

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
        description="Ollama/llama-server を使って翻訳")
    parser.add_argument('-i', '--input', required=True, help='入力ファイル')
    parser.add_argument('-o', '--output', help='出力ファイル')
    parser.add_argument('-c', '--casual', action='store_true', help='口語体モード（ゲームのセリフ用）')
    parser.add_argument('--backend', choices=['ollama', 'llama'], default='ollama',
                        help='LLMバックエンド (デフォルト: ollama)')
    parser.add_argument('--llama-host', default='http://localhost:8080',
                        help='llama-serverのホスト (デフォルト: http://localhost:8080)')
    parser.add_argument('--model', default=None,
                        help='モデル名を指定（省略時はデフォルト値を使用）')

    args = parser.parse_args()

    # バックエンド設定を反映
    setup_backend(args.backend, args.llama_host, args.model)

    if args.output is None:
        tdatetime = dt.now()
        date_time_str = tdatetime.strftime('%Y%m%d_%H%M%S')

        # 入力ファイル名と拡張子を分離
        base_name = os.path.splitext(args.input)[0]
        extension = os.path.splitext(args.input)[1]

        args.output = f"{base_name}_ollama_{date_time_str}{extension}"

    main(args)
