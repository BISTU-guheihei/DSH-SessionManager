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
- 兼容新旧 DSH 存储布局：会话日志 session.jsonl.zstd / session.v4.jsonl.zstd，
  统计缓存 session_projcache.json（单文件）/ session_projcache/sessions/*.json
'''

import csv
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
# 旧版 DSH：单个 JSON 文件；新版 DSH：storages/session_projcache/sessions/<会话ID>.json
SESSION_PROJCACHE_JSON = STORAGES_DIR / 'session_projcache.json'
SESSION_PROJCACHE_DIR = STORAGES_DIR / 'session_projcache'
SESSION_PROJCACHE_SESSIONS_DIR = SESSION_PROJCACHE_DIR / 'sessions'
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
    非 ASCII 字符编码成 ~XXXX~（UTF-16 码元十六进制，仅首个转义字符加波浪号，
    例如 E:\资料 -> E-~8D44~6599-）。

    注意：该编码把 "\\" 和 "-" 都折叠成 "-"，**不可逆**。因此显示用的真实路径
    优先取 workspace.json 里的权威 path（见 load_workspace_path_map），
    本函数仅作无索引时的启发式兜底。
    '''
    k = key
    if k.startswith('--'):
        k = k[2:]
    if k.endswith('--'):
        k = k[:-2]
    k = _unescape_workspace_name(k)
    if IS_WINDOWS:
        path = k.replace('-', '\\')
        if len(path) >= 2 and path[1] == '\\' and path[0].isalpha():
            path = path[0] + ':' + path[1:]
        return path
    # POSIX：- 还原成 /，补回开头斜杠
    return '/' + k.replace('-', '/')


def _unescape_workspace_name(text: str) -> str:
    r'''还原 DSH 目录名里的 ~XXXX~ 非 ASCII 转义（仅首个字符带波浪号）。

    DSH 对连续的非 ASCII 字符只写一次开头波浪号：
    E:\资料 -> E-~8D44~6599-（8D44=资 U+8D44，6599=料 U+6599）。
    解码时把 ~XXXX~ 转成该码元，后续裸的 4 位十六进制串按紧随其后的码元继续解。
    '''
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '~' and i + 5 <= n and _is_hex4(text[i + 1:i + 5]):
            out.append(chr(int(text[i + 1:i + 5], 16)))
            i += 5
            # 续接的裸 4 位十六进制码元（必须紧邻，且后面是 '-' 或字符串结尾）
            while i + 4 <= n and _is_hex4(text[i:i + 4]) and (i + 4 == n or text[i + 4] == '-'):
                out.append(chr(int(text[i:i + 4], 16)))
                i += 4
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def _is_hex4(s: str) -> bool:
    if len(s) != 4:
        return False
    for c in s:
        if c not in '0123456789abcdefABCDEF':
            return False
    return True


_WORKSPACE_PATH_MAP_CACHE = None


def load_workspace_path_map() -> dict:
    '''从 workspace.json 读取「编码目录名 -> 真实路径」映射（权威、无歧义）。

    DSH 的目录名编码会丢掉 ":" 并把 "\\" 与 "-" 混同，无法反推；但
    workspace.json 里存着原始 path，用同样的编码函数正推即可得到准确映射。
    附带从 path 末尾取末级目录名作为工作区显示名。
    '''
    mapping = {}
    data = _load_json(WORKSPACE_JSON)
    if not data:
        return mapping
    workspaces = (data.get('tables') or {}).get('workspaces') or {}
    if not isinstance(workspaces, dict):
        return mapping
    for entry in workspaces.values():
        if not isinstance(entry, dict):
            continue
        path = entry.get('path')
        if not path:
            continue
        try:
            mapping[encode_workspace(path)] = str(path)
        except Exception:
            continue
    return mapping


def workspace_display_name(workspace_key: str) -> str:
    '''工作区显示名：优先取权威真实路径，退化到启发式解码。'''
    global _WORKSPACE_PATH_MAP_CACHE
    if _WORKSPACE_PATH_MAP_CACHE is None:
        _WORKSPACE_PATH_MAP_CACHE = load_workspace_path_map()
    real = _WORKSPACE_PATH_MAP_CACHE.get(workspace_key)
    if real:
        return real
    return decode_workspace(workspace_key)


def encode_workspace(path_str) -> str:
    '''与 decode_workspace 相反：把真实路径编码成 DSH 工作区文件夹名。'''
    p = str(Path(path_str))
    if IS_WINDOWS:
        if len(p) >= 2 and p[1] == ':':
            p = p[0] + p[2:]
        body = p.replace('\\', '-')
    else:
        # POSIX：去掉开头斜杠，/ 换成 -
        if p.startswith('/'):
            p = p[1:]
        body = p.replace('/', '-')
    return '--' + _escape_workspace_name(body) + '--'


def _escape_workspace_name(text: str) -> str:
    r'''把非 ASCII 字符按 DSH 规则转义成 ~XXXX~。

    DSH 只给连续非 ASCII 串的**第一个**字符加前后波浪号，后续字符仅写 4 位
    十六进制（E:\资料 -> E-~8D44~6599-）。这里复刻该行为，保证
    encode_workspace 的结果与磁盘上的目录名逐字节一致。
    '''
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ord(ch) < 128:
            out.append(ch)
            i += 1
            continue
        # 连续非 ASCII 串：首个带波浪号，其余裸码元
        out.append('~' + format(ord(ch), '04X') + '~')
        i += 1
        while i < n and ord(text[i]) >= 128:
            out.append(format(ord(text[i]), '04X'))
            i += 1
    return ''.join(out)


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
#
# 各发行版的进程名并不统一，实测：
#   - DSH Desktop（Windows 安装包）可执行文件叫 "DeepSeek Harness.exe"，
#     进程名是 "DeepSeek Harness"（Electron 会起多个同名进程），
#     **与安装目录名 "Deepseek_desk" 无关**；
#   - 早期版本 / 网页版 host 用 dsh / dsh.exe / dsh-web / "dsh desktop"，
#     或作为 node 进程（node.exe / node）跑。
# 旧实现只找 'dsh'，因此在 DSH Desktop 运行时永远判定为"未运行"，
# 导致归档 / 清理缓存时缺少"DSH 运行中可能写回"的重要提醒。
# ----------------------------------------------------------------------
# 进程名基础名（已去掉 .exe 后缀、小写）精确匹配，避免把路径里偶然含
# dsh 的进程误判成 DSH
_DSH_PROCESS_BASENAMES = (
    'deepseek harness',      # DSH Desktop（Windows 安装包）
    'dsh',                   # CLI / host
    'dsh desktop',
    'dsh-desktop',
    'dsh-web',               # 网页版 host
)


def _list_process_names() -> list:
    '''返回当前进程名列表（小写、去路径、去 .exe 后缀）。

    用 csv 模块解析 tasklist 的 CSV 输出：进程名本身含空格
    （如 "DeepSeek Harness"），按空白切分会截断，必须先按 CSV 拆列。
    Windows 的 tasklist 给的是 xxx.exe，统一去掉后缀以便与基础名比较。
    '''
    names = []
    if IS_WINDOWS:
        out = subprocess.run(
            ['tasklist', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, errors='replace', timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        ).stdout or ''
        raw = [row[0] for row in csv.reader(out.splitlines()) if row and row[0].strip()]
    else:
        # comm= 只给可执行名
        out = subprocess.run(
            ['ps', '-ax', '-o', 'comm='],
            capture_output=True, text=True, errors='replace', timeout=10,
        ).stdout or ''
        raw = [line for line in out.splitlines() if line.strip()]
    for item in raw:
        name = os.path.basename(item.strip().strip('"')).lower()
        if name.endswith('.exe'):
            name = name[:-4]
        if name:
            names.append(name)
    return names


def detect_dsh_running() -> bool:
    '''检测 DSH 是否正在运行（Windows / macOS / Linux）。

    只做基础名精确匹配：'dsh' 能覆盖 dsh / dsh.exe / dsh-desktop 等，
    但不会把 dshhelper 这类无关进程误判成 DSH。
    '''
    try:
        for name in _list_process_names():
            if name in _DSH_PROCESS_BASENAMES:
                return True
        return False
    except Exception:
        # 检测失败时保守返回 False（不阻塞用户操作，只是少一条提示）
        return False


# ----------------------------------------------------------------------
# 会话扫描与统计
# ----------------------------------------------------------------------
def is_session_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name.startswith('session-'):
        return True
    return find_session_log(path) is not None


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


def _put(entry: dict, key: str, value):
    '''只在取到有效值时才写入，避免产生一堆 None 键（会让空 rows 也非空）。'''
    if value is not None:
        entry[key] = value


def _stats_from_rows(rows) -> dict:
    '''从 DSH 缓存的 rows 结构里取出标题与统计字段。

    rows 形如 {'title': {'val': ...}, 'sessionStats': {'val': {...}}, ...}。
    新旧 DSH 版本的行结构一致，差异只在文件布局，因此这里共用。
    '''
    if not isinstance(rows, dict):
        return {}
    entry = {}
    title = rows.get('title') or {}
    if isinstance(title, dict):
        title_val = title.get('val')
        if isinstance(title_val, str) and title_val.strip():
            entry['title'] = title_val.strip()
    # 新版另有 titleInput.first.text（首句原文），作为标题的兜底
    if not entry.get('title'):
        ti = rows.get('titleInput') or {}
        if isinstance(ti, dict):
            ti_val = ti.get('val') or {}
            if isinstance(ti_val, dict):
                first = ti_val.get('first') or {}
                if isinstance(first, dict):
                    text = first.get('text')
                    if isinstance(text, str) and text.strip():
                        entry['titleInput'] = text.strip()
    s = rows.get('sessionStats') or {}
    if isinstance(s, dict):
        val = s.get('val') or {}
        if isinstance(val, dict):
            _put(entry, 'turns', val.get('turns'))
            _put(entry, 'steps', val.get('steps'))
            _put(entry, 'llmMs', val.get('llmMs'))
            _put(entry, 'toolMs', val.get('toolMs'))
    t = rows.get('tokenUsage') or {}
    if isinstance(t, dict):
        val = t.get('val') or {}
        if isinstance(val, dict):
            totals = val.get('totals') or {}
            if isinstance(totals, dict):
                _put(entry, 'inputTokens', totals.get('uncachedInputTokens'))
                _put(entry, 'outputTokens', totals.get('outputTokens'))
                _put(entry, 'cacheReadTokens', totals.get('cacheReadTokens'))
    p = rows.get('contextPressure') or {}
    if isinstance(p, dict):
        val = p.get('val') or {}
        if isinstance(val, dict):
            _put(entry, 'surfaceTokens', val.get('surfaceTokens'))
            _put(entry, 'contextWindow', val.get('contextWindow'))
    return entry


def _iter_cached_session_ids():
    '''产出缓存里出现过的全部会话 ID（新旧布局）。'''
    seen = set()
    if SESSION_PROJCACHE_SESSIONS_DIR.is_dir():
        try:
            for f in SESSION_PROJCACHE_SESSIONS_DIR.iterdir():
                if f.is_file() and f.suffix == '.json':
                    seen.add(f.stem)
        except OSError:
            pass
    data = _load_json(SESSION_PROJCACHE_JSON)
    if data:
        sessions = (data.get('tables') or {}).get('sessions') or {}
        if isinstance(sessions, dict):
            seen.update(sessions.keys())
    return seen


def load_session_stats() -> dict:
    '''读取每个会话的统计信息（供界面/列表展示）。

    新版 DSH 把缓存拆成 storages/session_projcache/sessions/<会话ID>.json，
    旧版是单个 storages/session_projcache.json；这里两种都支持。
    '''
    stats = {}
    # 新版：每会话一个 JSON 文件
    if SESSION_PROJCACHE_SESSIONS_DIR.is_dir():
        try:
            entries = sorted(SESSION_PROJCACHE_SESSIONS_DIR.iterdir())
        except OSError:
            entries = []
        for f in entries:
            if not f.is_file() or f.suffix != '.json':
                continue
            obj = _load_json(f)
            if not isinstance(obj, dict):
                continue
            record = obj.get('record') if isinstance(obj.get('record'), dict) else obj
            rows = record.get('rows')
            entry = _stats_from_rows(rows)
            if entry:
                stats[f.stem] = entry
    # 旧版：单文件 tables.sessions
    data = _load_json(SESSION_PROJCACHE_JSON)
    if data:
        sessions = (data.get('tables') or {}).get('sessions') or {}
        if isinstance(sessions, dict):
            for sid, obj in sessions.items():
                if sid in stats or not isinstance(obj, dict):
                    continue
                entry = _stats_from_rows(obj.get('rows'))
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


# ----------------------------------------------------------------------
# 标题提取（会话日志 zstd 解码）
#
# DSH 会话日志是 zstd 压缩的「多帧串联 JSONL」，文件名随 DSH 版本变化：
#   旧版: session.jsonl.zstd
#   新版: session.v4.jsonl.zstd（版本号在文件名里）
# 因此不再硬编码文件名，改用 find_session_log() 按模式匹配。
#
# 标题优先级（extract_title_from_log 一次解码同时拿到全部候选）：
#   1. DSH 自产标题 session/title 事件且 source.kind == 'provider'（LLM 精炼，最佳）
#   2. 该事件的 'fallback' 版本（等于首句原文）
#   3. 首条 **真实用户** 消息（source.kind == 'user'；跳过 runtime-context /
#      skill-catalog 等系统注入消息）
# 首句很长时不再截断成乱码——交给 title 事件（DSH 已精炼成短标题）。
#
# Python 标准库无法解 zstd，故调用 Node 内置 zlib.zstdDecompress
# （Node >= 22.24，与 DSH 同一实现），由 title_extract.js 一次性扫描全部帧，
# 输出一行 JSON。提取结果按 (文件路径, 大小, mtime) 缓存，未变化不重复解码。
# ----------------------------------------------------------------------
_SCRIPT_NAME = 'title_extract.js'
_node_bin = None          # 探测到的 node 可执行路径
_title_cache = {}         # log_path -> (size, mtime, result_dict)
_title_retry_at = {}      # log_path -> 下次允许重试的时间戳（失败时防频繁重试）

_LEGACY_LOG_NAME = 'session.jsonl.zstd'
_LOG_SUFFIX = '.jsonl.zstd'


def _log_version_rank(name: str) -> tuple:
    '''日志文件名排序键：优先版本号更大的（v4 > v3 > 无版本号）。'''
    import re
    m = re.match(r'^session\.v(\d+)\.jsonl\.zstd$', name)
    if m:
        return (1, int(m.group(1)))
    return (0, 0)


def find_session_log(session_dir) -> Path:
    '''定位会话目录里的日志文件（兼容 session.jsonl.zstd / session.v4.jsonl.zstd 等）。

    找不到时返回 None。
    '''
    d = Path(session_dir)
    if not d.is_dir():
        return None
    # 常见优先，省一次列目录
    legacy = d / _LEGACY_LOG_NAME
    if legacy.is_file():
        return legacy
    try:
        cands = [f for f in d.iterdir()
                 if f.is_file() and f.name.startswith('session') and f.name.endswith(_LOG_SUFFIX)]
    except OSError:
        return None
    if not cands:
        return None
    # 版本号大的优先（v4 > v3 > 无版本号），再按名字稳定排序
    cands.sort(key=lambda p: (_log_version_rank(p.name), p.name), reverse=True)
    return cands[0]


def _find_node() -> str:
    '''探测系统可用的 node 可执行文件。找不到返回空串。'''
    global _node_bin
    if _node_bin is not None:
        return _node_bin
    candidates = []
    env_paths = os.environ.get('PATH', '')
    for p in env_paths.split(os.pathsep):
        if p:
            candidates.append(os.path.join(p, 'node'))
            candidates.append(os.path.join(p, 'node.exe'))
    # 常见安装位置
    candidates += [
        r'C:\Program Files\nodejs\node.exe',
        r'C:\Program Files (x86)\nodejs\node.exe',
        str(Path.home() / 'AppData' / 'Roaming' / 'nvm'),
        '/usr/bin/node', '/usr/local/bin/node', '/opt/homebrew/bin/node',
    ]
    seen = set()
    for c in candidates:
        c = c.replace('\\', os.sep)
        if c in seen or not c:
            continue
        seen.add(c)
        if Path(c).is_file() if os.sep == '\\' else os.access(c, os.X_OK):
            _node_bin = c
            return c
    _node_bin = ''
    return ''


def _title_script_path():
    '''定位 title_extract.js（exe 打包后从 _MEIPASS 读取，源码模式同目录）。'''
    candidates = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / _SCRIPT_NAME)
    candidates.append(Path(__file__).resolve().parent / _SCRIPT_NAME)
    for c in candidates:
        if c.exists():
            return str(c)
    return ''


def _truncate_utf8_safe(text: str, limit: int) -> str:
    '''按显示宽度截断，且绝不切断代理对（避免出现"一对字母"式的乱码尾巴）。'''
    if text is None:
        return ''
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # 若截断点落在高代理项上，回退一位，防止留下孤立代理项
    if cut and 0xD800 <= ord(cut[-1]) <= 0xDBFF:
        cut = cut[:-1]
    return cut.rstrip() + '…'


def _parse_extract_output(stdout: str) -> dict:
    '''解析 title_extract.js 输出的 JSON；兼容纯文本输出（异常兜底）。'''
    result = {'title': '', 'fallback_title': '', 'first_user_text': '', 'cwd': ''}
    raw = (stdout or '').strip()
    if not raw:
        return result
    line = raw.splitlines()[-1].strip()
    if line.startswith('{'):
        try:
            obj = json.loads(line)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            for key in ('title', 'fallback_title', 'first_user_text', 'cwd'):
                val = obj.get(key)
                if isinstance(val, str):
                    result[key] = val.strip()
            return result
    # 旧脚本版本只输出纯文本标题
    result['title'] = raw
    return result


def extract_title_from_log(session_file: Path) -> dict:
    '''解码会话日志，返回 {title, fallback_title, first_user_text, cwd}。

    无法提取时返回全空 dict（调用方按顺序降级，绝不显示"(无标题)"）。
    结果按 (大小, mtime) 缓存；失败时节流重试，避免 3 秒自动刷新反复解码。
    '''
    global _title_cache, _title_retry_at
    empty = {'title': '', 'fallback_title': '', 'first_user_text': '', 'cwd': ''}
    if not session_file:
        return empty
    try:
        session_file = Path(session_file)
        st = session_file.stat()
        cache_key = str(session_file)
        cached = _title_cache.get(cache_key)
        if cached and cached[0] == st.st_size and cached[1] == st.st_mtime:
            return cached[2]
        # 节流：同一文件 30s 内不重复解码（防自动刷新反复触发）
        import time as _time
        now = _time.time()
        if now < _title_retry_at.get(cache_key, 0):
            cached_old = _title_cache.get(cache_key)
            return cached_old[2] if cached_old else empty

        node = _find_node()
        script = _title_script_path()
        if not node or not script:
            _title_retry_at[cache_key] = now + 60
            return empty

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if IS_WINDOWS else 0
        proc = subprocess.run(
            [node, script, str(session_file)],
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=30,
            creationflags=creationflags,
        )
        result = _parse_extract_output(proc.stdout)
        _title_cache[cache_key] = (st.st_size, st.st_mtime, result)
        if not (result.get('title') or result.get('fallback_title')
                or result.get('first_user_text')):
            # 无结果（空会话/无用户消息）：30s 后再试
            _title_retry_at[cache_key] = now + 30
        return result
    except Exception:
        try:
            import time as _time2
            _title_retry_at[str(session_file)] = _time2.time() + 60
        except Exception:
            pass
        return empty


def infer_display_title(session) -> str:
    '''给一个会话算出"必定非空"的显示标题。

    优先级：
      1. DSH 缓存标题（projcache title，通常已是 LLM 精炼结果）
      2. 日志里 session/title 事件（provider 精炼版 → fallback 首句版）
      3. 缓存里的首句原文 titleInput.first.text
      4. 首条真实用户消息
      5. 会话 ID 截断（绝不显示"(无标题)"）
    '''
    t = session.get('title')
    if t and str(t).strip():
        return _truncate_utf8_safe(str(t), 60)

    # 只解码一次日志，所有候选都从同一份结果里取
    info = {}
    spath = session.get('path')
    if spath:
        log_file = find_session_log(spath)
        if log_file:
            info = extract_title_from_log(log_file)

    for key in ('title', 'fallback_title'):
        val = (info.get(key) or '').strip()
        if len(val) >= 2:
            return _truncate_utf8_safe(val, 60)

    stats = session.get('stats') or {}
    ti = (stats.get('titleInput') or '').strip()
    if len(ti) >= 2:
        return _truncate_utf8_safe(ti, 60)

    fu = (info.get('first_user_text') or '').strip()
    if len(fu) >= 2:
        return _truncate_utf8_safe(fu, 60)

    # 降级：会话 ID 截断（绝不显示"(无标题)"）
    sid = session.get('session_id', '')
    return ('会话 ' + sid) if sid else '(空会话)'


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
            session_file = find_session_log(child)
            if session_file is not None:
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
                'title': st_entry.get('title'),
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
            'name': workspace_display_name(ws_dir.name),
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
                # workspace_display_name 优先用 workspace.json 的权威路径，
                # 避免目录名编码不可逆（"\\" 与 "-" 混同）导致误判
                if os.path.normcase(os.path.normpath(workspace_display_name(d.name))) == norm_target:
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
def _trash_target_dir(session_id: str, timestamp: str = '') -> Path:
    '''回收站里该会话的目标文件夹。

    使用 "会话ID__删除时间戳" 命名，保证同一会话重复删除时生成
    唯一、不可覆盖的新恢复点（不会擦掉之前的恢复点）。
    '''
    if timestamp:
        return TRASH_DIR / f'{session_id}__{timestamp}'
    return TRASH_DIR / session_id


def _load_projcache_entry(session_id: str):
    '''读取某会话的完整缓存条目（删除时快照用）。

    新版：storages/session_projcache/sessions/<id>.json（整个文件即条目）
    旧版：storages/session_projcache.json 的 tables.sessions.<id>
    返回 dict；不存在时返回 None。
    '''
    per_session = SESSION_PROJCACHE_SESSIONS_DIR / (str(session_id) + '.json')
    if per_session.is_file():
        obj = _load_json(per_session)
        if isinstance(obj, dict):
            return obj
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return None
    sessions = (data.get('tables') or {}).get('sessions') or {}
    if not isinstance(sessions, dict):
        return None
    entry = sessions.get(session_id)
    return entry if isinstance(entry, dict) else None


def _write_projcache_entry(session_id: str, entry: dict) -> bool:
    '''把某会话的缓存条目写回（恢复标题/统计用），按原布局写回。'''
    if not entry:
        return True
    # 新版布局：整条记录写成一个 JSON 文件
    if SESSION_PROJCACHE_SESSIONS_DIR.is_dir() or not SESSION_PROJCACHE_JSON.exists():
        try:
            SESSION_PROJCACHE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return _save_json(SESSION_PROJCACHE_SESSIONS_DIR / (str(session_id) + '.json'), entry)
    # 旧版布局：合并进单文件
    data = _load_json(SESSION_PROJCACHE_JSON)
    if data is None:
        data = {'unit': {'name': 'session_projcache', 'version': 3},
                'global': None, 'tables': {'sessions': {}}}
    tables = data.get('tables')
    if not isinstance(tables, dict):
        tables = {}
        data['tables'] = tables
    sessions = tables.get('sessions')
    if not isinstance(sessions, dict):
        sessions = {}
        tables['sessions'] = sessions
    sessions[session_id] = entry
    return _save_json(SESSION_PROJCACHE_JSON, data)


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
            # 唯一时间戳目录：同一会话重复删除不覆盖旧恢复点
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            target = _trash_target_dir(s['session_id'], timestamp)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(s['path']), str(target))
            # 快照 projcache 缓存条目（标题/统计），恢复时写回缓存
            projcache_entry = _load_projcache_entry(s['session_id'])
            manifest = {
                'session_id': s['session_id'],
                'title': s.get('title') or s.get('display_title'),
                'display_title': s.get('display_title') or s.get('title'),
                'workspace_key': s.get('workspace_key'),
                'workspace_name': workspace_display_name(s.get('workspace_key', '')),
                'deleted_at': now_iso(),
                'timestamp': timestamp,
                'size': s.get('size', 0),
                'projcache': projcache_entry,
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
        # 目录名兼容两种格式：session-xxx（旧）或 session-xxx__时间戳（新）
        raw_sid = d.name
        session_id = manifest.get('session_id') or raw_sid
        if not manifest.get('session_id') and '__' in raw_sid:
            session_id = raw_sid.split('__', 1)[0]
        items.append({
            'trash_dir': d,
            'session_id': session_id,
            'title': manifest.get('title'),
            'workspace_key': manifest.get('workspace_key', ''),
            'workspace_name': manifest.get('workspace_name', ''),
            'deleted_at': manifest.get('deleted_at', ''),
            'size': manifest.get('size') or size,
            'mtime': mtime,
            'projcache': manifest.get('projcache'),
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
    '''从回收站恢复会话（移回原工作区并修复 workspace.json / 缓存）。返回 (成功, 失败)。'''
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
            # 恢复标题/统计：把删除时快照的 projcache 缓存条目写回
            projcache_entry = it.get('projcache')
            if projcache_entry:
                _write_projcache_entry(sid, projcache_entry)
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
    '''从会话统计缓存里删除指定会话（新旧两种布局都处理）。'''
    session_ids = set(session_ids)
    if not session_ids:
        return True
    ok = True
    # 新版：每会话一个文件
    if SESSION_PROJCACHE_SESSIONS_DIR.is_dir():
        for sid in session_ids:
            f = SESSION_PROJCACHE_SESSIONS_DIR / (str(sid) + '.json')
            try:
                if f.is_file():
                    f.unlink()
            except OSError:
                ok = False
    # 旧版：单文件
    data = _load_json(SESSION_PROJCACHE_JSON)
    if not data:
        return ok
    sessions = (data.get('tables') or {}).get('sessions') or {}
    if not isinstance(sessions, dict):
        return ok
    changed = False
    for sid in list(sessions.keys()):
        if sid in session_ids:
            del sessions[sid]
            changed = True
    if changed:
        ok = _save_json(SESSION_PROJCACHE_JSON, data) and ok
    return ok


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
    '''统计缓存中“磁盘上已不存在”的孤儿会话 ID（新旧布局都算）。'''
    disk_ids = set()
    if SESSIONS_DIR.exists():
        for ws_dir in SESSIONS_DIR.iterdir():
            if ws_dir.is_dir():
                try:
                    children = list(ws_dir.iterdir())
                except OSError:
                    continue
                for child in children:
                    if is_session_dir(child):
                        disk_ids.add(child.name)
    return sorted(sid for sid in _iter_cached_session_ids() if sid not in disk_ids)


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

    # 1) 统计缓存孤儿清理（新版每会话一文件；旧版单文件）
    if SESSION_PROJCACHE_SESSIONS_DIR.is_dir():
        try:
            cached_files = list(SESSION_PROJCACHE_SESSIONS_DIR.iterdir())
        except OSError:
            cached_files = []
        for f in cached_files:
            if not f.is_file() or f.suffix != '.json':
                continue
            if f.stem not in live_session_ids:
                try:
                    f.unlink()
                    result['projcache_orphans'] += 1
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
            title = infer_display_title(s)
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
        print('  - ' + workspace_display_name(s['workspace_key']) + '  (会话 ' + s['session_id'] + ')')
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
            title = infer_display_title(s).lower()
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
              f'{infer_display_title(s)}  @ {ws["name"]}{cur}{arch}')
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
        title = it.get('title') or ('会话 ' + it['session_id'])
        print(f'  [{i}] {it["session_id"]}  {format_size(it["size"])}  删除于 {it["deleted_at"]}  '
              f' {title}  @ {it.get("workspace_name") or "?"}')
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
        title = it.get('title') or ('会话 ' + it['session_id'])
        print('  - ' + it['session_id'] + '  (' + title + ')')
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
