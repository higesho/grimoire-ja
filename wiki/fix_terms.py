"""訳した記事の訳語をまとめて直す（何度かけてもよい）。

  python wiki/fix_terms.py        （_jp_work から）

- 武器の特性 *Lethal* は、日本語化パッチの画面の表示（dll/ui_strings.txt）どおり *致命* にする。
- モンスターの一覧（Monsters）は戦闘で出る名前に合わせ、glossary/monster_short.tsv の短い名前にする。
  ほかの記事は会話や説明文と同じ元の名前のまま（NPC の名前など）。
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JA = os.path.join(HERE, 'ja')

ALL = [('*Lethal*（致命）', '*致命*'), ('*LETHAL*', '*致命*'), ('*Lethal*', '*致命*')]
PER_FILE = {}


def monster_short():
    out = []
    for line in open(os.path.join(ROOT, 'glossary', 'monster_short.tsv'), encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and not line.startswith('#'):
            out.append((f[0], f[1]))
    return sorted(out, key=lambda t: -len(t[0]))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    PER_FILE['Monsters.html'] = monster_short()
    for p in sorted(glob.glob(os.path.join(JA, '*.html'))):
        name = os.path.basename(p)
        s = open(p, encoding='utf-8').read()
        t = s
        for a, b in ALL + PER_FILE.get(name, []):
            t = t.replace(a, b)
        if t != s:
            open(p, 'w', encoding='utf-8', newline='\n').write(t)
            print('直した:', name)


if __name__ == '__main__':
    main()
