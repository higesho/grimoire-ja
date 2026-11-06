# Grimoire: Heralds of the Winged Exemplar 日本語化

Steam 版 *Grimoire: Heralds of the Winged Exemplar*（3.0.0.0-R）を日本語で遊べるようにする、非公式のファンメイドパッチと、
Grimoire ファン Wiki の日本語訳です。開発元（Golden Era Enterprise）とは関係ありません。

An unofficial Japanese fan translation of *Grimoire: Heralds of the Winged Exemplar* (Steam, 3.0.0.0-R),
and a Japanese translation of the Grimoire fan wiki.

- サイト（入れ方・Wiki 翻訳）: https://higesho.github.io/grimoire-ja/
- ダウンロード: [リリース](https://github.com/higesho/grimoire-ja/releases/latest) の `Grimoire_JP.zip`

## 入れ方

1. Steam のライブラリでゲームを右クリックし、「管理」→「ローカルファイルを閲覧」でゲームのフォルダを開く。
2. `Grimoire_JP.zip` の中身（`version.dll`、`grimjp.ini`、`grimjp` フォルダ）をゲームのフォルダにコピーする。
3. ゲームを起動する。初めての起動のときだけ、日本語版のデータを `grimjp\cache` に作る。

元のゲームのファイル（Grimoire.exe・BUNDLE-Z.RSF）は書き換えません。配布物に原作のデータは入っていません。
外すときは、コピーしたものと `grimjp.log` を消せば英語版に戻ります。

## このリポジトリの中身

| フォルダ | 中身 |
|---|---|
| `docs/` | サイト（GitHub Pages）。パッチの紹介と Wiki 翻訳 |
| `wiki/` | Wiki 翻訳の訳文（`ja/`）、題の訳、道具（取り込み・検査・サイト作成）、訳し方の決まり |
| `patch/dll/` | 日本語を描く `version.dll` のソース（C++、Visual Studio 2022、32 ビット） |
| `patch/tools/` | パッチを作る道具（Python）。プレイヤーのゲームのファイルから文章を取り出し、訳を組み込む |
| `patch/glossary/` | 用語集（約 3,700 語）と、戦闘用に短くした魔物の名前 |
| `patch/notes/` | 作業メモ、訳し方の決まり、プレイヤー向けの説明書 |

ゲームから取り出したデータそのものは入れていません。

## 翻訳について

翻訳には AI（Anthropic 社の Claude）を使い、用語集で名前や用語を揃えています。
誤訳や不自然な訳に気づいたら Issues で教えてください。

## ライセンス

- Wiki 翻訳（`wiki/ja/`、`docs/wiki/`）: 元の Grimoire ファン Wiki（grimoirewiki.neocities.org）と同じ
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ja)。
  記事の画像とロゴは元の Wiki のものを表示していて、このリポジトリには入っていません。
  Wiki のページの見た目には MediaWiki（GPL-2.0-or-later）の Vector のスタイルシートを使っています。
- 美咲フォント（`patch/dll/fonts/misaki8.bin`）: Copyright (C) 2002-2021 Num Kadoma。`misaki_LICENSE.txt` を参照。
- Grimoire: Heralds of the Winged Exemplar &copy; Cleveland Mark Blakemore / Golden Era Enterprise。
  ゲームの画像・文章の権利は原作の権利者にあります。
