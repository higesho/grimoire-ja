"""訳した記事を元の記事と比べて調べる。

  python wiki/check_ja.py [名前 ...]     （省略すると全部。_jp_work から）

調べること: タグの種類ごとの数、href/src/id の集合、英語が多く残った文字の塊、題の訳の有無。
"""
import collections, glob, html, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'work', 'src')
JA = os.path.join(HERE, 'ja')
TITLES = os.path.join(HERE, 'work', 'titles')


def tags(h):
    return collections.Counter(re.findall(r'<(/?[a-zA-Z][a-zA-Z0-9]*)', h))


def attrs(h, a):
    return collections.Counter(re.findall(a + r'="([^"]*)"', h))


def english_runs(h):
    out = []
    h = re.sub(r'<pre>.*?</pre>', '', h, flags=re.S)
    for t in re.split(r'<[^>]+>', h):
        t = html.unescape(t).strip()
        words = re.findall(r'[A-Za-z]{3,}', t)
        if len(words) >= 6 and not re.search(r'[぀-ヿ一-鿿]', t):
            out.append(t[:80])
    return out


def check(name):
    sp, jp = os.path.join(SRC, name + '.html'), os.path.join(JA, name + '.html')
    if not os.path.exists(jp):
        return [f'{name}: 訳がまだ無い']
    s, j = open(sp, encoding='utf-8').read(), open(jp, encoding='utf-8').read()
    msgs = []
    ts, tj = tags(s), tags(j)
    for k in sorted(set(ts) | set(tj)):
        if ts[k] != tj[k]:
            msgs.append(f'{name}: タグ <{k}> の数が違う（元 {ts[k]}、訳 {tj[k]}）')
    for a in ('href', 'src', 'id'):
        if attrs(s, a) != attrs(j, a):
            d = (attrs(s, a) - attrs(j, a)) + (attrs(j, a) - attrs(s, a))
            msgs.append(f'{name}: {a} が変わった: {list(d)[:5]}')
    for t in english_runs(j):
        msgs.append(f'{name}: 英語のまま? 「{t}」')
    if not os.path.exists(os.path.join(TITLES, name + '.txt')):
        msgs.append(f'{name}: 題の訳（work/titles/{name}.txt）が無い')
    return msgs


def main(names):
    sys.stdout.reconfigure(encoding='utf-8')
    if not names:
        names = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(SRC, '*.html')))
    bad = 0
    for n in names:
        for m in check(n):
            print(m)
            bad += 1
    print('問題なし' if not bad else f'{bad} 件')


if __name__ == '__main__':
    main(sys.argv[1:])
