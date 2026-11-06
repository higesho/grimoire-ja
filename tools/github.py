"""GitHub の操作（gh の代わり）。認証は git が push に使っているもの（git credential fill、host=github.com）。値は表示しない。

  python -I tools/github.py create                 リポジトリ higesho/grimoire-ja を公開で作る（あれば何もしない）
  python -I tools/github.py pages                  GitHub Pages を main の /docs から出す設定にする
  python -I tools/github.py release <版> <zip> <本文.md> [--publish]
                                                   版のリリース（無ければ下書き）を作って zip を上げる。--publish で公開
  python -I tools/github.py status                 リポジトリ・Pages・リリースの状態を表示する
"""
import json, os, subprocess, sys, urllib.error, urllib.parse, urllib.request

OWNER, NAME = 'higesho', 'grimoire-ja'
REPO = f'{OWNER}/{NAME}'
API = 'https://api.github.com'
DESC = 'Grimoire: Heralds of the Winged Exemplar の非公式日本語化パッチと、ファン Wiki の日本語訳'


def token():
    out = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                         capture_output=True, text=True, timeout=30,
                         env=dict(os.environ, GIT_TERMINAL_PROMPT='0')).stdout
    cred = dict(l.split('=', 1) for l in out.splitlines() if '=' in l)
    if not cred.get('password'):
        sys.exit('GitHub の認証が見つからない（git credential fill）')
    return cred['password']


TOKEN = None


def call(method, url, data=None, ctype='application/json', ok404=False):
    global TOKEN
    TOKEN = TOKEN or token()
    headers = {'Authorization': 'token ' + TOKEN, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    body = json.dumps(data).encode('utf-8') if isinstance(data, (dict, list)) else data
    if body is not None:
        headers['Content-Type'] = ctype
    req = urllib.request.Request(url if url.startswith('http') else API + url, data=body, method=method,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if ok404 and e.code == 404:
            return None
        sys.exit(f'{method} {url.split("?")[0]} -> {e.code} {e.read()[:300]!r}')


def create():
    if call('GET', f'/repos/{REPO}', ok404=True):
        print('もうある:', f'https://github.com/{REPO}')
        return
    r = call('POST', '/user/repos', {'name': NAME, 'description': DESC, 'homepage': f'https://{OWNER}.github.io/{NAME}/',
                                     'private': False, 'has_wiki': False, 'auto_init': False})
    print('作った:', r['html_url'])


def pages():
    cur = call('GET', f'/repos/{REPO}/pages', ok404=True)
    src = {'source': {'branch': 'main', 'path': '/docs'}}
    if cur:
        call('PUT', f'/repos/{REPO}/pages', src)
    else:
        call('POST', f'/repos/{REPO}/pages', src)
    print('Pages: main /docs ->', f'https://{OWNER}.github.io/{NAME}/')


def release(ver, zpath, notes_path, publish):
    notes = open(notes_path, encoding='utf-8').read()
    rel = next((r for r in call('GET', f'/repos/{REPO}/releases?per_page=50') or [] if r['tag_name'] == ver), None)
    if not rel:
        rel = call('POST', f'/repos/{REPO}/releases', {'tag_name': ver, 'target_commitish': 'main',
                                                         'name': f'日本語化パッチ {ver}', 'body': notes,
                                                         'draft': True})
        print('下書きを作った:', rel['html_url'])
    name = os.path.basename(zpath)
    size = os.path.getsize(zpath)
    for a in rel['assets']:
        if a['name'] == name:
            if a['size'] == size:
                print('同じ大きさのものがあるので上げ直さない:', name)
                break
            call('DELETE', f'/repos/{REPO}/releases/assets/{a["id"]}')
    else:
        a = None
    if not any(x['name'] == name and x['size'] == size for x in rel['assets']):
        up = rel['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(name)
        call('POST', up, open(zpath, 'rb').read(), 'application/zip')
        print('上げた:', name, size, 'bytes')
    if publish:
        call('PATCH', f'/repos/{REPO}/releases/{rel["id"]}', {'body': notes, 'draft': False, 'make_latest': 'true'})
        print('公開した:', rel['html_url'].replace('/untagged-', '/tag/'))


def status():
    r = call('GET', f'/repos/{REPO}', ok404=True)
    if not r:
        print('リポジトリはまだ無い')
        return
    print('リポジトリ:', r['html_url'], '公開' if not r['private'] else '非公開')
    p = call('GET', f'/repos/{REPO}/pages', ok404=True)
    print('Pages:', (p['html_url'] + ' ' + str(p.get('status'))) if p else 'なし')
    for rel in call('GET', f'/repos/{REPO}/releases?per_page=10') or []:
        print('リリース:', rel['tag_name'], '下書き' if rel['draft'] else '公開',
              [(a['name'], a['size']) for a in rel['assets']])


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == 'create':
        create()
    elif cmd == 'pages':
        pages()
    elif cmd == 'status':
        status()
    elif cmd == 'release' and len(argv) >= 4:
        release(argv[1], argv[2], argv[3], '--publish' in argv)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
