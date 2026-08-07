# 修改记录 (CHANGELOG)

本文件记录 video_download.py 的每次修改，方便回退。

格式：[日期] 修改内容 | 涉及文件 | 回退方法

---

## 2026-08-07 初始化 Git 仓库并推送

- **仓库地址**：https://github.com/qiuqin1979/videos-download.git
- **分支**：main
- **提交**：`b60d498` Initial commit
- **包含文件**：video_download.py, start.bat, start.vbs, run.bat, export_cookies.py, requirements.txt, CHANGELOG.md, README.md, .gitignore
- **排除文件**（.gitignore）：downloads/ 等视频目录、cookies.txt、.video_downloader_settings.json、__pycache__/、*.part 等

---

## 2026-08-07 (本次会话)

### 1. 修复下载无声音问题
- **问题**：选择纯视频格式（video only）下载后文件没有声音
- **修改**：[video_download.py](file:///d:/AI/video_download/video_download.py) `_download_thread` 方法
  - 纯视频格式自动追加 `+bestaudio` 合并音频
  - 默认选项改为 `Best Quality (auto, video+audio)`
- **回退**：删除 `download_fmt = f"{fmt_id}+bestaudio/{fmt_id}"` 这段条件判断

### 2. 添加代理支持
- **目的**：绕过 YouTube IP 级风控
- **修改**：
  - UI 新增代理输入框（格式: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080）
  - 新增 `_proxy_options()` 方法，返回 `["--proxy", proxy]`
  - fetch 和 download 命令都加入代理参数
- **回退**：删除 `_proxy_options()` 方法和 UI 中的 proxy_row

### 3. 简化 Cookie 选项
- **修改**：Cookie 下拉框选项从 8 个简化为 4 个
  - 保留: 不使用 / Chrome / Firefox / Cookie 文件...
  - 移除: Edge / Safari / Opera / Brave（Chrome v127+ AppBound 加密无法读取）
- **回退**：恢复 `self.combo_cookies["values"]` 列表

### 4. 改进错误提示
- **修改**：`_error_hint()` 方法提供中文解决方案
  - Cookie 数据库锁定 → 提示关闭浏览器或切换"不使用"
  - YouTube 机器人检测 → 提示使用代理或 Cookie 文件
  - DPAPI 解密失败 → 提示用扩展导出 Cookie 文件

### 5. 下载跳过已存在文件 + archive 记录
- **目的**：系列视频下载中断后，下次继续不重复下载
- **修改**：`_download_thread` 新增参数
  - `--download-archive <save_dir>/.yt-dlp-archive.txt` — 记录已下载视频 ID
  - `--no-overwrites` — 不覆盖磁盘上已有的文件
- **效果**：260 集系列下到第 92 集中断，下次自动从第 92 集继续

### 6. 系列视频文件名加序号
- **目的**：遍历下载时文件按顺序排列（001.xxx.mp4, 002.xxx.mp4）
- **修改**：
  - traverse 模式输出模板改为 `%(playlist_index)s.%(title)s.%(ext)s`
  - 新增 `_rename_existing_playlist_files()` 方法重命名旧文件
  - 新增 `_get_playlist_entries()` 用 `--flat-playlist` 获取列表信息
  - 新增 `_sanitize_title()` 模拟 yt-dlp 文件名清洗
- **回退**：输出模板改回 `%(title)s.%(ext)s`，删除三个新方法

### 7. 单个视频失败不中断整个系列
- **问题**：260 集系列下到第 92 集失败，整个下载终止
- **修改**：
  - 加 `--ignore-errors` 跳过失败视频继续下一个
  - 加 `--retries 15` / `--fragment-retries 15` 自动重试网络错误
  - 加 `--retry-sleep fragment:exp=1::30` 指数退避
  - 加 `--socket-timeout 45` 超时重试
  - 新增 `_on_download_partial()` 方法显示失败汇总
  - 用 `--print before_dl/after_move` 标记行跟踪每个视频状态
- **回退**：删除这些参数和 `_on_download_partial` 方法

### 8. 修复进度条不显示
- **根因**：stdout 被 PIPE 重定向（非 TTY），yt-dlp 默认关闭进度条
- **修改**：
  - 加 `--progress` 强制输出进度（关键修复）
  - 加 `--progress-template "download:__PROG__ %(progress._percent_str)s"` 自定义进度格式
  - 双保险匹配：`__PROG__` 行 + `[download] N%` 正则回退
  - 每个视频开始/结束时进度条重置为 0
  - 标记行改为 TAB 分隔防止标题空格导致解析错误
- **验证**：实测确认 `__PROG__ 0.0%` → `__PROG__ 5.4%` 等进度行正常输出
- **回退**：删除 `--progress` 和 `--progress-template` 参数

### 9. 配置持久化（自动保存/加载）
- **目的**：退出后下次打开自动恢复 URL、目录、遍历、Cookie、代理等配置
- **修改**：
  - 新增 `SETTINGS_FILE` 常量（.video_downloader_settings.json）
  - 新增 `_register_auto_save_traces()` — 监听变量变化，300ms 节流自动保存
  - 新增 `_collect_settings()` / `_save_settings()` / `_load_settings()`
  - `_on_fetch_done()` 智能匹配上次选择的清晰度（按分辨率匹配）
  - 清晰度下拉框绑定 `<<ComboboxSelected>>` 自动保存
  - `__init__` 末尾调用 `_load_settings()`
- **保存内容**：URL / 目录 / 遍历 / Cookie / Cookie文件路径 / 代理 / 清晰度标签 / 窗口大小位置
- **回退**：删除 `_register_auto_save_traces` / `_collect_settings` / `_save_settings` / `_load_settings` / `_finish_loading_settings` 方法，删除 `__init__` 中的 `_load_settings()` 调用

### 10. 退出确认对话框
- **目的**：防止下载中误点 X 导致任务中断
- **修改**：`_on_close()` 方法
  - 下载中：弹确认框 "正在下载中，退出会中断当前任务..."
  - 空闲中：静默保存配置后关闭
- **回退**：`_on_close` 改为直接 `self.root.destroy()`

### 11. 断点续传（显式启用）
- **目的**：下载到一半断网，下次从断点继续而非从头开始
- **修改**：`_download_thread` 新增 `--continue` 参数
  - yt-dlp 默认就支持，但显式加上让意图更清晰
  - 中断时保留 `.part` 文件，下次用 HTTP Range 从断点续传
- **工作机制**：
  1. 下载到 50% 断网 → 留下 `video.mp4.part` 文件
  2. 下次运行 → archive 中没有此视频 ID → 尝试下载
  3. 检测到 `.part` 文件 → 从 50% 续传（不会从头开始）
  4. 完成后 `.part` 后缀移除 → 视频加入 archive
- **回退**：删除 `--continue` 参数行

---

## 文件清单

| 文件 | 用途 |
|---|---|
| [video_download.py](file:///d:/AI/video_download/video_download.py) | 主程序 |
| [start.bat](file:///d:/AI/video_download/start.bat) | 一键启动脚本 |
| [start.vbs](file:///d:/AI/video_download/start.vbs) | 静默启动脚本 |
| [export_cookies.py](file:///d:/AI/video_download/export_cookies.py) | Chrome Cookie 导出工具 |
| [requirements.txt](file:///d:/AI/video_download/requirements.txt) | Python 依赖 |
| .video_downloader_settings.json | 配置文件（运行后自动生成） |
| .yt-dlp-archive.txt | 下载记录（运行后自动生成，每个下载目录一个） |
| CHANGELOG.md | 本文件 |
