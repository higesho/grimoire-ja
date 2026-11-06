"""Build grimjp/tiny_fallback.txt: translated text -> original English for strings that the
game draws in its 5px font inside 5px-spaced lists (Japanese cannot fit there).

Usage: python make_fallback.py <extracted_dir> <patch_dir> <out_txt>
"""
import os, sys

# (file, section) pairs whose entries are drawn in tight 5px lists
TINY_SECTIONS = [('TXT/MASTER.TXT.txt', '@CONDITIONS'), ('TXT/MASTER.TXT.txt', '@RESISTANCES')]


def read(path):
    out = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if '\t' in line:
                    k, v = line.split('\t', 1)
                    out[int(k)] = v
    return out


def main(src, patch, dst):
    pairs = {}
    for rel, sec in TINY_SECTIONS:
        orig = read(os.path.join(src, rel)); tr = read(os.path.join(patch, rel))
        inside = False
        for i in sorted(orig):
            t = orig[i]
            if t.startswith('@'):
                inside = (t == sec)
                continue
            if inside and i in tr and tr[i] != t:
                pairs[tr[i]] = t
    # The game cuts these labels to 6 or 9 bytes (2 or 3 Japanese chars). The DLL then
    # matches by prefix, so translations must stay unique within their first 2 / 3 chars.
    for nchars in (2, 3):
        seen = {}
        for k, v in pairs.items():
            p = k[:nchars]
            if len(k) > nchars and p in seen and seen[p] != v:
                print(f'WARNING: "{k}" ({v}) and another entry ({seen[p]}) share the first {nchars} chars "{p}"')
            seen.setdefault(p, v)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        for k, v in pairs.items():
            f.write(f'{k}\t{v}\n')
    print(f'{len(pairs)} fallback entries -> {dst}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
