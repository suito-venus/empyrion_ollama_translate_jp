# Empyrion翻訳システム

Ollamaを使用したEmpyrion用の高品質翻訳システムです。Amazon Bedrockの代替として、ローカルLLMによる無料翻訳を実現します。

## 🚀 特徴

- **無料翻訳**: Gemma2-27B Q5_0による高品質ローカル翻訳
- **自動品質保証**: タグ検証、コンテンツフィルタ、カラータグ自動修正
- **リトライ機能**: 英語のまま翻訳された場合の自動再翻訳
- **HTMLプレビュー**: ゲーム内表示を再現した視覚的確認
- **用語集対応**: 動的フィルタリングによる効率的な専門用語翻訳

## 📋 必要環境

### システム要件
- **OS**: Linux (Ubuntu推奨)
- **GPU**: NVIDIA RTX 4060以上 (VRAM 8GB以上)
- **メモリ**: 16GB以上
- **ストレージ**: 30GB以上の空き容量

### 依存関係
- Python 3.8+
- Ollama
- NVIDIA CUDA (GPU使用時)

## 🛠️ セットアップ

### 1. Ollamaインストール
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. モデルダウンロード
```bash
# 環境変数設定（オプション）
export OLLAMA_MODELS="/path/to/your/models"

# Gemma2-27B Q5_0モデルをダウンロード（約19GB）
ollama pull gemma2:27b-instruct-q5_0
```

### 3. Pythonパッケージインストール
```bash
pip install ollama
```

### 4. Ollamaサーバー起動
```bash
ollama serve
```

## 📁 ファイル構成

```
empyrion_ollama_translate_jp/
├── ollama_translate.py          # メイン翻訳スクリプト
├── color_tag_fixer.py          # カラータグ自動修正
├── tag_validator.py            # タグ検証
├── content_filter_detector.py  # コンテンツフィルタ検出
├── text_preview.py             # HTMLプレビュー生成
├── deepl_glossary_empyrion.json # 用語集
├── preprocessor_words.tsv      # 前処理ルール
├── postprocessor_words.tsv     # 後処理ルール
└── README.md                   # このファイル
```

## 🎯 使用方法

### 基本的な翻訳
```bash
python ollama_translate.py -i input.txt
```

### 出力ファイル指定
```bash
python ollama_translate.py -i input.txt -o output.txt
```

### 実行例
```bash
python ollama_translate.py -i Empyrion_localization.txt
```

## 📊 出力ファイル

翻訳実行後、以下のファイルが生成されます：

- **翻訳結果**: `input_ollama_YYYYMMDD_HHMMSS.txt`
- **HTMLプレビュー**: `input_ollama_YYYYMMDD_HHMMSS_preview.html`

## 🎮 対応タグ

### 装飾タグ
- `[u][/u]`: 下線
- `[i][/i]`: イタリック
- `[b][/b]`: 太字
- `[sup][/sup]`: 上付き文字（60%サイズ）

### ゲーム固有タグ
- `[c][HHHHHH][-][/c]`: カラーコード
- `<size=NN></size>`: フォントサイズ
- `@p9`, `@w4`: 読み上げウェイト記号
- `\\n`: 改行コード

## 🔧 高度な機能

### カラータグ自動修正
不正な `[/c]` を正しい `[-][/c]` に自動修正します。

### 英語リトライ機能
翻訳結果が英語のままの場合、自動的に再翻訳を実行します。

### 動的用語集フィルタリング
翻訳対象テキストに含まれる用語のみを抽出し、効率的な翻訳を実現します。

## 📈 品質保証

### 自動チェック機能
- **タグ検証**: 開始・終了タグの対応確認
- **コンテンツフィルタ**: 不適切な内容の検出
- **カラータグ補完**: 終了タグの自動修正

### ログ出力
```
[INFO]: 翻訳中: 1行目
[INFO]: カラータグ修正: 行5: [/c] → [-][/c] を 1箇所修正
[WARNING]: 英語のまま翻訳されました。リトライします
[INFO]: 翻訳完了。HTMLプレビューを生成中...
```

## 🎨 HTMLプレビュー

翻訳完了後、自動的にHTMLプレビューが生成されます：

- **ダークテーマ**: ゲーム風の見た目
- **装飾表示**: カラー、サイズ、装飾タグを実際に表示
- **行番号**: 問題箇所の特定が容易
- **統計情報**: 総行数の表示

## ⚙️ 設定ファイル

### 用語集 (deepl_glossary_empyrion.json)
```json
{
    "entries": "Tool\tツール\nWeapon\t武器\nArmor\tアーマー"
}
```

### 前処理・後処理 (*.tsv)
```
検索パターン\t置換文字列
```

## 🐛 トラブルシューティング

### Ollama接続エラー
```bash
# サーバーが起動しているか確認
ps aux | grep ollama

# サーバー再起動
ollama serve
```

### モデルが見つからない
```bash
# モデル一覧確認
ollama list

# モデル再ダウンロード
ollama pull gemma2:27b-instruct-q5_0
```

### メモリ不足
- より小さなモデル（Q4_0）を使用
- 他のアプリケーションを終了
- スワップファイルを増設

## 📊 パフォーマンス

### 翻訳速度
- **RTX 4090**: 約2-3秒/行
- **RTX 4060**: 約5-8秒/行

### メモリ使用量
- **Q5_0**: 約15GB VRAM
- **Q4_0**: 約12GB VRAM

## 💰 コスト比較

| 翻訳方法 | 100行の翻訳コスト |
|----------|-------------------|
| Amazon Bedrock | $70 |
| **ローカルLLM** | **$0** (電気代のみ) |

## 🔄 アップデート

### モデル更新
```bash
ollama pull gemma2:27b-instruct-q5_0
```

### 用語集更新
`deepl_glossary_empyrion.json` を編集後、翻訳を再実行

## 📝 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🤝 貢献

バグ報告や機能要望は、GitHubのIssueでお知らせください。

## 📞 サポート

技術的な質問や問題については、以下をご確認ください：

1. このREADMEのトラブルシューティング
2. Ollamaの公式ドキュメント
3. GitHubのIssue

---

**Happy Translating! 🎮✨**