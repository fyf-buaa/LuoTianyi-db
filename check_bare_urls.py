import os, re
music_dir = 'music'
total = 0
for f in os.listdir(music_dir):
    if f.endswith('.md'):
        content = open(os.path.join(music_dir, f), encoding='utf-8').read()
        bare = re.findall(r'(https?://(?:www\.)?bilibili\.com(?!/video/)[^\s)\"\']*)', content)
        total += len(bare)
print(f'Total bare bilibili URLs: {total}')
