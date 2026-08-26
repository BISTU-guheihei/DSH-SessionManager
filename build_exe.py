# -*- coding: utf-8 -*-
'''
build_exe.py —— 把 DSH 会话管理器打包成独立可执行文件。

跨平台：Windows（.exe）/ macOS（.app 或二进制）/ Linux（二进制）。
- Windows: .venv\\Scripts\\python.exe + --windowed + .ico 图标
- macOS:   .venv/bin/python + --windowed + .icns 图标（自动从 PNG 生成）
- Linux:   .venv/bin/python + 二进制 + PNG 图标

流程：
1. 强制使用项目 .venv（没有则自动创建），不污染系统 Python；
2. 在 .venv 中安装/升级 pyinstaller + pillow；
3. 准备图标（whalegirl 鲸鱼娘 .ico 优先；缺失时从 PNG 生成/本地绘制备用）；
4. 把 assets（鲸鱼娘 logo / 头像 / 窗口图标）随程序打包；
5. PyInstaller 单文件打包。
'''

import importlib.util
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

IS_WINDOWS = os.name == 'nt'
IS_MACOS = sys.platform == 'darwin'

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_SCRIPT = PROJECT_DIR / 'manage_sessions.py'
VENV_DIR = PROJECT_DIR / '.venv'
if IS_WINDOWS:
    VENV_PYTHON = VENV_DIR / 'Scripts' / 'python.exe'
else:
    VENV_PYTHON = VENV_DIR / 'bin' / 'python'
BUILD_ASSETS_DIR = PROJECT_DIR / 'build_assets'
ICON_SOURCE_PNG = BUILD_ASSETS_DIR / 'chibi_girl_source.png'
ICON_FILE = BUILD_ASSETS_DIR / ('app_icon.ico' if IS_WINDOWS else 'app_icon.icns')

WHALEGIRL_DIR = PROJECT_DIR / 'whalegirl'
WHALEGIRL_ICO_NAME = 'DeepSeekHarness-WhaleGirl.ico'
WHALEGIRL_PNG_NAME = 'improved-1.png'
ASSETS_DIR = PROJECT_DIR / 'assets'

PYINSTALLER_WORK_DIR = PROJECT_DIR / 'build' / 'pyinstaller'
OUTPUT_DIR = PROJECT_DIR / 'dist'
EXE_NAME = 'DSH_SessionManager'
EXE_PATH = OUTPUT_DIR / (EXE_NAME + ('.exe' if IS_WINDOWS else ''))

ICON_SOURCE_URL = (
    'https://upload.wikimedia.org/wikipedia/commons/c/c1/Chibiw.png'
    '?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original'
)
ICON_SOURCE_PAGE = 'https://commons.wikimedia.org/wiki/File:Chibiw.png'
ICON_LICENSE = 'CC0 1.0 Universal (Public Domain Dedication)'
ICON_AUTHOR = 'asrafil / OpenClipart'


def log(message: str):
    print('[build_exe] ' + message)


def ensure_venv() -> Path:
    if not VENV_PYTHON.exists():
        log('没有找到项目虚拟环境 .venv，正在创建（不会影响系统 Python）...')
        subprocess.check_call([sys.executable, '-m', 'venv', str(VENV_DIR)])
        log('虚拟环境创建完成: ' + str(VENV_DIR))
    return VENV_PYTHON


def re_run_in_venv():
    '''如果不是 .venv 里的 python 运行本脚本，自动切过去重新执行。'''
    venv_python = ensure_venv()
    current_python = Path(sys.executable).resolve()
    if current_python == venv_python.resolve():
        return
    log('检测到当前使用的是系统 Python，自动切换到项目虚拟环境重新执行...')
    exit_code = subprocess.call([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(exit_code)


def ensure_packages():
    has_pyinstaller = importlib.util.find_spec('PyInstaller') is not None
    has_pillow = importlib.util.find_spec('PIL') is not None
    if has_pyinstaller and has_pillow:
        log('PyInstaller 和 Pillow 已安装，跳过 pip 安装。')
        return
    log('正在 .venv 中安装 PyInstaller 和 Pillow...')
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install', '--upgrade',
        'pyinstaller', 'pillow', '--disable-pip-version-check', '--no-input',
    ])
    log('依赖安装完成。')


def download_icon_source() -> bool:
    if ICON_SOURCE_PNG.exists() and ICON_SOURCE_PNG.stat().st_size > 0:
        log('已找到本地图标原图，直接复用: ' + str(ICON_SOURCE_PNG))
        return True
    log('正在下载 CC0 萌系少女图标原图...')
    log('来源: ' + ICON_SOURCE_PAGE + '  授权: ' + ICON_LICENSE)
    try:
        request = urllib.request.Request(
            ICON_SOURCE_URL,
            headers={'User-Agent': 'DSH-icon-builder/1.0 (local build script)'},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with open(ICON_SOURCE_PNG, 'wb') as f:
                shutil.copyfileobj(response, f)
        return True
    except (urllib.error.URLError, OSError) as ex:
        log('下载失败（' + str(ex) + '），稍后将使用本地绘制的备用图标。')
        return False


def generate_fallback_icon(png_path: Path):
    '''本地绘制蓝发萌系少女头像，作为无网络时的备用图标。'''
    from PIL import Image, ImageDraw
    size = 512
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, size - 16, size - 16), fill=(210, 235, 255, 255))
    draw.ellipse((36, 36, size - 36, size - 20), fill=(102, 153, 255, 255))
    draw.ellipse((46, 46, size - 46, size - 30), fill=(77, 121, 204, 255))
    draw.ellipse((110, 130, size - 110, size - 60), fill=(255, 245, 238, 255))
    hair_bangs = [
        (160, 140), (130, 210), (190, 210),
        (175, 140), (205, 210), (265, 210),
        (250, 140), (280, 210), (340, 210),
        (325, 140), (395, 210), (370, 210),
    ]
    for i in range(0, len(hair_bangs), 3):
        if i + 2 < len(hair_bangs):
            draw.polygon(hair_bangs[i:i + 3], fill=(102, 153, 255, 255))
    draw.ellipse((155, 230, 225, 320), fill=(80, 130, 255, 255))
    draw.ellipse((size - 225, 230, size - 155, 320), fill=(80, 130, 255, 255))
    draw.ellipse((175, 245, 205, 285), fill=(255, 255, 255, 255))
    draw.ellipse((size - 205, 245, size - 175, 285), fill=(255, 255, 255, 255))
    draw.ellipse((125, 315, 185, 350), fill=(255, 180, 200, 180))
    draw.ellipse((size - 185, 315, size - 125, 350), fill=(255, 180, 200, 180))
    draw.arc((210, 320, size - 210, 380), 10, 170, fill=(255, 130, 160, 255), width=6)
    draw.ellipse((230, 75, 250, 95), fill=(255, 102, 153, 255))
    draw.ellipse((size - 250, 75, size - 230, 95), fill=(255, 102, 153, 255))
    image.save(png_path)
    log('已生成蓝发萌系少女备用图标: ' + str(png_path))


def make_icon():
    '''生成打包图标（Windows .ico / macOS .icns）。优先级：
    1. whalegirl 现成 .ico（仅 Windows）
    2. whalegirl 透明 PNG 转换
    3. CC0 下载图 / 本地绘制备用图
    '''
    from PIL import Image
    BUILD_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # 优先级 1：现成 .ico（Windows）
    if IS_WINDOWS:
        ready_ico = WHALEGIRL_DIR / WHALEGIRL_ICO_NAME
        if ready_ico.exists() and ready_ico.stat().st_size > 0:
            shutil.copyfile(ready_ico, ICON_FILE)
            log('使用 whalegirl 现成鲸鱼娘图标: ' + str(ready_ico))
            return

    # 优先级 2：whalegirl PNG 转换
    source_png = WHALEGIRL_DIR / WHALEGIRL_PNG_NAME
    if not (source_png.exists() and source_png.stat().st_size > 0):
        if not download_icon_source():
            source_png = BUILD_ASSETS_DIR / 'fallback_chibi_icon.png'
            generate_fallback_icon(source_png)

    try:
        image = Image.open(source_png).convert('RGBA')
        image.load()
        if IS_WINDOWS:
            image.save(str(ICON_FILE), format='ICO', sizes=icon_sizes)
        elif IS_MACOS:
            image.save(str(ICON_FILE), format='ICNS',
                       append_images=[image.resize((s, s), Image.LANCZOS)
                                      for s in (16, 32, 48, 128, 256, 512, 1024)])
        else:
            # Linux：PyInstaller 接受 PNG 作为图标
            image.save(str(ICON_FILE.with_suffix('.png')), format='PNG')
        log('图标生成完成: ' + str(ICON_FILE))
    except Exception as ex:
        log('图标生成失败（' + str(ex) + '），使用默认图标继续。')


def run_pyinstaller():
    if not SOURCE_SCRIPT.exists():
        log('找不到要打包的入口脚本: ' + str(SOURCE_SCRIPT))
        sys.exit(1)

    log('开始 PyInstaller 打包，请稍候...')
    command = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean', '--onefile',
        '--name', EXE_NAME,
        '--distpath', str(OUTPUT_DIR),
        '--workpath', str(PYINSTALLER_WORK_DIR),
        '--specpath', str(PYINSTALLER_WORK_DIR),
    ]
    if IS_WINDOWS:
        command.append('--windowed')   # 双击不弹黑色终端
        if ICON_FILE.exists():
            command += ['--icon', str(ICON_FILE)]
    elif IS_MACOS:
        command.append('--windowed')
        if ICON_FILE.exists():
            command += ['--icon', str(ICON_FILE)]
    else:
        png_icon = ICON_FILE.with_suffix('.png')
        if png_icon.exists():
            command += ['--icon', str(png_icon)]

    # 数据文件：assets（鲸鱼娘 logo / 头像 / 窗口图标）+ whalegirl 图标
    sep = ';' if IS_WINDOWS else ':'
    for asset_name in os.listdir(ASSETS_DIR):
        asset_path = ASSETS_DIR / asset_name
        if asset_path.is_file():
            command += ['--add-data', str(asset_path) + sep + 'assets']
    for asset_name in (WHALEGIRL_ICO_NAME, WHALEGIRL_PNG_NAME):
        asset_path = WHALEGIRL_DIR / asset_name
        if asset_path.exists() and asset_path.stat().st_size > 0:
            command += ['--add-data', str(asset_path) + sep + 'whalegirl']

    command.append(str(SOURCE_SCRIPT))
    subprocess.check_call(command, cwd=str(PROJECT_DIR))


def main():
    re_run_in_venv()
    log('项目目录: ' + str(PROJECT_DIR))
    log('虚拟环境 Python: ' + str(Path(sys.executable)))
    ensure_packages()
    make_icon()
    run_pyinstaller()

    if not EXE_PATH.exists():
        log('构建失败：没有在预期位置找到可执行文件，请查看上面的 PyInstaller 输出。')
        sys.exit(1)

    size_mb = EXE_PATH.stat().st_size / (1024 * 1024)
    log('构建成功！')
    log('可执行文件: ' + str(EXE_PATH))
    log('大小: ' + str(round(size_mb, 2)) + ' MB')
    log('')
    log('使用方式：')
    log('  ' + EXE_NAME + ('（双击）' if IS_WINDOWS else '') + '            # 打开图形界面')
    log('  ' + EXE_NAME + ' list                 # 在命令行查看工作区/会话')
    log('  ' + EXE_NAME + ' delete 1 3           # 移入回收站')
    log('  ' + EXE_NAME + ' trash / restore      # 查看 / 恢复回收站')
    log('  ' + EXE_NAME + ' clean                # 清理缓存残留')


if __name__ == '__main__':
    main()
