# DSH 会话管理器 · 鲸鱼娘 🐋

DeepSeek Harness (DSH) 的会话管理工具：可视化 / 命令行查看、**回收站删除（可恢复）**、**归档/恢复**、搜索过滤、缓存清理，并带一个 **DeepSeek 鲸鱼娘主题** 的精美图形界面。

聊天记录实际存储在 `~/.dsh/sessions/`（工作区文件夹 → 会话文件夹 → `session.jsonl.zstd`），
索引在 `~/.dsh/storages/workspace.json`（含 `archivedSessionIds` 归档标记），
统计缓存在 `~/.dsh/storages/session_projcache.json`。
本工具删除会话时**同步清理这些缓存，不留残留**。

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🗑 回收站 | 删除先进回收站（`~/.dsh/.trash/`），可随时恢复；彻底删除才释放空间 |
| 🗂 归档 / 恢复 | 复用 DSH 的 `archivedSessionIds` 机制，把会话从活跃列表隐藏 / 恢复 |
| 📊 统计详情 | 显示轮数、步骤、LLM/工具耗时、Token 用量、上下文压力（动画进度条） |
| 🔍 搜索过滤 | 命令行 `search` 按标题 / 会话 ID / 工作区名搜索 |
| 🛡 安全保护 | 当前会话永不删除；删除前确认；DSH 运行中清理缓存会提示（会被写回覆盖） |
| ✓ 清理校验 | `clean` 后自动复查，报告是否仍有残留（例如被运行中的 DSH 写回） |
| 🌍 跨平台 | Windows / macOS / Linux 均可源码运行；`build-exe` 支持三平台打包 |
| 🎨 简约风 | 浅灰底 + 白卡片 + DeepSeek 蓝点缀；鲸鱼娘圆形头像；hover 过渡动画 |

## 环境要求

- **Python 3.8+**（推荐 3.10+；GUI 仅需标准库 tkinter，Pillow 可选）；
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
- 右侧：选中会话的**统计详情**（轮数 / 步骤 / 耗时 / Token / 上下文压力条，可滚动）+ 操作按钮；
- 底部：状态栏 + **DSH 运行状态呼吸灯**（运行中 = 绿色，提示缓存会被写回）。

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

Windows 下双击 exe 打开图形界面；在命令行执行 `DSH_SessionManager.exe list / delete / trash / restore / clean` 等同样可用。

> 说明：`build-exe` 是源码项目里的开发/构建命令；exe 本身已包含图形界面 + 全部命令行功能，可单独复制使用。

## 安全说明

- 当前会话（`DSH_SESSION_ID`；未设置则自动保护最近修改的会话）永远不会被删除；
- 删除默认进回收站；**`empty-trash` / “彻底删除”不可恢复**，操作前有确认；
- **DSH 运行中**：删除/清理对缓存的修改可能被 DSH 写回覆盖（会话文件本身不受影响），工具会弹出提示，建议先完全退出 DSH；
- 归档只隐藏不删除，数据保留在磁盘。

## 许可证与素材版权

- **代码**：[MIT License](LICENSE)；
- **图标素材**：`whalegirl/` 鲸鱼娘图标来自
  [deepseek-whale-girl-icon](https://github.com/fornarwhal/deepseek-whale-girl-icon)，
  **CC BY-NC-SA 4.0**（须署名、非商用、相同方式共享），与代码 MIT 相互独立；商用请替换为 CC0 素材。
