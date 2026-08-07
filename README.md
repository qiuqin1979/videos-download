# YouTube 视频下载器 - 使用说明

## 核心功能
支持 Bilibili 和 YouTube 视频下载，支持遍历系列/播放列表批量下载。

## 快速开始

### 1. 安装依赖并启动
双击 `start.bat` 或 `start.vbs`

### 2. 下载 YouTube 视频（需要 Cookie）

由于 Chrome v127+ 的 AppBound 加密机制，**YouTube 免费视频也需要 Cookie 才能下载**。获取 Cookie 的方法：

#### 方法 A：安装浏览器扩展（推荐）

1. 在 Chrome 中安装扩展：
   - 打开：https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - 或搜索 "Get cookies.txt LOCALLY"

2. 打开 YouTube 并确保已登录

3. 点击扩展图标 → 导出 Cookie 文件

4. 在下载器中选择 "Cookie 文件..." → 选择刚导出的文件

#### 方法 B：手动导出 v10 Cookie（仅适用于部分视频）

1. 完全关闭 Chrome（包括后台进程）
2. 运行 `export_cookies.py`（需要 pycryptodomex）
3. 在下载器中选择 "Cookie 文件..." → 选择生成的 cookies.txt

**注意**：方法 B 只能导出 v10 加密的 Cookie（约 14 个），可能不够。

### 3. 下载 Bilibili 视频

Bilibili 通常不需要 Cookie。如果遇到 412 错误：
- 确保已登录 B 站
- 使用方法 A 导出 Bilibili Cookie

## 功能说明

### URL 输入
支持格式：
- YouTube: `youtube.com/watch?v=XXX`、`youtu.be/XXX`
- YouTube 播放列表: `youtube.com/playlist?list=XXX`
- Bilibili: `bilibili.com/video/BVXXX`
- Bilibili 合集: `bilibili.com/medialist/playlists/XXX`

### 遍历选项
- **勾选"遍历系列视频"**：下载整个播放列表/合集
- **不勾选**：只下载当前页面的单个视频

### 清晰度选择
- 自动检测可用清晰度
- 支持 144p 到 4K

## 常见问题

**Q: 下载 YouTube 时提示 "Sign in to confirm you're not a bot"**
A: 你的 IP 被 YouTube 风控。使用方法 A 导出 Cookie 即可。

**Q: Chrome Cookie 数据库被锁定？**
A: 完全关闭 Chrome 后再试（Ctrl+Shift+Esc 结束所有 Chrome 进程）。

**Q: 启动脚本卡住？**
A: 检查网络连接，首次运行需要下载依赖。
