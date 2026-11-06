"""取り込んだ記事から本文を抜き出し、記事ごとの用語表を作る。

  python wiki/prepare.py        （_jp_work から）

出力
  wiki/work/src/<名前>.html   本文の HTML（編集リンク・コメントを除いたもの）
  wiki/work/gloss/<名前>.tsv  その記事に出てくる用語「英語<TAB>日本語版の訳<TAB>区分」
  wiki/work/meta.tsv          名前<TAB>元の題<TAB>最終更新<TAB>語数
"""
import glob, html, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, 'raw')
WORK = os.path.join(HERE, 'work')
# 中身の無いページと、同じ記事の別名（Classes は Professions への転送）
SKIP = {'Grimoire_About', 'Grimoire_General_disclaimer', 'Grimoire_Privacy_policy', 'Classes'}
# 用語表に入れない区分（一般語が多い・ゲーム内の出所が文脈依存）
CAT_SKIP = {'name?', 'title'}


def body_of(h):
    i = h.index('<div id="mw-content-text"')
    i = h.index('>', i) + 1
    j = h.index('<div class="printfooter">', i)
    b = h[i:j]
    b = re.sub(r'<!--.*?-->', '', b, flags=re.S)
    b = re.sub(r'<span class="mw-editsection">.*?</span>\s*</span>', '', b, flags=re.S)
    b = b.strip()
    if b.endswith('</div>'):
        b = b[:-6].rstrip()
    return b


def load_terms():
    terms = {}
    for line in open(os.path.join(ROOT, 'glossary', 'terms.tsv'), encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if len(f) < 3 or f[0] == 'cat' or f[0] in CAT_SKIP or not f[2]:
            continue
        en = f[1].strip('"').replace('~', '').strip()
        if len(en) < 3:
            continue
        terms.setdefault(en.lower(), (en, f[2], f[0]))
    return terms


def main():
    os.makedirs(os.path.join(WORK, 'src'), exist_ok=True)
    os.makedirs(os.path.join(WORK, 'gloss'), exist_ok=True)
    terms = load_terms()
    meta = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.html'))):
        name = os.path.splitext(os.path.basename(p))[0]
        if name in SKIP:
            continue
        h = open(p, encoding='utf-8', errors='replace').read()
        title = html.unescape(re.search(r'<h1 id="firstHeading"[^>]*>(.*?)</h1>', h, re.S).group(1))
        m = re.search(r'This page was last edited on ([^,<]+)', h)
        b = body_of(h)
        open(os.path.join(WORK, 'src', name + '.html'), 'w', encoding='utf-8', newline='\n').write(b + '\n')
        text = html.unescape(re.sub(r'<[^>]+>', ' ', b))
        low = ' ' + re.sub(r'\s+', ' ', text.lower()) + ' '
        hits = []
        for k, (en, ja, cat) in terms.items():
            if re.search(r'(?<![a-z])' + re.escape(k) + r'(?:s|es)?(?![a-z])', low):
                hits.append((en, ja, cat))
        hits.sort(key=lambda t: (t[2], t[0].lower()))
        with open(os.path.join(WORK, 'gloss', name + '.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            for en, ja, cat in hits:
                f.write(f'{en}\t{ja}\t{cat}\n')
        meta.append((name, title.strip(), m.group(1).strip() if m else '', len(text.split()), len(hits)))
    with open(os.path.join(WORK, 'meta.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for r in meta:
            f.write('\t'.join(map(str, r)) + '\n')
            print(*r, sep='\t')


if __name__ == '__main__':
    main()
