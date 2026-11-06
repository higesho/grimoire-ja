"""英語の語句を、日本語化パッチの訳から探す。

  python wiki/lookup.py "Glowmoth" ["Shrill Sound" ...]    （_jp_work から）

glossary/terms.tsv と glossary/monster_short.tsv、それからゲームのテキスト表
（extracted/ の英語の行 → patch_jp/ の同じ番号の行）を、大文字小文字を区別せずに部分一致で探す。
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def table(path):
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8', errors='replace'):
            line = line.rstrip('\n')
            if '\t' in line:
                k, v = line.split('\t', 1)
                out[k] = v
    return out


def main(words):
    sys.stdout.reconfigure(encoding='utf-8')
    terms = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'glossary', 'terms.tsv'), encoding='utf-8')]
    tables = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'patch_jp', '*', '*.txt'))):
        rel = os.path.relpath(p, os.path.join(ROOT, 'patch_jp'))
        tables.append((rel, table(os.path.join(ROOT, 'extracted', rel)), table(p)))
    for w in words:
        lw = w.lower()
        print(f'== {w}')
        n = 0
        for f in terms:
            if len(f) >= 3 and lw in f[1].lower():
                print(f'  [用語 {f[0]}] {f[1]} → {f[2]}' + (f'  ({f[4]})' if len(f) > 4 and f[4] else ''))
                n += 1
                if n >= 15:
                    break
        m = 0
        for rel, en, ja in tables:
            for k, e in en.items():
                if lw in e.lower() and k in ja and ja[k] != e:
                    print(f'  [{rel} {k}] {e[:120]}\n      → {ja[k][:120]}')
                    m += 1
                    if m >= 8:
                        break
            if m >= 8:
                break
        if not n and not m:
            print('  （見つからない）')


if __name__ == '__main__':
    main(sys.argv[1:])
