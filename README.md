# DSH 会话管理工具

`manage_sessions.py` 用来查看 / 删除 DSH 的历史聊天记录，提供 **图形界面** 和 **命令行** 两种方式。

聊天记录实际存储在 `~/.dsh/sessions/` 里，按“工作区文件夹 -> 会话文件夹 -> session.jsonl.zstd”组织。
此外 `~/.dsh/storages/workspace.json` 和 `~/.dsh/storages/session_projcache.json` 里还有会话索引/缓存，
本工具删除时会 **同步清理这些缓存，不留残留**。

## 环境要求

- **Python 3.8+**（3.6+ 即可运行，推荐 3.10+；仅用到标准库，无第三方运行时依赖）；
- **图形界面** 需要 Tkinter（Windows 官方安装包自带；Linux 需 `sudo apt install python3-tk` 之类）；
- 工具读取的是 **本机当前用户的 DSH 数据**（`~/.dsh`，即 `%USERPROFILE%\.dsh`），
  换台机器 / 换个用户运行时，会自动指向该用户自己的 DSH 数据，与本项目所在位置无关；
- 也支持用环境变量 `DSH_HOME` 覆盖 DSH 数据目录（默认 `~/.dsh`）。

## 图形界面

```bash
python manage_sessions.py          # 无参数时默认打开图形界面
python manage_sessions.py gui      # 同上
```

界面会清晰列出：

- 每个工作区的名字、会话数量、占用大小、最后修改时间；
- 每个工作区下面嵌套显示它的每个会话（标题、大小、最后修改时间）；
- 当前正在进行的会话会标记为“受保护”，不会被误删；
- 支持多选，可以删除指定会话、删除整个工作区（含其全部会话）、删除全部历史会话；
- 删除最后一个会话后，空工作区会自动清理；也可点“清理缓存残留”清理孤儿缓存。

## 命令行

```bash
python manage_sessions.py list         # 按工作区分组列出所有会话
python manage_sessions.py delete 1 3   # 删除编号为 1 和 3 的会话
python manage_sessions.py delete-old   # 删除所有“非当前”且超过 1 小时的历史会话
python manage_sessions.py clean        # 清理缓存/磁盘中的孤儿残留
```

## 生成独立 exe

> ⚠️ **仅限 Windows**：`build-exe` 使用 PyInstaller 的 `--windowed` 模式和
> `.venv\Scripts\python.exe`、`.ico` 等 Windows 专属路径，**在 macOS / Linux 上无法打包**。
> 主功能（`gui` / `list` / `delete` / `delete-old` / `clean`）本身不依赖 Windows，可在各平台直接以源码方式运行。

```bash
python manage_sessions.py build-exe
```

生成过程：

- 自动使用项目里的 `.venv` 虚拟环境，不会用系统 Python 安装任何包；
- 自动在 `.venv` 里安装/升级 `pyinstaller` 和 `pillow`；
- 自动从 Wikimedia Commons 下载 CC0 授权的 Q 版萌系少女图标（网络失败时会使用本地绘制的备用图标）；
- 用 PyInstaller `--onefile --windowed` 打出单个 exe，并把图标嵌入 exe；
- `--windowed` 保证双击 exe 打开图形界面时不会弹出黑色终端窗口。

生成结果：

```text
dist\DSH_SessionManager.exe
```

这个 exe 包含图形界面和全部命令行功能，可以单独复制使用：

```bash
DSH_SessionManager.exe                    # 双击打开图形界面（无黑色终端窗口）
DSH_SessionManager.exe list               # 在已有命令行窗口中查看工作区/会话
DSH_SessionManager.exe delete 1 3         # 删除指定会话
DSH_SessionManager.exe delete-old         # 删除历史会话
DSH_SessionManager.exe clean              # 清理残留
```

> 说明：`build-exe` 是源码项目里的开发/构建命令，用来生成这个 exe；exe 本身已经包含全部运行时功能（图形界面 + 会话管理命令行）。

## 安全说明

- 当前会话（环境变量 `DSH_SESSION_ID` 指定；若未设置则自动保护最近修改的会话）永远不会被删除；
- 删除前会弹出确认框 / 要求输入 `yes`；
- 删除的会话不可恢复，请确认好再操作。

## 许可证与素材版权

- **代码**：本仓库代码采用 [MIT License](LICENSE)；
- **图标素材**：`whalegirl/` 目录中的鲸鱼娘图标
  （`DeepSeekHarness-WhaleGirl.ico`、`improved-1.png` 等）来自
  [deepseek-whale-girl-icon](https://github.com/fornarwhal/deepseek-whale-girl-icon)，
  采用 **CC BY-NC-SA 4.0** 许可（须署名、非商业用途、相同方式共享），
  与代码的 MIT 许可相互独立；如需商用图标请自行替换为 CC0 等可商用素材。
