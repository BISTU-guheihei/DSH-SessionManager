# -*- coding: utf-8 -*-
'''一次性预处理脚本：把 whalegirl 原始素材转成 GUI 运行时直接可用的 PNG。

- 鲸鱼娘图标 improved-1.png -> logo.png（128px，带透明通道）
- 圆形裁切 -> logo_circle.png（96px，顶栏头像）
- 32px 小图标 -> logo32.png（窗口图标）
运行时 tk.PhotoImage 原生支持 PNG（Tk 8.6+），GUI 无需 PIL 依赖。
'''
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'assets'
OUT.mkdir(exist_ok=True)

# 1. 鲸鱼娘 logo：128px，保留透明
logo = Image.open(ROOT / 'whalegirl' / 'improved-1.png').convert('RGBA')
logo = logo.resize((128, 128), Image.LANCZOS)
logo.save(OUT / 'logo.png', optimize=True)
print('logo.png', logo.size)

# 2. 圆形裁切 logo（透明底 whale-girl-transparent.png 裁切，44px 适配顶栏）
circ = Image.open(ROOT / 'whalegirl' / 'whale-girl-transparent.png').convert('RGBA')
# 居中裁成正方形（保留人物主体）
w, h = circ.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
circ = circ.crop((left, top, left + side, top + side))
circ = circ.resize((176, 176), Image.LANCZOS)
mask = Image.new('L', (176, 176), 0)
from PIL import ImageDraw
d = ImageDraw.Draw(mask)
d.ellipse((4, 4, 172, 172), fill=255)
circ.putalpha(mask)
circ = circ.resize((44, 44), Image.LANCZOS)
circ.save(OUT / 'logo_circle.png', optimize=True)
print('logo_circle.png', circ.size)

# 3. 窗口小图标 32px
small = Image.open(ROOT / 'whalegirl' / 'improved-1.png').convert('RGBA')
small = small.resize((32, 32), Image.LANCZOS)
small.save(OUT / 'logo32.png', optimize=True)
print('logo32.png', small.size)

print('done ->', OUT)
