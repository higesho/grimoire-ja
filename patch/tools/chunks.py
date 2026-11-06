"""Split the game text into translation chunks and collect the translations back.

  python chunks.py make    <extracted_dir> <glossary.tsv> <chunk_dir> [chars_per_chunk]
  python chunks.py check   <extracted_dir> <chunk_dir> <chunk_id>     (self-check of one translated chunk)
  python chunks.py collect <extracted_dir> <chunk_dir> <patch_dir>

make writes <chunk_dir>/src/NNNN_<FILE>.txt. A translator writes <chunk_dir>/out/NNNN_<FILE>.txt with
the same '### ' header lines, each followed by the Japanese text.

Segments
  block segment  (GAMETEXT, ID, SUPERID, RACEENCY, STORY, NPC dialogue): the English lines between
                 control lines (@..., [pag], [new]) are one paragraph that the game shows line by line.
                 Header: '### FILE START L<n> W<w>'. The translation is written as one paragraph; collect
                 re-wraps it into the same n lines at width w (full-width char = 2). Several lines under
                 the header force those line breaks (poems, lists).
  line segment   (MASTER, SPELLTXT, RACEDESC, LOCKHINT, CREDITS, REGO): one string = one entry.
                 Header: '### FILE NUM'. Long lines are wrapped by the game itself.
Lines in English-only sections (policy 'keep') and the term lists filled from the glossary are skipped.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy, glossary, jptext

BLOCK_FILES = {'GAMETEXT.TXT', 'ID.TXT', 'SUPERID.TXT', 'RACEENCY.TXT', 'STORY.LST'}
TERM_SECTIONS = set(glossary.LIST_SECTIONS) | set(glossary.CSV_TERM_SECTIONS)
TAG_RE = re.compile(r'^(<[A-Z]{1,2}>)')
PH_W = {'[npc]': 10, '[sub]': 10, '[tgt]': 10, '[itm]': 12, '[des]': 12, '[tag]': 8, '[gpc]': 10,
        '[act]': 8, '[sal]': 8, '[num]': 3, '[val]': 3}
CONTROL = re.compile(r'^(@\S*|\[pag\]|\[new\]|\*[A-Z]+|<[A-Z]{1,2}>)$')
MIN_W = 34
# glossary categories offered as hints (common-word categories such as condition/resistance/title are
# left out: words like 'System' or 'Saint' in running text are usually not the term)
HINT_CATS = {'race', 'vocation', 'npc', 'place', 'patron', 'party', 'name?', 'spell', 'skill', 'attribute',
             'item', 'monster', 'monster_unid'}


def is_block_file(fn):
    base = fn[:-4] if fn.endswith('.txt') else fn     # accepts 'GAMETEXT.TXT' and 'GAMETEXT.TXT.txt'
    return base in BLOCK_FILES or base.startswith('NPC')


def segments(fn, rows):
    """-> list of dict(start, nums, en_lines, tag, block)"""
    sec = policy.sections(rows)
    out = []
    if not is_block_file(fn):
        for num, text in rows:
            s = sec.get(num, '')
            if (policy.kind(fn, s) == 'keep' or CONTROL.match(text) or not text.strip()
                    or (fn.startswith('MASTER') and s.lstrip('@') in TERM_SECTIONS)):
                continue
            out.append(dict(start=num, nums=[num], en=[text], tag='', block=False))
        return out
    cur = None
    for num, text in rows:
        tag = (TAG_RE.match(text) or [None, ''])[1] if TAG_RE.match(text) else ''
        if CONTROL.match(text) or not text.strip():
            cur = None
            continue
        if tag == '<H>':     # headings stand alone
            out.append(dict(start=num, nums=[num], en=[text[len(tag):]], tag=tag, block=True))
            cur = None
            continue
        if cur is None or cur['tag'] != tag:
            cur = dict(start=num, nums=[], en=[], tag=tag, block=True)
            out.append(cur)
        cur['nums'].append(num)
        cur['en'].append(text[len(tag):])
    return out


def seg_width(seg):
    return max(MIN_W, max(len(t) for t in seg['en']))


def load_npc_notes(gl):
    npcs = [(en, v) for (c, en), v in gl.items() if c == 'npc']
    return npcs


def cmd_make(ex, gpath, cdir, per=9000):
    gl = glossary.load_glossary(gpath)
    terms = [(en, v['ja']) for (c, en), v in gl.items() if v['ja'] and len(en) >= 3 and c in HINT_CATS]
    terms.sort(key=lambda t: -len(t[0]))
    pats = [(en, ja, glossary.word_re(en)) for en, ja in terms]
    npcs = load_npc_notes(gl)
    src = os.path.join(cdir, 'src')
    os.makedirs(src, exist_ok=True)
    os.makedirs(os.path.join(cdir, 'out'), exist_ok=True)
    n_chunk = 0
    total = 0
    index = []
    for typ in ('TXT', 'NTX'):
        for fn in sorted(os.listdir(os.path.join(ex, typ))):
            if not fn.endswith('.txt'):
                continue
            name = fn[:-4]
            if policy.kind(name, '') == 'keep':
                continue
            rows = glossary.read_table(os.path.join(ex, typ, fn))
            segs = segments(name, rows)
            if not segs:
                continue
            sec = policy.sections(rows)
            # group into chunks
            groups, cur, size = [], [], 0
            for sg in segs:
                ln = sum(len(t) for t in sg['en'])
                if cur and size + ln > per:
                    groups.append(cur); cur, size = [], 0
                cur.append(sg); size += ln
            if cur:
                groups.append(cur)
            for gi, grp in enumerate(groups):
                n_chunk += 1
                cid = f'{n_chunk:04d}_{name}'
                text_all = '\n'.join(t for sg in grp for t in sg['en'])
                hits = [(en, ja) for en, ja, rx in pats if rx.search(text_all)]
                with open(os.path.join(src, cid + '.txt'), 'w', encoding='utf-8', newline='\n') as f:
                    f.write(f'# {name}  part {gi + 1}/{len(groups)}\n')
                    if name.startswith('NPC'):
                        k = int(name[3:6])
                        if 1 <= k <= len(npcs):
                            en, v = npcs[k - 1]
                            f.write(f'# 話し手: {v["ja"]} ({en}) — {v["note"]}\n')
                    if hits:
                        f.write('# 用語（その名前として出てきたら必ずこの訳）: ' + ' / '.join(f'{en}={ja}' for en, ja in hits[:200]) + '\n')
                    f.write('\n')
                    last_sec = None
                    for sg in grp:
                        s = sec.get(sg['start'], '')
                        if not sg['block'] and s != last_sec and s:
                            f.write(f'# ---- section {s}\n')
                            last_sec = s
                        if sg['block']:
                            f.write(f"### {name} {sg['start']} L{len(sg['nums'])} W{seg_width(sg)}\n")
                            f.write(' '.join(t.strip() for t in sg['en']) + '\n\n')
                        else:
                            f.write(f"### {name} {sg['start']}\n{sg['en'][0]}\n\n")
                total += len(grp)
                index.append((cid, len(grp), sum(len(t) for sg in grp for t in sg['en'])))
    with open(os.path.join(cdir, 'index.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('chunk\tsegments\tchars\n')
        for r in index:
            f.write('\t'.join(map(str, r)) + '\n')
    print(f'{n_chunk} chunks, {total} segments -> {src}')


# ---------------------------------------------------------------- collect

TOKEN = re.compile(r'\[[a-z]{3}\]|<[A-Z]{1,2}>|[A-Za-z0-9\'\-+.,%/]+|.', re.S)
NO_START = jptext.NO_START
NO_END = jptext.NO_END


def tok_w(t):
    if t in PH_W:
        return PH_W[t]
    return jptext.width(t)


def is_hira(t):
    return len(t) == 1 and 'ぁ' <= t <= 'ゟ'


def wrap(text, w):
    """Greedy wrap of Japanese text to width w; ASCII words and placeholders are atomic."""
    toks = TOKEN.findall(text)
    lines, cur, cw = [], [], 0
    for t in toks:
        tw = tok_w(t)
        if cur and cw + tw > w:
            # kinsoku: do not start a line with NO_START -> pull it onto this line (small overflow)
            if t in NO_START:
                cur.append(t); cw += tw
                continue
            # prefer a natural break point within the last few characters:
            # after punctuation, or where hiragana is followed by kanji/katakana (a new word)
            carry = []
            best = None
            for k in range(len(cur) - 1, max(0, len(cur) - 7), -1):
                a, b = cur[k - 1], cur[k]
                if b in NO_START or a in NO_END:
                    continue
                if a in '、。！？!?」』）' or (is_hira(a) and not is_hira(b)) or b == ' ':
                    best = k
                    break
            if best:
                carry = cur[best:]
                cur = cur[:best]
            # do not end a line with NO_END -> move it to the next line
            while cur and cur[-1] in NO_END:
                carry.insert(0, cur.pop())
            line = ''.join(cur).rstrip()
            lines.append(line)
            cur = carry + ([] if t == ' ' else [t])
            cw = sum(tok_w(x) for x in cur)
        else:
            if not cur and t == ' ':
                continue
            cur.append(t); cw += tw
    if cur:
        lines.append(''.join(cur).rstrip())
    return lines


def parse_chunk(path):
    """-> list of (file, start, L, W, [text lines])"""
    out, cur = [], None
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('### '):
                p = line[4:].split()
                L = W = None
                for x in p[2:]:
                    if x.startswith('L'): L = int(x[1:])
                    if x.startswith('W'): W = int(x[1:])
                cur = [p[0], p[1], L, W, []]
                out.append(cur)
            elif line.startswith('#') and (cur is None or line.startswith(('# ---- section', '# 口調'))):
                continue    # comments: file header, section marks, voice notes; '# R.I.P. #' text inside a segment is kept
            elif cur is not None and line.strip():
                cur[4].append(line.strip() if cur[2] else line)
    return out


def placeholders(s):
    return sorted(re.findall(r'\[[a-z]{3}\]|<[A-Z]{1,2}>', s))


def cmd_check(ex, cdir, cid, show=False):
    """Self-check of one translated chunk (for translators). Exit code 1 when something is wrong."""
    cid = cid[:-4] if cid.endswith('.txt') else cid
    src = parse_chunk(os.path.join(cdir, 'src', cid + '.txt'))
    outp = os.path.join(cdir, 'out', cid + '.txt')
    if not os.path.exists(outp):
        sys.exit(f'no output file {outp}')
    out = {(f, s): lines for f, s, L, W, lines in parse_chunk(outp)}
    secmaps = {}
    probs = []
    gpath = os.path.join(os.path.dirname(os.path.abspath(cdir)), 'glossary', 'terms.tsv')
    pats = glossary.term_patterns(glossary.load_glossary(gpath)) if os.path.exists(gpath) else []
    for f, start, L, W, en_lines in src:
        en = ' '.join(en_lines)
        lines = out.get((f, start))
        if not lines:
            probs.append(f'{f} {start}: missing translation')
            continue
        ja = ''.join(lines) if L else ' '.join(lines)
        if ja.strip() == en.strip() and re.search(r'[a-z]{3}', en):
            probs.append(f'{f} {start}: not translated (same as English)')
        masked = en     # longest terms first; a shorter term inside a longer matched one is not checked again
        for ten, tja, rx in pats:
            m = rx.search(masked)
            if not m:
                continue
            if tja not in ja:
                probs.append(f'{f} {start}: term "{ten}" should be translated as "{tja}"')
            masked = rx.sub(lambda x: ' ' * len(x.group(0)), masked)
        if placeholders(en) != placeholders(ja):
            probs.append(f'{f} {start}: placeholders/tags {placeholders(en)} -> {placeholders(ja)}')
        if L:
            wrapped = []
            for ln in lines:
                wrapped += wrap(ln, W)
            if show:
                print(f'--- {f} {start}')
                for x in wrapped:
                    print('    ' + x)
            if len(wrapped) > L and len(wrap(''.join(lines), W + 4)) > L:
                probs.append(f'{f} {start}: too long: needs {len(wrapped)} lines of width {W}, only {L} available'
                             f' (shorten to about {L * W // 2} full-width chars)')
        else:
            if f not in secmaps:
                typ = 'NTX' if f.startswith('NPC') else 'TXT'
                rows = glossary.read_table(os.path.join(ex, typ, f + '.txt'))
                secmaps[f] = policy.sections(rows)
            use, level, msg = policy.check(f, secmaps[f].get(start, ''), en, ja)
            if level:
                probs.append(f'{f} {start}: {msg}')
            if f == 'RACEDESC.TXT' and jptext.width(ja) > 56:
                probs.append(f'{f} {start}: wider than 28 full-width chars (cut off on screen)')
    extra = set(out) - {(f, s) for f, s, *_ in src}
    for k in sorted(extra):
        probs.append(f'{k[0]} {k[1]}: segment not in the source chunk (header changed?)')
    for p in probs:
        print('PROBLEM', p)
    print(f'{cid}: {len(src)} segments, {len(probs)} problem(s)')
    sys.exit(1 if probs else 0)


def cmd_collect(ex, cdir, patch):
    srcs = {}
    for fn in os.listdir(os.path.join(cdir, 'src')):
        for f, start, L, W, lines in parse_chunk(os.path.join(cdir, 'src', fn)):
            srcs[(f, start)] = (L, W, ' '.join(lines))
    results = {}   # file -> {num: text}
    problems = []
    done = set()
    for fn in sorted(os.listdir(os.path.join(cdir, 'out'))):
        if not fn.endswith('.txt'):
            continue
        for f, start, L, W, lines in parse_chunk(os.path.join(cdir, 'out', fn)):
            key = (f, start)
            if key not in srcs:
                problems.append(f'{fn}: unknown segment {f} {start}')
                continue
            sL, sW, en = srcs[key]
            if not lines:
                continue
            done.add(key)
            ja = ''.join(lines) if sL else ' '.join(lines)
            if placeholders(en) != placeholders(ja):
                problems.append(f'{f} {start}: placeholders {placeholders(en)} != {placeholders(ja)}')
            res = results.setdefault(f, {})
            if not sL:                       # line segment
                res[start] = ' '.join(lines)
                continue
            if len(lines) > 1:               # forced breaks
                out = []
                for ln in lines:
                    out += wrap(ln, sW)
            else:
                out = wrap(lines[0], sW)
            if len(out) > sL:
                out2 = wrap(''.join(lines), sW + 4)
                if len(out2) <= sL:
                    out = out2
                else:
                    problems.append(f'{f} {start}: needs {len(out)} lines, has {sL} (last lines joined)')
                    out = out[:sL - 1] + [''.join(out[sL - 1:])]
            out += [''] * (sL - len(out))
            # map back to line numbers (consecutive)
            n0 = int(start)
            width_num = len(start)
            tagged = None
            for i, t in enumerate(out):
                num = f'{n0 + i:0{width_num}d}'
                res[num] = t
            res.setdefault('__tags__', []).append((start, sL))
    # write patch files (restore line tags such as <B>)
    n_lines = 0
    for f, res in results.items():
        typ = 'NTX' if f.startswith('NPC') else 'TXT'
        orig = glossary.read_table(os.path.join(ex, typ, f + '.txt'))
        odict = dict(orig)
        path = os.path.join(patch, typ, f + '.txt')
        existing = dict(glossary.read_table(path)) if os.path.exists(path) else {}
        for num, t in res.items():
            if num == '__tags__':
                continue
            m = TAG_RE.match(odict.get(num, ''))
            if m and t and not t.startswith(m.group(1)):
                t = m.group(1) + t
            existing[num] = t
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as fo:
            for num, _ in orig:
                if num in existing:
                    fo.write(f'{num}\t{existing[num]}\n'); n_lines += 1
    missing = [k for k in srcs if k not in done]
    for p in problems[:80]:
        print('PROBLEM', p)
    print(f'{len(done)} segments collected, {len(missing)} not translated yet, {len(problems)} problem(s), '
          f'{n_lines} lines written to {patch}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['make'] and len(a) in (4, 5):
        cmd_make(a[1], a[2], a[3], int(a[4]) if len(a) == 5 else 9000)
    elif a[:1] == ['check'] and len(a) in (4, 5):
        cmd_check(a[1], a[2], a[3], show=a[4:] == ['--show'])
    elif a[:1] == ['collect'] and len(a) == 4:
        cmd_collect(a[1], a[2], a[3])
    else:
        print(__doc__)
