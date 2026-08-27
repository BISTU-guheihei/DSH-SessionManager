# DSH 会话管理器 · 鲸鱼娘 🐋

DeepSeek Harness (DSH) 的会话管理工具：可视化 / 命令行查看、**回收站删除（可恢复）**、**归档/恢复**、搜索过滤、缓存清理，并带一个 **DeepSeek 鲸鱼娘主题** 的精美深色图形界面。

聊天记录实际存储在 `~/.dsh/sessions/`（工作区文件夹 → 会话文件夹 → `session.jsonl.zstd`），
索引在 `~/.dsh/storages/workspace.json`（含 `archivedSessionIds` 归档标记），
统计缓存在 `~/.dsh/storages/session_projcache.json`。
本工具删除会话时**同步清理这些缓存，不留残留**。

## 📣 社区

- [DSH 官方讨论帖](https://github.com/deepseek-ai/deepseek-harness/discussions/4716) —— 欢迎留言反馈、提出功能建议 🐋

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🗑 回收站 | 删除先进回收站（`~/.dsh/.trash/`），可随时恢复；彻底删除才释放空间 |
| 🗂 归档 / 恢复 | 复用 DSH 的 `archivedSessionIds` 机制，把会话从活跃列表隐藏 / 恢复（按钮文字随选中状态自动切换） |
| 📊 统计详情 | 显示轮数、步骤、LLM/工具耗时、Token 用量、上下文压力（动画进度条） |
| 🔍 搜索过滤 | 命令行 `search` 按标题 / 会话 ID / 工作区名搜索 |
| 🔄 实时监视 | GUI 每 3 秒自动静默刷新（保留选择），新会话出现 / 删除消失自动反映；孤儿缓存实时计数 |
| 🛡 安全保护 | 当前会话永不删除；删除前确认；当前会话 / 工作区高亮与选中区分 |
| ✓ 清理校验 | `clean` 后自动复查，报告是否仍有残留（例如被运行中的 DSH 写回） |
| 🎨 鲸鱼娘主题 | 深色护眼配色（黑灰底 + DeepSeek 蓝点缀）、圆形头像、渐变按钮（投影/上浮/按压）、深色对话框 |
| 🌍 跨平台 | Windows / macOS / Linux 均可源码运行；`build-exe` 支持三平台打包 |

## 📥 下载与安装

### Windows（直接下载 exe）

从 **GitHub Releases** 下载 `DSH_SessionManager-windows.zip`（单文件 exe，无需安装 Python）：

- 双击打开图形界面（无黑色终端窗口）；
- 或在命令行中执行（`list / delete / trash / restore / clean` 等全部可用）；
- exe 已内嵌鲸鱼娘图标与全部资源，可单独复制到任何 Windows 电脑使用。

### Linux（直接下载二进制）

从 **GitHub Releases** 下载 `DSH_SessionManager-linux.zip`（ELF 可执行文件，由 GitHub Actions 在 Ubuntu 上自动构建）：

```bash
unzip DSH_SessionManager-linux.zip
chmod +x DSH_SessionManager
./DSH_SessionManager            # 打开图形界面
./DSH_SessionManager list       # 命令行查看
```

> 注意：GUI 需要 tkinter，若缺少请先安装：`sudo apt install python3-tk`（命令行功能不受影响）。

### macOS / 其他平台（使用源码 + 构建脚本）

> 说明：PyInstaller **不支持交叉编译**，目前 Release 提供 Windows 与 Linux 预编译产物；macOS 版本请在对应系统上自行构建。

```bash
# 1. 克隆仓库
git clone https://github.com/BISTU-guheihei/DSH-SessionManager.git
cd DSH-SessionManager

# 2. 源码直接运行（需 Python 3.8+ 与 tkinter）
python3 manage_sessions.py           # 打开图形界面
python3 manage_sessions.py list      # 命令行查看

# 3. 生成独立可执行文件（可选）
python3 manage_sessions.py build-exe # 自动创建 .venv 并打包
```

- 构建产物：Windows → `dist\DSH_SessionManager.exe`；Linux → `dist/DSH_SessionManager`（ELF）；macOS → `dist/DSH_SessionManager`（.icns 图标二进制）；
- 也提供了 [GitHub Actions 工作流](.github/workflows/build.yml)，推送 `v*` 标签即可在云端自动产出 Windows exe 与 Linux 二进制（可作为替代打包方式）。

## 环境要求

- **Python 3.8+**（推荐 3.10+；GUI 仅需标准库 tkinter）；
- Linux 需 `sudo apt install python3-tk`（macOS 自带）；
- 支持环境变量 `DSH_HOME` 覆盖数据目录、`DSH_SESSION_ID` 指定受保护会话；
- 工具读取**本机当前用户的 DSH 数据**，换机器 / 换用户自动指向各自的 `~/.dsh`。

## 图形界面

```bash
python manage_sessions.py          # 无参数时默认打开图形界面
python manage_sessions.py gui      # 同上
```

界面包含：

- 顶部：鲸鱼娘圆形头像、标题、**会话 / 回收站视图切换**；
- 左侧：工作区 → 会话树（当前会话 🛡 受保护、已归档 🗂 置灰标记）；
- 右侧：选中会话的**统计详情**（轮数 / 步骤 / 耗时 / Token / 上下文压力条，可滚动）+ 操作按钮（删除 / 归档 / 恢复 / 清理）；
- 底部：状态栏 + **DSH 运行状态呼吸灯**（运行中 = 绿色）+ 孤儿缓存实时计数。

## 命令行

```bash
python manage_sessions.py list           # 按工作区分组列出所有会话（含统计）
python manage_sessions.py search 关键词   # 按标题 / ID / 工作区搜索
python manage_sessions.py delete 1 3     # 把编号 1、3 的会话移入回收站（可恢复）
python manage_sessions.py delete-old     # 移入回收站所有“非当前”且超 1 小时的历史会话
python manage_sessions.py archive 1 3    # 归档会话（从 DSH 活跃列表隐藏）
python manage_sessions.py unarchive 1 3  # 取消归档
python manage_sessions.py trash          # 列出回收站
python manage_sessions.py restore 1 3    # 从回收站恢复到原工作区
python manage_sessions.py empty-trash    # 彻底清空回收站（不可恢复！）
python manage_sessions.py clean [--yes]  # 清理缓存/磁盘孤儿残留 + 结果校验
python manage_sessions.py status         # DSH 运行状态 / 回收站概况
python manage_sessions.py build-exe      # 生成独立可执行文件
```

## 为什么选择本工具？

**1. 删除可反悔 —— 回收站机制**
其他 DSH 会话删除往往直接物理删除、不可恢复；本工具删除先入回收站，误删可随时恢复，彻底删除才真正释放空间。

**2. 清理最彻底 —— 缓存同步清理 + 结果校验**
删除会话时同步清理 `workspace.json` 与 `session_projcache.json` 的残留记录；`clean` 后自动复查，报告是否仍有孤儿（例如 DSH 运行中写回导致的残留），不留脏数据。

**3. DSH 运行中也能用 —— 无需关闭应用**
删除 / 恢复 / 彻底删除只操作会话文件，DSH 运行中直接执行；配合"重载 / F5"同步列表，全程无需重启 DSH。

**4. 实时可见 —— 自动监视**
GUI 每 3 秒静默刷新，DSH 里新建 / 删除会话自动反映；状态栏实时显示孤儿缓存数量与 DSH 运行状态。

**5. 双重操作方式 —— GUI + 命令行**
图形界面适合日常管理（深色鲸鱼娘主题、统计详情、动画交互）；命令行适合脚本化 / 无界面环境（`delete-old`、`clean --yes` 等）。

**6. 安全设计**
当前会话自动保护、危险操作双重确认、当前会话 / 选中项高亮区分；归档只隐藏不删除，数据永远保留在磁盘。

**7. 零依赖、可打包、跨平台**
运行时仅用 Python 标准库（tkinter）；可打成单文件 exe 随处携带；Windows / macOS / Linux 均可运行或自行打包。

## 生成独立可执行文件

```bash
python manage_sessions.py build-exe
```

- 自动使用项目 `.venv`（没有则自动创建），**不污染系统 Python**；
- 自动安装 / 升级 `pyinstaller` + `pillow`；
- 优先使用 whalegirl 鲸鱼娘图标（缺失时自动从 PNG 生成 / 下载 CC0 备用图 / 本地绘制）；
- 打包 `assets/`（鲸鱼娘 logo / 头像 / 窗口图标）随程序分发；
- **跨平台**：Windows 产出 `dist\DSH_SessionManager.exe`（`--windowed` 双击无黑窗）；
  macOS 产出 `.icns` 图标的 `--windowed` 二进制；Linux 产出带 PNG 图标的二进制。

> 说明：`build-exe` 是源码项目里的开发/构建命令；exe 本身已包含图形界面 + 全部命令行功能，可单独复制使用。

## 安全说明

- 当前会话（`DSH_SESSION_ID`；未设置则自动保护最近修改的会话）永远不会被删除；
- 删除默认进回收站；**`empty-trash` / “彻底删除”不可恢复**，操作前有确认；
- **DSH 运行中**：删除/恢复/彻底删除操作的是会话文件本身，**无需关闭 DSH**；但 DSH 界面（网页版/桌面版）的会话列表是内存快照，需手动刷新才会同步消失/出现：
  - **网页版**：按 **F5** 刷新页面；
  - **桌面版**：点窗口**自绘标题栏右侧的旋转箭头图标 → "重载 / Reload"**（或设置页 → 重启 → 重载，或试 Ctrl+R）——重载的是渲染窗口，host 主进程不重启；
  - 都无需重启 DSH；
- **归档 / 清理缓存**修改的是缓存文件，DSH 运行中可能被写回覆盖，工具会提示（仍可继续，改完重启 DSH 生效）；
- 归档只隐藏不删除，数据保留在磁盘。

## 许可证与素材版权

- **代码**：[MIT License](LICENSE)；
- **图标素材**：`whalegirl/` 鲸鱼娘图标来自
  [deepseek-whale-girl-icon](https://github.com/fornarwhal/deepseek-whale-girl-icon)，
  **CC BY-NC-SA 4.0**（须署名、非商用、相同方式共享），与代码 MIT 相互独立；商用请替换为 CC0 素材。
