'''
DSH 会话管理工具：提供“可视化界面”和“命令行”两种操作方式。

=====================================================================
【可视化界面】
    python manage_sessions.py              # 直接运行，打开图形界面
    python manage_sessions.py gui          # 同上

    图形界面会以树形结构列出：
        - 每个工作区的名字、会话数量、占用大小、最后修改时间；
        - 每个工作区下面嵌套显示该工作区的每个会话；
        - 当前正在进行的会话会标“受保护”，不会被误删；
        - 可以多选后删除指定会话、删除整个工作区（含其全部会话）、
          删除全部历史会话；
        - 删除时会同时清理磁盘上的会话文件夹，以及 DSH 的
          workspace.json / session_projcache.json 缓存，保证不留下残留。

【命令行】
    python manage_sessions.py list         # 按工作区分组列出所有会话
    python manage_sessions.py delete 1 3   # 删除编号为 1 和 3 的会话
    python manage_sessions.py delete-old   # 删除所有“非当前”的历史会话
    python manage_sessions.py clean        # 清理缓存中已不存在的会话/工作区记录
    python manage_sessions.py build-exe    # 调用 build_exe.py 生成独立 exe

【安全说明】
    - 当前正在进行的会话会被自动保护；
    - delete-old 只删“最后修改时间超过 1 小时”的旧会话；
    - 图形界面和命令行在真正删除前都会确认；
    - 删除的会话无法恢复，请确认好再删。
=====================================================================
'''

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------
DSH_HOME = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh')))
SESSIONS_DIR = DSH_HOME / 'sessions'
STORAGES_DIR = DSH_HOME / 'storages'
WORKSPACE_JSON = STORAGES_DIR / 'workspace.json'
SESSION_PROJCACHE_JSON = STORAGES_DIR / 'session_projcache.json'

# 当前正在进行的会话 ID（DSH 运行时一般会设置 DSH_SESSION_ID）
CURRENT_SESSION_ID = os.environ.get('DSH_SESSION_ID', '')

# delete-old 的“历史会话”判定门槛（秒），默认 1 小时
OLD_THRESHOLD_SECONDS = 60 * 60

# 图形界面相关
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    _TK_AVAILABLE = True
except Exception:  # 无 GUI 环境时仍可使用命令行
    _TK_AVAILABLE = False


# ----------------------------------------------------------------------
# 小工具函数
# ----------------------------------------------------------------------
def decode_workspace(key: str) -> str:
    r'''把工作区文件夹名尽量还原成可读路径。

    例如:
        --E-AAA_software-Deepseek-MyWorkspace-My_first_project--
    会被还原成:
        E:\AAA_software\Deepseek\MyWorkspace\My_first_project
    '''
    k = key
    if k.startswith('--'):
        k = k[2:]
    if k.endswith('--'):
        k = k[:-2]
    path = k.replace('-', '\\')
    # DSH 编码盘符时把 E:\ 存成了 E-（去掉了冒号），这里把它还原成 E:\
    if len(path) >= 2 and path[1] == '\\' and path[0].isalpha():
        path = path[0] + ':' + path[1:]
    return path


def encode_workspace(path_str) -> str:
    '''与 decode_workspace 相反：把真实路径编码成 DSH 的工作区文件夹名。'''
    p = str(Path(path_str))
    # DSH 编码盘符时会把 E:\ 变成 E-（冒号被去掉）
    if len(p) >= 2 and p[1] == ':':
        p = p[0] + p[2:]
    return '--' + p.replace('\\', '-') + '--'


def format_size(num_bytes) -> str:
    '''把字节数变成易读的大小（KB / MB）。'''
    try:
        num_bytes = int(num_bytes or 0)
    except (TypeError, ValueError):
        num_bytes = 0
    if num_bytes < 1024:
        return f'{num_bytes} B'
    if num_bytes < 1024 * 1024:
        return f'{num_bytes / 1024:.1f} KB'
    return f'{num_bytes / (1024 * 1024):.1f} MB'


def format_age(seconds) -> str:
    '''把“距离现在的秒数”变成易读时长。'''
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds < 60:
        return f'{int(seconds)} 秒前'
    if seconds < 3600:
        return f'{int(seconds // 60)} 分钟前'
    if seconds < 86400:
        return f'{int(seconds // 3600)} 小时前'
    return f'{int(seconds // 86400)} 天前'


def format_mtime(timestamp) -> str:
    '''把时间戳格式化成简短日期时间。'''
    try:
        if not timestamp:
            return '-'
        return datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OSError):
        return '-'


def is_session_dir(path: Path) -> bool:
    '''判断一个文件夹是否是一个会话文件夹。'''
    if not path.is_dir():
        return False
    if path.name.startswith('session-'):
        return True
    return (path / 'session.jsonl.zstd').exists()


def dir_total_size_mtime(path: Path):
    '''统计一个文件夹的总大小和最后修改时间。'''
    total = 0
    mtime = 0.0
    for f in path.rglob('*'):
        if f.is_file():
            try:
                st = f.stat()
                total += st.st_size
                mtime = max(mtime, st.st_mtime)
            except OSError:
                continue
    return total, mtime


def find_workspace_dir_by_entry_path(path_str):
    '''根据 workspace.json 里的真实路径，反查 sessions 目录下的工作区文件夹。'''
    if not path_str or not SESSIONS_DIR.exists():
        return None
    norm_target = os.path.normcase(os.path.normpath(str(path_str)))
    # 先按 DSH 的编码规则直接拼出文件夹名找，最快也最准确
    direct = SESSIONS_DIR / encode_workspace(path_str)
    if direct.is_dir():
        return direct
    # 找不到再遍历比对解码后的路径
    for d in SESSIONS_DIR.iterdir():
        if d.is_dir():
            try:
                if os.path.normcase(os.path.normpath(decode_workspace(d.name))) == norm_target:
                    return d
            except OSError:
                continue
    return None


# ----------------------------------------------------------------------
# JSON 缓存读写
# ----------------------------------------------------------------------
def _load_json(path: Path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _save_json(path: Path, data) -> bool:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------
# 会话扫描
# ----------------------------------------------------------------------
def load_session_titles() -> dict:
    '''从 session_projcache.json 读取每个会话的标题，用于界面显示。'''
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return {}
    tables = data.get('tables') or {}
    sessions = tables.get('sessions') or {}
    if not isinstance(sessions, dict):
        return {}
    titles = {}
    for sid, obj in sessions.items():
        if isinstance(obj, dict):
            title = (obj.get('rows') or {}).get('title') or {}
            if isinstance(title, dict):
                titles[sid] = title.get('val')
    return titles


def scan_workspaces() -> list:
    '''扫描 sessions 目录，返回“工作区 -> 会话”的树形列表。

    每个工作区 dict:
        key, path, name, sessions, session_count, size, mtime, is_current
    每个会话 dict:
        workspace_key, workspace_path, session_id, path, title,
        size, mtime, age, is_current
    '''
    workspaces = []
    if not SESSIONS_DIR.exists():
        return workspaces

    titles = load_session_titles()
    now = datetime.now().timestamp()

    try:
        ws_dirs = sorted(
            [p for p in SESSIONS_DIR.iterdir() if p.is_dir()],
            key=lambda p: p.name.lower(),
        )
    except OSError:
        return workspaces

    for ws_dir in ws_dirs:
        sessions = []
        try:
            children = sorted(ws_dir.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            children = []

        for child in children:
            if not is_session_dir(child):
                continue
            session_file = child / 'session.jsonl.zstd'
            if session_file.is_file():
                try:
                    st = session_file.stat()
                    size = st.st_size
                    mtime = st.st_mtime
                except OSError:
                    size, mtime = dir_total_size_mtime(child)
            else:
                size, mtime = dir_total_size_mtime(child)

            sessions.append({
                'workspace_key': ws_dir.name,
                'workspace_path': ws_dir,
                'session_id': child.name,
                'path': child,
                'title': titles.get(child.name),
                'size': size,
                'mtime': mtime,
                'age': max(0.0, now - mtime),
                'is_current': False,
            })

        workspaces.append({
            'key': ws_dir.name,
            'path': ws_dir,
            'name': decode_workspace(ws_dir.name),
            'sessions': sessions,
            'session_count': len(sessions),
            'size': sum(s['size'] for s in sessions),
            'mtime': max([s['mtime'] for s in sessions], default=0.0),
            'is_current': False,
        })

    mark_current_session(workspaces)
    return workspaces


def mark_current_session(workspaces: list):
    '''标记哪个会话是“当前正在进行的会话”。'''
    flat = [s for ws in workspaces for s in ws['sessions']]

    for s in flat:
        s['is_current'] = False

    if CURRENT_SESSION_ID:
        matched = False
        for s in flat:
            if s['session_id'] == CURRENT_SESSION_ID:
                s['is_current'] = True
                matched = True
        if not matched and flat:
            newest = max(flat, key=lambda s: s['mtime'])
            newest['is_current'] = True
    elif flat:
        newest = max(flat, key=lambda s: s['mtime'])
        newest['is_current'] = True

    for ws in workspaces:
        ws['is_current'] = any(s['is_current'] for s in ws['sessions'])
    return workspaces


def get_workspaces() -> list:
    '''返回带“当前会话”标记的工作区列表。'''
    return scan_workspaces()


def get_sessions() -> list:
    '''返回扁平的会话列表（兼容旧命令行逻辑）。'''
    return [s for ws in get_workspaces() for s in ws['sessions']]



# ----------------------------------------------------------------------
# 删除时的缓存清理（保证删干净，不残留）
# ----------------------------------------------------------------------
def remove_sessions_from_projcache(session_ids) -> bool:
    '''从 session_projcache.json 中删除指定会话的缓存记录。成功或无需处理返回 True。'''
    session_ids = set(session_ids)
    if not session_ids:
        return True
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return True
    tables = data.get('tables') or {}
    sessions = tables.get('sessions') or {}
    if not isinstance(sessions, dict):
        return True
    changed = False
    for sid in list(sessions.keys()):
        if sid in session_ids:
            del sessions[sid]
            changed = True
    if changed:
        return _save_json(SESSION_PROJCACHE_JSON, data)
    return True


def remove_sessions_from_workspace_json(session_ids) -> bool:
    '''从 workspace.json 的所有工作区里移除指定会话。成功或无需处理返回 True。

    如果某个工作区移除后已经没有会话、并且磁盘上对应的工作区文件夹也已经
    不存在了，就顺便把该工作区条目也删掉，避免残留一个空壳工作区。
    '''
    session_ids = set(session_ids)
    if not session_ids:
        return True
    data = _load_json(WORKSPACE_JSON)
    if not data:
        return True
    tables = data.get('tables') or {}
    workspaces = tables.get('workspaces') or {}
    if not isinstance(workspaces, dict):
        return True

    changed = False
    for ws_id in list(workspaces.keys()):
        entry = workspaces.get(ws_id)
        if not isinstance(entry, dict):
            continue
        old_ids = entry.get('sessionIds') or []
        if not isinstance(old_ids, list):
            old_ids = []
        new_ids = [sid for sid in old_ids if sid not in session_ids]
        if new_ids != old_ids:
            entry['sessionIds'] = new_ids
            changed = True
        if not new_ids:
            if find_workspace_dir_by_entry_path(entry.get('path', '')) is None:
                del workspaces[ws_id]
                _remove_workspace_id_from_global(data, ws_id)
                changed = True

    if _remove_session_ids_from_archived(data, session_ids):
        changed = True

    if changed:
        return _save_json(WORKSPACE_JSON, data)
    return True


def remove_workspace_from_workspace_json(workspace_key: str, session_ids) -> bool:
    '''删除整个工作区后，从 workspace.json 中移除该工作区条目。成功或无需处理返回 True。'''
    session_ids = set(session_ids)
    data = _load_json(WORKSPACE_JSON)
    if not data:
        return True
    tables = data.get('tables') or {}
    workspaces = tables.get('workspaces') or {}
    if not isinstance(workspaces, dict):
        return True

    norm_target = os.path.normcase(os.path.normpath(decode_workspace(workspace_key)))
    ids_to_remove = []

    for ws_id, entry in workspaces.items():
        if not isinstance(entry, dict):
            continue
        entry_path = entry.get('path', '')
        if entry_path and os.path.normcase(os.path.normpath(str(entry_path))) == norm_target:
            ids_to_remove.append(ws_id)

    if not ids_to_remove:
        for ws_id, entry in workspaces.items():
            if not isinstance(entry, dict):
                continue
            old_ids = set(entry.get('sessionIds') or [])
            if old_ids & session_ids:
                ids_to_remove.append(ws_id)

    changed = False
    for ws_id in ids_to_remove:
        if ws_id in workspaces:
            del workspaces[ws_id]
            changed = True

    if ids_to_remove:
        _remove_workspace_id_from_global(data, *ids_to_remove)

    for entry in workspaces.values():
        if not isinstance(entry, dict):
            continue
        old_ids = entry.get('sessionIds') or []
        if not isinstance(old_ids, list):
            old_ids = []
        new_ids = [sid for sid in old_ids if sid not in session_ids]
        if new_ids != old_ids:
            entry['sessionIds'] = new_ids
            changed = True

    if _remove_session_ids_from_archived(data, session_ids):
        changed = True

    if changed:
        return _save_json(WORKSPACE_JSON, data)
    return True


def _remove_workspace_id_from_global(data: dict, *workspace_ids):
    '''从 workspace.json 的 global.workspaceIds 中移除指定工作区 ID。'''
    global_part = data.get('global')
    if not isinstance(global_part, dict):
        return
    ids = global_part.get('workspaceIds')
    if not isinstance(ids, list):
        return
    remove_set = set(workspace_ids)
    new_ids = [x for x in ids if x not in remove_set]
    if new_ids != ids:
        global_part['workspaceIds'] = new_ids


def _remove_session_ids_from_archived(data: dict, session_ids) -> bool:
    '''从 workspace.json 的 global.archivedSessionIds 中移除指定会话 ID。'''
    global_part = data.get('global')
    if not isinstance(global_part, dict):
        return False
    archived = global_part.get('archivedSessionIds')
    if not isinstance(archived, list):
        return False
    remove_set = set(session_ids)
    new_ids = [x for x in archived if x not in remove_set]
    if new_ids != archived:
        global_part['archivedSessionIds'] = new_ids
        return True
    return False


# ----------------------------------------------------------------------
# 实际删除动作
# ----------------------------------------------------------------------
def _remove_workspace_dir_if_no_session_dirs(ws_dir: Path) -> bool:
    '''如果工作区文件夹里已经没有任何会话文件夹，就把整个工作区文件夹删掉。'''
    try:
        if not ws_dir.exists():
            return True
        if not ws_dir.is_dir():
            return False
        remaining_dirs = [p for p in ws_dir.iterdir() if p.is_dir()]
        if not remaining_dirs:
            shutil.rmtree(ws_dir)
            return True
        return False
    except OSError:
        return False


def perform_delete_sessions(sessions) -> tuple:
    '''删除指定会话。返回 (成功删除的会话列表, 被自动清掉的工作区列表, 失败列表)。'''
    deleted = []
    removed_ws_dirs = []
    failed = []

    ws_dirs = {}
    for s in sessions:
        if s.get('is_current'):
            failed.append((s, '当前会话受保护，不能删除'))
            continue
        try:
            shutil.rmtree(s['path'])
        except OSError as ex:
            failed.append((s, '删除失败: ' + str(ex)))
            continue
        deleted.append(s)
        ws_dirs[s['workspace_path']] = s['workspace_key']

    for ws_dir in ws_dirs:
        if _remove_workspace_dir_if_no_session_dirs(ws_dir):
            removed_ws_dirs.append(ws_dir)

    if deleted:
        ids = [s['session_id'] for s in deleted]
        try:
            if not remove_sessions_from_projcache(ids):
                failed.append((None, '清理 session_projcache.json 失败'))
        except Exception as ex:
            failed.append((None, '清理 session_projcache.json 失败: ' + str(ex)))
        try:
            if not remove_sessions_from_workspace_json(ids):
                failed.append((None, '清理 workspace.json 失败'))
        except Exception as ex:
            failed.append((None, '清理 workspace.json 失败: ' + str(ex)))

    return deleted, removed_ws_dirs, failed


def perform_delete_workspaces(workspaces) -> tuple:
    '''删除整个工作区（含其全部会话），并清理所有缓存记录。'''
    removed_ws = []
    failed = []

    for ws in workspaces:
        if ws.get('is_current'):
            failed.append((ws, '工作区包含当前会话，受保护，不能删除'))
            continue
        try:
            shutil.rmtree(ws['path'])
        except OSError as ex:
            failed.append((ws, '删除失败: ' + str(ex)))
            continue
        removed_ws.append(ws)

        session_ids = [s['session_id'] for s in ws['sessions']]
        try:
            if not remove_sessions_from_projcache(session_ids):
                failed.append((ws, '清理 session_projcache.json 失败'))
        except Exception as ex:
            failed.append((ws, '清理 session_projcache.json 失败: ' + str(ex)))
        try:
            if not remove_workspace_from_workspace_json(ws['key'], session_ids):
                failed.append((ws, '清理 workspace.json 失败'))
        except Exception as ex:
            failed.append((ws, '清理 workspace.json 失败: ' + str(ex)))

    return removed_ws, failed


def perform_delete_old_sessions(workspaces) -> tuple:
    '''删除所有“非当前”且最后修改时间超过阈值的旧会话。'''
    old = [
        s for ws in workspaces for s in ws['sessions']
        if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
    ]
    if not old:
        return [], [], []
    return perform_delete_sessions(old)


def perform_clean_residue() -> dict:
    '''清理缓存/磁盘中已经“没有对应会话/工作区”的残留。'''
    result = {
        'empty_workspace_dirs': 0,
        'projcache_orphans': 0,
        'workspace_entries_removed': 0,
        'workspace_session_ids_removed': 0,
        'archived_session_ids_removed': 0,
    }

    live = get_workspaces()
    live_session_ids = {s['session_id'] for ws in live for s in ws['sessions']}

    if SESSIONS_DIR.exists():
        for d in list(SESSIONS_DIR.iterdir()):
            if not d.is_dir():
                continue
            try:
                has_session_dir = any(is_session_dir(c) for c in d.iterdir())
            except OSError:
                has_session_dir = True
            if not has_session_dir:
                try:
                    shutil.rmtree(d)
                    result['empty_workspace_dirs'] += 1
                except OSError:
                    continue

    data = _load_json(SESSION_PROJCACHE_JSON)
    if data:
        sessions = (data.get('tables') or {}).get('sessions') or {}
        if isinstance(sessions, dict):
            changed = False
            for sid in list(sessions.keys()):
                if sid not in live_session_ids:
                    del sessions[sid]
                    result['projcache_orphans'] += 1
                    changed = True
            if changed:
                _save_json(SESSION_PROJCACHE_JSON, data)

    data = _load_json(WORKSPACE_JSON)
    if data:
        workspaces = (data.get('tables') or {}).get('workspaces') or {}
        if isinstance(workspaces, dict):
            changed = False
            for ws_id in list(workspaces.keys()):
                entry = workspaces.get(ws_id)
                if not isinstance(entry, dict):
                    continue
                ws_dir = find_workspace_dir_by_entry_path(entry.get('path', ''))
                if ws_dir is None:
                    del workspaces[ws_id]
                    result['workspace_entries_removed'] += 1
                    changed = True
                    continue
                old_ids = entry.get('sessionIds') or []
                if not isinstance(old_ids, list):
                    old_ids = []
                new_ids = [sid for sid in old_ids if sid in live_session_ids]
                if new_ids != old_ids:
                    entry['sessionIds'] = new_ids
                    result['workspace_session_ids_removed'] += len(old_ids) - len(new_ids)
                    changed = True
            global_part = data.get('global')
            if not isinstance(global_part, dict):
                global_part = {}
                data['global'] = global_part
            global_ids_changed = False
            global_ids = global_part.get('workspaceIds')
            if isinstance(global_ids, list):
                new_global_ids = [x for x in global_ids if x in workspaces]
                if new_global_ids != global_ids:
                    global_part['workspaceIds'] = new_global_ids
                    global_ids_changed = True
            else:
                global_part['workspaceIds'] = []
            archived = global_part.get('archivedSessionIds')
            if isinstance(archived, list):
                before = len(archived)
                global_part['archivedSessionIds'] = [x for x in archived if x in live_session_ids]
                result['archived_session_ids_removed'] += before - len(global_part['archivedSessionIds'])
            if changed or global_ids_changed or result['archived_session_ids_removed'] > 0:
                _save_json(WORKSPACE_JSON, data)

    return result


# ----------------------------------------------------------------------
# 命令行输出
# ----------------------------------------------------------------------
def print_workspaces(workspaces):
    '''按“工作区 -> 会话”分组打印。'''
    total_ws = len(workspaces)
    total_sessions = sum(ws['session_count'] for ws in workspaces)
    total_size = sum(ws['size'] for ws in workspaces)

    if total_ws == 0:
        print('没有找到任何工作区 / 会话记录。')
        return

    print()
    print('会话目录: ' + str(SESSIONS_DIR))
    print('共 ' + str(total_ws) + ' 个工作区，' + str(total_sessions) + ' 个会话，总占用 ' + format_size(total_size))
    print()

    idx = 0
    for wi, ws in enumerate(workspaces, 1):
        mark = '  [包含当前会话]' if ws['is_current'] else ''
        print('[' + str(wi) + '] 工作区: ' + ws['name'] + '  (' + str(ws['session_count']) + ' 个会话, ' + format_size(ws['size']) + ')' + mark)
        if not ws['sessions']:
            print('    (此工作区中还没有会话)')
            continue
        for s in ws['sessions']:
            idx += 1
            cur = '  <- 当前会话' if s['is_current'] else ''
            title = s.get('title') or '(无标题)'
            print(
                '    [' + str(idx) + '] ' + s['session_id'] + '  '
                + format_size(s['size']) + '  ' + format_age(s['age']) + '  '
                + title + cur
            )
    print()


def confirm_delete(targets) -> bool:
    '''打印要删除的会话，并让用户输入 yes 确认。'''
    print()
    print('即将删除以下会话：')
    for s in targets:
        print('  - ' + decode_workspace(s['workspace_key']) + '  (会话 ' + s['session_id'] + ')')
    print()
    answer = input('确认删除吗？输入 yes 继续，其它任何输入取消: ').strip().lower()
    return answer == 'yes'


# ----------------------------------------------------------------------
# 生成独立 exe
# ----------------------------------------------------------------------
def cmd_build_exe():
    '''
    运行 build_exe.py，把当前程序打包成一个独立的 exe 文件。

    设计思路（防止污染 Python 本体）：
        - 这个命令本身可能是在“系统 Python”里运行的；
        - 但我们不会用系统 Python 去 pip install，而是找到项目里的 .venv；
        - 如果 .venv 不存在，就先用当前 Python 创建 .venv；
        - 然后用 .venv\\Scripts\\python.exe 去执行 build_exe.py；
        - build_exe.py 内部还会再做一次“虚拟环境检查”，确保万无一失。

    生成的 exe 位于 dist\\DSH_SessionManager.exe，功能完整：
        - 双击 exe 打开图形界面；
        - 在命令行执行 DSH_SessionManager.exe list / delete / delete-old / clean；
        - 图标会被嵌入到 exe 中，不需要附带任何 .ico 或 .py 文件。
    '''
    # 如果当前运行的是已经打包好的 exe，那么 sys.frozen 为 True。
    # build-exe 需要源码目录、.venv 和 PyInstaller，是“源码项目里的开发功能”；
    # exe 本身已经包含图形界面和全部会话管理命令，所以这里给一个清晰提示即可。
    if getattr(sys, 'frozen', False):
        print('当前运行的是打包后的 exe。')
        print('build-exe 是源码项目里的开发/构建功能，请回到源码目录运行:')
        print('    python manage_sessions.py build-exe')
        return 1

    # 项目目录：manage_sessions.py 和 build_exe.py 都在这个目录下
    project_dir = Path(__file__).resolve().parent

    # 构建脚本必须存在
    build_script = project_dir / 'build_exe.py'
    if not build_script.exists():
        print('找不到构建脚本: ' + str(build_script))
        print('请确认 build_exe.py 和 manage_sessions.py 在同一个目录中。')
        return 1

    # Windows 下 venv 的 python 解释器路径固定是 .venv\\Scripts\\python.exe
    venv_dir = project_dir / '.venv'
    venv_python = venv_dir / 'Scripts' / 'python.exe'

    # 如果没有虚拟环境，先创建一个。这里使用的还是“当前 Python”，
    # 但只用来执行 python -m venv，不会安装任何第三方包到系统 Python。
    if not venv_python.exists():
        print('没有找到项目虚拟环境 .venv，正在创建...')
        print('虚拟环境路径: ' + str(venv_dir))
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', str(venv_dir)])
        except Exception as ex:
            print('创建虚拟环境失败: ' + str(ex))
            return 1
        if not venv_python.exists():
            print('创建虚拟环境后仍然找不到: ' + str(venv_python))
            return 1
        print('虚拟环境创建完成。')

    print('使用项目虚拟环境执行构建:')
    print('  Python: ' + str(venv_python))
    print('  脚本:   ' + str(build_script))
    print()

    # 把构建工作交给 .venv 里的 python。
    # build_exe.py 会在 .venv 内安装 PyInstaller/Pillow，不会污染系统 Python。
    return subprocess.call([str(venv_python), str(build_script)])


# ----------------------------------------------------------------------
# 命令行命令实现
# ----------------------------------------------------------------------
def cmd_list(workspaces):
    print_workspaces(workspaces)


def cmd_delete(workspaces, indexes):
    '''按编号删除指定会话（编号从 1 开始）。'''
    flat = [s for ws in workspaces for s in ws['sessions']]
    if not indexes:
        print('用法: python manage_sessions.py delete <编号> [编号...]')
        print('先用 list 看看有哪些编号。')
        return

    targets = []
    for idx in indexes:
        try:
            n = int(idx)
        except ValueError:
            print('编号 ' + str(idx) + ' 不是有效编号，跳过。')
            continue
        if not (1 <= n <= len(flat)):
            print('编号 ' + str(n) + ' 不存在，跳过（有效范围 1~' + str(len(flat)) + '）。')
            continue
        s = flat[n - 1]
        if s['is_current']:
            print('编号 ' + str(n) + ' 是当前会话，已被保护，不能删除。')
            continue
        targets.append(s)

    if not targets:
        print('没有可删除的会话。')
        return

    if confirm_delete(targets):
        deleted, removed_ws, failed = perform_delete_sessions(targets)
        print()
        print('完成：已删除 ' + str(len(deleted)) + ' 个会话，自动清理 ' + str(len(removed_ws)) + ' 个空工作区。')
        for obj, msg in failed:
            name = obj.get('session_id') if isinstance(obj, dict) else str(obj)
            print('  注意: ' + name + ' —— ' + msg)
    else:
        print('已取消，没有删除任何东西。')


def cmd_delete_old(workspaces):
    '''删除所有“历史会话”（非当前且超过 1 小时）。'''
    targets = [
        s for ws in workspaces for s in ws['sessions']
        if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
    ]
    if not targets:
        print('没有可删除的历史会话（可能只有当前会话，或其它会话都还很新）。')
        return

    if confirm_delete(targets):
        deleted, removed_ws, failed = perform_delete_sessions(targets)
        print()
        print('完成：已删除 ' + str(len(deleted)) + ' 个会话，自动清理 ' + str(len(removed_ws)) + ' 个空工作区。')
        for obj, msg in failed:
            name = obj.get('session_id') if isinstance(obj, dict) else str(obj)
            print('  注意: ' + name + ' —— ' + msg)
    else:
        print('已取消，没有删除任何东西。')


def cmd_clean(workspaces):
    '''清理缓存/磁盘残留。'''
    result = perform_clean_residue()
    print('清理完成：')
    print('  - 删除空工作区文件夹: ' + str(result['empty_workspace_dirs']) + ' 个')
    print('  - 删除 session_projcache 孤儿记录: ' + str(result['projcache_orphans']) + ' 条')
    print('  - 删除 workspace.json 孤儿工作区: ' + str(result['workspace_entries_removed']) + ' 条')
    print('  - 清理 workspace.json 中失效 sessionIds: ' + str(result['workspace_session_ids_removed']) + ' 条')
    print('  - 清理 workspace.json 中失效 archivedSessionIds: ' + str(result['archived_session_ids_removed']) + ' 条')
    print_workspaces(get_workspaces())


def print_usage():
    print(__doc__)


# ----------------------------------------------------------------------
# 图形界面
# ----------------------------------------------------------------------
class SessionManagerApp:
    '''DSH 会话管理图形界面。'''

    def __init__(self, root):
        self.root = root
        self.root.title('DSH 会话管理')
        self.root.geometry('1180x680')
        self.root.minsize(900, 520)

        self.workspaces = []
        self.item_data = {}

        self._build_widgets()
        self.refresh()

    def _build_widgets(self):
        top = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        self.summary_var = tk.StringVar(value='正在加载...')
        ttk.Label(top, textvariable=self.summary_var, font=('Microsoft YaHei', 11, 'bold')).pack(anchor=tk.W)
        self.current_var = tk.StringVar(value='')
        ttk.Label(top, textvariable=self.current_var, foreground='#c47b00').pack(anchor=tk.W)

        mid = ttk.Frame(self.root, padding=(12, 6))
        mid.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(mid)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ('type', 'count', 'size', 'mtime', 'note')
        self.tree = ttk.Treeview(tree_frame, columns=columns, selectmode='extended', show='tree headings')
        self.tree.heading('#0', text='名称 / 会话')
        self.tree.heading('type', text='类型')
        self.tree.heading('count', text='会话数')
        self.tree.heading('size', text='大小')
        self.tree.heading('mtime', text='最后修改')
        self.tree.heading('note', text='备注')

        self.tree.column('#0', width=470, minwidth=220, stretch=True)
        self.tree.column('type', width=60, minwidth=50, anchor=tk.CENTER, stretch=False)
        self.tree.column('count', width=70, minwidth=55, anchor=tk.CENTER, stretch=False)
        self.tree.column('size', width=95, minwidth=70, anchor=tk.E, stretch=False)
        self.tree.column('mtime', width=150, minwidth=110, anchor=tk.CENTER, stretch=False)
        self.tree.column('note', width=150, minwidth=90, anchor=tk.W, stretch=False)

        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(mid, padding=(12, 0, 0, 0))
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        buttons = [
            ('刷新', self.refresh),
            ('展开全部', self._expand_all),
            ('折叠全部', self._collapse_all),
            ('', None),
            ('删除选中会话', self._delete_selected_sessions),
            ('删除选中工作区', self._delete_selected_workspaces),
            ('', None),
            ('删除全部历史会话', self._delete_old_sessions),
            ('清理缓存残留', self._clean_residue),
        ]
        for text, cmd in buttons:
            if not text:
                ttk.Separator(btn_frame).pack(fill=tk.X, pady=6)
                continue
            ttk.Button(btn_frame, text=text, width=18, command=cmd).pack(fill=tk.X, pady=4)

        self.status_var = tk.StringVar(value='就绪。选择左侧项目后可执行删除操作。')
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(8, 3))
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def refresh(self):
        self.workspaces = get_workspaces()
        self.item_data.clear()
        self.tree.delete(*self.tree.get_children())

        total_ws = len(self.workspaces)
        total_sessions = sum(ws['session_count'] for ws in self.workspaces)
        total_size = sum(ws['size'] for ws in self.workspaces)
        current_names = [
            s['session_id'] for ws in self.workspaces for s in ws['sessions'] if s['is_current']
        ]

        self.summary_var.set(
            '工作区 ' + str(total_ws) + ' 个    会话 ' + str(total_sessions)
            + ' 个    总占用 ' + format_size(total_size)
        )
        self.current_var.set(
            '当前会话（受保护）: '
            + (', '.join(current_names) if current_names else '自动检测最近修改的会话')
        )

        for ws in self.workspaces:
            ws_note = '包含当前会话' if ws['is_current'] else ('无会话' if ws['session_count'] == 0 else '')
            ws_text = '工作区: ' + ws['name']
            ws_iid = self.tree.insert(
                '',
                'end',
                text=ws_text,
                values=('工作区', ws['session_count'], format_size(ws['size']), format_mtime(ws['mtime']), ws_note),
                open=True,
            )
            self.item_data[ws_iid] = {'kind': 'workspace', 'data': ws}

            for s in ws['sessions']:
                s_note = '受保护' if s['is_current'] else '可删除'
                title = s.get('title') or s['session_id']
                s_text = '会话: ' + title
                s_iid = self.tree.insert(
                    ws_iid,
                    'end',
                    text=s_text,
                    values=('会话', '', format_size(s['size']), format_mtime(s['mtime']), s_note),
                )
                self.item_data[s_iid] = {'kind': 'session', 'data': s}

        self.status_var.set('已刷新：' + str(total_ws) + ' 个工作区，' + str(total_sessions) + ' 个会话。')

    def _expand_all(self):
        for iid in self.tree.get_children():
            self.tree.item(iid, open=True)

    def _collapse_all(self):
        for iid in self.tree.get_children():
            self.tree.item(iid, open=False)

    def _selected_sessions(self):
        '''从当前选择中收集要删除的会话（选择工作区时视为选择其全部会话）。'''
        targets = []
        blocked = []
        for iid in self.tree.selection():
            item = self.item_data.get(iid)
            if not item:
                continue
            if item['kind'] == 'session':
                s = item['data']
                if s['is_current']:
                    blocked.append(s['session_id'])
                else:
                    targets.append(s)
            elif item['kind'] == 'workspace':
                ws = item['data']
                for s in ws['sessions']:
                    if s['is_current']:
                        blocked.append(s['session_id'])
                    else:
                        targets.append(s)
        seen = set()
        unique = []
        for s in targets:
            if s['session_id'] not in seen:
                seen.add(s['session_id'])
                unique.append(s)
        return unique, blocked

    def _selected_workspaces(self):
        '''从当前选择中收集要删除的工作区。'''
        targets = []
        blocked = []
        for iid in self.tree.selection():
            item = self.item_data.get(iid)
            if not item:
                continue
            if item['kind'] == 'workspace':
                ws = item['data']
                if ws['is_current']:
                    blocked.append(ws['name'])
                else:
                    targets.append(ws)
        return targets, blocked

    def _describe_session_targets(self, sessions):
        lines = ['会话 ' + str(len(sessions)) + ' 个：']
        for s in sessions[:12]:
            title = s.get('title') or s['session_id']
            lines.append('  • ' + title)
        if len(sessions) > 12:
            lines.append('  ... 还有 ' + str(len(sessions) - 12) + ' 个')
        return '\n'.join(lines)

    def _describe_workspace_targets(self, workspaces):
        lines = ['工作区 ' + str(len(workspaces)) + ' 个（包含其全部会话）：']
        total = 0
        for ws in workspaces[:12]:
            lines.append('  • ' + ws['name'] + '  (' + str(ws['session_count']) + ' 个会话)')
            total += ws['session_count']
        if len(workspaces) > 12:
            lines.append('  ... 还有 ' + str(len(workspaces) - 12) + ' 个工作区')
        return '\n'.join(lines), total

    def _delete_selected_sessions(self):
        targets, blocked = self._selected_sessions()
        if blocked:
            messagebox.showwarning(
                '当前会话受保护',
                '以下当前会话不会被删除：\n\n' + '\n'.join('  • ' + s for s in blocked),
                parent=self.root,
            )
        if not targets:
            if not blocked:
                messagebox.showinfo('提示', '请先在左侧选择要删除的会话（或工作区）。', parent=self.root)
            return

        msg = '即将删除：\n\n' + self._describe_session_targets(targets)
        msg += '\n\n删除后会同步清理 DSH 的缓存记录，且不可恢复。\n确认继续吗？'
        if not messagebox.askyesno('确认删除会话', msg, icon='warning', parent=self.root):
            self.status_var.set('已取消。')
            return

        deleted, removed_ws, failed = perform_delete_sessions(targets)
        self.refresh()
        self.status_var.set(
            '已删除 ' + str(len(deleted)) + ' 个会话，自动清理 '
            + str(len(removed_ws)) + ' 个空工作区。'
        )
        if failed:
            self._show_failed(failed)

    def _delete_selected_workspaces(self):
        targets, blocked = self._selected_workspaces()
        if blocked:
            messagebox.showwarning(
                '工作区受保护',
                '以下工作区包含当前会话，不会被删除：\n\n' + '\n'.join('  • ' + s for s in blocked),
                parent=self.root,
            )
        if not targets:
            if not blocked:
                messagebox.showinfo('提示', '请先在左侧选择要删除的工作区。', parent=self.root)
            return

        desc, total_sessions = self._describe_workspace_targets(targets)
        msg = '即将删除：\n\n' + desc + '\n\n共 ' + str(total_sessions) + ' 个会话会一并删除。'
        msg += '\n删除后会同步清理 DSH 的缓存记录，且不可恢复。\n确认继续吗？'
        if not messagebox.askyesno('确认删除工作区', msg, icon='warning', parent=self.root):
            self.status_var.set('已取消。')
            return

        removed_ws, failed = perform_delete_workspaces(targets)
        self.refresh()
        self.status_var.set('已删除 ' + str(len(removed_ws)) + ' 个工作区。')
        if failed:
            self._show_failed(failed)

    def _delete_old_sessions(self):
        targets = [
            s for ws in self.workspaces for s in ws['sessions']
            if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
        ]
        if not targets:
            messagebox.showinfo('提示', '没有可删除的历史会话（可能只有当前会话，或其它会话都还很新）。', parent=self.root)
            return

        msg = '即将删除所有历史会话：\n\n' + self._describe_session_targets(targets)
        msg += '\n\n只删除“非当前”且最后修改超过 1 小时的会话。\n确认继续吗？'
        if not messagebox.askyesno('确认删除历史会话', msg, icon='warning', parent=self.root):
            self.status_var.set('已取消。')
            return

        deleted, removed_ws, failed = perform_delete_old_sessions(self.workspaces)
        self.refresh()
        self.status_var.set(
            '已删除 ' + str(len(deleted)) + ' 个历史会话，自动清理 '
            + str(len(removed_ws)) + ' 个空工作区。'
        )
        if failed:
            self._show_failed(failed)

    def _clean_residue(self):
        msg = (
            '将扫描并清理以下残留：\n\n'
            '  1. sessions 目录中没有会话的空工作区文件夹；\n'
            '  2. session_projcache.json 中已不存在对应会话的记录；\n'
            '  3. workspace.json 中已不存在对应文件夹的工作区条目；\n'
            '  4. workspace.json 工作区条目中指向已不存在会话的 sessionIds；\n'
            '  5. workspace.json 中已不存在会话的 archivedSessionIds。\n\n'
            '当前会话及其所在工作区会被自动保护。\n确认继续吗？'
        )
        if not messagebox.askyesno('清理缓存残留', msg, icon='warning', parent=self.root):
            self.status_var.set('已取消。')
            return

        result = perform_clean_residue()
        self.refresh()
        self.status_var.set(
            '清理完成：删除空工作区 ' + str(result['empty_workspace_dirs']) + ' 个，'
            + '删除 session_projcache 孤儿 ' + str(result['projcache_orphans']) + ' 条，'
            + '删除 workspace.json 孤儿工作区 ' + str(result['workspace_entries_removed']) + ' 条，'
            + '清理失效 sessionIds ' + str(result['workspace_session_ids_removed']) + ' 条，'
            + '清理失效 archivedSessionIds ' + str(result['archived_session_ids_removed']) + ' 条。'
        )

    def _show_failed(self, failed):
        lines = []
        for obj, msg in failed:
            if isinstance(obj, dict):
                name = obj.get('name') or obj.get('session_id') or str(obj)
            else:
                name = str(obj)
            lines.append('  • ' + name + ': ' + msg)
        messagebox.showwarning('部分操作未完成', '以下项目未能完全处理：\n\n' + '\n'.join(lines), parent=self.root)


# ----------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------
def _app_resource(rel_path):
    '''
    定位随程序打包的资源文件（whalegirl 里的鲸鱼娘图标）。

    - PyInstaller 单文件模式：资源被解包到 sys._MEIPASS 临时目录；
    - 源码模式：回退到脚本所在目录。
    找不到时返回 None，调用方自行降级（不设置图标，界面照常启动）。
    '''
    candidates = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / rel_path)
    candidates.append(Path(__file__).resolve().parent / rel_path)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def launch_gui():
    '''启动图形界面。成功返回 0，失败返回 1。'''
    if not _TK_AVAILABLE:
        print('当前 Python 环境没有 tkinter，无法启动图形界面，已回退到命令行列表。')
        print()
        print_workspaces(get_workspaces())
        return 1

    try:
        root = tk.Tk()
    except Exception as ex:
        print('无法启动图形界面（' + str(ex) + '），已回退到命令行列表。')
        print()
        print_workspaces(get_workspaces())
        return 1

    # 设置窗口图标（标题栏 + 任务栏），两者相互独立、互不拖累：
    #   iconbitmap 设置标题栏小图标（Windows 经典图标,最清晰）；
    #   iconphoto  设置任务栏/Alt-Tab 大图标；
    # 任一失败或图标文件缺失都只跳过该项，绝不影响界面启动。
    ico_path = _app_resource(os.path.join('whalegirl', 'DeepSeekHarness-WhaleGirl.ico'))
    if ico_path:
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass
    png_path = _app_resource(os.path.join('whalegirl', 'improved-1.png'))
    if png_path:
        try:
            photo = tk.PhotoImage(file=png_path)
            root.iconphoto(True, photo)
            root._iconphoto_ref = photo  # 持有引用，防止图标被垃圾回收
        except Exception:
            pass

    try:
        app = SessionManagerApp(root)
    except Exception as ex:
        try:
            root.destroy()
        except Exception:
            pass
        print('图形界面初始化失败（' + str(ex) + '），已回退到命令行列表。')
        print()
        print_workspaces(get_workspaces())
        return 1

    root.mainloop()
    return 0



def _attach_parent_console_if_needed():
    '''
    当 exe 是用 PyInstaller --windowed 模式打包时，Windows 不会给它分配
    控制台窗口，因此 sys.stdout / sys.stderr / sys.stdin 都是 None。

    这样做的目的是：
        - 双击 exe 打开图形界面时：没有黑色控制台窗口；
        - 但在一个已经打开的命令行窗口里执行:
              DSH_SessionManager.exe list
          时，命令行功能仍然需要往控制台输出文字。

    解决办法：
        只有当用户“从命令行传入了参数”并且当前进程是 frozen 的 exe 时，
        才尝试调用 Windows API：
            - AttachConsole(-1)：把自己挂到父进程已有的控制台上；
            - 如果父进程没有控制台（例如从资源管理器带参数启动），
              则 AllocConsole() 临时分配一个控制台；
        然后重新打开 CONOUT$ / CONIN$ 作为标准输入输出。
        双击打开（无参数）时不会调用本函数，因此不会出现黑窗口。
    '''
    # 只有 Windows 上的 PyInstaller exe 才需要处理
    if sys.platform != 'win32':
        return
    if not getattr(sys, 'frozen', False):
        return
    # 如果已经有标准输出（例如 --console 模式打包的 exe），就不需要处理
    if sys.stdout is not None:
        return

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32

        # ATTACH_PARENT_PROCESS 的 Windows API 常量就是 0xFFFFFFFF（-1）
        attached = kernel32.AttachConsole(0xFFFFFFFF)
        if not attached:
            # 没有父控制台可以挂载，说明用户可能是从资源管理器/快捷方式
            # 带着 list/delete 等参数启动的。此时为命令行功能临时分配一个
            # 控制台。双击 exe（无参数）不会进入这里，所以仍然没有黑窗口。
            if not kernel32.AllocConsole():
                return

        # 把标准输出/错误/输入重新挂到当前控制台。
        # CONOUT$ 表示“当前控制台输出”，CONIN$ 表示“当前控制台输入”。
        if sys.stdout is None:
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        if sys.stderr is None:
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        if sys.stdin is None:
            sys.stdin = open('CONIN$', 'r', encoding='utf-8', errors='replace')
    except Exception:
        # 挂载失败时保持现状：命令行输出不可见，但程序不会崩溃。
        # GUI 模式完全不依赖本函数。
        pass


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'gui'

    # 关键点：只有传入了命令行参数（list/delete/clean 等）时才尝试挂到
    # 父控制台；无参数双击时走 GUI，不调用它，因此不会弹出黑色终端窗口。
    if cmd not in ('gui', 'ui', '--gui'):
        _attach_parent_console_if_needed()

    if cmd in ('gui', 'ui', '--gui'):
        sys.exit(launch_gui())

    if cmd in ('build-exe', 'build'):
        sys.exit(cmd_build_exe())

    workspaces = get_workspaces()

    if cmd in ('list', 'ls'):
        cmd_list(workspaces)
    elif cmd == 'delete':
        cmd_delete(workspaces, args[1:])
    elif cmd == 'delete-old':
        cmd_delete_old(workspaces)
    elif cmd == 'clean':
        cmd_clean(workspaces)
    elif cmd in ('-h', '--help', 'help'):
        print_usage()
    else:
        print('未知命令: ' + cmd)
        print()
        print_usage()


if __name__ == '__main__':
    main()