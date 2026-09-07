# -*- coding: utf-8 -*-
'''DSH 会话管理工具 —— 图形界面模块（深色高级风）。

设计：
- 深色主题（近黑灰底 + 深灰卡片），护眼不刺眼
- 统一字体（Microsoft YaHei UI / Segoe UI）
- 按钮：深灰底渐变，hover 上浮提亮，主按钮 DeepSeek 蓝渐变
- 顶栏圆形鲸鱼娘头像（透明底）+ 视图切换
- 详情面板：直接绘制 + 滚动条，内容不被裁剪
- DSH 运行状态呼吸灯

依赖：tkinter（标准库）。
'''

import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from session_core import (
    get_workspaces, list_trash_items, perform_delete_sessions,
    perform_delete_workspaces, perform_delete_old_sessions,
    perform_clean_residue, restore_trash_items, purge_trash_items,
    set_archived, detect_dsh_running, format_size, format_duration,
    format_tokens, format_age, format_mtime, decode_workspace,
    infer_display_title,
    TRASH_DIR, SESSIONS_DIR, DSH_HOME, CURRENT_SESSION_ID, OLD_THRESHOLD_SECONDS,
)


# ----------------------------------------------------------------------
# 深色主题
# ----------------------------------------------------------------------
BG = '#14161B'              # 窗口底
CARD = '#1C1F26'            # 卡片
CARD_2 = '#22262F'          # 次级卡片 / 表头
BORDER = '#2C313C'          # 边框
TEXT = '#E7EAF0'            # 主文字
TEXT_SUB = '#98A0AD'        # 次要文字
PRIMARY = '#5B7CFA'         # DeepSeek 蓝（深色版更亮）
PRIMARY_DARK = '#4260D6'
PRIMARY_LIGHT = '#27314F'   # 选中行背景（深蓝）
PRIMARY_GHOST = '#212737'   # 表头浅蓝底
DANGER = '#F06A6A'
DANGER_DARK = '#C94F4F'
DANGER_LIGHT = '#3A2428'
SUCCESS = '#34D399'
SUCCESS_DARK = '#1FA678'
WARN = '#F5B94B'
HOVER_BG = '#262B36'
DISABLED_FG = '#5A616D'

FONT_FAMILY = 'Microsoft YaHei UI'

_APP_FONTS = {}


def _font(size, bold=False):
    key = (size, bold)
    if key not in _APP_FONTS:
        fam = FONT_FAMILY
        avail = set(tkfont.families())
        if FONT_FAMILY not in avail:
            fam = 'Segoe UI' if 'Segoe UI' in avail else 'TkDefaultFont'
        _APP_FONTS[key] = tkfont.Font(family=fam, size=size,
                                      weight='bold' if bold else 'normal')
    return _APP_FONTS[key]


def _asset(rel_path):
    candidates = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, rel_path))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(c):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(x))) for x in c)


def _lerp(c1, c2, t):
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


# ----------------------------------------------------------------------
# 高级按钮：渐变底 + 投影 + hover 上浮 + 高光边
# ----------------------------------------------------------------------
class HoverButton(tk.Canvas):
    '''自绘圆角按钮：垂直渐变、底部投影、hover 上浮、顶部高光边、按下下沉。'''

    SHADOW = 4   # 底部投影高度（canvas 比按钮高这么多）

    def __init__(self, master, text, command=None, *, width=150, height=40,
                 radius=8, font_size=10, bold=False, danger=False, primary=False,
                 disabled=False):
        self._bw = width
        self._bh = height
        self._br = radius
        self._style = 'danger' if danger else ('primary' if primary else 'normal')
        self._command = command
        self._disabled = disabled
        self._text = text
        self._anim = None
        self._t = 0.0      # 0=normal 1=hover
        self._pressed = False
        super().__init__(master, width=width, height=height + self.SHADOW,
                         highlightthickness=0, bd=0, bg=master['bg'],
                         cursor='hand2' if not disabled else 'arrow')
        self._font = _font(font_size, bold)
        self._draw()
        if not disabled:
            self.bind('<Enter>', self._on_enter)
            self.bind('<Leave>', self._on_leave)
            self.bind('<ButtonPress-1>', self._on_press)
            self.bind('<ButtonRelease-1>', self._on_release)
        else:
            self.configure(cursor='arrow')

    def _palette(self):
        '''返回 (top, bottom, fg, border, glow, hover_top, hover_bottom, hover_glow)。'''
        if self._disabled:
            return '#23262E', '#23262E', DISABLED_FG, '#2C313C', '#1A1C22', None, None, None
        if self._style == 'primary':
            return PRIMARY, PRIMARY_DARK, '#FFFFFF', '#3E58C8', '#7E9BFF', '#6E8BFF', '#4E6CE8', '#A5BCFF'
        if self._style == 'danger':
            return '#3A262B', '#2E1E22', DANGER, '#5A3439', '#241519', '#4A2E33', '#382428', '#7A4A4E'
        return CARD_2, '#1A1D24', TEXT, '#39404D', '#101319', '#2E3440', '#252A34', '#4E5870'

    def _current(self, field):
        pal = self._palette()
        top, bottom, fg, border, glow, htop, hbot, hglow = pal
        if self._disabled or htop is None:
            return {'top': top, 'bottom': bottom, 'fg': fg,
                    'border': border, 'glow': glow}.get(field)
        a = {'top': top, 'bottom': bottom, 'border': border, 'glow': glow}
        b = {'top': htop, 'bottom': hbot, 'border': '#4A5570', 'glow': hglow}
        return _rgb_to_hex(_lerp(_hex_to_rgb(a[field]), _hex_to_rgb(b[field]), self._t))

    def _draw(self):
        self.delete('all')
        w, h, r = self._bw, self._bh, self._br
        top = self._current('top')
        bottom = self._current('bottom')
        border = self._current('border')
        glow = self._current('glow')

        # 按钮主体的垂直偏移：normal 0 / hover 上浮 2px / 按下下沉 1px
        if self._disabled:
            lift = 0
        elif self._pressed:
            lift = self.SHADOW - 1
        else:
            lift = int(self.SHADOW * (1 - self._t) - 1)

        # 底部投影（随 hover 加深、变小 = 上浮感）
        shadow_alpha = 0.35 + 0.25 * (1 - self._t)
        shadow_color = _rgb_to_hex(tuple(
            int(c * shadow_alpha) for c in _hex_to_rgb('#000000')))
        self._round_rect(2, self.SHADOW, w - 2, h + self.SHADOW, r,
                         fill=shadow_color, outline='')

        # 主体渐变
        steps = 22
        for i in range(steps):
            t = i / (steps - 1)
            color = _rgb_to_hex(_lerp(_hex_to_rgb(top), _hex_to_rgb(bottom), t))
            y0 = lift + i * h / steps
            y1 = lift + (i + 1) * h / steps + 1
            self._clip_band(i, steps, w, lift, h, r, y0, y1, color)

        # 顶部高光边（1.5px 亮线）
        if not self._disabled:
            self._round_rect(2, lift + 1, w - 2, lift + 3, r - 1,
                             fill='', outline=glow)

        # 边框
        self._round_rect(0, lift, w, lift + h, r, fill='', outline=border)

        fg = self._palette()[2] if not self._disabled else DISABLED_FG
        ty = lift + h / 2 + 1
        self.create_text(w / 2, ty, text=self._text, fill=fg, font=self._font)

    def _clip_band(self, i, steps, w, lift, h, r, y0, y1, color):
        '''画一条渐变带，顶部/底部圆角处缩进。'''
        x0, x1 = 0.0, float(w)
        top_band = y0 < lift + r and y1 > lift + r
        bot_band = y0 < lift + h - r and y1 > lift + h - r
        if i == 0:
            x0 = r
        if i == steps - 1:
            x1 = w - r
        if top_band or bot_band:
            return
        self.create_rectangle(x0, y0, x1, y1, fill=color, outline='')
        # 圆角段单独画
        if i == 0:
            self._round_rect(0, lift, w, lift + r * 2, r, fill=color, outline='')
        if i == steps - 1:
            self._round_rect(0, lift + h - r * 2, w, lift + h, r, fill=color, outline='')

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, **kw)

    def set_text(self, text):
        self._text = text
        self._draw()

    def _animate_to(self, target):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None

        def step():
            delta = target - self._t
            if abs(delta) < 0.05:
                self._t = target
                self._draw()
                self._anim = None
                return
            self._t += delta * 0.35
            self._draw()
            self._anim = self.after(16, step)
        step()

    def _on_enter(self, _e):
        self._animate_to(1.0)

    def _on_leave(self, _e):
        self._pressed = False
        self._animate_to(0.0)

    def _on_press(self, _e):
        self._pressed = True
        self._draw()

    def _on_release(self, _e):
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and self._command:
            self._command()


# ----------------------------------------------------------------------
# 深色对话框（替代白色系统 messagebox）
# ----------------------------------------------------------------------
class DarkDialog(tk.Toplevel):
    '''深色主题模态对话框：标题 + 消息 + 按钮，居中于父窗口。'''

    def __init__(self, parent, title, message, *, buttons=None, icon=None,
                 danger_title=False):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        self._result = None
        self._buttons = {}

        outer = tk.Frame(self, bg=CARD)
        outer.pack(fill='both', expand=True, padx=1, pady=1)
        tk.Frame(outer, bg=BORDER).pack(fill='both', expand=True, padx=0, pady=0)
        inner = tk.Frame(outer, bg=CARD, padx=22, pady=16)
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        # 标题行：图标 + 标题文字
        head = tk.Frame(inner, bg=CARD)
        head.pack(fill='x')
        if icon:
            tk.Label(head, text=icon, font=_font(14), bg=CARD,
                     fg=DANGER if danger_title else PRIMARY).pack(side='left', padx=(0, 8))
        tk.Label(head, text=title, font=_font(12, bold=True), bg=CARD,
                 fg=DANGER if danger_title else TEXT,
                 anchor='w', justify='left', wraplength=430).pack(side='left', fill='x')


        # 消息区（自动换行）
        msg_frame = tk.Frame(inner, bg=CARD)
        msg_frame.pack(fill='x', pady=(10, 6))
        tk.Label(msg_frame, text=message, font=_font(10), bg=CARD, fg=TEXT_SUB,
                 anchor='w', justify='left', wraplength=430).pack(fill='x')

        # 按钮行
        btn_row = tk.Frame(inner, bg=CARD)
        btn_row.pack(fill='x', pady=(10, 0))
        if not buttons:
            buttons = [('确定', 'ok', 'primary')]
        # 右对齐排列
        btn_row.columnconfigure(0, weight=1)
        col = 1
        for text, value, style in buttons:
            if style == 'primary':
                btn = HoverButton(btn_row, text, None, primary=True,
                                  width=92, height=34, radius=7, font_size=10)
            elif style == 'danger':
                btn = HoverButton(btn_row, text, None, danger=True,
                                  width=92, height=34, radius=7, font_size=10)
            else:
                btn = HoverButton(btn_row, text, None,
                                  width=92, height=34, radius=7, font_size=10)
            btn.grid(row=0, column=col, padx=(8, 0))
            self._buttons[btn] = value
            # 重新绑定：点击后记录结果并关闭
            for ev in ('<Enter>', '<Leave>', '<ButtonPress-1>', '<ButtonRelease-1>'):
                btn.unbind(ev)
            btn._command = lambda v=value: self._close(v)
            btn.bind('<Enter>', btn._on_enter)
            btn.bind('<Leave>', btn._on_leave)
            btn.bind('<ButtonPress-1>', btn._on_press)
            btn.bind('<ButtonRelease-1>', lambda e, v=value: self._close(v))
            col += 1

        # 快捷键：Enter=第一个按钮，Esc=取消（最后一个普通按钮或 None）
        self.bind('<Return>', lambda e: self._close(buttons[0][1]))
        self.bind('<Escape>', lambda e: self._close(None))
        self.protocol('WM_DELETE_WINDOW', lambda: self._close(None))

        self.update_idletasks()
        self._center(parent)
        # 对话框标题栏也深色化（Windows）
        self._apply_dark_titlebar()
        self.grab_set()
        self.focus_set()
        if self._buttons:
            first_btn = next(iter(self._buttons))
            first_btn.focus_set()

    def _apply_dark_titlebar(self):
        '''把对话框的 Windows 标题栏设为深色。'''
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            self.update_idletasks()
            hwnd = _top_hwnd(self)
            if not hwnd:
                return
            dwmapi = ctypes.windll.dwmapi
            value = ctypes.c_int(1)
            for attr in (20, 19):
                try:
                    if dwmapi.DwmSetWindowAttribute(hwnd, attr,
                                                    ctypes.byref(value),
                                                    ctypes.sizeof(value)) == 0:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    def _center(self, parent):
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2 - 30
        self.geometry(f'+{max(x, 0)}+{max(y, 0)}')

    def _close(self, value):
        self._result = value
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def show(self):
        '''显示并等待用户选择，返回按钮值（取消/关闭返回 None）。'''
        self.deiconify()
        self.wait_window()
        return self._result

    # ---- 便捷工厂 ----
    @classmethod
    def confirm(cls, parent, title, message, yes_text='确定', no_text='取消',
                danger=False):
        dlg = cls(parent, title, message,
                  buttons=[(no_text, False, 'normal'), (yes_text, True, 'primary')],
                  icon='⚠' if danger else '❓', danger_title=danger)
        return dlg.show()

    @classmethod
    def info(cls, parent, title, message):
        dlg = cls(parent, title, message,
                  buttons=[('确定', True, 'primary')], icon='ℹ')
        return dlg.show()

    @classmethod
    def warn(cls, parent, title, message):
        dlg = cls(parent, title, message,
                  buttons=[('确定', True, 'primary')], icon='⚠', danger_title=True)
        return dlg.show()


# ----------------------------------------------------------------------
# 状态灯
# ----------------------------------------------------------------------
class StatusDot(tk.Canvas):
    def __init__(self, master, size=11, bg_color=CARD):
        super().__init__(master, width=size + 6, height=size + 6,
                         highlightthickness=0, bd=0, bg=bg_color)
        self._size = size
        self._running = False
        self._phase = 0.0
        self._tick()

    def set_running(self, running):
        self._running = running
        self._tick()

    def _tick(self):
        self.delete('all')
        s = self._size
        cx, cy = (s + 6) / 2, (s + 6) / 2
        self._phase = (self._phase + 0.12) % 6.28
        if self._running:
            self.create_oval(cx - s / 2 - 2, cy - s / 2 - 2, cx + s / 2 + 2, cy + s / 2 + 2,
                             fill=SUCCESS, outline='', stipple='gray50')
        self.create_oval(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2,
                         fill=SUCCESS if self._running else '#4A505C', outline='')
        self.after(120, self._tick)


# ----------------------------------------------------------------------
# 上下文压力进度条
# ----------------------------------------------------------------------
class PressureBar(tk.Canvas):
    def __init__(self, master, width=240, height=10, bg_color=CARD):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, bg=bg_color)
        self._bw, self._bh = width, height
        self._target = 0.0
        self._cur = 0.0
        self._anim = None

    def set_value(self, ratio):
        self._target = max(0.0, min(1.0, ratio))
        if self._anim is None:
            self._anim_step()

    def _anim_step(self):
        delta = self._target - self._cur
        if abs(delta) < 0.005:
            self._cur = self._target
            self._draw()
            self._anim = None
            return
        self._cur += delta * 0.18
        self._draw()
        self._anim = self.after(20, self._anim_step)

    def _draw(self):
        self.delete('all')
        w, h = self._bw, self._bh
        r = h / 2
        self.create_oval(0, 0, h, h, fill='#2A2F3A', outline='')
        self.create_oval(w - h, 0, w, h, fill='#2A2F3A', outline='')
        self.create_rectangle(h / 2, 0, w - h / 2, h, fill='#2A2F3A', outline='')
        fw = w * self._cur
        if fw > 2:
            if self._cur < 0.6:
                c1 = PRIMARY
            elif self._cur < 0.85:
                c1 = WARN
            else:
                c1 = DANGER
            if fw < h:
                self.create_oval(0, 0, h, h, fill=c1, outline='')
            else:
                self.create_oval(0, 0, h, h, fill=c1, outline='')
                self.create_rectangle(h / 2, 0, fw, h, fill=c1, outline='')
                self.create_oval(fw - h, 0, fw, h, fill=c1, outline='')


# ----------------------------------------------------------------------
# 主应用
# ----------------------------------------------------------------------
class SessionManagerApp:
    TOP_H = 62
    BOT_H = 44

    def __init__(self, root):
        self.root = root
        self.root.title('DSH 会话管理器')
        self.root.geometry('1240x780')
        # 最小窗口：保证详情面板(标题+3行按钮+统计内容)和树均不被压缩遮挡
        self.root.minsize(1060, 700)
        self.root.configure(bg=BG)

        self.workspaces = []
        self.item_data = {}
        self.view = 'sessions'
        self.trash_items = []
        self._images = []
        self._hover_tags = {}

        self._build_ui()
        self.root.bind('<Configure>', self._on_resize)
        self.refresh()
        self._refresh_dsh_status()
        self._auto_refresh_loop()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # 顶栏
        self.top_bar = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                                highlightbackground=BORDER)
        self.top_bar.place(x=0, y=0, relwidth=1, height=self.TOP_H)

        # 圆形鲸鱼娘头像（透明底 44px）
        logo_file = _asset(os.path.join('assets', 'logo_circle.png'))
        if logo_file:
            try:
                logo_img = tk.PhotoImage(file=logo_file)
                self._images.append(logo_img)
                tk.Label(self.top_bar, image=logo_img, bg=CARD).place(x=16, y=9)
            except Exception:
                pass

        tk.Label(self.top_bar, text='DSH 会话管理器', font=_font(14, bold=True),
                 bg=CARD, fg=TEXT).place(x=70, y=9)
        tk.Label(self.top_bar, text='鲸鱼娘守护的会话回收站', font=_font(8),
                 bg=CARD, fg=TEXT_SUB).place(x=71, y=36)

        self.btn_view_sessions = HoverButton(self.top_bar, '会话', self._show_sessions_view,
                                             width=76, height=30, radius=7,
                                             primary=True)
        self.btn_view_sessions.place(relx=1.0, x=-168, y=16)
        self.btn_view_trash = HoverButton(self.top_bar, '回收站', self._show_trash_view,
                                          width=76, height=30, radius=7)
        self.btn_view_trash.place(relx=1.0, x=-86, y=16)

        # 底栏
        self.bottom_bar = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.bottom_bar.place(x=0, rely=1.0, relwidth=1, height=self.BOT_H, anchor='sw')
        self.status_var = tk.StringVar(value='正在加载...')
        tk.Label(self.bottom_bar, textvariable=self.status_var, font=_font(9),
                 bg=CARD, fg=TEXT_SUB).place(x=14, y=15)
        self.dot = StatusDot(self.bottom_bar)
        self.dot.place(relx=1.0, x=-140, y=14)
        self.dsh_label = tk.Label(self.bottom_bar, text='DSH 状态', font=_font(9),
                                  bg=CARD, fg=TEXT_SUB)
        self.dsh_label.place(relx=1.0, x=-126, y=15)

        # 左侧：会话树卡片
        self.left_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                                  highlightbackground=BORDER)
        self.left_card.place(relx=0.012, y=self.TOP_H + 10, relwidth=0.60)

        self.tree_header = tk.Frame(self.left_card, bg=CARD_2)
        self.tree_header.pack(fill='x')
        self.view_title_var = tk.StringVar(value='会话列表')
        tk.Label(self.tree_header, textvariable=self.view_title_var, font=_font(11, bold=True),
                 bg=CARD_2, fg=PRIMARY).pack(side='left', padx=14, pady=6)
        self.count_var = tk.StringVar(value='')
        tk.Label(self.tree_header, textvariable=self.count_var, font=_font(9),
                 bg=CARD_2, fg=TEXT_SUB).pack(side='right', padx=14)

        tree_frame = tk.Frame(self.left_card, bg=CARD)
        tree_frame.pack(fill='both', expand=True, padx=6, pady=6)

        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self.style.configure('Whale.Treeview', background=CARD, fieldbackground=CARD,
                             foreground=TEXT, borderwidth=0, rowheight=32,
                             font=(FONT_FAMILY, 10))
        self.style.configure('Whale.Treeview.Heading', background=CARD_2,
                             foreground=TEXT_SUB, font=(FONT_FAMILY, 9, 'bold'),
                             borderwidth=0, relief='flat', padding=6)
        self.style.map('Whale.Treeview',
                       background=[('selected', '#3A465E')],
                       foreground=[('selected', '#FFFFFF')])
        self.style.map('Whale.Treeview.Heading', background=[('active', CARD_2)])

        columns = ('size', 'mtime', 'note')
        self.tree = ttk.Treeview(tree_frame, columns=columns, style='Whale.Treeview',
                                 selectmode='extended', show='tree headings')
        self.tree.heading('#0', text='名称 / 会话')
        self.tree.heading('size', text='大小')
        self.tree.heading('mtime', text='最后修改')
        self.tree.heading('note', text='备注')
        self.tree.column('#0', width=360, minwidth=230, stretch=True)
        self.tree.column('size', width=88, minwidth=66, anchor='e', stretch=False)
        self.tree.column('mtime', width=140, minwidth=105, anchor='center', stretch=False)
        self.tree.column('note', width=120, minwidth=90, anchor='w', stretch=False)
        self.tree.tag_configure('workspace', font=(FONT_FAMILY, 11, 'bold'),
                                foreground='#C9CEDA', background=CARD)
        self.tree.tag_configure('session', foreground=TEXT, background=CARD)
        self.tree.tag_configure('current', foreground='#AEBEFF', background=PRIMARY_LIGHT,
                                font=(FONT_FAMILY, 10, 'bold'))
        self.tree.tag_configure('archived', foreground='#6B7280', background=CARD)
        self.tree.tag_configure('trash_item', foreground=TEXT, background=CARD)
        self.tree.tag_configure('hover', background=HOVER_BG)

        yscroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Motion>', self._on_tree_motion)
        self.tree.bind('<Leave>', self._on_tree_leave)
        self._hover_row = None

        # 右侧：详情卡片
        self.right_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.right_card.place(relx=0.632, y=self.TOP_H + 10, relwidth=0.356)

        self.detail_header = tk.Label(self.right_card, text='会话详情',
                                      font=_font(12, bold=True), bg=CARD, fg=TEXT,
                                      anchor='w')
        self.detail_header.pack(fill='x', padx=16, pady=(12, 4))

        detail_frame = tk.Frame(self.right_card, bg=CARD)
        detail_frame.pack(fill='both', expand=True, padx=(16, 8), pady=(0, 8))
        self.detail = tk.Canvas(detail_frame, bg=CARD, highlightthickness=0, bd=0)
        self.detail_sb = ttk.Scrollbar(detail_frame, orient='vertical',
                                       command=self.detail.yview)
        self.detail.configure(yscrollcommand=self.detail_sb.set)
        self.detail.pack(side='left', fill='both', expand=True)
        self.detail_sb.pack(side='right', fill='y')
        self._detail_state = None
        self._detail_views = []

        # 右侧按钮区
        self.btn_panel = tk.Frame(self.right_card, bg=CARD)
        self.btn_panel.pack(side='bottom', fill='x', padx=16, pady=(6, 14))
        self._build_buttons()
        self._sync_view_buttons()

    def _build_buttons(self):
        grid = tk.Frame(self.btn_panel, bg=CARD)
        grid.pack(fill='x')
        grid.columnconfigure(0, weight=1, uniform='btn')
        grid.columnconfigure(1, weight=1, uniform='btn')

        self.btn_refresh = HoverButton(grid, '刷新', self.refresh, width=120, height=38)
        self.btn_refresh.grid(row=0, column=0, padx=(0, 5), pady=3, sticky='ew')
        self.btn_archive = HoverButton(grid, '归档选中', self._archive_selected,
                                       width=120, height=38)
        self.btn_archive.grid(row=0, column=1, padx=(5, 0), pady=3, sticky='ew')

        self.btn_delete = HoverButton(grid, '删除选中 → 回收站', self._delete_selected,
                                      danger=True, width=120, height=38)
        self.btn_delete.grid(row=1, column=0, padx=(0, 5), pady=3, sticky='ew')
        self.btn_delold = HoverButton(grid, '删除历史会话', self._delete_old,
                                      width=120, height=38)
        self.btn_delold.grid(row=1, column=1, padx=(5, 0), pady=3, sticky='ew')

        self.btn_delws = HoverButton(grid, '删除选中工作区', self._delete_selected_workspace,
                                     danger=True, width=120, height=38)
        self.btn_delws.grid(row=2, column=0, padx=(0, 5), pady=3, sticky='ew')
        self.btn_clean = HoverButton(grid, '清理缓存残留', self._clean_residue,
                                     width=120, height=38)
        self.btn_clean.grid(row=2, column=1, padx=(5, 0), pady=3, sticky='ew')

        self.btn_restore = HoverButton(grid, '恢复选中', self._restore_selected,
                                       primary=True, width=120, height=38)
        self.btn_restore.grid(row=0, column=0, padx=(0, 5), pady=3, sticky='ew')
        self.btn_purge = HoverButton(grid, '彻底删除', self._purge_selected,
                                     danger=True, width=120, height=38)
        self.btn_purge.grid(row=0, column=1, padx=(5, 0), pady=3, sticky='ew')

        self.btn_empty_trash = HoverButton(grid, '清空回收站', self._empty_trash,
                                           danger=True, width=120, height=38)
        self.btn_empty_trash.grid(row=1, column=0, padx=(0, 5), pady=3, sticky='ew')

    # ------------------------------------------------------------------
    # 窗口缩放
    # ------------------------------------------------------------------
    def _on_resize(self, e):
        if e.widget is not self.root:
            return
        h = self.root.winfo_height()
        card_top = self.TOP_H + 10
        card_bottom = h - self.BOT_H - 10
        card_h = max(card_bottom - card_top, 280)
        self.left_card.place(y=card_top, height=card_h)
        self.right_card.place(y=card_top, height=card_h)

    # ------------------------------------------------------------------
    # DSH 状态灯
    # ------------------------------------------------------------------
    def _refresh_dsh_status(self):
        running = detect_dsh_running()
        self.dot.set_running(running)
        self.dsh_label.configure(
            text='DSH 运行中' if running else 'DSH 未运行',
            fg=SUCCESS if running else TEXT_SUB)
        self.root.after(8000, self._refresh_dsh_status)

    def _auto_refresh_loop(self):
        '''后台自动刷新：每 3 秒静默刷新一次列表（保留选择、不打断操作），
        让 DSH 运行中产生的新会话 / 删除变化实时反映到界面。'''
        try:
            self.refresh(silent=True)
        except Exception:
            pass
        self.root.after(3000, self._auto_refresh_loop)

    # ------------------------------------------------------------------
    # 视图与刷新
    # ------------------------------------------------------------------
    def _sync_view_buttons(self):
        if self.view == 'sessions':
            self._set_tab_style(self.btn_view_sessions, True)
            self._set_tab_style(self.btn_view_trash, False)
            self.view_title_var.set('会话列表')
            self.btn_restore.grid_remove()
            self.btn_purge.grid_remove()
            self.btn_empty_trash.grid_remove()
            self.btn_archive.grid()
            self.btn_delete.grid()
            self.btn_delold.grid()
            self.btn_delws.grid()
            self.btn_clean.grid()
        else:
            self._set_tab_style(self.btn_view_trash, True)
            self._set_tab_style(self.btn_view_sessions, False)
            self.view_title_var.set('回收站')
            self.btn_archive.grid_remove()
            self.btn_delete.grid_remove()
            self.btn_delold.grid_remove()
            self.btn_delws.grid_remove()
            self.btn_clean.grid_remove()
            self.btn_restore.grid()
            self.btn_purge.grid()
            self.btn_empty_trash.grid()

    def _set_tab_style(self, btn, active):
        if active:
            btn._style = 'primary'
            btn._t = 0.0
        else:
            btn._style = 'normal'
            btn._t = 0.0
        btn._draw()

    def _show_sessions_view(self):
        if self.view != 'sessions':
            self.view = 'sessions'
            self._sync_view_buttons()
            self.refresh()

    def _show_trash_view(self):
        if self.view != 'trash':
            self.view = 'trash'
            self._sync_view_buttons()
            self.refresh()

    def refresh(self, silent=False):
        '''刷新列表。silent=True 用于后台自动刷新：保留选择、不打断用户操作。'''
        # 记录当前选中（按会话 ID / 回收站条目），刷新后恢复
        selected_ids = set()
        for iid in self.tree.selection():
            item = self.item_data.get(iid)
            if item:
                if item['kind'] == 'session':
                    selected_ids.add(('s', item['data']['session_id']))
                elif item['kind'] == 'trash':
                    selected_ids.add(('t', item['data']['session_id']))
                elif item['kind'] == 'workspace':
                    selected_ids.add(('w', item['data']['name']))

        if self.view == 'sessions':
            self.workspaces = get_workspaces()
            self._populate_sessions()
            self._update_archive_button()
        else:
            self.trash_items = list_trash_items()
            self._populate_trash()

        # 恢复选择
        if selected_ids:
            for iid, item in self.item_data.items():
                key = None
                if item['kind'] == 'session':
                    key = ('s', item['data']['session_id'])
                elif item['kind'] == 'trash':
                    key = ('t', item['data']['session_id'])
                elif item['kind'] == 'workspace':
                    key = ('w', item['data']['name'])
                if key in selected_ids:
                    self.tree.selection_add(iid)
            if self.tree.selection():
                self._on_select(None)

        self._update_status_line()

    def _update_status_line(self, force=False):
        '''状态栏：会话统计 + 孤儿缓存提示 + DSH 提示。

        force=False 且存在 pending 操作提示时不覆盖（保留操作结果文字）；
        孤儿计数变化时会强制更新。'''
        now = self._status_line_text()
        if not force and getattr(self, '_status_pending', None):
            # 有操作结果要展示，跳过本次更新
            if now != getattr(self, '_last_status', ''):
                pass
            else:
                return
        self._last_status = now
        self.status_var.set(now)

    def _status_line_text(self):
        total_sessions = sum(ws['session_count'] for ws in self.workspaces)
        base = f'工作区 {len(self.workspaces)} 个 · 会话 {total_sessions} 个'
        if self.view == 'sessions':
            base += f' · 数据目录 {DSH_HOME}'
        else:
            base += f' · 回收站 {len(self.trash_items)} 条'
        # 孤儿缓存实时计数
        try:
            from session_core import count_projcache_orphans
            orphans = count_projcache_orphans()
            if orphans:
                base += f' · [发现 {len(orphans)} 条孤儿缓存，可清理]'
        except Exception:
            pass
        return base

    def _set_status(self, text):
        '''操作结果提示：设 pending，3 秒后自动回到实时状态栏。'''
        self._status_pending = text
        self.status_var.set(text)

        def _restore():
            self._status_pending = None
            self._update_status_line(force=True)
        try:
            self.root.after(3000, _restore)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 树填充
    # ------------------------------------------------------------------
    def _populate_sessions(self):
        self.tree.delete(*self.tree.get_children())
        self.item_data.clear()
        total = 0
        for ws in self.workspaces:
            ws_iid = self.tree.insert(
                '', 'end', text=f'▸ {ws["name"]}',
                values=('', '', '工作区'),
                tags=('workspace',), open=True)
            self.item_data[ws_iid] = {'kind': 'workspace', 'data': ws}
            for s in ws['sessions']:
                title = infer_display_title(s)
                s['display_title'] = title   # 缓存，详情/删除确认复用
                if s['is_current']:
                    note = '🛡 当前会话'
                elif s['is_archived']:
                    note = '🗂 已归档'
                else:
                    note = '可删除'
                s_iid = self.tree.insert(
                    ws_iid, 'end', text='  ' + title,
                    values=(format_size(s['size']), format_mtime(s['mtime']), note),
                    tags=('current' if s['is_current'] else
                          ('archived' if s['is_archived'] else 'session'),))
                self.item_data[s_iid] = {'kind': 'session', 'data': s}
                total += 1
        self.count_var.set(f'共 {total} 个会话')
        if self.tree.selection():
            self._on_select(None)

    def _populate_trash(self):
        self.tree.delete(*self.tree.get_children())
        self.item_data.clear()
        shown = 0
        for it in self.trash_items:
            title = it.get('title') or ('会话 ' + (it.get('session_id') or ''))
            shown += 1
            iid = self.tree.insert(
                '', 'end', text='  ' + title,
                values=(format_size(it['size']),
                        it.get('deleted_at', ''),
                        f'@ {it.get("workspace_name") or "?"}'),
                tags=('trash_item',))
            self.item_data[iid] = {'kind': 'trash', 'data': it}
        self.count_var.set(f'回收站 {shown} 条')
        if self.tree.selection():
            self._on_select(None)

    # ------------------------------------------------------------------
    # 树 hover
    # ------------------------------------------------------------------
    def _on_tree_motion(self, e):
        row = self.tree.identify_row(e.y)
        if row != self._hover_row:
            if self._hover_row and self.tree.exists(self._hover_row):
                if self._hover_row not in self.tree.selection():
                    self.tree.item(self._hover_row, tags=self._original_tags(self._hover_row))
            self._hover_row = row
            if row and self.tree.exists(row):
                if row not in self.tree.selection():
                    self._hover_tags[row] = self.tree.item(row, 'tags')
                    self.tree.item(row, tags=tuple(list(self.tree.item(row, 'tags')) + ['hover']))

    def _original_tags(self, row):
        return self._hover_tags.pop(row, self.tree.item(row, 'tags'))

    def _on_tree_leave(self, _e):
        if self._hover_row and self.tree.exists(self._hover_row):
            if self._hover_row not in self.tree.selection():
                self.tree.item(self._hover_row, tags=self._original_tags(self._hover_row))
        self._hover_row = None

    # ------------------------------------------------------------------
    # 选择与详情
    # ------------------------------------------------------------------
    def _on_select(self, _e):
        self._update_archive_button()
        selection = self.tree.selection()
        if len(selection) == 1:
            item = self.item_data.get(selection[0])
            if item and item['kind'] in ('session', 'trash'):
                self._show_detail(item['data'], item['kind'])
                return
        self._show_detail(None, None)

    def _update_archive_button(self):
        '''根据选中会话的归档状态动态更新按钮文字。'''
        targets, _ = self._selected_items('session')
        if not targets:
            self.btn_archive.set_text('归档选中')
            return
        archived_count = sum(1 for t in targets if t['is_archived'])
        if archived_count == 0:
            self.btn_archive.set_text('归档选中')
        elif archived_count == len(targets):
            self.btn_archive.set_text('取消归档')
        else:
            self.btn_archive.set_text('切换归档')

    def _show_detail(self, data, kind):
        self._detail_state = (data, kind)
        self._redraw_detail()

    def _redraw_detail(self):
        for w in self._detail_views:
            try:
                w.destroy()
            except Exception:
                pass
        self._detail_views.clear()
        self.detail.delete('all')
        data, kind = self._detail_state or (None, None)

        w = max(self.detail.winfo_width(), 220)
        pad = 6
        y = 16   # 顶部留足空间：create_text 的 y 是文字中心，需给半行高

        if data is None:
            logo_file = _asset(os.path.join('assets', 'logo.png'))
            if logo_file:
                try:
                    img = tk.PhotoImage(file=logo_file)
                    self._images.append(img)
                    self.detail.create_image(w / 2, 92, image=img)
                    y = 170
                except Exception:
                    y = 70
            self.detail.create_text(w / 2, y, text='选一个会话看看吧',
                                    font=_font(11, bold=True), fill=TEXT_SUB)
            self.detail.create_text(w / 2, y + 26,
                                    text='这里会显示会话的统计信息\n（轮数、耗时、Token 用量、上下文压力）',
                                    font=_font(9), fill='#6B7280', justify='center')
            self.detail.configure(scrollregion=(0, 0, w, max(self.detail.winfo_height(), 220)))
            return

        if kind == 'session':
            content_h = self._draw_session_detail(self.detail, data, w, pad, y)
        else:
            content_h = self._draw_trash_detail(self.detail, data, w, pad, y)
        # 直接绘制 + scrollregion：内容完整可滚动，不会被裁剪
        self.detail.configure(scrollregion=(0, 0, w, max(content_h + 10, self.detail.winfo_height())))
        self.detail.yview_moveto(0)
        self.detail.bind('<MouseWheel>', self._on_detail_wheel)

    def _on_detail_wheel(self, e):
        region = self.detail.cget('scrollregion')
        try:
            _, _, _, total_h = (float(v) for v in region.split())
            if total_h > self.detail.winfo_height():
                self.detail.yview_scroll(-1 * int(e.delta / 120), 'units')
                return 'break'
        except Exception:
            pass

    def _detail_row(self, canvas, y, key, value, w, pad=6):
        canvas.create_text(pad + 4, y, text=key, font=_font(9), fill=TEXT_SUB, anchor='w')
        canvas.create_text(w - pad - 20, y, text=value, font=_font(9, bold=True),
                           fill=TEXT, anchor='e')
        return y + 26

    def _draw_session_detail(self, canvas, s, w, pad, y):
        title = s.get('display_title') or infer_display_title(s)
        canvas.create_text(pad + 4, y, text=title, font=_font(13, bold=True),
                           fill=TEXT, anchor='w', width=w - 2 * pad - 24)
        y += 34
        badges = []
        if s['is_current']:
            badges.append(('🛡 当前会话', '#AEBEFF', PRIMARY_LIGHT))
        if s['is_archived']:
            badges.append(('🗂 已归档', '#9CA3AF', '#262B36'))
        if not badges:
            badges.append(('会话', TEXT_SUB, CARD_2))
        bx = pad + 4
        for text, fg, bg in badges:
            tw = _font(9).measure(text) + 16
            canvas.create_rectangle(bx, y, bx + tw, y + 22, fill=bg, outline='')
            canvas.create_text(bx + tw / 2, y + 11, text=text, font=_font(9), fill=fg)
            bx += tw + 8
        y += 36
        canvas.create_line(pad, y, w - pad - 10, y, fill=BORDER)
        y += 14

        stats = s.get('stats') or {}
        y = self._detail_row(canvas, y, '会话 ID', s['session_id'][:20] + '…', w, pad)
        y = self._detail_row(canvas, y, '工作区', decode_workspace(s['workspace_key'])[-28:] or s['workspace_key'][:24], w, pad)
        y = self._detail_row(canvas, y, '占用空间', format_size(s['size']), w, pad)
        y = self._detail_row(canvas, y, '最后修改', format_mtime(s['mtime']), w, pad)
        if stats:
            y += 6
            canvas.create_text(pad + 4, y, text='— 统计 —', font=_font(9, bold=True),
                               fill=TEXT_SUB, anchor='w')
            y += 26
            turns = stats.get('turns')
            steps = stats.get('steps')
            if turns is not None:
                y = self._detail_row(canvas, y, '对话轮数', str(turns) + ' 轮', w, pad)
            if steps is not None:
                y = self._detail_row(canvas, y, '执行步骤', str(steps) + ' 步', w, pad)
            if stats.get('llmMs') is not None:
                y = self._detail_row(canvas, y, 'LLM 耗时', format_duration(stats['llmMs']), w, pad)
            if stats.get('toolMs') is not None:
                y = self._detail_row(canvas, y, '工具耗时', format_duration(stats['toolMs']), w, pad)
            if stats.get('inputTokens') is not None:
                y = self._detail_row(canvas, y, '输入 Token', format_tokens(stats['inputTokens']), w, pad)
            if stats.get('outputTokens') is not None:
                y = self._detail_row(canvas, y, '输出 Token', format_tokens(stats['outputTokens']), w, pad)
            if stats.get('cacheReadTokens') is not None:
                y = self._detail_row(canvas, y, '缓存读取', format_tokens(stats['cacheReadTokens']), w, pad)
            surface = stats.get('surfaceTokens')
            window = stats.get('contextWindow')
            if surface is not None and window:
                y += 8
                ratio = min(1.0, surface / window)
                canvas.create_text(pad + 4, y, text='上下文压力', font=_font(9), fill=TEXT_SUB, anchor='w')
                canvas.create_text(w - pad - 20, y, text=f'{ratio * 100:.0f}%',
                                   font=_font(9, bold=True),
                                   fill=WARN if ratio > 0.85 else TEXT, anchor='e')
                y += 16
                bar_w = w - 2 * pad - 24
                bar = PressureBar(canvas, width=bar_w, height=10)
                canvas.create_window(pad + 4, y, window=bar, anchor='nw')
                bar.set_value(ratio)
                self._detail_views.append(bar)
                y += 20
        else:
            y += 6
            canvas.create_text(pad + 4, y, text='暂无统计缓存（新会话或 DSH 未记录）',
                               font=_font(9), fill='#6B7280', anchor='w')
            y += 22
        return y

    def _draw_trash_detail(self, canvas, it, w, pad, y):
        title = it.get('title') or ('会话 ' + (it.get('session_id') or ''))
        canvas.create_text(pad + 4, y, text=title, font=_font(13, bold=True),
                           fill=TEXT, anchor='w', width=w - 2 * pad - 24)
        y += 34
        canvas.create_rectangle(pad + 4, y, pad + 60, y + 22, fill=DANGER_LIGHT, outline='')
        canvas.create_text(pad + 32, y + 11, text='回收站', font=_font(9), fill=DANGER)
        y += 36
        canvas.create_line(pad, y, w - pad - 10, y, fill=BORDER)
        y += 14
        y = self._detail_row(canvas, y, '会话 ID', it['session_id'][:20] + '…', w, pad)
        y = self._detail_row(canvas, y, '原工作区', it.get('workspace_name') or '?', w, pad)
        y = self._detail_row(canvas, y, '删除时间', it.get('deleted_at') or '-', w, pad)
        y = self._detail_row(canvas, y, '占用空间', format_size(it['size']), w, pad)
        y += 10
        canvas.create_text(pad + 4, y, text='可随时恢复到原工作区，\n或彻底删除释放空间。',
                           font=_font(9), fill=TEXT_SUB, anchor='nw', justify='left')
        y += 40
        return y

    # ------------------------------------------------------------------
    # 选中目标收集
    # ------------------------------------------------------------------
    def _selected_items(self, kind):
        targets, blocked = [], []
        for iid in self.tree.selection():
            item = self.item_data.get(iid)
            if not item or item['kind'] != kind:
                continue
            data = item['data']
            if kind == 'session':
                if data.get('is_current'):
                    blocked.append(data)
                else:
                    targets.append(data)
            else:
                targets.append(data)
        return targets, blocked

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def _warn_cache_action(self, action_name):
        '''仅缓存类操作（归档/清理）需要提示：DSH 运行时会写回缓存覆盖修改。
        删除/恢复/彻底删除只动会话文件，不受影响，无需关闭 DSH。'''
        if not detect_dsh_running():
            return True
        return DarkDialog.confirm(
            self.root, 'DSH 正在运行',
            f'检测到 DSH Desktop 正在运行。\n\n{action_name} 修改的是 DSH 的缓存文件'
            f'（workspace.json），DSH 运行中可能会把缓存写回覆盖本次修改。\n\n'
            f'建议先完全退出 DSH 再执行 {action_name}。\n\n仍要继续吗？',
            yes_text='仍要继续', no_text='取消', danger=True)

    def _note_cache_residue(self):
        '''删除类操作后，若 DSH 运行中，提示刷新 DSH 界面同步列表（无需重启）。'''
        if detect_dsh_running():
            return ' · 提示: DSH 运行中，请点 DSH 标题栏"重载"或刷新网页同步列表'
        return ''

    def _delete_selected(self):
        targets, blocked = self._selected_items('session')
        if blocked:
            DarkDialog.warn(
                self.root, '当前会话受保护',
                '以下会话正在进行中，不能删除：\n\n' +
                '\n'.join('  • ' + (b.get('display_title') or b.get('title') or b['session_id'])
                          for b in blocked))
        if not targets:
            DarkDialog.info(self.root, '提示', '请先选择要删除的会话。')
            return
        names = '\n'.join('  • ' + (t.get('display_title') or infer_display_title(t))
                          for t in targets[:8])
        if len(targets) > 8:
            names += f'\n  … 还有 {len(targets) - 8} 个'
        if not DarkDialog.confirm(
                self.root, '移入回收站',
                f'将把 {len(targets)} 个会话移入回收站（可恢复）：\n\n{names}\n\n确认继续吗？',
                danger=True):
            return
        moved, removed_ws, failed = perform_delete_sessions(targets)
        self.refresh()
        self._set_status(
            f'已把 {len(moved)} 个会话移入回收站 · 自动清理 {len(removed_ws)} 个空工作区'
            + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _selected_workspaces(self):
        '''收集选中的工作区（含其全部会话），受保护工作区单独列出。'''
        targets, blocked = [], []
        for iid in self.tree.selection():
            item = self.item_data.get(iid)
            if not item or item['kind'] != 'workspace':
                continue
            ws = item['data']
            if ws.get('is_current'):
                blocked.append(ws)
            else:
                targets.append(ws)
        return targets, blocked

    def _delete_selected_workspace(self):
        targets, blocked = self._selected_workspaces()
        if blocked:
            DarkDialog.warn(
                self.root, '工作区受保护',
                '以下工作区包含当前会话，不能删除：\n\n' +
                '\n'.join('  • ' + b['name'] for b in blocked))
        if not targets:
            DarkDialog.info(self.root, '提示', '请先在左侧选择要删除的工作区。')
            return
        names = '\n'.join('  • ' + w['name'] + f'  ({w["session_count"]} 个会话)'
                          for w in targets[:8])
        if len(targets) > 8:
            names += f'\n  … 还有 {len(targets) - 8} 个'
        total = sum(w['session_count'] for w in targets)
        if not DarkDialog.confirm(
                self.root, '删除工作区',
                f'将把 {len(targets)} 个工作区（共 {total} 个会话）移入回收站。\n\n'
                f'{names}\n\n移入后工作区条目自动清理，会话可在回收站恢复。确认继续吗？',
                danger=True):
            return
        removed_ws, failed = perform_delete_workspaces(targets)
        self.refresh()
        self._set_status(
            f'已删除 {len(removed_ws)} 个工作区（会话已入回收站）' + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _purge_selected(self):
        targets, blocked = self._selected_items('trash')
        if not targets:
            DarkDialog.info(self.root, '提示', '请先在回收站视图中选择要彻底删除的条目。')
            return
        if not DarkDialog.confirm(
                self.root, '彻底删除',
                f'将彻底删除 {len(targets)} 个回收站条目，不可恢复！\n\n确认继续吗？',
                yes_text='彻底删除', danger=True):
            return
        purged, failed = purge_trash_items(targets)
        self.refresh()
        self._set_status(f'已彻底删除 {len(purged)} 个条目' + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _empty_trash(self):
        items = self.trash_items
        if not items:
            DarkDialog.info(self.root, '提示', '回收站是空的。')
            return
        if not DarkDialog.confirm(
                self.root, '清空回收站',
                f'将彻底删除回收站全部 {len(items)} 个条目，不可恢复！\n\n确认继续吗？',
                yes_text='清空', danger=True):
            return
        purged, failed = purge_trash_items(items)
        self.refresh()
        self._set_status(f'回收站已清空（{len(purged)} 条）' + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _restore_selected(self):
        targets, _ = self._selected_items('trash')
        if not targets:
            DarkDialog.info(self.root, '提示', '请先选择要恢复的回收站条目。')
            return
        restored, failed = restore_trash_items(targets)
        self.refresh()
        self._set_status(f'已恢复 {len(restored)} 个会话到原工作区' + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _archive_selected(self):
        targets, blocked = self._selected_items('session')
        if not targets:
            DarkDialog.info(self.root, '提示', '请先选择要归档 / 取消归档的会话。')
            return
        # 分别处理：已归档的取消，未归档的归档（混合选择时各自归位）
        to_archive = [t for t in targets if not t['is_archived']]
        to_unarchive = [t for t in targets if t['is_archived']]
        parts = []
        if to_archive:
            parts.append(f'归档 {len(to_archive)} 个')
        if to_unarchive:
            parts.append(f'取消归档 {len(to_unarchive)} 个')
        action_desc = '、'.join(parts)
        if not DarkDialog.confirm(
                self.root, '归档操作',
                f'将{action_desc}会话。\n\n'
                '归档会把会话从 DSH 的活跃列表隐藏（数据保留在磁盘），'
                '取消归档则恢复显示。\n确认继续吗？'):
            return
        if not self._warn_cache_action(action_desc):
            self._set_status('已取消。')
            return
        failed = False
        if to_archive:
            if not set_archived([t['session_id'] for t in to_archive], True):
                failed = True
        if to_unarchive:
            if not set_archived([t['session_id'] for t in to_unarchive], False):
                failed = True
        if failed:
            DarkDialog.warn(self.root, '失败', '写入 workspace.json 失败。')
            return
        self.refresh()
        self._set_status(f'已完成：{action_desc}')
        self._update_archive_button()

    def _delete_old(self):
        targets = [
            s for ws in self.workspaces for s in ws['sessions']
            if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
        ]
        if not targets:
            DarkDialog.info(self.root, '提示', '没有可删除的历史会话。')
            return
        if not DarkDialog.confirm(
                self.root, '删除历史会话',
                f'将把 {len(targets)} 个“超过 1 小时”的历史会话移入回收站。\n\n确认继续吗？',
                danger=True):
            return
        moved, removed_ws, failed = perform_delete_old_sessions(self.workspaces)
        self.refresh()
        self._set_status(f'已把 {len(moved)} 个历史会话移入回收站' + self._note_cache_residue())
        if failed:
            self._show_failed(failed)

    def _clean_residue(self):
        if not self._warn_cache_action('清理缓存残留'):
            self._set_status('已取消清理。')
            return
        result = perform_clean_residue()
        self.refresh()
        lines = [
            f'删除空工作区文件夹: {result["empty_workspace_dirs"]} 个',
            f'删除 projcache 孤儿记录: {result["projcache_orphans"]} 条',
            f'删除 workspace.json 孤儿工作区: {result["workspace_entries_removed"]} 条',
            f'清理失效 sessionIds: {result["workspace_session_ids_removed"]} 条',
            f'清理失效 archivedSessionIds: {result["archived_session_ids_removed"]} 条',
        ]
        ver = result.get('verification') or {}
        remaining = ver.get('remaining_orphans', 0)
        if remaining:
            lines.append('')
            lines.append(f'⚠ 复查发现仍有 {remaining} 条孤儿记录')
            if ver.get('dsh_running'):
                lines.append('（DSH 运行中会写回缓存，请先退出 DSH 再清理）')
        else:
            lines.append('')
            lines.append('✓ 复查通过：缓存与磁盘一致')
        DarkDialog.info(self.root, '清理完成', '\n'.join(lines))
        self._set_status('清理完成')

    def _show_failed(self, failed):
        lines = []
        for obj, msg in failed:
            name = (obj or {}).get('session_id') if isinstance(obj, dict) else str(obj)
            lines.append('  • ' + name + ': ' + msg)
        DarkDialog.warn(self.root, '部分操作未完成', '\n'.join(lines))


# ----------------------------------------------------------------------
# 入口 + Windows 图标 / 深色标题栏
# ----------------------------------------------------------------------
def _top_hwnd(root):
    '''获取真正的顶层窗口 HWND（Tk winfo_id 只是内部子窗口）。'''
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
    except Exception:
        return None


def _apply_window_icon(hwnd, ico_path):
    '''向顶层窗口发送 WM_SETICON（小图标=标题栏，大图标=任务栏/Alt-Tab）。'''
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        WM_SETICON = 0x0080
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        hinst = kernel32.GetModuleHandleW(None)
        for size, which in ((16, 0), (32, 1), (48, 1)):
            hicon = user32.LoadImageW(hinst, str(ico_path), IMAGE_ICON,
                                      size, size, LR_LOADFROMFILE)
            if hicon:
                user32.SendMessageW(hwnd, WM_SETICON, which, hicon)
        return True
    except Exception:
        return False


def _apply_dark_titlebar(hwnd):
    '''把窗口标题栏设为深色（Windows 10 1809+ / Windows 11）。'''
    try:
        import ctypes
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Win11/Win10 20H1+)
        # 19 = 同属性旧值 (Win10 1809-1909)
        for attr in (20, 19):
            if dwmapi.DwmSetWindowAttribute(hwnd, attr,
                                            ctypes.byref(value),
                                            ctypes.sizeof(value)) == 0:
                return True
        return False
    except Exception:
        return False


def _set_process_app_id():
    '''必须在任何窗口创建之前调用：让任务栏把 exe 图标与进程关联。'''
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                'DSH.SessionManager.WhaleGirl')
        except Exception:
            pass


def _set_windows_icons(root, ico_path, png32_path):
    '''设置 Windows 窗口图标：标题栏 + 任务栏 + Alt-Tab，并深色化标题栏。'''
    if ico_path:
        try:
            root.iconbitmap(default=ico_path)
        except Exception:
            pass
    if png32_path:
        try:
            photo = tk.PhotoImage(file=png32_path)
            root.iconphoto(True, photo)
            root._iconphoto_ref = photo
        except Exception:
            pass

    if sys.platform == 'win32' and ico_path:
        root.update_idletasks()
        hwnd = _top_hwnd(root)
        if hwnd:
            _apply_window_icon(hwnd, ico_path)
            _apply_dark_titlebar(hwnd)
            # Tk 在窗口映射时会重置图标 -> 绑定 Map 事件 + 多次延迟重设
            def _reapply(_e=None):
                h = _top_hwnd(root)
                if h:
                    _apply_window_icon(h, ico_path)
                    _apply_dark_titlebar(h)
            try:
                root.bind('<Map>', _reapply)
            except Exception:
                pass
            for delay in (300, 800, 1600, 3000):
                try:
                    root.after(delay, _reapply)
                except Exception:
                    pass


def launch_gui():
    try:
        import tkinter as tk
    except Exception:
        print('当前环境没有 tkinter，无法启动图形界面。')
        return 1
    # 关键：AppUserModelID 必须在 Tk 创建窗口之前设置
    _set_process_app_id()
    try:
        root = tk.Tk()
    except Exception as ex:
        print('无法启动图形界面（' + str(ex) + '）。')
        return 1

    ico = _asset(os.path.join('whalegirl', 'DeepSeekHarness-WhaleGirl.ico'))
    png32 = _asset(os.path.join('assets', 'logo32.png'))
    _set_windows_icons(root, ico, png32)

    try:
        app = SessionManagerApp(root)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        try:
            root.destroy()
        except Exception:
            pass
        print('图形界面初始化失败: ' + str(ex))
        return 1

    root.mainloop()
    return 0
