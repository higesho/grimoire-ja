"""Assemble the drop-in Japanese patch for distribution.

  python tools/package.py [patch_dir] [out_dir]      (defaults: patch_jp, dist/Grimoire_JP; run from _jp_work)

Steps
  1. build the Japanese archive from the original (backup/BUNDLE-Z.RSF.orig) + patch_dir
     into dist_work/BUNDLE-Z.RSF (grimtool.py build; the game folder is not touched)
  2. jp_bundle.pat = difference original -> Japanese archive (make_dist.py; no original data inside)
  3. copy version.dll, grimjp.ini and the grimjp/ files, write the readme, zip it

Players copy the contents of out_dir into the game folder. The original files stay untouched;
version.dll builds grimjp/cache/BUNDLE-Z.RSF on the first launch and loads it instead.
"""
import os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(*args):
    subprocess.run([sys.executable, '-I', *args], cwd=ROOT, check=True)


def main(patch='patch_jp', out='dist/Grimoire_JP'):
    os.chdir(ROOT)
    os.makedirs('dist_work', exist_ok=True)
    run('tools/grimtool.py', 'build', '../Grimoire.exe', 'backup/BUNDLE-Z.RSF.orig', patch, 'dist_work/BUNDLE-Z.RSF')
    if os.path.isdir(out):
        shutil.rmtree(out)
    g = os.path.join(out, 'grimjp')
    os.makedirs(g)
    run('tools/make_dist.py', 'backup/BUNDLE-Z.RSF.orig', 'dist_work/BUNDLE-Z.RSF', os.path.join(g, 'jp_bundle.pat'))
    run('tools/make_fallback.py', 'extracted', patch, os.path.join(g, 'tiny_fallback.txt'))
    shutil.copy('dll/version.dll', out)
    shutil.copy('dll/grimjp.ini', out)
    for f in ('fonts/misaki8.bin', 'fonts/misaki_LICENSE.txt', 'ui_strings.txt', 'exe_strings.txt'):
        shutil.copy(os.path.join('dll', f), g)
    shutil.copy('dist_readme.txt', os.path.join(out, 'はじめにお読みください.txt'))
    z = out.rstrip('/\\') + '.zip'
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dp, _, fs in os.walk(out):
            for f in fs:
                p = os.path.join(dp, f)
                zf.write(p, os.path.relpath(p, os.path.dirname(out)))
    print('package:', out, '->', z, os.path.getsize(z), 'bytes')


if __name__ == '__main__':
    main(*sys.argv[1:])
