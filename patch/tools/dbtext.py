"""Translatable text inside database resources (not string tables).

GPC.DBS (XOR encrypted, fixed layout, size must not change)
  15 vocations x 219 bytes from 0x6CB: 9 rank titles x 13 bytes (12 visible, byte 13 = separator),
  then 22 bytes of data, then an 80-byte description (space padded; the game shows only
  the first 78 bytes, so translations are limited to 78 bytes = 26 Japanese chars).
  53 skills x 120 bytes from 0x1440: 80-byte description (space padded) + 40 bytes of data.
  Text file lines:  <offset>:<maxbytes>:<pad>\t<text>     pad = 'nul' or 'space'

NPCWORDS.MLB (not encrypted, length-prefixed records; size may change)
  header 'MLB' ... u32 @0x0C = file size - 16, column names, then records:
  u32 reclen, 9 x (u32 len, bytes): TAG SYNONYMS VERBOSE BRIEF DISPATCH KNOWLINK KNOWINDEX CONTEXT NPCSKNOW
  Only VERBOSE / BRIEF are exported. SYNONYMS are what the player types: keep them English.
  Text file lines:  <record>.<VERBOSE|BRIEF>\t<text>    (line breaks written as \\n)
"""
import struct

GPC_VOC_BASE, GPC_VOC_SIZE, GPC_VOC_COUNT = 0x6CB, 219, 15
GPC_SKILL_BASE, GPC_SKILL_SIZE = 0x1440, 120
MLB_FIELDS = ['TAG', 'SYNONYMS', 'VERBOSE', 'BRIEF', 'DISPATCH', 'KNOWLINK', 'KNOWINDEX', 'CONTEXT', 'NPCSKNOW']
MLB_TEXT = ('VERBOSE', 'BRIEF')


import jptext


def _enc(text):
    try:
        return text.encode('cp1252')
    except UnicodeEncodeError:
        return text.encode('utf-8')


# ------------------------------------------------------------------ GPC.DBS
def gpc_fields(data):
    """Yields (offset, maxbytes, pad) of every text field."""
    for v in range(GPC_VOC_COUNT):
        base = GPC_VOC_BASE + v * GPC_VOC_SIZE
        for t in range(9):
            yield base + t * 13, 12, 'nul'
        yield base + 139, 78, 'space'     # 80-byte field, but the game shows Left(78)
    n = (len(data) - GPC_SKILL_BASE) // GPC_SKILL_SIZE
    for s in range(n):
        yield GPC_SKILL_BASE + s * GPC_SKILL_SIZE, 78, 'space'   # assume Left(78) like vocations


def gpc_export(data):
    out = []
    for off, mx, pad in gpc_fields(data):
        raw = data[off:off + mx]
        text = raw.split(b'\0')[0].rstrip(b' ').decode('cp1252')
        out.append(f'{off}:{mx}:{pad}\t{text}')
    return out


def gpc_apply(data, lines):
    buf = bytearray(data)
    errors = []
    for line in lines:
        if '\t' not in line:
            continue
        key, text = line.split('\t', 1)
        off, mx, pad = key.split(':')
        off, mx = int(off), int(mx)
        b = _enc(text)
        if len(b) > mx:
            errors.append(f'GPC.DBS @{off}: {len(b)} bytes > {mx}: {text}')
            continue
        orig = data[off:off + mx].split(b'\0')[0].rstrip(b' ')
        if b == orig:
            continue      # unchanged: keep original bytes exactly
        filler = b'\0' if pad == 'nul' else b' '
        buf[off:off + mx] = b + filler * (mx - len(b))
    return bytes(buf), errors


# ------------------------------------------------------------------ NPCWORDS.MLB
def mlb_parse(data):
    assert data[:3] == b'MLB'
    # the column header ends right after the last column name ("NPCSKNOW\0")
    p = data.index(b'NPCSKNOW') + len(b'NPCSKNOW')
    head = data[:p]
    recs = []
    while p < len(data):
        (L,) = struct.unpack_from('<I', data, p)
        q = p + 4
        fields = []
        while q < p + 4 + L:
            (n,) = struct.unpack_from('<I', data, q)
            fields.append(data[q + 4:q + 4 + n])
            q += 4 + n
        assert q == p + 4 + L and len(fields) == len(MLB_FIELDS)
        recs.append(fields)
        p = q
    return head, recs


def mlb_build(head, recs):
    body = bytearray()
    for fields in recs:
        rec = b''.join(struct.pack('<I', len(f)) + f for f in fields)
        body += struct.pack('<I', len(rec)) + rec
    out = bytearray(head) + body
    struct.pack_into('<I', out, 0x0C, len(out) - 16)
    return bytes(out)


def mlb_export(data):
    head, recs = mlb_parse(data)
    out = []
    for i, f in enumerate(recs):
        tag = f[0].decode('cp1252')
        for name in MLB_TEXT:
            v = f[MLB_FIELDS.index(name)]
            if v:
                text = v.decode('cp1252').replace('\\', '\\\\').replace('\r\n', '\\n')
                out.append(f'{i:03d}.{name}\t{text}')
        out.append(f'# {i:03d} TAG={tag} SYNONYMS={f[1].decode("cp1252")}')
    return out


def mlb_apply(data, lines):
    head, recs = mlb_parse(data)
    errors = []
    for line in lines:
        if line.startswith('#') or '\t' not in line:
            continue
        key, text = line.split('\t', 1)
        idx, name = key.split('.')
        idx = int(idx)
        if name not in MLB_TEXT or not (0 <= idx < len(recs)):
            errors.append(f'NPCWORDS.MLB: bad key {key}')
            continue
        val = text.replace('\\n', '\r\n').replace('\\\\', '\\')
        val = '\r\n'.join(jptext.softbreak(x) for x in val.split('\r\n'))   # word-wrap points
        b = _enc(val)
        recs[idx][MLB_FIELDS.index(name)] = b
    new = mlb_build(head, recs)
    return new, errors
