"""作業フォルダ（_jp_work）から、公開用のリポジトリ（既定 L:\\project4\\grimoire-ja）へ写す。

  python -I tools/sync_repo.py [リポジトリのフォルダ]      （_jp_work から）

写すもの
  docs/                サイト（wiki/build_site.py の出力。GitHub Pages は main の /docs から）
  patch/dll/           DLL のソースと設定・文字列表・美咲フォント
  patch/tools/         パッチを作る道具
  patch/glossary/      用語集・魔物の短い名前
  patch/notes/         作業メモ・訳し方の決まり・プレイヤー向けの説明書
  wiki/                Wiki 翻訳の道具・訳（ja/）・題・自分で決めた訳語
写さないもの: ゲームから取り出したデータ（extracted/、backup/、patch_jp/ など）、Wiki の取り込み元（wiki/raw/）、
  作業用の生成物。配布物（dist/Grimoire_JP.zip）は GitHub のリリースに上げる。
リポジトリ側の README.md・LICENSE 類・.gitignore・tools/ は、このスクリプトでは触らない。
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DLL = ['grimjp.cpp', 'grimjp.rc', 'version.def', 'build.bat', 'grimjp.ini', 'ui_strings.txt', 'exe_strings.txt']
FONTS = ['misaki8.bin', 'misaki_LICENSE.txt']
TOOLS = ['grimtool.py', 'dbtext.py', 'jptext.py', 'policy.py', 'glossary.py', 'chunks.py', 'build_patch.py',
         'make_images.py', 'make_images_small.py', 'make_flyers.py', 'pixfont.py', 'retitle.py', 'imgtool.py',
         'img2png.py', 'bdf2bin.py', 'make_fallback.py', 'make_dist.py', 'package.py', 'dbcheck.py',
         'sync_repo.py']
GLOSSARY = ['terms.tsv', 'monster_short.tsv']
NOTES = ['NOTES_ja.md', 'STYLE_ja.md', 'TRANSLATION_TARGETS.md', 'dist_readme.txt', 'install_test.bat',
         'restore_original.bat']
WIKI_FILES = ['TRANSLATING.md', 'fetch_wiki.py', 'prepare.py', 'lookup.py', 'check_ja.py', 'fix_terms.py',
              'build_site.py']
WIKI_DIRS = [('ja', 'ja'), ('assets', 'assets'), (os.path.join('work', 'titles'), 'titles'),
             (os.path.join('work', 'new_terms'), 'new_terms')]


def fresh(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)


def copy(names, src, dst):
    os.makedirs(dst, exist_ok=True)
    for n in names:
        shutil.copy2(os.path.join(src, n), os.path.join(dst, n))


def main(repo=r'L:\project4\grimoire-ja'):
    sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.isdir(os.path.join(repo, '.git')):
        sys.exit(f'{repo} は git のリポジトリではない')
    docs = os.path.join(repo, 'docs')
    if os.path.isdir(docs):
        shutil.rmtree(docs)
    shutil.copytree(os.path.join(ROOT, 'site'), docs)
    p = os.path.join(repo, 'patch')
    fresh(p)
    copy(DLL, os.path.join(ROOT, 'dll'), os.path.join(p, 'dll'))
    copy(FONTS, os.path.join(ROOT, 'dll', 'fonts'), os.path.join(p, 'dll', 'fonts'))
    copy(TOOLS, os.path.join(ROOT, 'tools'), os.path.join(p, 'tools'))
    copy(GLOSSARY, os.path.join(ROOT, 'glossary'), os.path.join(p, 'glossary'))
    copy(NOTES, ROOT, os.path.join(p, 'notes'))
    w = os.path.join(repo, 'wiki')
    fresh(w)
    copy(WIKI_FILES, os.path.join(ROOT, 'wiki'), w)
    for a, b in WIKI_DIRS:
        shutil.copytree(os.path.join(ROOT, 'wiki', a), os.path.join(w, b))
    n = sum(len(fs) for _, _, fs in os.walk(repo) if '.git' not in _)
    print(f'{repo} に写した（{n} ファイル）')


if __name__ == '__main__':
    main(*sys.argv[1:])
