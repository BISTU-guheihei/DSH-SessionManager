# -*- coding: utf-8 -*-
'''DSH 会话管理工具 —— 图形界面模块。

DeepSeek 主题 GUI：
- 壁纸背景（bizhi/wallhaven 壁纸，随窗口缩放，大面积露出）
- 深蓝渐变顶栏 / 底栏，白色文字
- 鲸鱼娘圆形头像
- 圆角卡片、渐变按钮、hover 动画、点击涟漪、进度条动画、呼吸状态灯
- 会话 / 回收站双视图 + 实时搜索过滤
- 会话统计详情（可滚动）、DSH 运行状态

依赖：tkinter（必需）；Pillow（可选，有则壁纸随窗口平滑缩放）。
'''

import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

from session_core import (
    get_workspaces, list_trash_items, perform_delete_sessions,
    perform_delete_workspaces, perform_delete_old_sessions,
    perform_clean_residue, restore_trash_items, purge_trash_items,
    set_archived, detect_dsh_running, format_size, format_duration,
    format_tokens, format_age, format_mtime, decode_workspace,
    TRASH_DIR, SESSIONS_DIR, DSH_HOME, CURRENT_SESSION_ID, OLD_THRESHOLD_SECONDS,
)

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


# ----------------------------------------------------------------------
# 主题（DeepSeek 蓝）
# ----------------------------------------------------------------------
PRIMARY = '#4D6BFE'
PRIMARY_DARK = '#3B50D6'
PRIMARY_LIGHT = '#E8EEFF'
PRIMARY_GHOST = '#F3F6FF'
TOP_GRAD_A = '#2B3F9E'      # 顶栏渐变深蓝
TOP_GRAD_B = '#4D6BFE'
BOT_GRAD_A = '#22336F'
BOT_GRAD_B = '#3B50D6'
BG_FALLBACK = '#838983'
CARD = '#FFFFFF'
TEXT = '#1F2937'
TEXT_SUB = '#6B7280'
DANGER = '#EF4444'
DANGER_DARK = '#D93232'
DANGER_LIGHT = '#FEE2E2'
SUCCESS = '#22C55E'
SUCCESS_DARK = '#16A34A'
WARN = '#F59E0B'
BORDER = '#E5E7EB'

FONT_FAMILY = 'Microsoft YaHei UI'


def _font(size, bold=False):
    try:
        return tkfont.Font(family=FONT_FAMILY, size=size, weight='bold' if bold else 'normal')
    except Exception:
        return tkfont.Font(size=size, weight='bold' if bold else 'normal')


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


# ----------------------------------------------------------------------
# 颜色工具
# ----------------------------------------------------------------------
def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(c):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(x))) for x in c)


def _lerp(c1, c2, t):
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def draw_vertical_gradient(canvas, x1, y1, x2, y2, top, bottom, tag):
    '''在 canvas 区域画垂直渐变矩形。'''
    canvas.delete(tag)
    steps = 60
    t1 = _hex_to_rgb(top)
    b1 = _hex_to_rgb(bottom)
    h = y2 - y1
    for i in range(steps):
        t = i / (steps - 1)
        color = _rgb_to_hex(_lerp(t1, b1, t))
        canvas.create_rectangle(x1, y1 + i * h / steps, x2, y1 + (i + 1) * h / steps + 1,
                                fill=color, outline='', tags=tag)


# ----------------------------------------------------------------------
# 圆角按钮（hover 渐变 + 点击涟漪）
# ----------------------------------------------------------------------
class HoverButton(tk.Canvas):
    def __init__(self, master, text, command=None, *, color=PRIMARY, text_color='#FFFFFF',
                 width=150, height=42, radius=12, font_size=11, bold=False,
                 danger=False, ghost=False, disabled=False, bg_color=None):
        self._bw = width
        self._bh = height
        self._br = radius
        self._base = DANGER if danger else ((bg_color or CARD) if ghost else color)
        self._hover = DANGER_DARK if danger else (PRIMARY_GHOST if ghost else PRIMARY_DARK)
        self._press = DANGER_DARK if danger else (PRIMARY if ghost else '#3347B8')
        self._fg = DANGER if danger else (PRIMARY if ghost else text_color)
        self._command = command
        self._disabled = disabled
        self._text = text
        self._ripples = []
        self._anim = None
        self._t = 0.0
        self._bg_color = bg_color
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0,
                         bg=bg_color if bg_color else master['bg'],
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

    def _current_color(self):
        return _rgb_to_hex(_lerp(_hex_to_rgb(self._base), _hex_to_rgb(self._hover), self._t))

    def _draw(self):
        self.delete('all')
        w, h, r = self._bw, self._bh, self._br
        fill = self._current_color() if not self._disabled else '#D1D5DB'
        self._round_rect(0, 0, w, h, r, fill=fill, outline='')
        fg = self._fg if not self._disabled else '#9CA3AF'
        self.create_text(w / 2, h / 2 + 1, text=self._text, fill=fg,
                         font=self._font)
        for x, y, rad, alpha in self._ripples:
            color = _rgb_to_hex(_lerp(_hex_to_rgb(fill), _hex_to_rgb('#FFFFFF'), 0.5))
            self.create_oval(x - rad, y - rad, x + rad, y + rad,
                             outline=color, width=2)

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
            if abs(delta) < 0.04:
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
        self._animate_to(0.0)

    def _on_press(self, e):
        self._t = 1.0
        self._draw()
        x, y = e.x, e.y

        def ripple(rad=6, alpha=0.6):
            if rad > max(self._bw, self._bh):
                self._ripples = [r for r in self._ripples if r[2] < rad - 10]
                self._draw()
                return
            self._ripples.append((x, y, rad, alpha))
            if len(self._ripples) > 4:
                self._ripples.pop(0)
            self._draw()
            self.after(16, ripple, rad + 7, alpha * 0.88)
        ripple()

    def _on_release(self, e):
        if self._command:
            self._command()


# ----------------------------------------------------------------------
# 状态灯（呼吸动画）
# ----------------------------------------------------------------------
class StatusDot(tk.Canvas):
    def __init__(self, master, size=14, bg_color=None):
        super().__init__(master, width=size + 8, height=size + 8,
                         highlightthickness=0, bd=0,
                         bg=bg_color if bg_color else master['bg'])
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
        cx, cy = (s + 8) / 2, (s + 8) / 2
        self._phase = (self._phase + 0.12) % 6.28
        if self._running:
            halo = 3 + abs(self._phase) * 0.6
            self.create_oval(cx - halo - s / 2, cy - halo - s / 2,
                             cx + halo + s / 2, cy + halo + s / 2,
                             fill=SUCCESS, outline='', stipple='gray50')
        else:
            color = '#C9CEE0'
        self.create_oval(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2,
                         fill=SUCCESS if self._running else color, outline='')
        self.after(120, self._tick)


# ----------------------------------------------------------------------
# 上下文压力进度条（动画填充）
# ----------------------------------------------------------------------
class PressureBar(tk.Canvas):
    def __init__(self, master, width=240, height=12, bg_color=CARD):
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
        self.create_oval(0, 0, h, h, fill='#EDF0F7', outline='')
        self.create_oval(w - h, 0, w, h, fill='#EDF0F7', outline='')
        self.create_rectangle(h / 2, 0, w - h / 2, h, fill='#EDF0F7', outline='')
        fw = w * self._cur
        if fw > 2:
            if self._cur < 0.6:
                c1, c2 = PRIMARY, '#6E8BFF'
            elif self._cur < 0.85:
                c1, c2 = '#6E8BFF', WARN
            else:
                c1, c2 = WARN, DANGER
            if fw < h:
                self.create_oval(0, 0, h, h, fill=c1, outline='')
            else:
                self.create_oval(0, 0, h, h, fill=c1, outline='')
                self.create_rectangle(h / 2, 0, fw, h, fill=c1, outline='')
                for i in range(20):
                    t = i / 20
                    x0 = fw - (h / 2) * t * 0.8
                    col = _rgb_to_hex(_lerp(_hex_to_rgb(c1), _hex_to_rgb(c2), t * 0.6))
                    self.create_oval(x0 - h / 2, 0, x0 + h / 2, h, fill=col, outline='')
                self.create_oval(fw - h, 0, fw, h, fill=c2, outline='')


# ----------------------------------------------------------------------
# 主应用
# ----------------------------------------------------------------------
class SessionManagerApp:
    TOP_H = 104                # 顶栏高度
    BOT_H = 40                 # 底栏高度
    CARD_MARGIN = 16           # 卡片与窗口边缘的壁纸留白

    def __init__(self, root):
        self.root = root
        self.root.title('DSH 会话管理器 · 鲸鱼娘')
        self.root.geometry('1280x820')
        self.root.minsize(1080, 700)
        self.root.configure(bg=BG_FALLBACK)

        self.workspaces = []
        self.item_data = {}
        self.view = 'sessions'
        self.search_text = ''
        self.trash_items = []
        self._search_job = None
        self._resize_job = None
        self._wallpaper_ref = None
        self._images = []
        self._hover_tags = {}
        self._logo_img = None

        self._build_ui()
        self._load_wallpaper()
        self.root.bind('<Configure>', self._on_resize)
        self.refresh()
        self._refresh_dsh_status()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # 背景画布（壁纸铺满）
        self.bg = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        draw_vertical_gradient(self.bg, 0, 0, 1280, 820, '#9FB4D8', '#E8EDF5', 'gradient')

        # 顶栏渐变（放在壁纸上层，保证标题可读）
        self.top_bar = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.top_bar.place(x=0, y=0, relwidth=1, height=self.TOP_H)
        draw_vertical_gradient(self.top_bar, 0, 0, 1280, self.TOP_H, TOP_GRAD_A, TOP_GRAD_B, 'topgrad')

        # 底栏渐变
        self.bottom_bar = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.bottom_bar.place(x=0, rely=1.0, relwidth=1, height=self.BOT_H, anchor='sw')
        draw_vertical_gradient(self.bottom_bar, 0, 0, 1280, self.BOT_H, BOT_GRAD_A, BOT_GRAD_B, 'botgrad')

        # 鲸鱼娘圆形头像（顶栏左）
        logo_file = _asset(os.path.join('assets', 'logo_circle.png'))
        if logo_file:
            try:
                logo_img = tk.PhotoImage(file=logo_file)
                self._images.append(logo_img)
                self.bg.create_image(44, self.TOP_H / 2, image=logo_img)
            except Exception:
                pass

        # 标题（顶栏）
        self.top_bar.create_text(96, 24, anchor='w', text='DSH 会话管理器',
                                 font=_font(17, bold=True), fill='#FFFFFF')
        self.top_bar.create_text(97, 48, anchor='w',
                                 text='鲸鱼娘守护的会话回收站 · DeepSeek Harness',
                                 font=_font(9), fill='#CBD5FF')
        self.top_bar.create_text(97, 66, anchor='w',
                                 text='删除先进回收站可恢复 · DSH 运行中清理缓存会被写回',
                                 font=_font(8), fill='#9FB0E8')

        # 搜索框（顶栏右侧，白色圆角）
        self.search_canvas = tk.Canvas(self.top_bar, width=280, height=38,
                                       highlightthickness=0, bd=0, bg=PRIMARY)
        self.search_canvas.place(relx=1.0, x=-480, y=33)
        self._round_rect(self.search_canvas, 0, 0, 280, 38, 12, fill='#FFFFFF', outline='')
        self.search_canvas.create_text(30, 19, text='🔍', font=_font(12), tags='icon')
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.top_bar, textvariable=self.search_var,
                                     font=_font(11), bd=0, relief='flat',
                                     bg='#FFFFFF', fg=TEXT, insertbackground=PRIMARY)
        self.search_entry.place(relx=1.0, x=-456, y=42, width=236, height=20, anchor='w')
        self.search_var.trace_add('write', self._on_search_change)

        # 视图切换按钮
        self.btn_view_sessions = HoverButton(self.top_bar, '会话', self._show_sessions_view,
                                             width=88, height=34, radius=10,
                                             bg_color=PRIMARY)
        self.btn_view_sessions.place(relx=1.0, x=-188, y=35)
        self.btn_view_trash = HoverButton(self.top_bar, '回收站', self._show_trash_view,
                                          width=88, height=34, radius=10, ghost=True,
                                          bg_color=PRIMARY)
        self.btn_view_trash.place(relx=1.0, x=-94, y=35)

        # 左侧：会话树卡片（白卡浮于壁纸，四周留白露出壁纸）
        self.left_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                                  highlightbackground=BORDER)
        self.left_card.place(relx=0.014, y=self.TOP_H + 12, relwidth=0.595)

        self.tree_header = tk.Frame(self.left_card, bg=PRIMARY_GHOST)
        self.tree_header.pack(fill='x')
        self.view_title_var = tk.StringVar(value='会话列表')
        tk.Label(self.tree_header, textvariable=self.view_title_var, font=_font(11, bold=True),
                 bg=PRIMARY_GHOST, fg=PRIMARY).pack(side='left', padx=14, pady=7)
        self.count_var = tk.StringVar(value='')
        tk.Label(self.tree_header, textvariable=self.count_var, font=_font(9),
                 bg=PRIMARY_GHOST, fg=TEXT_SUB).pack(side='right', padx=14)

        tree_frame = tk.Frame(self.left_card, bg=CARD)
        tree_frame.pack(fill='both', expand=True, padx=6, pady=6)

        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self.style.configure('Whale.Treeview', background=CARD, fieldbackground=CARD,
                             foreground=TEXT, borderwidth=0, rowheight=34,
                             font=(FONT_FAMILY, 10))
        self.style.configure('Whale.Treeview.Heading', background=PRIMARY_GHOST,
                             foreground=PRIMARY, font=(FONT_FAMILY, 9, 'bold'),
                             borderwidth=0, relief='flat', padding=6)
        self.style.map('Whale.Treeview',
                       background=[('selected', PRIMARY_LIGHT)],
                       foreground=[('selected', PRIMARY_DARK)])
        self.style.map('Whale.Treeview.Heading', background=[('active', PRIMARY_LIGHT)])

        columns = ('size', 'mtime', 'note')
        self.tree = ttk.Treeview(tree_frame, columns=columns, style='Whale.Treeview',
                                 selectmode='extended', show='tree headings')
        self.tree.heading('#0', text='名称 / 会话')
        self.tree.heading('size', text='大小')
        self.tree.heading('mtime', text='最后修改')
        self.tree.heading('note', text='备注')
        self.tree.column('#0', width=380, minwidth=240, stretch=True)
        self.tree.column('size', width=90, minwidth=70, anchor='e', stretch=False)
        self.tree.column('mtime', width=150, minwidth=110, anchor='center', stretch=False)
        self.tree.column('note', width=140, minwidth=90, anchor='w', stretch=False)
        self.tree.tag_configure('workspace', font=(FONT_FAMILY, 11, 'bold'),
                                foreground='#374151', background=CARD)
        self.tree.tag_configure('session', foreground=TEXT, background=CARD)
        self.tree.tag_configure('current', foreground=PRIMARY, background=PRIMARY_LIGHT,
                                font=(FONT_FAMILY, 10, 'bold'))
        self.tree.tag_configure('archived', foreground='#9CA3AF', background=CARD)
        self.tree.tag_configure('trash_item', foreground=TEXT, background=CARD)
        self.tree.tag_configure('hover', background='#EEF2FF')

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
        self.right_card.place(relx=0.63, y=self.TOP_H + 12, relwidth=0.356)

        self.detail_header = tk.Label(self.right_card, text='会话详情',
                                      font=_font(12, bold=True), bg=CARD, fg=TEXT,
                                      anchor='w')
        self.detail_header.pack(fill='x', padx=16, pady=(12, 4))

        # 详情内容（外层 frame：canvas + 滚动条）
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

        # 右侧按钮组
        self.btn_panel = tk.Frame(self.right_card, bg=CARD)
        self.btn_panel.pack(side='bottom', fill='x', padx=16, pady=(6, 14))

        row1 = tk.Frame(self.btn_panel, bg=CARD)
        row1.pack(fill='x', pady=3)
        self.btn_refresh = HoverButton(row1, '刷新', self.refresh, ghost=True, width=110)
        self.btn_refresh.pack(side='left', padx=(0, 8))
        self.btn_archive = HoverButton(row1, '归档选中', self._archive_selected,
                                       ghost=True, width=110)
        self.btn_archive.pack(side='left', padx=(0, 8))
        self.btn_restore = HoverButton(row1, '恢复选中', self._restore_selected,
                                       width=110)
        self.btn_restore.pack(side='left')

        row2 = tk.Frame(self.btn_panel, bg=CARD)
        row2.pack(fill='x', pady=3)
        self.btn_delete = HoverButton(row2, '删除选中 → 回收站', self._delete_selected,
                                      danger=True, width=164)
        self.btn_delete.pack(side='left', padx=(0, 8))
        self.btn_purge = HoverButton(row2, '彻底删除', self._purge_selected,
                                     danger=True, width=110, ghost=True)
        self.btn_purge.pack(side='left')

        row3 = tk.Frame(self.btn_panel, bg=CARD)
        row3.pack(fill='x', pady=3)
        self.btn_delold = HoverButton(row3, '删除历史会话', self._delete_old,
                                      ghost=True, width=164)
        self.btn_delold.pack(side='left', padx=(0, 8))
        self.btn_clean = HoverButton(row3, '清理缓存残留', self._clean_residue,
                                     width=110)
        self.btn_clean.pack(side='left')

        self.btn_empty_trash = HoverButton(row3, '清空回收站', self._empty_trash,
                                           danger=True, width=274)
        self.btn_empty_trash.pack_forget()

        # 底栏：状态文字 + 状态灯
        self.status_var = tk.StringVar(value='正在加载...')
        self.bottom_status = tk.Label(self.bottom_bar, textvariable=self.status_var,
                                      font=_font(9), fg='#FFFFFF', bg=BOT_GRAD_A)
        self.bottom_status.place(x=14, y=self.BOT_H / 2, anchor='w')
        self.dot = StatusDot(self.bottom_bar, bg_color=BOT_GRAD_A)
        self.dot.place(relx=1.0, x=-120, y=self.BOT_H / 2 - 11)
        self.dsh_label = tk.Label(self.bottom_bar, text='DSH 状态', font=_font(9),
                                  fg='#FFFFFF', bg=BOT_GRAD_A)
        self.dsh_label.place(relx=1.0, x=-104, y=self.BOT_H / 2, anchor='w')

        self._sync_view_buttons()

    def _round_rect(self, canvas, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        canvas.create_polygon(pts, smooth=True, **kw)

    # ------------------------------------------------------------------
    # 壁纸
    # ------------------------------------------------------------------
    def _load_wallpaper(self):
        wp = _asset(os.path.join('assets', 'wallpaper.png'))
        if not wp:
            return
        if _HAS_PIL:
            self._wallpaper_src = Image.open(wp).convert('RGB')
            self._render_wallpaper()
        else:
            try:
                img = tk.PhotoImage(file=wp)
                self._wallpaper_ref = img
                self.bg.delete('wallpaper')
                self.bg.create_image(0, 0, image=img, anchor='nw', tags='wallpaper')
            except Exception:
                pass

    def _render_wallpaper(self):
        if not (_HAS_PIL and hasattr(self, '_wallpaper_src')):
            return
        w = max(self.root.winfo_width(), 200)
        h = max(self.root.winfo_height(), 200)
        src = self._wallpaper_src
        sw, sh = src.size
        scale = max(w / sw, h / sh)
        nw, nh = int(sw * scale), int(sh * scale)
        img = src.resize((nw, nh), Image.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        img = img.crop((left, top, left + w, top + h))
        photo = ImageTk.PhotoImage(img)
        self._wallpaper_ref = photo
        self.bg.delete('wallpaper')
        self.bg.create_image(0, 0, image=photo, anchor='nw', tags='wallpaper')
        self.bg.tag_lower('wallpaper')
        self.bg.tag_lower('gradient')

    def _on_resize(self, e):
        if e.widget is not self.root:
            return
        h = self.root.winfo_height()
        card_top = self.TOP_H + 10
        card_bottom = h - self.BOT_H - 10
        card_h = max(card_bottom - card_top, 300)
        self.left_card.place(y=card_top, height=card_h)
        self.right_card.place(y=card_top, height=card_h)
        # 顶/底栏渐变重绘
        w = self.root.winfo_width()
        draw_vertical_gradient(self.top_bar, 0, 0, w, self.TOP_H, TOP_GRAD_A, TOP_GRAD_B, 'topgrad')
        draw_vertical_gradient(self.bottom_bar, 0, 0, w, self.BOT_H, BOT_GRAD_A, BOT_GRAD_B, 'botgrad')
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(250, self._render_wallpaper)

    # ------------------------------------------------------------------
    # DSH 状态灯
    # ------------------------------------------------------------------
    def _refresh_dsh_status(self):
        running = detect_dsh_running()
        self.dot.set_running(running)
        self.dsh_label.configure(
            text='DSH 运行中 · 缓存将被写回' if running else 'DSH 未运行 · 可安全清理',
            fg='#A7F3D0' if running else '#FFFFFF')
        self.root.after(8000, self._refresh_dsh_status)

    # ------------------------------------------------------------------
    # 视图与刷新
    # ------------------------------------------------------------------
    def _sync_view_buttons(self):
        if self.view == 'sessions':
            self.btn_view_sessions._base = PRIMARY_DARK
            self.btn_view_sessions._fg = '#FFFFFF'
            self.btn_view_sessions._t = 0.0
            self.btn_view_sessions._draw()
            self.btn_view_trash._base = PRIMARY
            self.btn_view_trash._fg = '#FFFFFF'
            self.btn_view_trash._t = 0.0
            self.btn_view_trash._draw()
            self.view_title_var.set('会话列表')
            self.btn_restore.pack_forget()
            self.btn_purge.pack_forget()
            self.btn_empty_trash.pack_forget()
            self.btn_archive.pack(side='left', padx=(0, 8))
            self.btn_delete.pack(side='left', padx=(0, 8))
            self.btn_delold.pack(side='left', padx=(0, 8))
            self.btn_clean.pack(side='left')
        else:
            self.btn_view_trash._base = PRIMARY_DARK
            self.btn_view_trash._fg = '#FFFFFF'
            self.btn_view_trash._t = 0.0
            self.btn_view_trash._draw()
            self.btn_view_sessions._base = PRIMARY
            self.btn_view_sessions._fg = '#FFFFFF'
            self.btn_view_sessions._t = 0.0
            self.btn_view_sessions._draw()
            self.view_title_var.set('回收站')
            self.btn_archive.pack_forget()
            self.btn_delete.pack_forget()
            self.btn_delold.pack_forget()
            self.btn_clean.pack_forget()
            self.btn_restore.pack(side='left', padx=(0, 8))
            self.btn_purge.pack(side='left')
            self.btn_empty_trash.pack(side='left')

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

    def refresh(self):
        if self.view == 'sessions':
            self.workspaces = get_workspaces()
            self._populate_sessions()
        else:
            self.trash_items = list_trash_items()
            self._populate_trash()

    # ------------------------------------------------------------------
    # 树填充（会话视图）
    # ------------------------------------------------------------------
    def _matches(self, text):
        kw = self.search_text.lower()
        return kw in text.lower()

    def _populate_sessions(self):
        self.tree.delete(*self.tree.get_children())
        self.item_data.clear()
        total = 0
        for ws in self.workspaces:
            shown = []
            for s in ws['sessions']:
                title = s.get('title') or ''
                if self.search_text and not (
                        self._matches(title) or self._matches(s['session_id'])
                        or self._matches(ws['name'])):
                    continue
                shown.append(s)
            if not shown and self.search_text:
                if not self._matches(ws['name']):
                    continue
            total += len(shown)
            ws_iid = self.tree.insert(
                '', 'end', text=f'▸ {ws["name"]}',
                values=('', '', '工作区'),
                tags=('workspace',), open=True)
            self.item_data[ws_iid] = {'kind': 'workspace', 'data': ws}
            for s in shown:
                title = s.get('title') or '(无标题)'
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
        self.count_var.set(f'共 {total} 个会话')
        self.status_var.set(
            f'工作区 {len(self.workspaces)} 个 · 会话 {total} 个 · '
            f'数据目录 {DSH_HOME}')
        if self.tree.selection():
            self._on_select(None)

    def _populate_trash(self):
        self.tree.delete(*self.tree.get_children())
        self.item_data.clear()
        shown = 0
        for it in self.trash_items:
            title = it.get('title') or '(无标题)'
            if self.search_text and not (
                    self._matches(title) or self._matches(it['session_id'])
                    or self._matches(it.get('workspace_name') or '')):
                continue
            shown += 1
            iid = self.tree.insert(
                '', 'end', text='  ' + title,
                values=(format_size(it['size']),
                        it.get('deleted_at', ''),
                        f'@ {it.get("workspace_name") or "?"}'),
                tags=('trash_item',))
            self.item_data[iid] = {'kind': 'trash', 'data': it}
        self.count_var.set(f'回收站 {shown} 条')
        total_size = sum(it['size'] for it in self.trash_items)
        self.status_var.set(f'回收站共 {len(self.trash_items)} 条 · 占用 {format_size(total_size)} · {TRASH_DIR}')
        if self.tree.selection():
            self._on_select(None)

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    def _on_search_change(self, *_):
        if self._search_job:
            self.root.after_cancel(self._search_job)
        self._search_job = self.root.after(250, self._apply_search)

    def _apply_search(self):
        self.search_text = self.search_var.get().strip()
        self.refresh()

    # ------------------------------------------------------------------
    # 树 hover 高亮
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
        selection = self.tree.selection()
        if len(selection) == 1:
            item = self.item_data.get(selection[0])
            if item and item['kind'] in ('session', 'trash'):
                self._show_detail(item['data'], item['kind'])
                return
        self._show_detail(None, None)

    def _show_detail(self, data, kind):
        self._detail_state = (data, kind)
        self._redraw_detail()

    def _redraw_detail(self):
        # 清空旧内容（含滚动窗口）
        for w in self._detail_views:
            try:
                w.destroy()
            except Exception:
                pass
        self._detail_views.clear()
        self.detail.delete('all')
        data, kind = self._detail_state or (None, None)

        w = max(self.detail.winfo_width(), 240)
        pad = 6
        y = 4

        if data is None:
            # 空状态：鲸鱼娘欢迎
            logo_file = _asset(os.path.join('assets', 'logo.png'))
            if logo_file:
                try:
                    img = tk.PhotoImage(file=logo_file)
                    self._images.append(img)
                    self.detail.create_image(w / 2, 110, image=img)
                    y = 190
                except Exception:
                    y = 60
            self.detail.create_text(w / 2, y, text='选一个会话看看吧',
                                    font=_font(11, bold=True), fill=TEXT_SUB)
            self.detail.create_text(w / 2, y + 24,
                                    text='这里会显示会话的统计信息\n（轮数、耗时、Token 用量、上下文压力）',
                                    font=_font(9), fill='#9CA3AF', justify='center')
            self.detail.configure(scrollregion=(0, 0, w, max(self.detail.winfo_height(), 200)))
            return

        # 内容装进一个内嵌 Canvas 以支持滚动
        inner = tk.Canvas(self.detail, bg=CARD, highlightthickness=0, bd=0)
        self.detail.create_window(0, 0, window=inner, anchor='nw')
        self._detail_views.append(inner)

        if kind == 'session':
            content_h = self._draw_session_detail(inner, data, w, pad, y)
        else:
            content_h = self._draw_trash_detail(inner, data, w, pad, y)
        inner.configure(width=max(w - 2, 10), height=max(content_h + 10, 10))
        self.detail.configure(scrollregion=(0, 0, w, content_h + 10))
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
        title = s.get('title') or '（无标题）'
        canvas.create_text(pad + 4, y, text=title, font=_font(13, bold=True),
                           fill=TEXT, anchor='w', width=w - 2 * pad - 24)
        y += 34
        badges = []
        if s['is_current']:
            badges.append(('🛡 当前会话', PRIMARY, PRIMARY_LIGHT))
        if s['is_archived']:
            badges.append(('🗂 已归档', '#9CA3AF', '#F3F4F6'))
        if not badges:
            badges.append(('会话', TEXT_SUB, PRIMARY_GHOST))
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
                y += 18
                bar_w = w - 2 * pad - 24
                bar = PressureBar(canvas, width=bar_w, height=12)
                canvas.create_window(pad + 4, y, window=bar, anchor='nw')
                bar.set_value(ratio)
                self._detail_views.append(bar)
                y += 22
        else:
            y += 6
            canvas.create_text(pad + 4, y, text='暂无统计缓存（新会话或 DSH 未记录）',
                               font=_font(9), fill='#9CA3AF', anchor='w')
            y += 22
        return y

    def _draw_trash_detail(self, canvas, it, w, pad, y):
        title = it.get('title') or '（无标题）'
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
    def _warn_dsh_running(self, action_name):
        if not detect_dsh_running():
            return True
        return messagebox.askyesno(
            'DSH 正在运行',
            f'检测到 DSH Desktop 正在运行。\n\n{action_name} 对缓存的修改可能被 DSH 写回覆盖'
            f'（会话文件本身不受影响）。\n\n建议先完全退出 DSH 再操作。\n\n仍要继续吗？',
            icon='warning', parent=self.root)

    def _delete_selected(self):
        targets, blocked = self._selected_items('session')
        if blocked:
            messagebox.showwarning(
                '当前会话受保护',
                '以下会话正在进行中，不能删除：\n\n' +
                '\n'.join('  • ' + (b.get('title') or b['session_id']) for b in blocked),
                parent=self.root)
        if not targets:
            messagebox.showinfo('提示', '请先选择要删除的会话。', parent=self.root)
            return
        names = '\n'.join('  • ' + (t.get('title') or '(无标题)') for t in targets[:8])
        if len(targets) > 8:
            names += f'\n  … 还有 {len(targets) - 8} 个'
        if not messagebox.askyesno(
                '移入回收站',
                f'将把 {len(targets)} 个会话移入回收站（可恢复）：\n\n{names}\n\n'
                '确认继续吗？', icon='question', parent=self.root):
            return
        self._warn_dsh_running('删除会话')
        moved, removed_ws, failed = perform_delete_sessions(targets)
        self.refresh()
        self.status_var.set(
            f'已把 {len(moved)} 个会话移入回收站 · 自动清理 {len(removed_ws)} 个空工作区')
        if failed:
            self._show_failed(failed)

    def _purge_selected(self):
        targets, blocked = self._selected_items('trash')
        if not targets:
            messagebox.showinfo('提示', '请先在回收站视图中选择要彻底删除的条目。', parent=self.root)
            return
        if not messagebox.askyesno(
                '彻底删除',
                f'将彻底删除 {len(targets)} 个回收站条目，不可恢复！\n\n确认继续吗？',
                icon='warning', parent=self.root):
            return
        purged, failed = purge_trash_items(targets)
        self.refresh()
        self.status_var.set(f'已彻底删除 {len(purged)} 个条目')
        if failed:
            self._show_failed(failed)

    def _empty_trash(self):
        items = self.trash_items
        if not items:
            messagebox.showinfo('提示', '回收站是空的。', parent=self.root)
            return
        if not messagebox.askyesno(
                '清空回收站',
                f'将彻底删除回收站全部 {len(items)} 个条目，不可恢复！\n\n确认继续吗？',
                icon='warning', parent=self.root):
            return
        purged, failed = purge_trash_items(items)
        self.refresh()
        self.status_var.set(f'回收站已清空（{len(purged)} 条）')
        if failed:
            self._show_failed(failed)

    def _restore_selected(self):
        targets, _ = self._selected_items('trash')
        if not targets:
            messagebox.showinfo('提示', '请先选择要恢复的回收站条目。', parent=self.root)
            return
        restored, failed = restore_trash_items(targets)
        self.refresh()
        self.status_var.set(f'已恢复 {len(restored)} 个会话到原工作区')
        if failed:
            self._show_failed(failed)

    def _archive_selected(self):
        targets, blocked = self._selected_items('session')
        if not targets:
            messagebox.showinfo('提示', '请先选择要归档 / 取消归档的会话。', parent=self.root)
            return
        has_archived = any(t['is_archived'] for t in targets)
        action = '取消归档' if has_archived else '归档'
        if not messagebox.askyesno(
                action,
                f'将{action} {len(targets)} 个会话。\n\n'
                '归档会把会话从 DSH 的活跃列表隐藏（数据保留在磁盘）。\n确认继续吗？',
                icon='question', parent=self.root):
            return
        self._warn_dsh_running(action)
        ids = [t['session_id'] for t in targets]
        if set_archived(ids, not has_archived):
            self.refresh()
            self.status_var.set(f'已{action} {len(ids)} 个会话')
        else:
            messagebox.showerror('失败', '写入 workspace.json 失败。', parent=self.root)

    def _delete_old(self):
        targets = [
            s for ws in self.workspaces for s in ws['sessions']
            if not s['is_current'] and s['age'] > OLD_THRESHOLD_SECONDS
        ]
        if not targets:
            messagebox.showinfo('提示', '没有可删除的历史会话。', parent=self.root)
            return
        if not messagebox.askyesno(
                '删除历史会话',
                f'将把 {len(targets)} 个“超过 1 小时”的历史会话移入回收站。\n\n确认继续吗？',
                icon='question', parent=self.root):
            return
        self._warn_dsh_running('删除历史会话')
        moved, removed_ws, failed = perform_delete_old_sessions(self.workspaces)
        self.refresh()
        self.status_var.set(f'已把 {len(moved)} 个历史会话移入回收站')
        if failed:
            self._show_failed(failed)

    def _clean_residue(self):
        if not self._warn_dsh_running('清理缓存残留'):
            self.status_var.set('已取消清理。')
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
        messagebox.showinfo('清理完成', '\n'.join(lines), parent=self.root)
        self.status_var.set('清理完成')

    def _show_failed(self, failed):
        lines = []
        for obj, msg in failed:
            name = (obj or {}).get('session_id') if isinstance(obj, dict) else str(obj)
            lines.append('  • ' + name + ': ' + msg)
        messagebox.showwarning('部分操作未完成', '\n'.join(lines), parent=self.root)


# ----------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------
def launch_gui():
    try:
        import tkinter as tk
    except Exception:
        print('当前环境没有 tkinter，无法启动图形界面。')
        return 1
    try:
        root = tk.Tk()
    except Exception as ex:
        print('无法启动图形界面（' + str(ex) + '）。')
        return 1

    ico = _asset(os.path.join('whalegirl', 'DeepSeekHarness-WhaleGirl.ico'))
    if ico:
        try:
            root.iconbitmap(ico)
        except Exception:
            pass
    png = _asset(os.path.join('assets', 'logo.png'))
    if png:
        try:
            photo = tk.PhotoImage(file=png)
            root.iconphoto(True, photo)
            root._iconphoto_ref = photo
        except Exception:
            pass

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
