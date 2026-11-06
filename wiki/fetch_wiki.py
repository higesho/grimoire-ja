"""Grimoire ファン Wiki（grimoirewiki.neocities.org、静的な保存版）の記事を取り込む。

  python wiki/fetch_wiki.py            （_jp_work から。wiki/raw/ に保存、取得済みは飛ばす）

記事は index.php/<名前>.html。特殊ページ・編集・履歴・トークのリンクはたどらない。
画像（File_*.html の先の実ファイル）は取らず、記事の HTML だけを取る。
"""
import os, re, sys, time, urllib.parse, urllib.request

BASE = 'https://grimoirewiki.neocities.org/index.php/'
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
UA = 'Mozilla/5.0 (Grimoire Japanese wiki translation; polite crawler)'
SKIP = re.compile(r'^(Special_|Talk_|User_|User_talk_|Grimoire_Talk|MediaWiki_|Template_talk)', re.I)


def get(name):
    u = BASE + urllib.parse.quote(name)
    req = urllib.request.Request(u, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=60).read()


def links(html):
    out = set()
    for h in re.findall(r'href="([^"#?]+\.html)"', html):
        if '/' in h or h.startswith('..') or ':' in h:
            continue
        h = urllib.parse.unquote(h.replace('&amp;', '&'))
        if not SKIP.match(h):
            out.add(h)
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    todo, seen, fails = ['Main_Page.html'], {'Main_Page.html'}, []
    while todo:
        name = todo.pop(0)
        path = os.path.join(RAW, name)
        if os.path.exists(path):
            data = open(path, 'rb').read()
        else:
            try:
                data = get(name)
            except Exception as e:
                fails.append((name, str(e)))
                print('FAIL', name, e, flush=True)
                continue
            open(path, 'wb').write(data)
            time.sleep(0.7)
        for l in sorted(links(data.decode('utf-8', 'replace'))):
            if l not in seen:
                seen.add(l)
                todo.append(l)
        print(len(seen) - len(todo), '/', len(seen), name, flush=True)
    print('done:', len(seen) - len(fails), 'pages,', len(fails), 'failed')
    with open(os.path.join(HERE, 'fetch_fail.txt'), 'w', encoding='utf-8') as f:
        for n, e in fails:
            f.write(f'{n}\t{e}\n')


if __name__ == '__main__':
    main()
