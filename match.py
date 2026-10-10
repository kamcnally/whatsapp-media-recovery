import base64, csv, hashlib, os, shutil, sys, collections

src, expected, out = sys.argv[1:4]

want = collections.defaultdict(set)
paths = set()
with open(expected, newline='') as f:
    for fh, oh, path in csv.reader(f, delimiter='\t'):
        paths.add(path)
        for h in (fh, oh):
            if h:
                want[h].add(path)

def dest_for(rel):
    i = rel.find('Media/')
    rel = rel[i:] if i >= 0 else 'other/' + rel.lstrip('/')
    rel = os.path.normpath(rel)
    return None if rel.startswith('..') else os.path.join(out, rel)

have = {}
for root, _, files in os.walk(src):
    for name in files:
        if name.lower().endswith('.json'):
            continue
        p = os.path.join(root, name)
        d = hashlib.sha256()
        with open(p, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                d.update(chunk)
        have[base64.b64encode(d.digest()).decode()] = p

print(f'hashed {len(have)} unique files, overlap {len(have.keys() & want.keys())}')

new = 0
for h, p in have.items():
    for rel in want.get(h, ()):
        dest = dest_for(rel)
        if dest is None or os.path.exists(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(p, dest)
        new += 1

missing = sorted(r for r in paths
                 if (d := dest_for(r)) is None or not os.path.exists(d))
with open('missing.txt', 'w') as f:
    f.write('\n'.join(missing))
print(f'copied {new} new, {len(paths) - len(missing)} of {len(paths)} now present, missing {len(missing)}')
