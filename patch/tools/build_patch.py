"""Rebuild the whole Japanese patch folder from the work files.

  python tools/build_patch.py [patch_dir]        (default: patch_jp; run from _jp_work)

1. chunks/out  -> <patch>/TXT, <patch>/NTX        (chunks.py collect)
2. glossary    -> MASTER term lists + GPC titles  (glossary.py apply)
   + glossary/monster_short.tsv: short monster names (the game cuts names to 20/14 bytes)
3. dbwork/gpc_desc.txt   -> <patch>/DBS/GPC.DBS.txt (descriptions; 3 slots of binary junk are skipped)
4. dbwork/mlb_part1-5    -> <patch>/DBS/NPCWORDS.MLB.txt
5. images                -> <patch>/IMG              (make_images.py)
Then install with install_test.bat <patch_dir>.
"""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GPC_SKIP = {'11184:78:space', '11304:78:space', '11424:78:space'}


def run(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


# byte limits of the name fields of a @MONSTERS line: name, plural, unidentified, unidentified plural
# (20/14 are the game's own cuts; 30/21 are the raised limits patched by the DLL for list modes)
NAME_LIMITS = (20, 30, 14, 21)


def apply_monster_short(patch):
    import glossary
    short = {}
    for line in open('glossary/monster_short.tsv', encoding='utf-8'):
        if line.startswith('#') or '\t' not in line:
            continue
        long_, sh = line.rstrip('\n').split('\t')[:2]
        short[long_] = sh
    rows, sec = glossary.master_rows('extracted')
    en = dict(rows)
    p = os.path.join(patch, 'TXT', 'MASTER.TXT.txt')
    lines = open(p, encoding='utf-8').read().split('\n')
    n = 0
    over = []
    for i, l in enumerate(lines):
        if '\t' not in l:
            continue
        num, text = l.split('\t', 1)
        if sec.get(num, '').lstrip('@') != 'MONSTERS' or text.startswith('@'):
            continue
        fields = text.split(',')
        for k, f in enumerate(fields[:4]):
            pre, core, post = glossary.split_field(f)
            if core in short:
                fields[k] = pre + short[core] + post
        new = ','.join(fields)
        if new != text:
            lines[i] = num + '\t' + new
            n += 1
        ef = en.get(num, '').split(',')
        for k, lim in enumerate(NAME_LIMITS):
            if k >= len(fields) or k >= len(ef) or fields[k] == '*':
                continue
            nb = len(fields[k].encode('utf-8'))
            if nb > lim and len(ef[k]) <= lim:      # lines too long in English as well are puzzles: skip
                over.append(f'{num} field {k}: {fields[k]} ({nb} > {lim} bytes)')
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print(f'monster short names: {n} lines')
    for o in over:
        print('  WARNING name too long:', o)


def main(patch='patch_jp'):
    os.chdir(ROOT)
    if os.path.isdir(patch):
        shutil.rmtree(patch)
    run('tools/chunks.py', 'collect', 'extracted', 'chunks', patch)
    run('tools/glossary.py', 'apply', 'extracted', 'glossary/terms.tsv', patch)
    apply_monster_short(patch)
    desc = {}
    for line in open('dbwork/gpc_desc.txt', encoding='utf-8').read().split('\n'):
        if '\t' in line:
            k, v = line.split('\t', 1)
            if k not in GPC_SKIP and v.strip():
                desc[k] = v
    p = os.path.join(patch, 'DBS', 'GPC.DBS.txt')
    lines = open(p, encoding='utf-8').read().split('\n')
    lines = [(l.split('\t', 1)[0] + '\t' + desc[l.split('\t', 1)[0]]) if '\t' in l and l.split('\t', 1)[0] in desc else l
             for l in lines]
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    mlb = []
    for i in range(1, 6):
        mlb += [l for l in open(f'dbwork/mlb_part{i}.txt', encoding='utf-8').read().split('\n') if l.strip()]
    open(os.path.join(patch, 'DBS', 'NPCWORDS.MLB.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(mlb) + '\n')
    run('tools/make_images.py', patch)
    print('patch rebuilt:', patch)


if __name__ == '__main__':
    main(*sys.argv[1:])
