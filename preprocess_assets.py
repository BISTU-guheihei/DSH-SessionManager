# -*- coding: utf-8 -*-
'''一次性预处理脚本：把 bizhi/whalegirl 的原始素材转成 GUI 运行时直接可用的 PNG。

- 壁纸 2560x1440 RGBA 9MB -> 1600x900 RGB（轻微白色柔纱，保证白卡片可读性）
- 瓶子 webp 960x1200 -> PNG（竖版装饰图）
- 鲸鱼娘图标 improved-1.png -> logo.png（128px，带透明通道）
运行时 tk.PhotoImage 原生支持 PNG（Tk 8.6+），GUI 无需 PIL 依赖。
'''
import pathlib
from PIL import Image, ImageEnhance

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'assets'
OUT.mkdir(exist_ok=True)

# 1. 壁纸：RGBA 扁平化到白底后转 RGB，缩放到 1600x900，叠加 12% 白色柔纱
wall = Image.open(ROOT / 'bizhi' / 'wallhaven-qrm1k5_2560x1440.png').convert('RGBA')
wall = Image.alpha_composite(Image.new('RGBA', wall.size, (255, 255, 255, 255)), wall)
wall = wall.convert('RGB')
wall = wall.resize((1600, 900), Image.LANCZOS)
veil = Image.new('RGB', wall.size, (255, 255, 255))
wall = Image.blend(wall, veil, 0.12)
wall.save(OUT / 'wallpaper.png', optimize=True, format='PNG')
print('wallpaper.png', wall.size)

# 2. 瓶子：RGB 直转 PNG，等比缩到高 720
bottle = Image.open(ROOT / 'bizhi' / 'DeepSeek鲸鱼娘瓶子.webp').convert('RGB')
w, h = bottle.size
bottle = bottle.resize((int(w * 720 / h), 720), Image.LANCZOS)
bottle.save(OUT / 'bottle.png', optimize=True)
print('bottle.png', bottle.size)

# 3. 鲸鱼娘 logo：128px，保留透明
logo = Image.open(ROOT / 'whalegirl' / 'improved-1.png').convert('RGBA')
logo = logo.resize((128, 128), Image.LANCZOS)
logo.save(OUT / 'logo.png', optimize=True)
print('logo.png', logo.size)

# 3b. 圆形裁切 logo（96px，用于标题栏圆形头像）
circ = Image.open(ROOT / 'whalegirl' / 'improved-1.png').convert('RGBA')
circ = circ.resize((192, 192), Image.LANCZOS)
mask = Image.new('L', (192, 192), 0)
from PIL import ImageDraw
d = ImageDraw.Draw(mask)
d.ellipse((0, 0, 192, 192), fill=255)
circ.putalpha(mask)
circ = circ.resize((96, 96), Image.LANCZOS)
circ.save(OUT / 'logo_circle.png', optimize=True)
print('logo_circle.png', circ.size)

# 3c. 瓶子小图（右侧详情面板底部装饰，高 260）
bottle_small = Image.open(ROOT / 'bizhi' / 'DeepSeek鲸鱼娘瓶子.webp').convert('RGB')
bw, bh = bottle_small.size
bottle_small = bottle_small.resize((int(bw * 260 / bh), 260), Image.LANCZOS)
bottle_small.save(OUT / 'bottle_small.png', optimize=True)
print('bottle_small.png', bottle_small.size)

# 4. 状态栏小图标 32px
small = Image.open(ROOT / 'whalegirl' / 'improved-1.png').convert('RGBA')
small = small.resize((32, 32), Image.LANCZOS)
small.save(OUT / 'logo32.png', optimize=True)
print('logo32.png', small.size)

# 5. 计算壁纸平均色（GUI 间隙色）
wall_small = wall.resize((16, 9))
px = list(wall_small.getdata())
avg = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
print('wallpaper avg color RGB:', avg)

print('done ->', OUT)
