"""Glossary (用語集) for consistent translation of names.

  python glossary.py extract <extracted_dir> <glossary.tsv>
      Collect term candidates (names of races, NPCs, places, spells, items, monsters, ...) from
      MASTER.TXT term-list sections and GPC.DBS, plus proper-noun candidates mined from the text.
      Existing translations (ja column) in glossary.tsv are kept.
  python glossary.py apply <extracted_dir> <glossary.tsv> <patch_dir>
      Write the term-list sections of MASTER.TXT (ITEMS, MONSTERS, SPELLS, ...) and the GPC titles
      from the glossary into patch_dir (merging with lines already translated there).
  python glossary.py merge <glossary.tsv> <part.tsv>...
      Fill the ja column from part files (cat<TAB>en<TAB>ja[<TAB>note]).
  python glossary.py check <extracted_dir> <glossary.tsv> <patch_dir>
      Report translated lines whose English contains a term but whose Japanese lacks the agreed
      translation, and terms whose Japanese is much wider than the English.

glossary.tsv columns: cat <TAB> en <TAB> ja <TAB> count <TAB> note
  count = occurrences of en in the game text (whole words); note = free comment / example.
"""
import os, re, sys, unicodedata
from collections import Counter, OrderedDict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy

# MASTER.TXT sections whose every line is a term (category name, field mode)
LIST_SECTIONS = OrderedDict([
    ('RACES', 'race'), ('NPCS', 'npc'), ('MAPLIST', 'place'), ('PATRONS', 'patron'),
    ('PARTIES', 'party'), ('ATTRIBUTES', 'attribute'), ('CONDITIONS', 'condition'),
    ('RESISTANCES', 'resistance'), ('SKILLS', 'skill'), ('SPELLBOOK', 'school'),
    ('PAGES', 'page'), ('SPELLS', 'spell'), ('MONSTYPE', 'monstype'), ('SUBTYPE', 'subtype'),
    ('ITEMCLASSES', 'itemclass'), ('ITEMTYPE', 'itemtype'), ('HOARDS', 'hoard'),
    ('SUPERMIX', 'container'), ('HITLOCS', 'hitloc'), ('TAROT', 'tarot'), ('LEGENDS', 'legend'),
])
CSV_TERM_SECTIONS = {'ITEMS': ('item', 'item_unid'),
                     'MONSTERS': ('monster', 'monster_pl', 'monster_unid', 'monster_unid_pl', 'monster_group')}
CAT_ORDER = (['race', 'vocation', 'title', 'npc', 'place', 'patron', 'party', 'name?']
             + [c for c in LIST_SECTIONS.values() if c not in ('race', 'npc', 'place', 'patron', 'party')]
             + ['item', 'item_unid', 'monster', 'monster_pl', 'monster_unid', 'monster_unid_pl', 'monster_group'])

FIELD_RE = re.compile(r'^(\s*\|?\s*"?)(.*?)("?\s*\|?\s*)$')


def split_field(f):
    """'"LACHESIS"' -> ('"', 'LACHESIS', '"'); '| Wicker Man' -> ('| ', 'Wicker Man', '')"""
    m = FIELD_RE.match(f)
    return m.group(1), m.group(2), m.group(3)


def is_term(t):
    return bool(t) and t not in ('*', '-', '?', '~') and not t.isdigit() and not t.startswith('@')


def read_table(path):
    with open(path, encoding='utf-8') as f:
        return [line.rstrip('\n').split('\t', 1) for line in f if '\t' in line]


def master_rows(ex):
    rows = read_table(os.path.join(ex, 'TXT', 'MASTER.TXT.txt'))
    sec = policy.sections(rows)
    return rows, sec


def gpc_rows(ex):
    rows = []
    with open(os.path.join(ex, 'DBS', 'GPC.DBS.txt'), encoding='utf-8') as f:
        for line in f:
            if '\t' in line:
                k, t = line.rstrip('\n').split('\t', 1)
                rows.append((k, t))
    return rows


def corpus(ex):
    """All translatable text lines (English) -> list of (file, num, text)."""
    out = []
    for typ in ('TXT', 'NTX'):
        for fn in sorted(os.listdir(os.path.join(ex, typ))):
            if not fn.endswith('.txt'):
                continue
            rows = read_table(os.path.join(ex, typ, fn))
            sec = policy.sections(rows)
            for num, text in rows:
                if policy.kind(fn, sec.get(num, '')) != 'keep' and not text.startswith('@'):
                    out.append((fn, num, text))
    return out


def collect_terms(ex):
    terms = OrderedDict()   # (cat, en) -> note

    def add(cat, en, note=''):
        en = en.strip()
        if is_term(en) and (cat, en) not in terms:
            terms[(cat, en)] = note

    rows, sec = master_rows(ex)
    for num, text in rows:
        s = sec.get(num, '').lstrip('@')
        if text.startswith('@'):
            continue
        if s in LIST_SECTIONS:
            add(LIST_SECTIONS[s], split_field(text)[1], f'MASTER {num}')
        elif s in CSV_TERM_SECTIONS:
            cats = CSV_TERM_SECTIONS[s]
            for i, f in enumerate(text.split(',')):
                add(cats[min(i, len(cats) - 1)], split_field(f)[1], f'MASTER {num}')
    # GPC: vocation titles. The vocation names themselves are MONSTYPE 1-15 / HOARDS "<X> Store".
    for k, t in gpc_rows(ex):
        if k.split(':')[1] == '12':
            add('title', t, f'GPC {k.split(":")[0]}')
    voc = [en for (c, en) in terms if c == 'monstype'][:15]
    for v in voc:
        add('vocation', v, 'MONSTYPE / GPC')
    return terms


def mine_names(lines, known):
    """Capitalised words that never occur in lower case: likely proper nouns."""
    words = Counter()
    lower = set()
    example = {}
    for fn, num, text in lines:
        plain = re.sub(r'\[[a-z]{3}\]|<[^>]*>', ' ', text)
        for w in re.findall(r"[A-Za-z][A-Za-z']+", plain):
            if w[0].isupper() and not w.isupper():
                words[w] += 1
                example.setdefault(w, f'{fn} {num}: {text[:70]}')
            elif w.islower():
                lower.add(w)
    known_words = set()
    for (c, en) in known:
        known_words.update(re.findall(r"[A-Za-z][A-Za-z']+", en))
    out = []
    for w, n in words.most_common():
        if n < 2 or w.lower() in lower or w in known_words or len(w) < 3:
            continue
        out.append((w, n, example[w]))
    return out


def load_glossary(path):
    g = OrderedDict()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for i, line in enumerate(f):
                p = line.rstrip('\n').split('\t')
                if i == 0 and p[0] == 'cat':
                    continue
                if len(p) >= 2:
                    p += [''] * (5 - len(p))
                    g[(p[0], p[1])] = {'ja': p[2], 'count': p[3], 'note': p[4]}
    return g


def save_glossary(path, g):
    order = {c: i for i, c in enumerate(CAT_ORDER)}
    items = sorted(g.items(), key=lambda kv: order.get(kv[0][0], 99))   # stable within a category
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('cat\ten\tja\tcount\tnote\n')
        for (c, en), v in items:
            f.write(f"{c}\t{en}\t{v['ja']}\t{v['count']}\t{v['note']}\n")


def word_re(en):
    return re.compile(r'(?<![A-Za-z])' + re.escape(en) + r'(?![A-Za-z])')


def cmd_extract(ex, path):
    old = load_glossary(path)
    terms = collect_terms(ex)
    lines = corpus(ex)
    blob = '\n'.join(t for _, _, t in lines)
    g = OrderedDict()
    for (c, en), note in terms.items():
        o = old.get((c, en), {})
        g[(c, en)] = {'ja': o.get('ja', ''), 'count': str(len(word_re(en).findall(blob))),
                      'note': o.get('note') or note}
    for w, n, ex_line in mine_names(lines, terms):
        o = old.get(('name?', w), {})
        g[('name?', w)] = {'ja': o.get('ja', ''), 'count': str(n), 'note': o.get('note') or ex_line}
    # keep hand-added entries
    for k, v in old.items():
        if k not in g:
            g[k] = v
    save_glossary(path, g)
    cnt = Counter(c for c, _ in g)
    print(f'{len(g)} terms -> {path}')
    print('  ' + ', '.join(f'{c} {cnt[c]}' for c in CAT_ORDER if cnt[c]))


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in s)


def lookup(g):
    d = {}
    for (c, en), v in g.items():
        if v['ja']:
            d.setdefault(c, {})[en] = v['ja']
    return d


def cmd_apply(ex, path, patch):
    g = lookup(load_glossary(path))
    rows, sec = master_rows(ex)
    out_path = os.path.join(patch, 'TXT', 'MASTER.TXT.txt')
    existing = dict(read_table(out_path)) if os.path.exists(out_path) else {}
    n = missing = 0
    for num, text in rows:
        s = sec.get(num, '').lstrip('@')
        if text.startswith('@'):
            continue
        if s in LIST_SECTIONS:
            cats = (LIST_SECTIONS[s],)
        elif s in CSV_TERM_SECTIONS:
            cats = CSV_TERM_SECTIONS[s]
        else:
            continue
        fields = text.split(',') if s in CSV_TERM_SECTIONS else [text]
        new = []
        for i, f in enumerate(fields):
            pre, core, post = split_field(f)
            cat = cats[min(i, len(cats) - 1)]
            if is_term(core):
                ja = g.get(cat, {}).get(core)
                if ja is None:
                    missing += 1
                    ja = core
                new.append(pre + ja + post)
            else:
                new.append(f)
        new = ','.join(new)
        if new != text:
            existing[num] = new
            n += 1
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for num, text in rows:
            if num in existing:
                f.write(f'{num}\t{existing[num]}\n')
    # GPC titles
    gpc_out = os.path.join(patch, 'DBS', 'GPC.DBS.txt')
    gx = {}
    if os.path.exists(gpc_out):
        for k, t in gpc_rows(os.path.join(patch)):
            gx[k] = t
    for k, t in gpc_rows(ex):
        if k.split(':')[1] == '12' and t in g.get('title', {}):
            gx[k] = g['title'][t]
    os.makedirs(os.path.dirname(gpc_out), exist_ok=True)
    with open(gpc_out, 'w', encoding='utf-8', newline='\n') as f:
        for k, t in gpc_rows(ex):
            f.write(f'{k}\t{gx.get(k, t)}\n')
    print(f'MASTER: {n} term lines written ({missing} fields without a translation, kept English)')


def term_patterns(gl):
    """Terms checked in running text: proper names, and multi-word spell/item/monster/skill names."""
    canon = {}
    for (c, en), v in gl.items():
        names = c in ('race', 'vocation', 'npc', 'place', 'patron', 'party', 'name?')
        multi = c in ('spell', 'item', 'monster', 'skill') and ' ' in en
        if v['ja'] and en not in canon and len(en) >= 3 and (names or multi):
            canon[en] = v['ja']
    return [(en, ja, word_re(en)) for en, ja in sorted(canon.items(), key=lambda x: -len(x[0]))]


def cmd_check(ex, path, patch):
    gl = load_glossary(path)
    pats = term_patterns(gl)
    issues = Counter()
    shown = 0
    for typ in ('TXT', 'NTX'):
        d = os.path.join(patch, typ)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            src = os.path.join(ex, typ, fn)
            if not os.path.exists(src):
                continue
            orig_rows = read_table(src)
            orig = dict(orig_rows)
            osec = policy.sections(orig_rows)
            tr = dict(read_table(os.path.join(d, fn)))
            # compare whole messages: lines between control lines (@..., [pag], [new]) form one unit,
            # because re-wrapping can move a word to the neighbouring line
            units, cur = [], []
            for num, text in orig_rows:
                if re.match(r'^(@\S*|\[pag\]|\[new\]|\*[A-Z]+)$', text) or fn.startswith('MASTER'):
                    if cur: units.append(cur)
                    cur = [] if not fn.startswith('MASTER') else [num]
                    if fn.startswith('MASTER'):
                        units.append(cur); cur = []
                    continue
                cur.append(num)
            if cur: units.append(cur)
            for u in units:
                if not any(n in tr for n in u):
                    continue
                if fn.startswith('MASTER') and osec.get(u[0], '').lstrip('@') in                         set(LIST_SECTIONS) | set(CSV_TERM_SECTIONS):
                    continue
                en_text = ' '.join(orig[n] for n in u)
                ja_text = ''.join(tr.get(n, orig[n]) for n in u)
                if ja_text.replace(' ', '') == en_text.replace(' ', ''):
                    continue
                for en, ja, rx in pats:
                    if rx.search(en_text) and ja not in ja_text:
                        issues[en] += 1
                        if shown < 60:
                            print(f'{fn} {u[0]}: "{en}" -> expected "{ja}"')
                            shown += 1
    wide = [(c, en, v['ja']) for (c, en), v in gl.items() if c not in ('name?', 'npc')
            and v['ja'] and width(v['ja']) > max(width(en) * 1.5, width(en) + 4)]
    for c, en, ja in wide[:40]:
        print(f'wide: [{c}] {en} ({width(en)}) -> {ja} ({width(ja)})')
    print(f'{sum(issues.values())} line(s) missing an agreed term; {len(wide)} wide term(s)')


def cmd_merge(path, parts):
    """Fill the ja (and note, if given) column from part files: cat<TAB>en<TAB>ja[<TAB>note]."""
    g = load_glossary(path)
    n = unknown = 0
    for p in parts:
        with open(p, encoding='utf-8') as f:
            for line in f:
                c = line.rstrip('\n').split('\t')
                if len(c) < 3 or c[0] == 'cat':
                    continue
                k = (c[0], c[1])
                if k not in g:
                    unknown += 1
                    print('unknown term:', p, k)
                    continue
                if c[2] != g[k]['ja']:
                    g[k]['ja'] = c[2]
                    n += 1
                if len(c) > 3 and c[3]:
                    g[k]['note'] = c[3]
    save_glossary(path, g)
    print(f'{n} translation(s) merged, {unknown} unknown')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['merge'] and len(a) >= 3:
        cmd_merge(a[1], a[2:])
    elif a[:1] == ['extract'] and len(a) == 3:
        cmd_extract(a[1], a[2])
    elif a[:1] == ['apply'] and len(a) == 4:
        cmd_apply(a[1], a[2], a[3])
    elif a[:1] == ['check'] and len(a) == 4:
        cmd_check(a[1], a[2], a[3])
    else:
        print(__doc__)
