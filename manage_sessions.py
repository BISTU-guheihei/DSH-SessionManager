# -*- coding: utf-8 -*-
'''
DSH 会话管理工具 —— 鲸鱼娘守护的会话回收站
=============================================================

提供“可视化界面”和“命令行”两种操作方式，管理 DeepSeek Harness (DSH)
的历史聊天记录：删除（先进回收站、可恢复）、归档/取消归档、
彻底删除、清理缓存残留、搜索过滤。

【图形界面】
    python manage_sessions.py              # 打开图形界面
    python manage_sessions.py gui          # 同上

    特性：
      - DeepSeek 鲸鱼娘主题（壁纸背景 / 圆形头像 / 瓶子装饰）
      - 圆角卡片 + 渐变按钮 + hover 动画 + 点击涟漪 + 呼吸状态灯
      - 会话 / 回收站 双视图，实时搜索过滤
      - 选中会话显示统计详情（轮数 / 步骤 / 耗时 / Token / 上下文压力条）
      - 当前会话自动保护；DSH 运行状态实时显示

【命令行】
    python manage_sessions.py list         # 按工作区分组列出所有会话
    python manage_sessions.py search 关键词 # 按标题 / ID / 工作区搜索
    python manage_sessions.py delete 1 3   # 把编号 1、3 的会话移入回收站
    python manage_sessions.py delete-old   # 移入回收站所有“非当前”且超 1 小时的历史会话
    python manage_sessions.py archive 1 3  # 归档指定会话（从 DSH 活跃列表隐藏）
    python manage_sessions.py unarchive 1 3# 取消归档
    python manage_sessions.py trash        # 列出回收站
    python manage_sessions.py restore 1 3  # 从回收站恢复到原工作区
    python manage_sessions.py empty-trash  # 彻底清空回收站（不可恢复）
    python manage_sessions.py clean        # 清理缓存/磁盘孤儿残留（含结果校验）
    python manage_sessions.py status       # 显示 DSH 状态 / 回收站概况
    python manage_sessions.py build-exe    # 调用 build_exe.py 生成独立 exe

【数据位置】
    聊天记录:  ~/.dsh/sessions/（工作区文件夹 -> 会话文件夹 -> session.jsonl.zstd）
    会话索引:  ~/.dsh/storages/workspace.json（含 archivedSessionIds 归档标记）
    统计缓存:  ~/.dsh/storages/session_projcache.json
    回收站:    ~/.dsh/.trash/（本工具专用，DSH 不会读取）
    支持环境变量 DSH_HOME 覆盖数据目录；DSH_SESSION_ID 指定当前会话。

【安全说明】
    - 当前会话（DSH_SESSION_ID）永不删除；
    - 删除先进回收站；empty-trash / 彻底删除不可恢复；
    - 删除前均有确认；DSH 运行中清理缓存会被写回，工具会提示。
'''

import os
import subprocess
import sys
from pathlib import Path

from session_core import (
    get_workspaces, cmd_list, cmd_search, cmd_delete, cmd_delete_old,
    cmd_clean, cmd_trash, cmd_restore, cmd_empty_trash, cmd_archive,
    cmd_unarchive, cmd_status, print_workspaces, SESSIONS_DIR,
)
from session_gui import launch_gui


def cmd_build_exe():
    '''运行 build_exe.py，在项目 .venv 中打包独立 exe。'''
    if getattr(sys, 'frozen', False):
        print('当前运行的是打包后的 exe。')
        print('build-exe 是源码项目里的开发/构建功能，请回到源码目录运行:')
        print('    python manage_sessions.py build-exe')
        return 1
    project_dir = Path(__file__).resolve().parent
    build_script = project_dir / 'build_exe.py'
    if not build_script.exists():
        print('找不到构建脚本: ' + str(build_script))
        return 1
    if os.name == 'nt':
        venv_python = project_dir / '.venv' / 'Scripts' / 'python.exe'
    else:
        venv_python = project_dir / '.venv' / 'bin' / 'python'
    if not venv_python.exists():
        print('没有找到项目虚拟环境 .venv，正在创建...')
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', str(project_dir / '.venv')])
        except Exception as ex:
            print('创建虚拟环境失败: ' + str(ex))
            return 1
    print('使用项目虚拟环境执行构建: ' + str(venv_python))
    return subprocess.call([str(venv_python), str(build_script)])


def print_usage():
    print(__doc__)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'gui'

    if cmd in ('-h', '--help', 'help'):
        print_usage()
        return 0

    if cmd in ('gui', 'ui', '--gui'):
        return launch_gui()

    if cmd in ('build-exe', 'build'):
        return cmd_build_exe()

    workspaces = get_workspaces()

    if cmd in ('list', 'ls'):
        cmd_list(workspaces)
    elif cmd in ('search', 'find'):
        cmd_search(workspaces, ' '.join(args[1:]))
    elif cmd in ('delete', 'del', 'rm'):
        cmd_delete(workspaces, args[1:])
    elif cmd in ('delete-old', 'delold'):
        cmd_delete_old(workspaces)
    elif cmd == 'archive':
        cmd_archive(workspaces, args[1:])
    elif cmd == 'unarchive':
        cmd_unarchive(workspaces, args[1:])
    elif cmd == 'trash':
        cmd_trash()
    elif cmd in ('restore', 'recover'):
        cmd_restore(args[1:])
    elif cmd in ('empty-trash', 'purge-trash', 'emptrash'):
        cmd_empty_trash()
    elif cmd == 'clean':
        cmd_clean(workspaces, '--yes' in args)
    elif cmd == 'status':
        cmd_status()
    else:
        print('未知命令: ' + cmd)
        print()
        print_usage()
        return 2
    return 0


# ----------------------------------------------------------------------
# Windows: PyInstaller --windowed 打包后挂接父控制台
# ----------------------------------------------------------------------
def _attach_parent_console_if_needed():
    '''windowed exe 无控制台：带参数运行时挂到父控制台，否则命令行输出不可见。'''
    if sys.platform != 'win32':
        return
    if not getattr(sys, 'frozen', False):
        return
    if sys.stdout is not None:
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        attached = kernel32.AttachConsole(0xFFFFFFFF)
        if not attached:
            if not kernel32.AllocConsole():
                return
        if sys.stdout is None:
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        if sys.stderr is None:
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        if sys.stdin is None:
            sys.stdin = open('CONIN$', 'r', encoding='utf-8', errors='replace')
    except Exception:
        pass


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] not in ('gui', 'ui', '--gui'):
        _attach_parent_console_if_needed()
    sys.exit(main())
