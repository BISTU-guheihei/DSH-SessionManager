'''
build_exe.py —— 把 manage_sessions.py 打包成一个独立、可整体使用的 .exe 文件。

=====================================================================
这个脚本做了什么？
=====================================================================
1. 强制使用本项目自己的虚拟环境 .venv（没有就自动创建），
   并在 .venv 里安装打包需要的 PyInstaller 和 Pillow；
   ###不会污染系统 Python。

2. 从本项目的 whalegirl\\ 文件夹读取 DeepSeek 小鲸鱼娘化版图标
   （优先使用现成的多尺寸 .ico；没有 .ico 时用 improved-1.png
   透明底原图转成 .ico；都没有时才用本地绘制的备用图标，保证
   构建流程不会中断）：
        文件: whalegirl\\DeepSeekHarness-WhaleGirl.ico（16~256 多尺寸）
        原图: whalegirl\\improved-1.png（透明底、去伪影修复版）
        角色: 「溟月」(OC, 作者: 上善无形)
        DeepSeek 元素二创: ZipZipPipe;修复: QYQCAMIAO
        仓库: https://github.com/fornarwhal/deepseek-whale-girl-icon
        授权: CC BY-NC-SA 4.0(须署名、非商用、相同方式共享;
              个人本地使用没问题,如需商用请另选 CC0 图标)

3. 把图标原图转换成 Windows 可执行文件需要的 .ico 多尺寸图标。

4. 调用 PyInstaller，用 --onefile --windowed 把 manage_sessions.py 打成
   单个 exe 文件，并且把图标直接“嵌入”exe：
       dist\\DSH_SessionManager.exe
   --windowed 保证双击 exe 时不会弹出黑色控制台窗口；
   exe 里已经包含图形界面、命令行全部功能，也包含图标本身，
   可以把这个 exe 单独复制到任何地方使用，不需要再带着 .ico 或 .py。

=====================================================================
如何使用？
=====================================================================
推荐（会自动帮你切到 .venv）：
    python manage_sessions.py build-exe

也可以直接运行本脚本（会自动切到 .venv）：
    .venv\\Scripts\\python.exe build_exe.py

生成成功后：
    dist\\DSH_SessionManager.exe          # 双击直接打开图形界面（不会弹黑色终端窗口）
    DSH_SessionManager.exe list           # 在已打开的命令行窗口里执行 list 等命令
=====================================================================
'''

import importlib.util
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ----------------------------------------------------------------------
# 路径配置（全部基于本脚本所在目录，不依赖用户当前工作目录）
# ----------------------------------------------------------------------
# 项目根目录：本脚本和 manage_sessions.py 都在这个目录里
PROJECT_DIR = Path(__file__).resolve().parent

# 要打包的 Python 入口脚本
SOURCE_SCRIPT = PROJECT_DIR / 'manage_sessions.py'

# 本项目自己的虚拟环境。Windows 下 venv 的 python 解释器在 .venv\\Scripts\\ 里
VENV_DIR = PROJECT_DIR / '.venv'
VENV_PYTHON = VENV_DIR / 'Scripts' / 'python.exe'

# 构建过程中生成的中间文件都放在 build_assets 目录里
BUILD_ASSETS_DIR = PROJECT_DIR / 'build_assets'

# 从网上下载下来的图标原图（CC0 萌系少女）
ICON_SOURCE_PNG = BUILD_ASSETS_DIR / 'chibi_girl_source.png'

# 最终给 PyInstaller 使用的 Windows 多尺寸图标
ICON_FILE = BUILD_ASSETS_DIR / 'app_icon.ico'

# ----------------------------------------------------------------------
# 鲸鱼娘图标来源（whalegirl 文件夹,优先级最高;CC BY-NC-SA 4.0）
# ----------------------------------------------------------------------
WHALEGIRL_DIR = PROJECT_DIR / 'whalegirl'
WHALEGIRL_ICO_NAME = 'DeepSeekHarness-WhaleGirl.ico'
WHALEGIRL_PNG_NAME = 'improved-1.png'

# PyInstaller 的临时工作目录和最终输出目录
PYINSTALLER_WORK_DIR = PROJECT_DIR / 'build' / 'pyinstaller'
OUTPUT_DIR = PROJECT_DIR / 'dist'

# exe 的名称。这里故意使用英文名，避免某些 Windows 版本/工具对中文文件名的兼容问题。
EXE_NAME = 'DSH_SessionManager'
EXE_PATH = OUTPUT_DIR / (EXE_NAME + '.exe')

# ----------------------------------------------------------------------
# 图标来源说明（CC0，可自由使用）
# ----------------------------------------------------------------------
ICON_SOURCE_URL = (
    'https://upload.wikimedia.org/wikipedia/commons/c/c1/Chibiw.png'
    '?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original'
)
ICON_SOURCE_PAGE = 'https://commons.wikimedia.org/wiki/File:Chibiw.png'
ICON_LICENSE = 'CC0 1.0 Universal (Public Domain Dedication)'
ICON_AUTHOR = 'asrafil / OpenClipart'


# ----------------------------------------------------------------------
# 小工具：打印带前缀的日志，让用户能看清构建进行到哪一步
# ----------------------------------------------------------------------
def log(message: str):
    '''打印一条带 [build_exe] 前缀的日志。'''
    print('[build_exe] ' + message)


def ensure_venv() -> Path:
    '''
    确保项目虚拟环境存在。

    返回虚拟环境里的 python.exe 路径。
    如果 .venv 不存在，就用“当前这个 python”创建一个新的 .venv，
    而不是往系统 Python 里装任何东西。
    '''
    if not VENV_PYTHON.exists():
        log('没有找到项目虚拟环境 .venv，正在创建（不会影响系统 Python）...')
        subprocess.check_call([sys.executable, '-m', 'venv', str(VENV_DIR)])
        log('虚拟环境创建完成: ' + str(VENV_DIR))
    return VENV_PYTHON


def re_run_in_venv():
    '''
    如果用户不是用 .venv 里的 python 运行本脚本，
    就自动用 .venv 里的 python 重新运行本脚本，然后退出当前进程。

    这样即使用户图省事输入了：
        python build_exe.py
    最终真正执行安装和打包的仍然是 .venv 的 python，不会污染系统 Python。
    '''
    venv_python = ensure_venv()
    current_python = Path(sys.executable).resolve()
    venv_python_resolved = venv_python.resolve()

    if current_python == venv_python_resolved:
        # 已经是在 .venv 里运行了，无需切换
        return

    log('检测到当前使用的是系统 Python，自动切换到项目虚拟环境重新执行...')
    log('当前: ' + str(current_python))
    log('切换到: ' + str(venv_python_resolved))
    # 用 .venv python 重新执行本脚本，并把本次命令行参数原样传过去；
    # 把子进程的退出码原样返回，这样构建失败时父进程也会返回失败。
    exit_code = subprocess.call([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(exit_code)


def ensure_packages():
    '''
    在“虚拟环境内部”安装打包所需第三方包：
        - pyinstaller：用来生成 exe
        - pillow：用来下载/处理图标并生成 .ico

    注意：这个函数只会被 .venv 的 python 执行（前面 re_run_in_venv 保证过），
    因此 pip 安装不会碰到系统 Python 的 site-packages。

    另外，如果发现这两个包已经安装好了，就直接跳过 pip 联网检查；
    这样即使断网，已经装过依赖的机器也仍然可以重复构建。
    '''
    has_pyinstaller = importlib.util.find_spec('PyInstaller') is not None
    has_pillow = importlib.util.find_spec('PIL') is not None

    if has_pyinstaller and has_pillow:
        log('PyInstaller 和 Pillow 已经安装在 .venv 中，跳过 pip 安装。')
        return

    log('正在 .venv 虚拟环境中安装 PyInstaller 和 Pillow...')
    subprocess.check_call([
        sys.executable,
        '-m', 'pip',
        'install',
        '--upgrade',
        'pyinstaller',
        'pillow',
        '--disable-pip-version-check',
        '--no-input',
    ])
    log('依赖安装完成。')


def download_icon_source() -> bool:
    '''
    从 Wikimedia Commons 下载 CC0 的 Q 版萌系少女原图。

    返回 True 表示下载成功；返回 False 表示下载失败（稍后会改用本地绘制的图标）。
    下载前会先检查本地是否已经有原图，有就直接复用，避免每次构建都联网。
    '''
    if ICON_SOURCE_PNG.exists() and ICON_SOURCE_PNG.stat().st_size > 0:
        log('已找到本地图标原图，直接复用: ' + str(ICON_SOURCE_PNG))
        return True

    log('正在下载 CC0 萌系少女图标原图...')
    log('来源: ' + ICON_SOURCE_PAGE)
    log('授权: ' + ICON_LICENSE)

    try:
        # User-Agent 是 Wikimedia 要求的礼貌访问标识
        request = urllib.request.Request(
            ICON_SOURCE_URL,
            headers={'User-Agent': 'DSH-icon-builder/1.0 (local build script)'},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with open(ICON_SOURCE_PNG, 'wb') as f:
                shutil.copyfileobj(response, f)
        log('图标原图下载完成: ' + str(ICON_SOURCE_PNG))
        return True
    except (urllib.error.URLError, OSError) as ex:
        log('下载失败（' + str(ex) + '），稍后将使用本地绘制的备用图标。')
        return False


def generate_fallback_icon(png_path: Path):
    '''
    本地绘制一个蓝发萌系娘化小女孩头像，
    作为“没有网络”时的备用图标。
    '''
    from PIL import Image, ImageDraw

    size = 512
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # 透明背景上先画一个柔和蓝色圆形底
    draw.ellipse((16, 16, size - 16, size - 16), fill=(210, 235, 255, 255))

    # 头发外圈：浅蓝色长发轮廓
    draw.ellipse((36, 36, size - 36, size - 20), fill=(102, 153, 255, 255))

    # 内圈深蓝头发阴影
    draw.ellipse((46, 46, size - 46, size - 30), fill=(77, 121, 204, 255))

    # 脸：米白色圆脸
    draw.ellipse((110, 130, size - 110, size - 60), fill=(255, 245, 238, 255))

    # 刘海：蓝色三角形刘海
    hair_bangs = [
        (160, 140),
        (130, 210),
        (190, 210),
        (175, 140),
        (205, 210),
        (265, 210),
        (250, 140),
        (280, 210),
        (340, 210),
        (325, 140),
    ]
    for i in range(0, len(hair_bangs), 3):
        if i + 2 < len(hair_bangs):
            draw.polygon(hair_bangs[i:i+3], fill=(102, 153, 255, 255))

    # 眼睛：大眼睛，蓝紫渐变感
    draw.ellipse((155, 230, 225, 320), fill=(80, 130, 255, 255))
    draw.ellipse((size - 225, 230, size - 155, 320), fill=(80, 130, 255, 255))

    # 瞳孔高光
    draw.ellipse((175, 245, 205, 285), fill=(255, 255, 255, 255))
    draw.ellipse((size - 205, 245, size - 175, 285), fill=(255, 255, 255, 255))

    # 小星光眼装饰
    draw.ellipse((185, 265, 195, 275), fill=(255, 255, 255, 255))
    draw.ellipse((size - 195, 265, size - 185, 275), fill=(255, 255, 255, 255))

    # 腮红：淡粉色椭圆
    draw.ellipse((125, 315, 185, 350), fill=(255, 180, 200, 180))
    draw.ellipse((size - 185, 315, size - 125, 350), fill=(255, 180, 200, 180))

    # 嘴巴：小小的可爱微笑
    draw.arc((210, 320, size - 210, 380), 10, 170, fill=(255, 130, 160, 255), width=6)

    # 头上的小呆毛 / 爱心装饰
    draw.ellipse((230, 75, 250, 95), fill=(255, 102, 153, 255))
    draw.ellipse((size - 250, 75, size - 230, 95), fill=(255, 102, 153, 255))

    image.save(png_path)
    log('已生成蓝发萌系少女备用图标: ' + str(png_path))



def make_icon():
    '''
    生成 Windows 可执行文件使用的多尺寸 .ico 图标。

    图标来源优先级：
        1. whalegirl\\DeepSeekHarness-WhaleGirl.ico —— 现成的多尺寸鲸鱼娘图标，直接复用；
        2. whalegirl\\improved-1.png —— 鲸鱼娘透明底原图，用 Pillow 转成多尺寸 .ico；
        3. 都没有时，使用本地绘制的备用图标，保证构建流程不会中断。
    '''
    from PIL import Image

    BUILD_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # 优先级 1：whalegirl 里现成的鲸鱼娘 .ico
    ready_ico = WHALEGIRL_DIR / WHALEGIRL_ICO_NAME
    if ready_ico.exists() and ready_ico.stat().st_size > 0:
        shutil.copyfile(ready_ico, ICON_FILE)
        log('使用 whalegirl 现成鲸鱼娘图标: ' + str(ready_ico))
        return

    # 优先级 2：whalegirl 里的鲸鱼娘透明底 PNG 原图
    source_png = WHALEGIRL_DIR / WHALEGIRL_PNG_NAME
    if source_png.exists() and source_png.stat().st_size > 0:
        try:
            image = Image.open(source_png).convert('RGBA')
            image.load()
            image.save(str(ICON_FILE), format='ICO', sizes=icon_sizes)
            log('已用 whalegirl 鲸鱼娘原图生成多尺寸图标: ' + str(ICON_FILE))
            return
        except Exception as ex:
            log('读取 whalegirl 鲸鱼娘原图失败（' + str(ex) + '），改用本地备用图标。')

    # 优先级 3：本地绘制的备用图标（离线也能构建成功）
    fallback_png = BUILD_ASSETS_DIR / 'fallback_chibi_icon.png'
    generate_fallback_icon(fallback_png)
    image = Image.open(fallback_png).convert('RGBA')
    image.load()
    image.save(str(ICON_FILE), format='ICO', sizes=icon_sizes)
    log('已生成本地备用多尺寸图标: ' + str(ICON_FILE))


def run_pyinstaller():
    '''
    调用 PyInstaller 进行打包。

    --onefile  : 打成单个 exe 文件
    --windowed : 用 Windows GUI 子系统打包。双击打开图形界面时，
                 不会再弹出黑色的控制台窗口。
                 manage_sessions.py 内部已经实现了 AttachConsole 逻辑：
                 如果在已有命令行窗口里执行 list / delete / clean 等命令，
                 仍会尝试把输出挂到父控制台，因此命令行功能依然可用。
    --icon     : 把 app_icon.ico 嵌入 exe（构建后不需要再带着 .ico 文件）
    '''
    if not SOURCE_SCRIPT.exists():
        log('找不到要打包的入口脚本: ' + str(SOURCE_SCRIPT))
        sys.exit(1)

    log('开始 PyInstaller 打包，请稍候...')
    command = [
        sys.executable,               # 现在是 .venv 里的 python
        '-m', 'PyInstaller',
        '--noconfirm',                # 如果存在旧构建，不询问直接覆盖
        '--clean',                    # 清理 PyInstaller 缓存，避免旧文件残留
        '--onefile',                  # 打成单个 exe
        '--windowed',                 # GUI 模式：双击不弹黑色控制台窗口
        '--name', EXE_NAME,           # exe 文件名
        '--icon', str(ICON_FILE),     # 嵌入 exe 的 PE 图标
        '--distpath', str(OUTPUT_DIR),
        '--workpath', str(PYINSTALLER_WORK_DIR),
        '--specpath', str(PYINSTALLER_WORK_DIR),
    ]

    # 把鲸鱼娘图标文件作为“数据文件”一起打进 exe：
    # 运行时窗口图标（manage_sessions.py 里的 iconbitmap/iconphoto）
    # 从 sys._MEIPASS 解包目录读取，因此 exe 单独拷贝到哪里都能显示鲸鱼娘。
    for asset_name in (WHALEGIRL_ICO_NAME, WHALEGIRL_PNG_NAME):
        asset_path = WHALEGIRL_DIR / asset_name
        if asset_path.exists() and asset_path.stat().st_size > 0:
            command += ['--add-data', str(asset_path) + ';whalegirl']

    command.append(str(SOURCE_SCRIPT))
    subprocess.check_call(command, cwd=str(PROJECT_DIR))


def main():
    '''构建入口。'''
    # 第一步：确保最终是在 .venv 虚拟环境中执行（不污染系统 Python）
    re_run_in_venv()

    log('项目目录: ' + str(PROJECT_DIR))
    log('虚拟环境 Python: ' + str(Path(sys.executable)))

    # 第二步：在 .venv 里安装/升级打包依赖
    ensure_packages()

    # 第三步：准备图标
    make_icon()

    # 第四步：调用 PyInstaller 生成单文件 exe
    run_pyinstaller()

    # 第五步：检查结果并给出后续使用提示
    if not EXE_PATH.exists():
        log('构建失败：没有在预期位置找到 exe，请查看上面的 PyInstaller 输出。')
        sys.exit(1)

    size_mb = EXE_PATH.stat().st_size / (1024 * 1024)
    log('构建成功！')
    log('exe 路径: ' + str(EXE_PATH))
    log('exe 大小: ' + str(round(size_mb, 2)) + ' MB')
    log('')
    log('使用方式：')
    log('  双击 ' + EXE_NAME + '.exe                 # 打开图形界面')
    log('  ' + EXE_NAME + '.exe list                 # 在命令行查看工作区/会话')
    log('  ' + EXE_NAME + '.exe delete 1 3           # 在命令行删除编号 1 和 3 的会话')
    log('  ' + EXE_NAME + '.exe delete-old           # 删除超过 1 小时的历史会话')
    log('  ' + EXE_NAME + '.exe clean                # 清理缓存残留')
    log('')
    log('图标已嵌入 exe 内部，可以把这个 exe 单独复制到任何地方使用。')


if __name__ == '__main__':
    main()
