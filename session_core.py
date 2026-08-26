# -*- coding: utf-8 -*-
'''DSH 会话管理工具 —— 核心逻辑模块（无 GUI 依赖，可独立测试）。

功能：
- 扫描 DSH 会话（工作区 -> 会话树，含标题/大小/统计/归档标记）
- 回收站（删除先入回收站，可恢复；purge 彻底删除）
- 归档 / 取消归档（复用 DSH 的 archivedSessionIds 机制）
- 清理缓存残留 + 清理结果校验
- DSH 运行检测（归档 / 清理缓存等缓存类操作前提示）
- 命令行界面（list / search / delete / purge / trash / restore / archive 等）
- 跨平台：Windows / macOS / Linux 路径编码与进程检测
'''

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Windows CI runner 默认 cp1252 编码，强制 UTF-8 输出避免中文日志报错
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ----------------------------------------------------------------------
# 平台与路径配置
# ----------------------------------------------------------------------
IS_WINDOWS = os.name == 'nt'

DSH_HOME = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh')))
SESSIONS_DIR = DSH_HOME / 'sessions'
STORAGES_DIR = DSH_HOME / 'storages'
WORKSPACE_JSON = STORAGES_DIR / 'workspace.json'
SESSION_PROJCACHE_JSON = STORAGES_DIR / 'session_projcache.json'
TRASH_DIR = DSH_HOME / '.trash'
TRASH_MANIFEST_NAME = 'manifest.json'

CURRENT_SESSION_ID = os.environ.get('DSH_SESSION_ID', '')
OLD_THRESHOLD_SECONDS = 60 * 60


def is_frozen() -> bool:
    '''是否运行在 PyInstaller 打包的 exe 中。'''
    return bool(getattr(sys, 'frozen', False))


# ----------------------------------------------------------------------
# 工作区目录名编码 / 解码（跨平台）
# ----------------------------------------------------------------------
def decode_workspace(key: str) -> str:
    r'''把 DSH 的工作区文件夹名还原成可读路径。

    Windows 上 DSH 把 E:\AAA\proj 编码成 --E-AAA-proj--（冒号去掉，\\ 换成 -）；
    POSIX 上 /home/user/proj 编码成 --home-user-proj--（/ 换成 -）。
    '''
    k = key
    if k.startswith('--'):
        k = k[2:]
    if k.endswith('--'):
        k = k[:-2]
    if IS_WINDOWS:
        path = k.replace('-', '\\')
        if len(path) >= 2 and path[1] == '\\' and path[0].isalpha():
            path = path[0] + ':' + path[1:]
        return path
    # POSIX：- 还原成 /，补回开头斜杠
    return '/' + k.replace('-', '/')


def encode_workspace(path_str) -> str:
    '''与 decode_workspace 相反：把真实路径编码成 DSH 工作区文件夹名。'''
    p = str(Path(path_str))
    if IS_WINDOWS:
        if len(p) >= 2 and p[1] == ':':
            p = p[0] + p[2:]
        return '--' + p.replace('\\', '-') + '--'
    # POSIX：去掉开头斜杠，/ 换成 -
    if p.startswith('/'):
        p = p[1:]
    return '--' + p.replace('/', '-') + '--'


# ----------------------------------------------------------------------
# 格式化工具
# ----------------------------------------------------------------------
def format_size(num_bytes) -> str:
    try:
        num_bytes = int(num_bytes or 0)
    except (TypeError, ValueError):
        num_bytes = 0
    if num_bytes < 1024:
        return f'{num_bytes} B'
    if num_bytes < 1024 * 1024:
        return f'{num_bytes / 1024:.1f} KB'
    return f'{num_bytes / (1024 * 1024):.1f} MB'


def format_duration(ms) -> str:
    '''毫秒时长 -> 易读。'''
    try:
        ms = float(ms or 0)
    except (TypeError, ValueError):
        ms = 0.0
    if ms < 1000:
        return f'{int(ms)} ms'
    if ms < 60000:
        return f'{ms / 1000:.1f} s'
    if ms < 3600000:
        return f'{ms / 60000:.1f} min'
    return f'{ms / 3600000:.2f} h'


def format_tokens(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    if n >= 1000000:
        return f'{n / 1000000:.2f}M'
    if n >= 1000:
        return f'{n / 1000:.1f}K'
    return str(n)


def format_age(seconds) -> str:
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
    try:
        if not timestamp:
            return '-'
        return datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OSError):
        return '-'


def now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ----------------------------------------------------------------------
# JSON 读写（原子写）
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
# DSH 运行检测
# ----------------------------------------------------------------------
def detect_dsh_running() -> bool:
    '''检测 DSH 是否正在运行（跨平台）。'''
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            ).stdout.lower()
            return 'dsh' in out and ('dsh desktop' in out or 'dsh-web' in out or 'dsh.exe' in out or 'node.exe' in out and 'dsh' in out)
        out = subprocess.run(
            ['ps', '-ax', '-o', 'comm='],
            capture_output=True, text=True, timeout=10,
        ).stdout.lower()
        return 'dsh' in out
    except Exception:
        # 检测失败时保守返回 False（不阻塞用户操作）
        return False


# ----------------------------------------------------------------------
# 会话扫描与统计
# ----------------------------------------------------------------------
def is_session_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name.startswith('session-'):
        return True
    return (path / 'session.jsonl.zstd').exists()


def dir_total_size_mtime(path: Path):
    total = 0
    mtime = 0.0
    try:
        for f in path.rglob('*'):
            if f.is_file():
                try:
                    st = f.stat()
                    total += st.st_size
                    mtime = max(mtime, st.st_mtime)
                except OSError:
                    continue
    except OSError:
        pass
    return total, mtime


def load_session_stats() -> dict:
    '''从 session_projcache.json 读取每个会话的统计信息（供界面/列表展示）。'''
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return {}
    sessions = (data.get('tables') or {}).get('sessions') or {}
    if not isinstance(sessions, dict):
        return {}
    stats = {}
    for sid, obj in sessions.items():
        if not isinstance(obj, dict):
            continue
        rows = obj.get('rows') or {}
        if not isinstance(rows, dict):
            continue
        entry = {}
        title = rows.get('title') or {}
        if isinstance(title, dict):
            entry['title'] = title.get('val')
        s = rows.get('sessionStats') or {}
        if isinstance(s, dict):
            val = s.get('val') or {}
            if isinstance(val, dict):
                entry['turns'] = val.get('turns')
                entry['steps'] = val.get('steps')
                entry['llmMs'] = val.get('llmMs')
                entry['toolMs'] = val.get('toolMs')
        t = rows.get('tokenUsage') or {}
        if isinstance(t, dict):
            val = t.get('val') or {}
            if isinstance(val, dict):
                totals = val.get('totals') or {}
                if isinstance(totals, dict):
                    entry['inputTokens'] = totals.get('uncachedInputTokens')
                    entry['outputTokens'] = totals.get('outputTokens')
                    entry['cacheReadTokens'] = totals.get('cacheReadTokens')
        p = rows.get('contextPressure') or {}
        if isinstance(p, dict):
            val = p.get('val') or {}
            if isinstance(val, dict):
                entry['surfaceTokens'] = val.get('surfaceTokens')
                entry['contextWindow'] = val.get('contextWindow')
        if entry:
            stats[sid] = entry
    return stats


def load_archived_ids() -> list:
    '''读取 workspace.json 里 global.archivedSessionIds。'''
    data = _load_json(WORKSPACE_JSON)
    if not data:
        return []
    global_part = data.get('global') or {}
    ids = global_part.get('archivedSessionIds')
    return list(ids) if isinstance(ids, list) else []


def scan_workspaces() -> list:
    '''扫描 sessions 目录，返回“工作区 -> 会话”树形列表。

    每个工作区 dict: key, path, name, sessions, session_count, size, mtime, is_current
    每个会话 dict:   workspace_key, workspace_path, session_id, path, title,
                     size, mtime, age, is_current, is_archived, stats
    '''
    workspaces = []
    if not SESSIONS_DIR.exists():
        return workspaces

    stats_map = load_session_stats()
    archived_ids = set(load_archived_ids())
    now = datetime.now().timestamp()

    try:
        ws_dirs = sorted([p for p in SESSIONS_DIR.iterdir() if p.is_dir()],
                         key=lambda p: p.name.lower())
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
                    size, mtime = st.st_size, st.st_mtime
                except OSError:
                    size, mtime = dir_total_size_mtime(child)
            else:
                size, mtime = dir_total_size_mtime(child)
            sid = child.name
            st_entry = stats_map.get(sid) or {}
            sessions.append({
                'workspace_key': ws_dir.name,
                'workspace_path': ws_dir,
                'session_id': sid,
                'path': child,
                'title': st_entry.get('title') or stats_map.get(sid, {}).get('title'),
                'size': size,
                'mtime': mtime,
                'age': max(0.0, now - mtime),
                'is_current': False,
                'is_archived': sid in archived_ids,
                'stats': st_entry,
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
            max(flat, key=lambda s: s['mtime'])['is_current'] = True
    elif flat:
        max(flat, key=lambda s: s['mtime'])['is_current'] = True
    for ws in workspaces:
        ws['is_current'] = any(s['is_current'] for s in ws['sessions'])
    return workspaces


def get_workspaces() -> list:
    return scan_workspaces()


# ----------------------------------------------------------------------
# 工作区目录反查
# ----------------------------------------------------------------------
def find_workspace_dir_by_entry_path(path_str):
    if not path_str or not SESSIONS_DIR.exists():
        return None
    norm_target = os.path.normcase(os.path.normpath(str(path_str)))
    direct = SESSIONS_DIR / encode_workspace(path_str)
    if direct.is_dir():
        return direct
    for d in SESSIONS_DIR.iterdir():
        if d.is_dir():
            try:
                if os.path.normcase(os.path.normpath(decode_workspace(d.name))) == norm_target:
                    return d
            except OSError:
                continue
    return None


def _workspace_entry_for_key(data: dict, workspace_key: str):
    '''在 workspace.json 数据中找 path 编码后等于 workspace_key 的工作区条目。'''
    workspaces = (data.get('tables') or {}).get('workspaces') or {}
    if not isinstance(workspaces, dict):
        return None
    for ws_id, entry in workspaces.items():
        if isinstance(entry, dict):
            if encode_workspace(entry.get('path', '')) == workspace_key:
                return ws_id, entry
    return None


# ----------------------------------------------------------------------
# 回收站
# ----------------------------------------------------------------------
def _trash_target_dir(session_id: str) -> Path:
    '''回收站里该会话的目标文件夹（按会话 ID 命名，重复删除时覆盖前一次）。'''
    return TRASH_DIR / session_id


def move_sessions_to_trash(sessions: list) -> tuple:
    '''把会话移入回收站（move 而非删除），返回 (成功列表, 失败列表)。'''
    moved = []
    failed = []
    for s in sessions:
        if s.get('is_current'):
            failed.append((s, '当前会话受保护，不能删除'))
            continue
        try:
            TRASH_DIR.mkdir(parents=True, exist_ok=True)
            target = _trash_target_dir(s['session_id'])
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(s['path']), str(target))
            manifest = {
                'session_id': s['session_id'],
                'title': s.get('title'),
                'workspace_key': s.get('workspace_key'),
                'workspace_name': decode_workspace(s.get('workspace_key', '')),
                'deleted_at': now_iso(),
                'size': s.get('size', 0),
            }
            with open(target / TRASH_MANIFEST_NAME, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            moved.append(s)
        except OSError as ex:
            failed.append((s, '移入回收站失败: ' + str(ex)))
    return moved, failed


def list_trash_items() -> list:
    '''列出回收站条目（按删除时间倒序）。'''
    items = []
    if not TRASH_DIR.exists():
        return items
    for d in sorted(TRASH_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir():
            continue
        manifest_path = d / TRASH_MANIFEST_NAME
        manifest = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except Exception:
                manifest = {}
        size, mtime = dir_total_size_mtime(d)
        items.append({
            'trash_dir': d,
            'session_id': manifest.get('session_id') or d.name,
            'title': manifest.get('title'),
            'workspace_key': manifest.get('workspace_key', ''),
            'workspace_name': manifest.get('workspace_name', ''),
            'deleted_at': manifest.get('deleted_at', ''),
            'size': manifest.get('size') or size,
            'mtime': mtime,
        })
    # 按删除时间倒序（有 manifest 的用字段，否则按目录 mtime）
    def _sort_key(it):
        try:
            return datetime.strptime(it['deleted_at'], '%Y-%m-%d %H:%M:%S')
        except Exception:
            return datetime.fromtimestamp(it['mtime'])
    items.sort(key=_sort_key, reverse=True)
    return items


def restore_trash_items(items: list) -> tuple:
    '''从回收站恢复会话（移回原工作区并修复 workspace.json）。返回 (成功, 失败)。'''
    restored = []
    failed = []
    for it in items:
        ws_key = it.get('workspace_key')
        sid = it.get('session_id')
        src = it.get('trash_dir')
        try:
            if not src or not src.exists():
                failed.append((it, '回收站条目不存在'))
                continue
            ws_dir = SESSIONS_DIR / ws_key if ws_key else None
            if not ws_dir:
                failed.append((it, 'manifest 缺少工作区信息，无法恢复'))
                continue
            ws_dir.mkdir(parents=True, exist_ok=True)
            dest = ws_dir / sid
            if dest.exists():
                failed.append((it, '目标位置已存在同名会话'))
                continue
            shutil.move(str(src), str(dest))
            _fix_workspace_json_after_restore(ws_key, sid)
            restored.append(it)
        except OSError as ex:
            failed.append((it, '恢复失败: ' + str(ex)))
    return restored, failed


def _fix_workspace_json_after_restore(workspace_key: str, session_id: str) -> bool:
    '''恢复后把会话 ID 加回 workspace.json（必要时重建工作区条目）。'''
    data = _load_json(WORKSPACE_JSON)
    if data is None:
        return True  # 没有 workspace.json 就不修，DSH 下次启动会重建
    tables = data.get('tables')
    if not isinstance(tables, dict):
        tables = {}
        data['tables'] = tables
    workspaces = tables.get('workspaces')
    if not isinstance(workspaces, dict):
        workspaces = {}
        tables['workspaces'] = workspaces

    found = _workspace_entry_for_key(data, workspace_key)
    changed = False
    if found:
        ws_id, entry = found
        ids = entry.get('sessionIds')
        if not isinstance(ids, list):
            ids = []
        if session_id not in ids:
            ids.append(session_id)
            entry['sessionIds'] = ids
            entry['updatedAt'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            changed = True
    else:
        new_id = str(uuid.uuid4())
        workspaces[new_id] = {
            'path': decode_workspace(workspace_key),
            'title': Path(decode_workspace(workspace_key)).name or decode_workspace(workspace_key),
            'sessionIds': [session_id],
            'createdAt': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'updatedAt': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        }
        global_part = data.get('global')
        if not isinstance(global_part, dict):
            global_part = {}
            data['global'] = global_part
        ids = global_part.get('workspaceIds')
        if not isinstance(ids, list):
            ids = []
        if new_id not in ids:
            ids.append(new_id)
            global_part['workspaceIds'] = ids
        changed = True

    if changed:
        return _save_json(WORKSPACE_JSON, data)
    return True


def purge_trash_items(items: list) -> tuple:
    '''彻底删除回收站条目。'''
    purged = []
    failed = []
    for it in items:
        try:
            src = it.get('trash_dir')
            if src and src.exists():
                shutil.rmtree(src)
            purged.append(it)
        except OSError as ex:
            failed.append((it, '清空失败: ' + str(ex)))
    return purged, failed


# ----------------------------------------------------------------------
# 归档 / 取消归档
# ----------------------------------------------------------------------
def set_archived(session_ids, archived: bool) -> bool:
    '''把会话 ID 加入 / 移出 workspace.json 的 archivedSessionIds。'''
    session_ids = list(session_ids)
    if not session_ids:
        return True
    data = _load_json(WORKSPACE_JSON)
    if data is None:
        return False
    global_part = data.get('global')
    if not isinstance(global_part, dict):
        global_part = {}
        data['global'] = global_part
    ids = global_part.get('archivedSessionIds')
    if not isinstance(ids, list):
        ids = []
    changed = False
    for sid in session_ids:
        if archived and sid not in ids:
            ids.append(sid)
            changed = True
        elif not archived and sid in ids:
            ids.remove(sid)
            changed = True
    if changed:
        global_part['archivedSessionIds'] = ids
        return _save_json(WORKSPACE_JSON, data)
    return True


# ----------------------------------------------------------------------
# 删除（入回收站）与清理缓存
# ----------------------------------------------------------------------
def remove_sessions_from_projcache(session_ids) -> bool:
    session_ids = set(session_ids)
    if not session_ids:
        return True
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return True
    sessions = (data.get('tables') or {}).get('sessions') or {}
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


def _remove_workspace_id_from_global(data: dict, ws_id):
    global_part = data.get('global')
    if not isinstance(global_part, dict):
        return
    ids = global_part.get('workspaceIds')
    if isinstance(ids, list) and ws_id in ids:
        ids.remove(ws_id)


def remove_sessions_from_workspace_json(session_ids) -> bool:
    '''从 workspace.json 移除会话（含 archivedSessionIds；空工作区顺手清理）。'''
    session_ids = set(session_ids)
    if not session_ids:
        return True
    data = _load_json(WORKSPACE_JSON)
    if not data:
        return True
    workspaces = (data.get('tables') or {}).get('workspaces') or {}
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
    archived = (data.get('global') or {}).get('archivedSessionIds')
    if isinstance(archived, list):
        new_archived = [x for x in archived if x not in session_ids]
        if new_archived != archived:
            data['global']['archivedSessionIds'] = new_archived
            changed = True
    if changed:
        return _save_json(WORKSPACE_JSON, data)
    return True


def _remove_workspace_dir_if_no_session_dirs(ws_dir: Path) -> bool:
    try:
        if not ws_dir.exists():
            return True
        if not ws_dir.is_dir():
            return False
        remaining = [p for p in ws_dir.iterdir() if p.is_dir()]
        if not remaining:
            shutil.rmtree(ws_dir)
            return True
        return False
    except OSError:
        return False


def perform_delete_sessions(sessions) -> tuple:
    '''删除指定会话（移入回收站），并同步清理缓存。返回 (成功, 空工作区, 失败)。'''
    moved, failed = move_sessions_to_trash(sessions)
    removed_ws_dirs = []
    ws_dirs = {}
    for s in moved:
        ws_dirs[s['workspace_path']] = s['workspace_key']
    for ws_dir in ws_dirs:
        if _remove_workspace_dir_if_no_session_dirs(ws_dir):
            removed_ws_dirs.append(ws_dir)
    if moved:
        ids = [s['session_id'] for s in moved]
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
    return moved, removed_ws_dirs, failed


def perform_delete_workspaces(workspaces) -> tuple:
    '''删除整个工作区（会话全部入回收站），并清理缓存。'''
    removed_ws = []
    failed = []
    for ws in workspaces:
        if ws.get('is_current'):
            failed.append((ws, '工作区包含当前会话，受保护，不能删除'))
            continue
        try:
            moved, move_failed = move_sessions_to_trash(ws['sessions'])
            failed.extend(move_failed)
            try:
                shutil.rmtree(ws['path'])
            except OSError:
                pass  # 会话都移走了，目录若残留则留待 clean 清理
            removed_ws.append(ws)
            ids = [s['session_id'] for s in moved]
            if ids:
                remove_sessions_from_projcache(ids)
                remove_sessions_from_workspace_json(ids)
        except OSError as ex:
            failed.append((ws, '删除失败: ' + str(ex)))
    return removed_ws, failed


def perform_delete_old_sessions(workspaces) -> tuple:
    old = [
        s for ws in workspaces for s in ws['sessions']
        if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
    ]
    if not old:
        return [], [], []
    return perform_delete_sessions(old)


# ----------------------------------------------------------------------
# 清理残留 + 结果校验
# ----------------------------------------------------------------------
def count_projcache_orphans() -> list:
    '''统计 projcache 中“磁盘上已不存在”的孤儿会话 ID。'''
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return []
    sessions = (data.get('tables') or {}).get('sessions') or {}
    if not isinstance(sessions, dict):
        return []
    disk_ids = set()
    if SESSIONS_DIR.exists():
        for ws_dir in SESSIONS_DIR.iterdir():
            if ws_dir.is_dir():
                for child in ws_dir.iterdir():
                    if is_session_dir(child):
                        disk_ids.add(child.name)
    return [sid for sid in sessions.keys() if sid not in disk_ids]


def perform_clean_residue() -> dict:
    '''清理缓存/磁盘残留，并返回带校验的统计结果。'''
    result = {
        'empty_workspace_dirs': 0,
        'projcache_orphans': 0,
        'workspace_entries_removed': 0,
        'workspace_session_ids_removed': 0,
        'archived_session_ids_removed': 0,
        'verification': {},   # 清理后复查结果
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

    # 1) projcache 孤儿清理
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

    # 2) workspace.json 清理
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

    # 3) 清理后校验：复查 projcache 是否还有孤儿（可能被运行中的 DSH 写回）
    remaining = count_projcache_orphans()
    result['verification'] = {
        'remaining_orphans': len(remaining),
        'remaining_ids': remaining,
        'dsh_running': detect_dsh_running(),
    }
    return result


# ----------------------------------------------------------------------
# 命令行输出
# ----------------------------------------------------------------------
def print_workspaces(workspaces):
    total_ws = len(workspaces)
    total_sessions = sum(ws['session_count'] for ws in workspaces)
    total_size = sum(ws['size'] for ws in workspaces)
    if total_ws == 0:
        print('没有找到任何工作区 / 会话记录。')
        return
    print()
    print('会话目录: ' + str(SESSIONS_DIR))
    print(f'共 {total_ws} 个工作区，{total_sessions} 个会话，总占用 {format_size(total_size)}')
    print()
    idx = 0
    for wi, ws in enumerate(workspaces, 1):
        mark = '  [包含当前会话]' if ws['is_current'] else ''
        print(f'[{wi}] 工作区: {ws["name"]}  ({ws["session_count"]} 个会话, {format_size(ws["size"])}){mark}')
        if not ws['sessions']:
            print('    (此工作区中还没有会话)')
            continue
        for s in ws['sessions']:
            idx += 1
            cur = '  <- 当前会话' if s['is_current'] else ''
            arch = '  [已归档]' if s['is_archived'] else ''
            title = s.get('title') or '(无标题)'
            stats = s.get('stats') or {}
            extra = ''
            if stats:
                turns = stats.get('turns')
                if turns is not None:
                    extra = f'  轮数{turns}  '
                out_t = stats.get('outputTokens')
                if out_t is not None:
                    extra += f'输出{format_tokens(out_t)} tokens'
            print(
                f'    [{idx}] {s["session_id"]}  {format_size(s["size"])}  '
                f'{format_age(s["age"])}  {title}{cur}{arch}{extra}'
            )
    print()


def confirm_delete(targets) -> bool:
    print()
    print('即将删除以下会话（移入回收站，可恢复）：')
    for s in targets:
        print('  - ' + decode_workspace(s['workspace_key']) + '  (会话 ' + s['session_id'] + ')')
    print()
    answer = input('确认删除吗？输入 yes 继续，其它任何输入取消: ').strip().lower()
    return answer == 'yes'


def _describe_failed(failed):
    for obj, msg in failed:
        name = obj.get('session_id') if isinstance(obj, dict) else str(obj)
        print('  注意: ' + name + ' —— ' + msg)


# ----------------------------------------------------------------------
# 命令行命令
# ----------------------------------------------------------------------
def cmd_list(workspaces):
    print_workspaces(workspaces)


def cmd_search(workspaces, keyword):
    kw = keyword.strip().lower()
    if not kw:
        print('用法: python manage_sessions.py search <关键词>')
        return
    matched = []
    for ws in workspaces:
        for s in ws['sessions']:
            title = (s.get('title') or '').lower()
            if kw in title or kw in s['session_id'].lower() or kw in ws['name'].lower():
                matched.append((ws, s))
    if not matched:
        print('没有匹配 "' + keyword + '" 的会话。')
        return
    print()
    print('匹配 "' + keyword + '" 的会话 ' + str(len(matched)) + ' 个：')
    for i, (ws, s) in enumerate(matched, 1):
        cur = '  <- 当前会话' if s['is_current'] else ''
        arch = '  [已归档]' if s['is_archived'] else ''
        print(f'  [{i}] {s["session_id"]}  {format_size(s["size"])}  {format_age(s["age"])}  '
              f'{s.get("title") or "(无标题)"}  @ {ws["name"]}{cur}{arch}')
    print()


def cmd_delete(workspaces, indexes):
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
            print(f'编号 {n} 不存在，跳过（有效范围 1~{len(flat)}）。')
            continue
        s = flat[n - 1]
        if s['is_current']:
            print(f'编号 {n} 是当前会话，已被保护，不能删除。')
            continue
        targets.append(s)
    if not targets:
        print('没有可删除的会话。')
        return
    if confirm_delete(targets):
        moved, removed_ws, failed = perform_delete_sessions(targets)
        print()
        print(f'完成：已把 {len(moved)} 个会话移入回收站，自动清理 {len(removed_ws)} 个空工作区。')
        print('回收站位置: ' + str(TRASH_DIR))
        _describe_failed(failed)
    else:
        print('已取消，没有删除任何东西。')


def cmd_delete_old(workspaces):
    targets = [
        s for ws in workspaces for s in ws['sessions']
        if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
    ]
    if not targets:
        print('没有可删除的历史会话（可能只有当前会话，或其它会话都还很新）。')
        return
    if confirm_delete(targets):
        moved, removed_ws, failed = perform_delete_old_sessions(workspaces)
        print()
        print(f'完成：已把 {len(moved)} 个历史会话移入回收站，自动清理 {len(removed_ws)} 个空工作区。')
        _describe_failed(failed)
    else:
        print('已取消，没有删除任何东西。')


def cmd_trash():
    items = list_trash_items()
    if not items:
        print('回收站是空的。')
        return
    print()
    print('回收站 ' + str(len(items)) + ' 个条目：')
    for i, it in enumerate(items, 1):
        print(f'  [{i}] {it["session_id"]}  {format_size(it["size"])}  删除于 {it["deleted_at"]}  '
              f' {it.get("title") or "(无标题)"}  @ {it.get("workspace_name") or "?"}')
    print()


def cmd_restore(indexes):
    items = list_trash_items()
    if not items:
        print('回收站是空的。')
        return
    if not indexes:
        print('用法: python manage_sessions.py restore <编号> [编号...]')
        print('先用 trash 看看有哪些编号。')
        return
    targets = []
    for idx in indexes:
        try:
            n = int(idx)
        except ValueError:
            print('编号 ' + str(idx) + ' 不是有效编号，跳过。')
            continue
        if not (1 <= n <= len(items)):
            print(f'编号 {n} 不存在，跳过（有效范围 1~{len(items)}）。')
            continue
        targets.append(items[n - 1])
    if not targets:
        return
    print()
    print('即将恢复：')
    for it in targets:
        print('  - ' + it['session_id'] + '  (' + (it.get('title') or '无标题') + ')')
    answer = input('确认恢复吗？输入 yes 继续: ').strip().lower()
    if answer != 'yes':
        print('已取消。')
        return
    restored, failed = restore_trash_items(targets)
    print()
    print(f'完成：已恢复 {len(restored)} 个会话。')
    _describe_failed(failed)


def cmd_empty_trash():
    items = list_trash_items()
    if not items:
        print('回收站是空的。')
        return
    print()
    print('即将彻底删除回收站中 ' + str(len(items)) + ' 个条目（不可恢复！）。')
    answer = input('确认清空回收站吗？输入 yes 继续: ').strip().lower()
    if answer != 'yes':
        print('已取消。')
        return
    purged, failed = purge_trash_items(items)
    print(f'完成：已彻底删除 {len(purged)} 个条目。')
    _describe_failed(failed)


def cmd_archive(workspaces, indexes):
    flat = [s for ws in workspaces for s in ws['sessions']]
    if not indexes:
        print('用法: python manage_sessions.py archive <编号> [编号...]')
        return
    targets = []
    for idx in indexes:
        try:
            n = int(idx)
        except ValueError:
            continue
        if 1 <= n <= len(flat):
            targets.append(flat[n - 1])
    if not targets:
        print('没有有效的会话编号。')
        return
    ids = [s['session_id'] for s in targets]
    if set_archived(ids, True):
        print(f'完成：已归档 {len(ids)} 个会话。')
    else:
        print('归档失败：无法读取/写入 workspace.json。')


def cmd_unarchive(workspaces, indexes):
    flat = [s for ws in workspaces for s in ws['sessions']]
    if not indexes:
        print('用法: python manage_sessions.py unarchive <编号> [编号...]')
        return
    targets = []
    for idx in indexes:
        try:
            n = int(idx)
        except ValueError:
            continue
        if 1 <= n <= len(flat):
            targets.append(flat[n - 1])
    if not targets:
        print('没有有效的会话编号。')
        return
    ids = [s['session_id'] for s in targets]
    if set_archived(ids, False):
        print(f'完成：已取消归档 {len(ids)} 个会话。')
    else:
        print('取消归档失败：无法读取/写入 workspace.json。')


def cmd_clean(workspaces, assume_yes=False):
    if detect_dsh_running():
        print('[注意] 检测到 DSH 正在运行：清理缓存可能被 DSH 写回覆盖。')
        print('  建议先完全退出 DSH 再清理。')
        if not assume_yes:
            answer = input('仍要继续吗？输入 yes 继续: ').strip().lower()
            if answer != 'yes':
                print('已取消。')
                return
    result = perform_clean_residue()
    print('清理完成：')
    print('  - 删除空工作区文件夹: ' + str(result['empty_workspace_dirs']) + ' 个')
    print('  - 删除 session_projcache 孤儿记录: ' + str(result['projcache_orphans']) + ' 条')
    print('  - 删除 workspace.json 孤儿工作区: ' + str(result['workspace_entries_removed']) + ' 条')
    print('  - 清理 workspace.json 中失效 sessionIds: ' + str(result['workspace_session_ids_removed']) + ' 条')
    print('  - 清理 workspace.json 中失效 archivedSessionIds: ' + str(result['archived_session_ids_removed']) + ' 条')
    ver = result.get('verification') or {}
    remaining = ver.get('remaining_orphans', 0)
    if remaining:
        print()
        print('[注意] 校验发现仍有 ' + str(remaining) + ' 条孤儿记录（DSH 运行中会写回缓存）。')
        if ver.get('dsh_running'):
            print('  请完全退出 DSH 后重新清理。')
    else:
        print()
        print('[OK] 校验通过：session_projcache.json 与磁盘一致，无残留。')
    print_workspaces(get_workspaces())


def cmd_status():
    running = detect_dsh_running()
    print('DSH 数据目录: ' + str(DSH_HOME))
    print('会话目录:     ' + str(SESSIONS_DIR))
    print('回收站目录:   ' + str(TRASH_DIR))
    print('DSH 运行状态: ' + ('运行中 [注意]' if running else '未运行 [安全]'))
    print('当前会话:     ' + (CURRENT_SESSION_ID or '（未设置，自动保护最近会话）'))
    trash_count = len(list_trash_items())
    print('回收站条目:   ' + str(trash_count) + ' 个')
