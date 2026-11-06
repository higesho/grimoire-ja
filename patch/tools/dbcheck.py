"""Self-check of the translated DBS work files (dbwork/).

  python tools/dbcheck.py mlb dbwork/mlb_part1.txt     NPCWORDS.MLB answers (VERBOSE / BRIEF)
  python tools/dbcheck.py gpc dbwork/gpc_desc.txt      GPC.DBS vocation / skill descriptions (<= 78 bytes)

Compares each line with extracted/DBS/<file>.txt: same keys in the same order, same placeholders
([sub] [pag] <B> ...), no line left in English, and for GPC the UTF-8 byte limit.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(os.path.dirname(HERE), 'extracted', 'DBS')
PH = re.compile(r'\[[a-z]{3}\]|<[A-Z]{1,2}>')
JA = re.compile(r'[぀-ヿ一-鿿]')


def table(path):
    out = []
    for line in open(path, encoding='utf-8').read().split('\n'):
        if line.startswith('#') or '\t' not in line:
            continue
        k, v = line.split('\t', 1)
        out.append((k, v))
    return out


def main():
    kind, path = sys.argv[1], sys.argv[2]
    src = dict(table(os.path.join(EX, 'NPCWORDS.MLB.txt' if kind == 'mlb' else 'GPC.DBS.txt')))
    rows = table(path)
    probs = []
    for k, v in rows:
        if k not in src:
            probs.append(f'{k}: key not in the source'); continue
        en = src[k]
        if sorted(PH.findall(en)) != sorted(PH.findall(v)):
            probs.append(f'{k}: placeholders {sorted(PH.findall(en))} -> {sorted(PH.findall(v))}')
        if en.strip() and not JA.search(v):
            probs.append(f'{k}: not translated (no Japanese)')
        if kind == 'gpc':
            mx = int(k.split(':')[1])
            n = len(v.encode('utf-8'))
            if n > mx:
                probs.append(f'{k}: {n} bytes > {mx} (全角は1文字3バイト。全角{mx // 3}文字まで)')
        if kind == 'mlb' and en.count('[pag]') != v.count('[pag]'):
            probs.append(f'{k}: [pag] count {en.count("[pag]")} -> {v.count("[pag]")}')
    want = [l.split('\t', 1)[0] for l in open(path, encoding='utf-8') if '\t' in l and not l.startswith('#')]
    print(f'{os.path.basename(path)}: {len(rows)} lines, {len(probs)} problem(s)')
    for p in probs:
        print('PROBLEM', p)
    sys.exit(1 if probs else 0)


if __name__ == '__main__':
    main()
