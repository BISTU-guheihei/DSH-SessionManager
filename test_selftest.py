# -*- coding: utf-8 -*-
'''DSH 会话管理工具 —— 自测脚本（纯标准库，不需要真实 DSH 数据）。

用法:
    python test_selftest.py           # 或 python manage_sessions.py test

覆盖不依赖本机 DSH 数据的关键逻辑：
- 工作区目录名的编码 / 解码（含非 ASCII 的 ~XXXX~ 转义）
- DSH 运行检测的识别与误报
- 会话日志文件名解析
- 标题提取结果的解析与 UTF-8 安全截断
- 空输入 / 异常输入的容错
'''

import sys
from pathlib import Path

import session_core as sc

_PASS = 0
_FAIL = []


def check(name, got, want):
    global _PASS
    if got == want:
        _PASS += 1
        print('  [OK]   ' + name)
    else:
        _FAIL.append(name)
        print('  [FAIL] ' + name)
        print('         期望: ' + repr(want))
        print('         实际: ' + repr(got))


def check_true(name, got):
    check(name, bool(got), True)


# ----------------------------------------------------------------------
def test_workspace_encoding():
    print('\n[1] 工作区目录名 编码/解码')
    # 纯 ASCII 路径（含连字符，编码本身不可逆，用 encode 的结果做基准）
    check('ASCII 编码', sc.encode_workspace(r'E:\AAA_software\proj'),
          '--E-AAA_software-proj--')
    # 非 ASCII：DSH 只给连续非 ASCII 串的首个字符加波浪号
    check('中文路径编码', sc.encode_workspace(r'E:\资料\2026.10.10\dwg'),
          '--E-~8D44~6599-2026.10.10-dwg--')
    check('单个中文编码', sc.encode_workspace(r'E:\资\x'), '--E-~8D44~-x--')
    # 解码可还原中文路径
    check('中文路径解码', sc.decode_workspace('--E-~8D44~6599-2026.10.10-dwg--'),
          r'E:\资料\2026.10.10\dwg')
    # 被 "\\" 与 "-" 混同的路径不可逆 —— 这正是必须用 workspace.json 权威路径的原因
    check('不可逆路径解码（预期有损）',
          sc.decode_workspace('--C-Users-a-deepseek-harness-default-workspace--'),
          r'C:\Users\a\deepseek\harness\default\workspace')
    # 十六进制辅助
    check('_is_hex4 合法', sc._is_hex4('8D44'), True)
    check('_is_hex4 非法', sc._is_hex4('8D4'), False)
    check('_is_hex4 非十六进制', sc._is_hex4('ZZZZ'), False)


def test_detect_running():
    print('\n[2] DSH 运行检测（解析与误报）')
    orig = sc._list_process_names
    try:
        # 真实场景：DSH Desktop 的进程名是 "DeepSeek Harness.exe"
        sc._list_process_names = lambda: ['explorer', 'deepseek harness', 'chrome']
        check('识别 DSH Desktop', sc.detect_dsh_running(), True)
        # 旧命名
        for nm in ('dsh', 'dsh-desktop', 'dsh-web', 'dsh desktop'):
            sc._list_process_names = lambda n=nm: ['svchost', n]
            check('识别旧命名 ' + nm, sc.detect_dsh_running(), True)
        # 误报：普通 Node 进程不算 DSH
        sc._list_process_names = lambda: ['node', 'explorer', 'code']
        check('纯 Node 不误报', sc.detect_dsh_running(), False)
        # 误报：空进程表
        sc._list_process_names = lambda: []
        check('空进程表', sc.detect_dsh_running(), False)
        # 误报：名字里偶然含 dsh 的无关进程 —— 精确匹配必须挡住
        sc._list_process_names = lambda: ['mydshtool', 'dshhelper', 'notdshatall']
        check('相似名不误报', sc.detect_dsh_running(), False)
        # 异常容错
        def _boom():
            raise OSError('tasklist 不可用')
        sc._list_process_names = _boom
        check('检测异常时保守返回 False', sc.detect_dsh_running(), False)
    finally:
        sc._list_process_names = orig


def test_session_log_resolution():
    print('\n[3] 会话日志文件名解析')
    check('v4 排名高于无版本号', sc._log_version_rank('session.v4.jsonl.zstd'),
          (1, 4))
    check('无版本号排名', sc._log_version_rank('session.jsonl.zstd'), (0, 0))
    check('不存在的目录返回 None',
          sc.find_session_log(Path('Z:/definitely/not/here')), None)


def test_extract_output_parsing():
    print('\n[4] 提取结果解析')
    empty = {'title': '', 'fallback_title': '', 'first_user_text': '', 'cwd': ''}
    check('空输出', sc._parse_extract_output(''), empty)
    check('None 输出', sc._parse_extract_output(None), empty)
    # 新版 JSON 输出
    got = sc._parse_extract_output(
        '{"title":"精炼标题","fallback_title":"首句","first_user_text":"首句原文","cwd":"E:\\\\x"}')
    check('解析 JSON: title', got['title'], '精炼标题')
    check('解析 JSON: fallback', got['fallback_title'], '首句')
    check('解析 JSON: cwd', got['cwd'], r'E:\x')
    # 兼容旧脚本的纯文本输出
    check('兼容纯文本输出', sc._parse_extract_output('老版纯文本标题')['title'], '老版纯文本标题')
    # 坏 JSON 不应抛异常
    check_true('坏 JSON 不抛异常', isinstance(sc._parse_extract_output('{bad json'), dict))


def test_utf8_safe_truncate():
    print('\n[5] UTF-8 安全截断')
    check('None 输入', sc._truncate_utf8_safe(None, 10), '')
    check('短文本不截断', sc._truncate_utf8_safe('  hi  ', 10), 'hi')
    check('刚好等长不加省略号', sc._truncate_utf8_safe('abcde', 5), 'abcde')
    # emoji 是代理对：截断点不能留下孤立的高代理项
    emoji = '\U0001F600'
    out = sc._truncate_utf8_safe('a' * 59 + emoji + 'tail', 60)
    check_true('代理对未被截断', not any(0xD800 <= ord(c) <= 0xDBFF for c in out))
    check_true('截断后带省略号', out.endswith('…'))
    check('超长文本加省略号', sc._truncate_utf8_safe('x' * 100, 60), 'x' * 60 + '…')


def test_stats_parsing():
    print('\n[6] 统计缓存 rows 解析（新旧布局共用）')
    rows = {
        'title': {'ver': 1, 'val': '缓存标题'},
        'sessionStats': {'ver': 1, 'val': {'turns': 3, 'steps': 9,
                                           'llmMs': 1234, 'toolMs': 56}},
        'tokenUsage': {'ver': 2, 'val': {'totals': {
            'uncachedInputTokens': 11, 'outputTokens': 22, 'cacheReadTokens': 33}}},
        'contextPressure': {'ver': 5, 'val': {
            'surfaceTokens': 500, 'contextWindow': 1000}},
    }
    e = sc._stats_from_rows(rows)
    check('标题', e.get('title'), '缓存标题')
    check('轮数', e.get('turns'), 3)
    check('步骤', e.get('steps'), 9)
    check('LLM 耗时', e.get('llmMs'), 1234)
    check('输出 token', e.get('outputTokens'), 22)
    check('上下文窗口', e.get('contextWindow'), 1000)
    # 无 title 时退回 titleInput.first.text
    e2 = sc._stats_from_rows({'titleInput': {'val': {'first': {'text': '首句原文'}}}})
    check('titleInput 兜底', e2.get('titleInput'), '首句原文')
    # 异常输入不抛
    check('非 dict 输入', sc._stats_from_rows(None), {})
    check('空 dict 输入', sc._stats_from_rows({}), {})


def test_misc_helpers():
    print('\n[7] 其它格式化 / 容错')
    check('format_size 0', sc.format_size(0), '0 B')
    check('format_size KB', sc.format_size(2048), '2.0 KB')
    check('format_size MB', sc.format_size(3 * 1024 * 1024), '3.0 MB')
    check('format_size 异常输入', sc.format_size(None), '0 B')
    check('format_tokens 千', sc.format_tokens(1500), '1.5K')
    check('format_tokens 百万', sc.format_tokens(2000000), '2.00M')
    check('format_age 秒', sc.format_age(30), '30 秒前')
    check('format_age 分', sc.format_age(120), '2 分钟前')
    check('format_age 异常', sc.format_age(None), '0 秒前')
    check('format_mtime 空', sc.format_mtime(0), '-')
    # infer_display_title 绝不返回空
    t = sc.infer_display_title({'session_id': 'session-abc', 'path': None})
    check_true('infer_display_title 非空', bool(t) and t != '(无标题)')


def main():
    print('=' * 62)
    print('DSH 会话管理器 自测')
    print('=' * 62)
    test_workspace_encoding()
    test_detect_running()
    test_session_log_resolution()
    test_extract_output_parsing()
    test_utf8_safe_truncate()
    test_stats_parsing()
    test_misc_helpers()
    print('\n' + '=' * 62)
    total = _PASS + len(_FAIL)
    if _FAIL:
        print('失败 {0}/{1}'.format(len(_FAIL), total))
        for n in _FAIL:
            print('  - ' + n)
        return 1
    print('全部通过 {0}/{1}'.format(_PASS, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
