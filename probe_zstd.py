# -*- coding: utf-8 -*-
'''探测 session.jsonl.zstd 解码后的首行结构（了解消息格式）。'''
import sys
import json
import pathlib

home = pathlib.Path(r'C:\Users\44726\.dsh')
target = None
# 找一个无标题会话
for ws in (home / 'sessions').iterdir():
    if not ws.is_dir():
        continue
    for s in ws.iterdir():
        if s.name.startswith('session-7c325ca2') or s.name.startswith('session-8f0edf9b'):
            target = s / 'session.jsonl.zstd'
            break
    if target:
        break

if not target:
    print('未找到目标会话文件')
    sys.exit(0)

print('file:', target)
print('size:', target.stat().st_size)

# 尝试用 zstandard 解码首帧
try:
    import zstandard
    print('zstandard available')
    with open(target, 'rb') as f:
        raw = f.read()
    dctx = zstandard.ZstdDecompressor()
    # 解出尽可能多的内容（可能多帧，decompressobj 可流式）
    dobj = dctx.decompressobj()
    out = dobj.decompress(raw)
    # 也可能有残余帧
    if not dobj.eof:
        out2 = dobj.flush()
        if out2:
            out += out2
    text = out.decode('utf-8', errors='replace')
    lines = text.splitlines()
    print('decoded bytes:', len(out), 'first line count:', len(lines))
    for i, ln in enumerate(lines[:6]):
        print(f'--- line {i} (len {len(ln)}) ---')
        print(ln[:500])
except ImportError:
    print('zstandard NOT installed - cannot decode')
