"""Grimoire: Heralds of the Winged Exemplar - resource extraction tool.

Usage:
    python grimtool.py extract <game_dir> <out_dir>
    python grimtool.py verify  <game_dir>
    python grimtool.py build   <Grimoire.exe> <orig.RSF> <patch_dir> <out.RSF>

Read-only with respect to the game: BUNDLE-Z.RSF and Grimoire.exe are never modified.

Format notes (reverse-engineered):
  BUNDLE-Z.RSF
    0x0000  copyright banner / name / version / date
    0x00B4  type table: {char[4] tag, u16 count, u16 first_index} until the entry list
    then    entry list: {char[12] name, u16 flags, u32 size, u32 offset, u32 unknown}  (26 bytes)
            flags 0x1000 = string table (TXT/NTX), 0x0200 = bitmap
  Encryption (Grimoire.exe 0x565140 / 0x5651F0)
    Four 64-char ASCII keys, pointer table at VA 0x6B5620.
    Plain files : buf[i] ^= key[len(buf) % 4][i % 64]
    String table: header {u16 unk, u32 n_strings, u16 n_extra}
                  n_strings * {i16 len, u32 offset}, n_extra * 8 bytes,
                  then string data; each string s: s[i] ^= key[len(s) % 4][i % 64]
"""
import os
import struct
import sys

KEY_TABLE_VA = 0x6B5620
FLAG_STRTABLE = 0x1000
# Types whose content is (or contains) text worth translating.
TEXT_TYPES = {'TXT', 'NTX', 'SKP', 'SPL', 'DLG', 'DBS', 'MON', 'ITM'}


def load_keys(exe_path):
    import pefile
    pe = pefile.PE(exe_path, fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    ptrs = struct.unpack('<4I', pe.get_data(KEY_TABLE_VA - ib, 16))
    keys = [pe.get_data(p - ib, 256).split(b'\0')[0] for p in ptrs]
    assert all(len(k) == 64 for k in keys), 'unexpected key layout (different exe build?)'
    return keys


def xor(buf, key):
    n = len(key)
    return bytes(c ^ key[i % n] for i, c in enumerate(buf))


class Bundle:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        d = self.data
        p = 0xB4
        self.types = []
        while True:
            tag = d[p:p + 4].rstrip(b'\0').decode('latin1')
            cnt, start = struct.unpack_from('<HH', d, p + 4)
            expect = self.types[-1][1] + self.types[-1][2] if self.types else 0
            if start != expect or not tag.isalpha():
                break
            self.types.append((tag, cnt, start))
            p += 8
        self.entry_base = p
        total = sum(c for _, c, _ in self.types)
        self.entries = []
        for i in range(total):
            q = p + i * 26
            name = d[q:q + 12].split(b'\0')[0].decode('latin1')
            flags, size, off, unk = struct.unpack_from('<HIII', d, q + 12)
            self.entries.append(dict(index=i, name=name, flags=flags, size=size, offset=off, unk=unk))
        for tag, cnt, start in self.types:
            for e in self.entries[start:start + cnt]:
                e['type'] = tag

    def raw(self, e):
        return self.data[e['offset']:e['offset'] + e['size']]


def decode_strtable(buf, keys):
    unk, n, m = struct.unpack_from('<HIH', buf, 0)
    recs = [struct.unpack_from('<hI', buf, 8 + i * 6) for i in range(n)]
    extra = buf[8 + n * 6: 8 + n * 6 + m * 8]
    base = 8 + n * 6 + m * 8
    strings = []
    for ln, off in recs:
        raw = buf[base + off: base + off + ln]
        strings.append(xor(raw, keys[ln % 4]))
    return (unk, n, m), recs, extra, strings, buf[base:]


def encode_strtable(unk, extra, strings, keys, tail_layout=None):
    """Rebuild a string table. Strings are stored NUL-terminated, back to back."""
    m = len(extra) // 8
    recs, blob = [], bytearray()
    for s in strings:
        recs.append((len(s), len(blob)))
        blob += xor(s, keys[len(s) % 4]) + b'\0'
    out = bytearray(struct.pack('<HIH', unk, len(strings), m))
    for ln, off in recs:
        out += struct.pack('<hI', ln, off)
    out += extra + blob
    return bytes(out)


def cmd_extract(game_dir, out_dir):
    keys = load_keys(os.path.join(game_dir, 'Grimoire.exe'))
    b = Bundle(os.path.join(game_dir, 'BUNDLE-Z.RSF'))
    n_files = n_strings = 0
    for e in b.entries:
        if e['type'] not in TEXT_TYPES or e['name'] == 'FILEPAD.000':
            continue
        raw = b.raw(e)
        d = os.path.join(out_dir, e['type'])
        os.makedirs(d, exist_ok=True)
        if e['flags'] & FLAG_STRTABLE:
            hdr, recs, extra, strings, _ = decode_strtable(raw, keys)
            with open(os.path.join(d, e['name'] + '.txt'), 'w', encoding='utf-8', newline='\n') as f:
                for i, s in enumerate(strings):
                    f.write(f'{i:05d}\t{s.decode("cp1252")}\n')
            n_strings += len(strings)
        else:
            plain = raw if is_plain(raw) else xor(raw, keys[len(raw) % 4])
            with open(os.path.join(d, e['name']), 'wb') as f:
                f.write(plain)
            exporter = DB_TEXT.get(e['name'])
            if exporter:
                with open(os.path.join(d, e['name'] + '.txt'), 'w', encoding='utf-8', newline='\n') as f:
                    f.write('\n'.join(exporter[0](plain)) + '\n')
        n_files += 1
    print(f'extracted {n_files} files, {n_strings} table strings -> {out_dir}')


def is_plain(raw):
    """Resources stored without encryption (the game loads them through another path)."""
    return raw[:3] == b'MLB'


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tools dir (python -I omits it)
import dbtext
import jptext
import policy
# name -> (export, apply)
DB_TEXT = {'GPC.DBS': (dbtext.gpc_export, dbtext.gpc_apply),
           'NPCWORDS.MLB': (dbtext.mlb_export, dbtext.mlb_apply)}


def cmd_verify(game_dir):
    """Check that decode->encode reproduces every string table byte-for-byte."""
    keys = load_keys(os.path.join(game_dir, 'Grimoire.exe'))
    b = Bundle(os.path.join(game_dir, 'BUNDLE-Z.RSF'))
    ok = bad = 0
    for e in b.entries:
        if not e['flags'] & FLAG_STRTABLE:
            continue
        raw = b.raw(e)
        hdr, recs, extra, strings, _ = decode_strtable(raw, keys)
        rebuilt = encode_strtable(hdr[0], extra, strings, keys)
        if rebuilt == raw:
            ok += 1
        else:
            bad += 1
            print('MISMATCH', e['name'], len(raw), len(rebuilt))
    print(f'string tables round-trip: {ok} ok, {bad} mismatch')
    # plain XOR files are trivially reversible (xor twice == identity)


def encode_text(s):
    """cp1252 when possible (keeps original bytes), otherwise UTF-8 (decoded by the jp DLL)."""
    try:
        return s.encode('cp1252')
    except UnicodeEncodeError:
        # invisible wrap points in long lines. Comma lists (monster/item name fields such as
        # 'name,plural,unidentified,...') are handled per field: the game cuts single names to
        # 14-20 bytes, so wrap spaces inside short names would make them too long.
        # Prose (with 。 or 、, e.g. riddle text followed by ',ANSWER') keeps the old behaviour.
        if ',' in s and '。' not in s and '、' not in s:
            return ','.join(jptext.softbreak(x) for x in s.split(',')).encode('utf-8')
        return jptext.softbreak(s).encode('utf-8')


def read_table_file(path):
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or '\t' not in line:
                continue
            num, text = line.split('\t', 1)
            out[int(num)] = text
    return out


def cmd_build(exe_path, orig_rsf, patch_dir, out_rsf):
    """Rebuild the bundle, replacing string tables found in patch_dir/<TYPE>/<NAME>.txt.

    Only listed line numbers are replaced; other strings keep their original bytes.
    """
    keys = load_keys(exe_path)
    b = Bundle(orig_rsf)
    d = b.data
    first = b.entries[0]['offset']
    head = bytearray(d[:first])
    blobs, replaced = [], []
    pal = None
    n_errors = n_warn = 0
    for e in b.entries:
        raw = b.raw(e)
        p = os.path.join(patch_dir, e['type'], e['name'] + '.txt')
        if e['flags'] & FLAG_STRTABLE and os.path.exists(p):
            hdr, recs, extra, strings, _ = decode_strtable(raw, keys)
            repl = read_table_file(p)
            changed = 0
            secmap = policy.sections((i, s.decode('cp1252')) for i, s in enumerate(strings))
            for i, text in repl.items():
                if 0 <= i < len(strings):
                    orig = strings[i].decode('cp1252')
                    use, level, msg = policy.check(e['name'], secmap.get(i, ''), orig, text)
                    if level == 'error':
                        print('ERROR', msg); n_errors += 1
                    elif level == 'warn':
                        n_warn += 1
                        if n_warn <= 20:
                            print('WARNING', msg)
                    if not use:
                        continue
                    new = encode_text(text)
                    if new != strings[i]:
                        strings[i] = new
                        changed += 1
            if changed:
                raw = encode_strtable(hdr[0], extra, strings, keys)
                replaced.append((e['name'], changed))
        elif e['name'].endswith('.BMP') and os.path.exists(
                os.path.join(patch_dir, 'IMG', e['type'], e['name'][:-4] + '.png')):
            import imgtool
            if pal is None:
                pal = imgtool.load_palette(b, keys)
            plain = xor(raw, keys[len(raw) % 4])
            png = os.path.join(patch_dir, 'IMG', e['type'], e['name'][:-4] + '.png')
            try:
                new = imgtool.encode(png, plain, pal)
            except ValueError as ex:
                print('ERROR', e['name'], ex)
                sys.exit(1)
            if new != plain:
                raw = xor(new, keys[len(new) % 4])
                replaced.append((e['name'], 'img'))
        elif e['name'] in DB_TEXT and os.path.exists(p):
            plain = raw if is_plain(raw) else xor(raw, keys[len(raw) % 4])
            with open(p, encoding='utf-8') as f:
                lines = f.read().splitlines()
            new, errors = DB_TEXT[e['name']][1](plain, lines)
            for err in errors:
                print('ERROR', err)
            if errors:
                sys.exit(1)
            if new != plain:
                raw = new if is_plain(new) else xor(new, keys[len(new) % 4])
                replaced.append((e['name'], 'db'))
        blobs.append(raw)
    if n_warn:
        print(f'{n_warn} change(s) in English-only sections were ignored')
    if n_errors:
        print(f'{n_errors} error(s): bundle not written')
        sys.exit(1)
    # rewrite directory
    off = first
    total_sum = 0
    for e, raw in zip(b.entries, blobs):
        q = b.entry_base + e['index'] * 26
        s = sum(raw)
        struct.pack_into('<HIII', head, q + 12, e['flags'], len(raw), off, s)
        off += len(raw)
        total_sum += s
    struct.pack_into('<I', head, 0xA2, off)                       # file size
    struct.pack_into('<I', head, 0xB0, total_sum & 0xFFFFFFFF)     # byte sum of all data
    tmp = out_rsf + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(head)
        for raw in blobs:
            f.write(raw)
    os.replace(tmp, out_rsf)
    print(f'built {out_rsf}: {off} bytes, replaced {replaced}')


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'extract':
        cmd_extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == 'verify':
        cmd_verify(sys.argv[2])
    elif len(sys.argv) >= 6 and sys.argv[1] == 'build':
        cmd_build(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        print(__doc__)
