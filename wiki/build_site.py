"""日本語化パッチの紹介ページと、ファン Wiki の翻訳をまとめた静的サイトを作る。

  python wiki/build_site.py [--out site] [--repo higesho/grimoire-ja] [--images remote|local|none]

読むもの
  wiki/ja/<名前>.html        訳した本文
  wiki/raw/<名前>.html       取り込んだ元の記事（題・最終更新日）
  wiki/work/titles/*.txt     題の訳（1 行目 英語、2 行目 訳）
  wiki/assets/grimoire.css   見た目
  screenshots/*.png          紹介ページの画面写真
出力（--out、既定は _jp_work/site）
  index.html                 日本語化パッチの紹介・入れ方・ダウンロード
  wiki/index.html            元の Wiki のトップページの訳
  wiki/<名前>.html, wiki/all.html, wiki/license.html

Wiki の訳は元と同じ CC BY-NC-SA 4.0 で公開する。各ページに元の記事へのリンクと、翻訳であることを書く。
画像（ゲームの画面・肖像・地図）は既定では元の Wiki のものを直接表示し（--images remote）、こちらには置かない。
"""
NL = chr(10)
import argparse, html, os, re, shutil, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, 'raw')
JA = os.path.join(HERE, 'ja')
TITLES = os.path.join(HERE, 'work', 'titles')
SITE = 'https://grimoirewiki.neocities.org/'
BASE = SITE + 'index.php/'
ALIASES = {'Classes': 'Professions'}
MONTHS = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                      'September', 'October', 'November', 'December'], 1)}
LICENSE_URL = 'https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ja'
SHOTS = [('ingame_start_jp.png', 'ゲームの始まり'), ('ui_charsheet_jp.png', 'キャラクターの画面'),
         ('combat_group_name.png', '戦闘'), ('img_replace_ingame.png', '日本語に描き直した画像')]


def esc(s):
    return html.escape(s, quote=True)


def page(title, desc, body, here, depth, extra_class=''):
    up = '../' * depth
    nav = [(up + 'index.html', '日本語化パッチ'), (up + 'wiki/index.html', 'Wiki 翻訳'),
           (up + 'wiki/all.html', '記事一覧')]
    links = ''.join(f'<a href="{h}"{" class=here" if h.endswith(here) and here else ""}>{t}</a>' for h, t in nav)
    if depth:
        foot = (f'<p>Wiki 翻訳のページは、Grimoire ファン Wiki（<a href="{SITE}">grimoirewiki.neocities.org</a>）の記事を'
                f'日本語に訳したもので、元と同じ <a href="license.html">CC BY-NC-SA 4.0</a> で公開しています。'
                f'ゲームの用語は日本語化パッチの訳語に合わせました。画像は元の Wiki のものを表示しています。</p>')
    else:
        foot = ''
    foot += ('<p>非公式のファン翻訳です。Grimoire: Heralds of the Winged Exemplar &copy; Cleveland Mark Blakemore / '
             'Golden Era Enterprise。開発元とは関係ありません。</p>')
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} &mdash; Grimoire 日本語化</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="{up}grimoire.css">
</head>
<body>
<header class="jpn" id="jpn"><div class="jpn-band"><a class="jpn-home" href="https://higesho.github.io/ja/">日本語化プロジェクト</a></div></header>
<script src="https://higesho.github.io/ja/nav.js"></script>
<main class="band{extra_class}">
{body}
</main>
<footer class="foot"><div class="band">
  {foot}
</div></footer>
</body>
</html>
"""


def wiki_page(title, en, body, edited='', orig=''):
    """元の Wiki（MediaWiki の Vector）と同じ骨組みのページ。"""
    sub = f' <span class="en">{esc(en)}</span>' if en and en != title else ''
    orig_tab = (f'<li id="ca-orig"><span><a href="{orig}">英語版</a></span></li>' if orig else '')
    orig_tool = (f'<li><a href="{orig}">この記事の英語版</a></li>' if orig else '')
    lastmod = (f'<li id="footer-info-lastmod">元の記事の最終更新: {edited}</li>' if edited else '')
    return f"""<!doctype html>
<html lang="ja" dir="ltr" class="client-nojs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - Grimoire Wiki 日本語訳</title>
<meta name="description" content="{esc(title)}{f'（{esc(en)}）' if sub else ''}。Grimoire ファン Wiki の日本語訳。">
<link rel="stylesheet" href="wiki.css">
<link rel="license" href="https://creativecommons.org/licenses/by-nc-sa/4.0/">
</head>
<body class="mediawiki ltr sitedir-ltr ns-0 ns-subject skin-vector action-view">
<header class="jpn" id="jpn"><div class="jpn-band"><a class="jpn-home" href="https://higesho.github.io/ja/">日本語化プロジェクト</a></div></header>
<script src="https://higesho.github.io/ja/nav.js"></script>
<div id="mw-page-base" class="noprint"></div>
<div id="mw-head-base" class="noprint"></div>
<div id="content" class="mw-body" role="main">
<a id="top"></a>
<h1 id="firstHeading" class="firstHeading" lang="ja">{esc(title)}{sub}</h1>
<div id="bodyContent" class="mw-body-content">
<div id="siteSub">出典: Grimoire : Heralds of the Winged Exemplar Wiki</div>
<div id="contentSub"></div>
<div id="mw-content-text" lang="ja" dir="ltr" class="mw-content-ltr">
{body}
</div>
<div class="visualClear"></div>
</div>
</div>
<div id="mw-navigation">
<h2>案内</h2>
<div id="mw-head">
<div id="left-navigation">
<div id="p-namespaces" role="navigation" class="vectorTabs">
<h3>名前空間</h3>
<ul><li id="ca-nstab-main" class="selected"><span><a href="#top">ページ</a></span></li></ul>
</div>
</div>
<div id="right-navigation">
<div id="p-views" role="navigation" class="vectorTabs">
<h3>表示</h3>
<ul><li id="ca-view" class="selected"><span><a href="#top">閲覧</a></span></li>{orig_tab}</ul>
</div>
</div>
</div>
<div id="mw-panel">
<div id="p-logo" role="banner"><a class="mw-wiki-logo" href="index.html" title="メインページ"></a></div>
<div class="portal" role="navigation" id="p-navigation">
<h3>案内</h3>
<div class="body"><ul>
<li><a href="index.html">メインページ</a></li>
<li><a href="all.html">記事一覧</a></li>
<li><a href="../index.html">日本語化パッチ</a></li>
<li><a href="{SITE}index.php/Main_Page.html">元の英語版 Wiki</a></li>
</ul></div>
</div>
<div class="portal" role="navigation" id="p-tb">
<h3>ツール</h3>
<div class="body"><ul>
{orig_tool}<li><a href="license.html">ライセンス</a></li>
</ul></div>
</div>
</div>
</div>
<div id="footer" role="contentinfo">
<ul id="footer-info">
{lastmod}
<li id="footer-info-copyright">Grimoire ファン Wiki の記事の日本語訳です。内容は <a class="external" href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ja">クリエイティブ・コモンズ 表示-非営利-継承</a>（CC BY-NC-SA 4.0）で利用できます。ゲームの用語は日本語化パッチの訳語に合わせました。</li>
<li>非公式のファン翻訳です。Grimoire: Heralds of the Winged Exemplar &copy; Cleveland Mark Blakemore / Golden Era Enterprise。記事の画像は元の Wiki のものを表示しています。</li>
</ul>
<ul id="footer-places">
<li><a href="license.html">ライセンス</a></li>
<li><a href="../index.html">日本語化パッチ</a></li>
</ul>
<ul id="footer-icons" class="noprint">
<li id="footer-copyrightico"><a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ja"><img src="https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png" alt="CC BY-NC-SA 4.0" width="88" height="31"></a></li>
</ul>
<div style="clear:both"></div>
</div>
</body>
</html>
"""


def last_edited(raw):
    m = re.search(r'This page was last edited on (\d+) (\w+) (\d{4})', raw)
    return f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}' if m else ''


def load_titles():
    t = {}
    if os.path.isdir(TITLES):
        for f in sorted(os.listdir(TITLES)):
            lines = open(os.path.join(TITLES, f), encoding='utf-8').read().strip().splitlines()
            if len(lines) >= 2:
                t[os.path.splitext(f)[0]] = lines[1].strip()
    return t


def rewrite(body, done, images, out_img):
    def img_url(src):
        return urllib.parse.urljoin(BASE, src)

    srcs = {}

    def src(m):
        u = img_url(m.group(1))
        if images == 'local':
            name = urllib.parse.unquote(u.rsplit('/', 1)[1])
            srcs[name] = u
            return f'src="img/{name}"'
        return f'src="{u}" loading="lazy"'
    body = re.sub(r'src="(\.\./images/[^"]+)"', src, body)
    if images == 'none':
        body = re.sub(r'<a href="File_[^"]*" class="image">\s*<img[^>]*>\s*</a>', '', body)
        body = re.sub(r'<img[^>]*>', '', body)

    # 画像の説明ページ（File_*.html）は保存版に無いので、画像そのものへつなぐ
    by_stem = {}
    for u in re.findall(r'src="([^"]+)"', body):
        by_stem[os.path.splitext(urllib.parse.unquote(u.rsplit('/', 1)[-1]))[0].replace(' ', '_').lower()] = u

    def file_link(m):
        stem = os.path.splitext(urllib.parse.unquote(m.group(1))[5:])[0].replace(' ', '_').lower()
        target = by_stem.get(stem)
        return f'href="{target}"' if target else m.group(0)
    body = re.sub(r'href="(File_[^"]+)"', file_link, body)

    def href(m):
        t = m.group(1)
        if t.startswith(('#', 'http:', 'https:', 'mailto:', 'img/')):
            return m.group(0)
        path, _, frag = t.partition('#')
        frag = '#' + frag if frag else ''
        stem = os.path.splitext(urllib.parse.unquote(path))[0]
        stem = ALIASES.get(stem, stem)
        if stem in done:
            return f'href="{done[stem]}{frag}"'
        return f'href="{urllib.parse.urljoin(BASE, path)}{frag}" data-untr="1"'
    body = re.sub(r'href="([^"]*)"', href, body)
    if out_img is not None:
        out_img.update(srcs)
    return body


def fetch_images(srcs, out):
    os.makedirs(out, exist_ok=True)
    cache = os.path.join(HERE, 'work', 'img')
    os.makedirs(cache, exist_ok=True)
    for name, u in sorted(srcs.items()):
        c = os.path.join(cache, name)
        if not os.path.exists(c):
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Grimoire Japanese wiki translation)'})
            open(c, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
        shutil.copyfile(c, os.path.join(out, name))


def top_page(repo):
    rel = f'https://github.com/{repo}/releases/latest'
    shots = []
    for f, cap in SHOTS:
        if os.path.exists(os.path.join(ROOT, 'screenshots', f)):
            shots.append(f'<figure><img src="img/{f}" alt="{esc(cap)}の画面（日本語化後）" loading="lazy">'
                         f'<figcaption>{esc(cap)}</figcaption></figure>')
    return f"""<section class="hero">
<h1>Grimoire: Heralds of the Winged Exemplar 日本語化パッチ</h1>
<p class="tag">Steam 版 Grimoire（3.0.0.0-R）を日本語で遊べるようにする、非公式のファンメイドパッチです。
ゲームのフォルダにファイルを置くだけで日本語になり、消せば英語に戻ります。</p>
<p><a class="dl" href="{rel}">ダウンロード（GitHub）</a><a class="dl sub" href="wiki/index.html">Wiki 翻訳を読む</a></p>
</section>
<div class="manual">
<h2>入れ方</h2>
<ol>
<li>Steam のライブラリでゲームを右クリックし、「管理」→「ローカルファイルを閲覧」でゲームのフォルダ（Grimoire.exe があるフォルダ）を開きます。</li>
<li>ダウンロードした zip の中身（<code>version.dll</code>、<code>grimjp.ini</code>、<code>grimjp</code> フォルダ）を、ゲームのフォルダにそのままコピーします。</li>
<li>ゲームを起動します。初めての起動のときだけ、日本語版のデータ（約 80MB）を <code>grimjp\\cache</code> に作ります。数秒かかることがあります。</li>
</ol>
<p>元のゲームのファイル（Grimoire.exe や BUNDLE-Z.RSF）は書き換えません。配布物に原作のデータは入っていません。</p>
<h2>外し方</h2>
<p>ゲームのフォルダから <code>version.dll</code>、<code>grimjp.ini</code>、<code>grimjp.log</code>、<code>grimjp</code> フォルダを消すと、英語版に戻ります。</p>
<h2>遊ぶときの注意</h2>
<ul>
<li>NPC への質問は、原作どおり英単語で打ち込みます。会話の中では「黒の魔導士（LICH）」のように、尋ねられる英単語を添えています。</li>
<li>一部の狭い一覧（状態異常・耐性の小さな文字）は、日本語が入りきらないため英語のままです。</li>
<li>戦闘で出る魔物の名前は、ゲームの文字数の制限に合わせて短くしたものがあります（例：ヴァンガード兵 → 前衛兵）。</li>
<li>「日本語化データを使えませんでした」と出たときは、ゲームの版が違うかファイルが壊れています。英語のまま起動するので、Steam で「ゲームファイルの整合性を確認」をしてから試してください。</li>
</ul>
<h2>画面</h2>
</div>
<div class="shots">
{''.join(shots)}
</div>
<div class="manual">
<h2>更新履歴</h2>
<ul>
<li>v1.2（2026-11-29）: 呪文選択画面の系統ボタンで、火・風・水・地・精の5つが英語で出ていたのを直しました（Issue #1）。ボタンの1文字が重ならないよう、大地は「地」、地獄は「獄」と表示します。</li>
<li>v1.1（2026-11-24）: ウイルス対策ソフトに誤検知されにくいよう、配布版に不要だった試験用のコードを外し、DLL にバージョン情報を入れました。訳文は前の版と同じです。</li>
<li>v1.0（2026-11-06）: 最初の版</li>
</ul>
<h2>翻訳について</h2>
<p>本文の翻訳には AI（Anthropic 社の Claude）を使い、約 3,700 語の用語集で名前や用語を揃えています。
誤訳や不自然な訳が残っているかもしれません。気づいたことは <a href="https://github.com/{repo}/issues">GitHub の Issues</a> で教えてください。</p>
<h2>ライセンス・クレジット</h2>
<ul>
<li>小さい文字の表示に美咲フォント（Copyright &copy; 2002-2021 Num Kadoma）を使っています。そのほかの文字は Windows の MS ゴシックで表示します。</li>
<li>Wiki 翻訳は、Grimoire ファン Wiki の記事の日本語訳で、CC BY-NC-SA 4.0 で公開しています。</li>
<li>このパッチの使用は自己責任でお願いします。</li>
</ul>
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'site'))
    ap.add_argument('--repo', default='higesho/grimoire-ja')
    ap.add_argument('--images', choices=('remote', 'local', 'none'), default='remote')
    a = ap.parse_args()
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    out, wout = a.out, os.path.join(a.out, 'wiki')
    os.makedirs(wout, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, 'assets', 'grimoire.css'), os.path.join(out, 'grimoire.css'))
    titles = load_titles()
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(JA) if f.endswith('.html'))
    done = {n: ('index.html' if n == 'Main_Page' else n + '.html') for n in names}
    srcs = {}
    rows = []
    main_body, main_meta = '', ('', '')
    shutil.copyfile(os.path.join(HERE, 'assets', 'wiki.css'), os.path.join(wout, 'wiki.css'))
    for n in names:
        raw = open(os.path.join(RAW, n + '.html'), encoding='utf-8', errors='replace').read()
        en = html.unescape(re.search(r'<h1 id="firstHeading"[^>]*>(.*?)</h1>', raw, re.S).group(1)).strip()
        ja = titles.get(n, en)
        body = rewrite(open(os.path.join(JA, n + '.html'), encoding='utf-8').read(), done, a.images, srcs)
        edited = last_edited(raw)
        orig = f'{BASE}{urllib.parse.quote(n)}.html'
        if n == 'Main_Page':
            main_body, main_meta = body, (edited, orig)
            continue
        note = (f'<div class="jp-note">Grimoire ファン Wiki の記事「<a href="{orig}">{esc(en)}</a>」の日本語訳です。'
                f'原文は 2019 年ごろの版（V2）について書かれていて、今の版（3.0）とは違うところがあるかもしれません。</div>')
        open(os.path.join(wout, n + '.html'), 'w', encoding='utf-8', newline=NL).write(
            wiki_page(ja, en, note + NL + body, edited, orig))
        rows.append((ja, en, n))
    items = ''.join(f'<li><a href="{n}.html">{esc(ja)}</a>' + (f'（{esc(en)}）' if ja != en else '')
                    + '</li>' for ja, en, n in sorted(rows))
    allp = f'<p>日本語に訳した記事の一覧です（{len(rows)} 本）。</p>{NL}<ul>{NL}{items}{NL}</ul>'
    open(os.path.join(wout, 'all.html'), 'w', encoding='utf-8', newline=NL).write(wiki_page('記事一覧', '', allp))
    lead = (f'<div class="jp-note">Grimoire ファン Wiki（<a href="{SITE}index.php/Main_Page.html">grimoirewiki.neocities.org</a>）を'
            f'日本語に訳したものです。ゲームの用語は日本語化パッチの訳語に合わせています。'
            f'まだ訳していないページへのリンクは英語版につながります。</div>')
    if main_body:
        idx = wiki_page('メインページ', 'Main Page', lead + NL + main_body, *main_meta)
    else:
        idx = wiki_page('メインページ', '', lead + NL + allp)
    open(os.path.join(wout, 'index.html'), 'w', encoding='utf-8', newline=NL).write(idx)
    lic = f"""<p>この Wiki 翻訳は、Grimoire ファン Wiki（<a href="{SITE}index.php/Main_Page.html">grimoirewiki.neocities.org</a>）の記事を日本語に訳したものです。
元の Wiki は <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">クリエイティブ・コモンズ 表示 - 非営利 - 継承 4.0 国際（CC BY-NC-SA 4.0）</a>で公開されているので、
この翻訳も同じライセンスで公開しています。</p>
<ul>
<li>原著作者: Grimoire ファン Wiki の寄稿者のみなさん（各記事の先頭と「英語版」のタブに、元の記事へのリンクがあります）</li>
<li>変更: 英語から日本語に翻訳し、ゲームの用語を日本語化パッチの訳語に置き換えました。リンク先を翻訳のページに変えています。</li>
<li>ライセンスの内容: <a href="{LICENSE_URL}">CC BY-NC-SA 4.0 の説明（日本語）</a>・<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.ja">利用許諾の全文（日本語）</a></li>
</ul>
<p>記事の中の画像（ゲームの画面・肖像・地図など）と左上のロゴは、元の Wiki のサーバーにあるものを表示しています。
ゲームの画像やゲームの文章の著作権は、原作の権利者（Cleveland Mark Blakemore / Golden Era Enterprise）にあります。</p>
<p>ページの見た目には、元の Wiki と同じ MediaWiki（GPL-2.0-or-later）の Vector のスタイルシートを使っています。</p>"""
    open(os.path.join(wout, 'license.html'), 'w', encoding='utf-8', newline=NL).write(wiki_page('ライセンス', '', lic))
    # 紹介ページ
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    for f, _ in SHOTS:
        p = os.path.join(ROOT, 'screenshots', f)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(out, 'img', f))
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8', newline='\n').write(
        page('日本語化パッチ', 'Grimoire: Heralds of the Winged Exemplar の非公式日本語化パッチと、ファン Wiki の日本語訳。',
             top_page(a.repo), 'index.html', 0))
    open(os.path.join(out, '.nojekyll'), 'w').close()
    if a.images == 'local':
        fetch_images(srcs, os.path.join(wout, 'img'))
    print(f'{out}: 記事 {len(rows)} 本' + ('、トップページあり' if main_body else '') + f'、画像 {a.images}')


if __name__ == '__main__':
    main()
