"""Make the drop-in patch data: the difference between the original and the Japanese archive.

  python tools/make_dist.py <original BUNDLE-Z.RSF> <japanese BUNDLE-Z.RSF> <out.pat>

The Japanese archive is the one built by `grimtool.py build` (install_test.bat). The output holds
only what changed (archive header, entry table, replaced entries); everything else is a
"copy from the original" instruction, so no original game data is distributed.
The jp DLL (version.dll) rebuilds the Japanese archive from the player's own original archive
with this file, and opens it instead of the original.

Format (little endian):
  char[4] 'GJPP', u32 version (1)
  u32 orig_size, u32 orig_crc32, u32 new_size, u32 new_crc32, u32 op_count, u32 literal_size
  op_count x { u32 kind (0 = copy from original, 1 = literal), u32 src, u32 len }
             (src = offset in the original archive, or in the literal pool)
  literal pool
"""
import os, struct, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grimtool import Bundle


def main(orig_path, new_path, out_path):
    a, b = Bundle(orig_path), Bundle(new_path)
    if len(a.entries) != len(b.entries):
        sys.exit('entry count differs')
    ops, pool = [], bytearray()

    def literal(data):
        if not data:
            return
        if ops and ops[-1][0] == 1 and ops[-1][1] + ops[-1][2] == len(pool):
            ops[-1][2] += len(data)
        else:
            ops.append([1, len(pool), len(data)])
        pool.extend(data)

    def copy(src, n):
        if ops and ops[-1][0] == 0 and ops[-1][1] + ops[-1][2] == src:
            ops[-1][2] += n
        else:
            ops.append([0, src, n])

    pos = 0
    changed = 0
    for e in sorted(b.entries, key=lambda e: e['offset']):
        o = a.entries[e['index']]
        if o['name'] != e['name']:
            sys.exit(f"entry {e['index']}: {o['name']} != {e['name']}")
        literal(b.data[pos:e['offset']])
        blob = b.raw(e)
        if blob == a.raw(o):
            copy(o['offset'], o['size'])
        else:
            literal(blob)
            changed += 1
        pos = e['offset'] + e['size']
    literal(b.data[pos:])

    # self-check: replay the instructions
    out = bytearray()
    for k, s, n in ops:
        out += (a.data if k == 0 else pool)[s:s + n]
    assert out == b.data, 'replay mismatch'

    with open(out_path, 'wb') as f:
        f.write(b'GJPP' + struct.pack('<I', 1))
        f.write(struct.pack('<6I', len(a.data), zlib.crc32(a.data), len(b.data), zlib.crc32(b.data),
                            len(ops), len(pool)))
        for k, s, n in ops:
            f.write(struct.pack('<3I', k, s, n))
        f.write(pool)
    print(f'{out_path}: {changed} entries replaced, {len(ops)} ops, {len(pool)} literal bytes, '
          f'{os.path.getsize(out_path)} bytes')


if __name__ == '__main__':
    main(*sys.argv[1:])
