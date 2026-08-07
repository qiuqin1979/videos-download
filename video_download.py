"""
Video Downloader - Download videos from X.com and YouTube
GUI application using tkinter + yt-dlp
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import re
import subprocess
import json


class VideoDownloader:
    # Where settings are persisted between runs.
    SETTINGS_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".video_downloader_settings.json"
    )

    def __init__(self, root):
        self.root = root
        self.root.title("Video Downloader")
        self.root.geometry("700x640")
        self.root.resizable(True, True)
        self.root.configure(bg="#1e1e2e")

        # Default save directory: same folder as this script
        self.default_save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(self.default_save_dir, exist_ok=True)

        self.formats = []  # available formats from yt-dlp
        self.downloading = False
        # Used to avoid saving settings while we're still loading them.
        self._loading_settings = False

        self._build_ui()
        self._load_settings()
        # Save settings when the user closes the window (covers any traces
        # we might have missed, and runs even if auto-save was suppressed).
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Colors
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        accent = "#89b4fa"
        entry_bg = "#313244"
        btn_bg = "#45475a"

        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI", 16, "bold"))
        style.configure("TButton", background=btn_bg, foreground=fg, font=("Segoe UI", 10), padding=6)
        style.map("TButton", background=[("active", accent)])
        style.configure("Accent.TButton", background=accent, foreground="#1e1e2e", font=("Segoe UI", 11, "bold"), padding=8)
        style.map("Accent.TButton", background=[("active", "#74c7ec")])
        style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Horizontal.TProgressbar", troughcolor=entry_bg, background=accent)

        pad = {"padx": 15, "pady": 5}

        # Header
        ttk.Label(self.root, text="Video Downloader", style="Header.TLabel").pack(pady=(18, 4))
        ttk.Label(self.root, text="Supports X.com (Twitter), YouTube and Bilibili").pack()

        # --- URL ---
        frame_url = tk.Frame(self.root, bg=bg)
        frame_url.pack(fill="x", padx=15, pady=(14, 2))
        ttk.Label(frame_url, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        self.entry_url = ttk.Entry(frame_url, textvariable=self.url_var, font=("Segoe UI", 11))
        self.entry_url.pack(fill="x", pady=4)

        # Traverse series checkbox (Bilibili multi-part / YouTube playlist)
        self.traverse_var = tk.BooleanVar(value=False)
        self.chk_traverse = tk.Checkbutton(
            frame_url, text="遍历系列视频（B站全部分P / 合集，YouTube 播放列表）",
            variable=self.traverse_var, bg=bg, fg=fg, selectcolor=entry_bg,
            activebackground=bg, activeforeground=fg, font=("Segoe UI", 10)
        )
        self.chk_traverse.pack(anchor="w", pady=(2, 4))

        # Cookies source (for YouTube bot-authentication / Bilibili VIP videos)
        cookies_row = tk.Frame(frame_url, bg=bg)
        cookies_row.pack(fill="x", pady=(2, 4))
        ttk.Label(cookies_row, text="Cookies:").pack(side="left")
        self.cookies_var = tk.StringVar(value="不使用")
        self.combo_cookies = ttk.Combobox(cookies_row, textvariable=self.cookies_var,
                                          state="readonly", width=18, font=("Segoe UI", 10))
        self.combo_cookies["values"] = [
            "不使用", "Chrome", "Firefox", "Cookie 文件...",
        ]
        self.combo_cookies.pack(side="left", padx=(6, 0))
        self.combo_cookies.bind("<<ComboboxSelected>>", self._on_cookies_change)
        ttk.Label(cookies_row, text="  (YouTube 认证 / B站 VIP)",
                  foreground="#a6adc8", font=("Segoe UI", 9)).pack(side="left")

        # Cookie file path row (hidden by default, shown when "Cookie 文件..." is selected)
        self.cookie_file_frame = tk.Frame(self.root, bg=bg)
        self.cookie_file_var = tk.StringVar()
        self.entry_cookie_file = ttk.Entry(self.cookie_file_frame, textvariable=self.cookie_file_var,
                                           font=("Segoe UI", 10))
        self.entry_cookie_file.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(self.cookie_file_frame, text="选择 Cookie 文件", command=self._browse_cookie_file).pack(side="right")

        # Proxy row (optional, for bypassing IP-based YouTube blocking)
        proxy_row = tk.Frame(frame_url, bg=bg)
        proxy_row.pack(fill="x", pady=(2, 4))
        ttk.Label(proxy_row, text="代理:").pack(side="left")
        self.proxy_var = tk.StringVar()
        entry_proxy = ttk.Entry(proxy_row, textvariable=self.proxy_var, width=30, font=("Segoe UI", 10))
        entry_proxy.pack(side="left", padx=(6, 0))
        ttk.Label(proxy_row, text="  (格式: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080)",
                  foreground="#a6adc8", font=("Segoe UI", 9)).pack(side="left")

        # Fetch qualities button
        self.btn_fetch = ttk.Button(frame_url, text="Fetch Available Qualities", command=self._fetch_formats)
        self.btn_fetch.pack(anchor="e", pady=2)

        # --- Quality selector ---
        frame_quality = tk.Frame(self.root, bg=bg)
        frame_quality.pack(fill="x", **pad)
        ttk.Label(frame_quality, text="Select Quality:").pack(anchor="w")
        self.quality_var = tk.StringVar()
        self.combo_quality = ttk.Combobox(frame_quality, textvariable=self.quality_var,
                                          state="readonly", font=("Segoe UI", 10))
        self.combo_quality.pack(fill="x", pady=4)
        self.combo_quality.set("-- Fetch qualities first --")
        self.combo_quality.bind("<<ComboboxSelected>>", lambda _e: self._save_settings())

        # --- Save directory ---
        frame_dir = tk.Frame(self.root, bg=bg)
        frame_dir.pack(fill="x", **pad)
        ttk.Label(frame_dir, text="Save To:").pack(anchor="w")
        dir_row = tk.Frame(frame_dir, bg=bg)
        dir_row.pack(fill="x", pady=4)
        self.dir_var = tk.StringVar(value=self.default_save_dir)
        self.entry_dir = ttk.Entry(dir_row, textvariable=self.dir_var, font=("Segoe UI", 10))
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(dir_row, text="Browse", command=self._browse_dir).pack(side="right")

        # --- Download button ---
        self.btn_download = ttk.Button(self.root, text="Download", style="Accent.TButton",
                                       command=self._start_download)
        self.btn_download.pack(pady=14)

        # --- Progress ---
        frame_prog = tk.Frame(self.root, bg=bg)
        frame_prog.pack(fill="x", **pad)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame_prog, variable=self.progress_var,
                                            maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", pady=4)
        self.lbl_status = ttk.Label(frame_prog, text="Ready")
        self.lbl_status.pack(anchor="w")

        # --- Log area ---
        frame_log = tk.Frame(self.root, bg=bg)
        frame_log.pack(fill="both", expand=True, padx=15, pady=(2, 12))
        self.text_log = tk.Text(frame_log, height=8, bg="#313244", fg=fg,
                                font=("Consolas", 9), wrap="word", state="disabled",
                                relief="flat", borderwidth=0)
        scrollbar = ttk.Scrollbar(frame_log, command=self.text_log.yview)
        self.text_log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.text_log.pack(side="left", fill="both", expand=True)

        # Auto-save settings whenever the user changes any field.
        self._register_auto_save_traces()

        # ------------------------------------------------------------------ helpers
    # ------------------------------------------------------------ settings
    def _register_auto_save_traces(self):
        """Attach 'write' traces to every tk variable so any user-editable variable
        StringVar/BooleanVar.  When the user types, settings are flushed to disk.
        (Throttled via `after` so fast writes do not spam disk, but still
        immediate user changes are persisted within ~300 ms.)
        """
        self._save_job = None

        def _schedule_save(*_a):
            if self._loading_settings:
                return
            if self._save_job is not None:
                try:
                    self.root.after_cancel(self._save_job)
                except Exception:
                    pass
            self._save_job = self.root.after(300, self._save_settings)

        for var in (self.url_var, self.dir_var, self.cookies_var,
                    self.cookie_file_var, self.proxy_var):
            var.trace_add("write", _schedule_save)
        self.traverse_var.trace_add("write", _schedule_save)

    def _collect_settings(self):
        """Return a dict of the current user-editable state."""
        # Remember which quality label was selected so we can try to re-select it
        # next time (the format IDs can change between runs).
        try:
            qual_label = self.combo_quality.get()
        except Exception:
            qual_label = ""
        return {
            "url": self.url_var.get(),
            "save_dir": self.dir_var.get(),
            "traverse": bool(self.traverse_var.get()),
            "cookies": self.cookies_var.get(),
            "cookie_file": self.cookie_file_var.get(),
            "proxy": self.proxy_var.get(),
            "quality_label": qual_label,
            "window_geometry": self.root.geometry(),
        }

    def _save_settings(self):
        """Write current settings to the JSON settings file."""
        self._save_job = None
        try:
            data = self._collect_settings()
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            # Don't nag the user about this; settings persistence is best-effort.
            print(f"[settings save warning: {e}")

    def _load_settings(self):
        """Load settings from disk into the UI variables (if file exists)."""
        self._loading_settings = True
        try:
            if not os.path.isfile(self.SETTINGS_FILE):
                return
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return

            if isinstance(data.get("url"), str):
                self.url_var.set(data["url"])
            save_dir = data.get("save_dir")
            if isinstance(save_dir, str) and save_dir:
                self.dir_var.set(save_dir)
            if isinstance(data.get("traverse"), bool):
                self.traverse_var.set(data["traverse"])
            if isinstance(data.get("cookies"), str):
                # Only restore if it's still in the allowed list (defensive).
                if data["cookies"] in self.combo_cookies["values"]:
                    self.cookies_var.set(data["cookies"])
                    self._on_cookies_change()
            if isinstance(data.get("cookie_file"), str):
                self.cookie_file_var.set(data["cookie_file"])
            if isinstance(data.get("proxy"), str):
                self.proxy_var.set(data["proxy"])
            # window geometry (restore size/position if recorded)
            geom = data.get("window_geometry")
            if isinstance(geom, str) and "x" in geom:
                try:
                    self.root.geometry(geom)
                except tk.TclError:
                        pass
            # Save the label of the chosen quality, *however*, that requires formats are
            # have been re-fetched.  Keep it in case the user clicks Fetch right away.
            self._last_quality_label = data.get("quality_label", "")

        except (OSError, json.JSONDecodeError) as e:
            print(f"[settings] load warning: {e}")
        finally:
            self.root.after(50, self._finish_loading_settings)

    def _finish_loading_settings(self):
        """Flip the 'loading' guard off after the event loop has processed
        all the `trace_add` fires triggered by _load_settings()."""
        self._loading_settings = False

    def _on_close(self):
        """Ask for confirmation before closing; always save settings on the way out.

        Settings are auto-saved every 300 ms after any edit, so the only
        destructive thing the user can do by accidentally closing the window
        is aborting an in-progress download — that's the only case where we
        show a confirmation dialog.
        """
        if self.downloading:
            if not messagebox.askyesno(
                "确认退出",
                "正在下载中，退出会中断当前任务。\n\n"
                "已下载完成的视频会自动跳过，下次可继续下载剩余的。\n\n"
                "确定要退出吗？",
                icon="warning",
            ):
                # User said "No" — stay open, try to kill any outstanding
                # close-handler state (nothing to reset for Tk WM_DELETE_WINDOW).
                return
        # Always save settings, regardless of the download state, then quit.
        try:
            self._save_settings()
        except Exception:
            pass
        self.root.destroy()

    # ------------------------------------------------------------ helpers
    def _log(self, msg):
        self.text_log.configure(state="normal")
        self.text_log.insert("end", msg + "\n")
        self.text_log.see("end")
        self.text_log.configure(state="disabled")

    def _set_status(self, msg):
        self.lbl_status.configure(text=msg)

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _on_cookies_change(self, _event=None):
        """Show/hide the cookie-file row based on the selected cookies source."""
        if self.cookies_var.get() == "Cookie 文件...":
            self.cookie_file_frame.pack(fill="x", padx=15, pady=(2, 4))
        else:
            self.cookie_file_frame.pack_forget()

    def _browse_cookie_file(self):
        f = filedialog.askopenfilename(
            title="Select cookie file (Netscape format)",
            filetypes=[("Cookie files", "*.txt *.cookie *.netscape"), ("All files", "*.*")],
        )
        if f:
            self.cookie_file_var.set(f)

    def _validate_url(self, url):
        patterns = [
            r"https?://(www\.)?(twitter|x)\.com/.+/status/\d+",
            r"https?://(www\.)?(youtube\.com|youtu\.be)/.+",
            r"https?://(www\.)?bilibili\.com/video/[AaBb][Vv]?\d+",
            r"https?://(www\.)?bilibili\.com/(list|medialist)/.+",
            r"https?://space\.bilibili\.com/\d+/lists?.+",
        ]
        return any(re.match(p, url) for p in patterns)

    def _is_youtube(self, url):
        return bool(re.search(r"youtube\.com|youtu\.be", url, re.IGNORECASE))

    def _get_ytdlp_cmd(self):
        """Return yt-dlp command - try system install first, then local."""
        return "yt-dlp"

    def _is_bilibili(self, url):
        return bool(re.search(r"bilibili\.com|b23\.tv", url, re.IGNORECASE))

    def _bilibili_options(self, url):
        """Extra yt-dlp options for Bilibili to avoid HTTP 412."""
        if not self._is_bilibili(url):
            return []
        return [
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "--add-header",
            "Referer:https://www.bilibili.com/",
        ]

    def _youtube_options(self, url):
        """Extra yt-dlp options for YouTube.

        Recent yt-dlp versions require a JavaScript runtime (deno or node) to
        extract YouTube formats.  deno is the default but usually not installed;
        node is widely available, so we explicitly enable it.
        """
        if not self._is_youtube(url):
            return []
        return ["--js-runtimes", "node"]

    def _cookies_options(self):
        """Cookies options for authenticating with sites (YouTube bot / Bilibili VIP).

        Supports three modes:
          - "不使用"  -> no cookie options
          - Browser name -> --cookies-from-browser <browser>
          - "Cookie 文件..." -> --cookies <file_path>
        """
        source = self.cookies_var.get()
        if not source or source == "不使用":
            return []
        if source == "Cookie 文件...":
            path = self.cookie_file_var.get().strip()
            if not path or not os.path.isfile(path):
                self._log(f"WARNING: Cookie file not found: {path}")
                return []
            return ["--cookies", path]
        # Browser name
        self._log(f"Using {source} cookies (make sure {source} is closed)")
        return ["--cookies-from-browser", source.lower()]

    def _proxy_options(self):
        """Proxy options for bypassing IP-based blocking."""
        proxy = self.proxy_var.get().strip()
        if not proxy:
            return []
        self._log(f"Using proxy: {proxy}")
        return ["--proxy", proxy]

    # ------------------------------------------------------------------ fetch formats
    def _fetch_formats(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a URL first.")
            return
        if not self._validate_url(url):
            messagebox.showwarning("Warning",
                "URL not recognised.\nSupported: X.com/Twitter, YouTube and Bilibili links.")
            return

        self.btn_fetch.configure(state="disabled")
        self._set_status("Fetching available qualities...")
        self._log(f"Fetching formats for: {url}")
        threading.Thread(target=self._fetch_formats_thread, args=(url,), daemon=True).start()

    def _fetch_formats_thread(self, url):
        try:
            # Always fetch only the first item to keep it fast for playlists.
            cmd = [self._get_ytdlp_cmd(), "-j", "--no-download",
                   "--playlist-items", "1"] + self._bilibili_options(url) + self._youtube_options(url) + self._cookies_options() + self._proxy_options() + [url]
            # YouTube extraction can be slow, give it plenty of time.
            timeout = 120 if self._is_youtube(url) else 60
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                    encoding="utf-8", errors="replace")

            if result.returncode != 0:
                # Build a helpful error message from stderr (fall back to stdout).
                err = (result.stderr or "").strip()
                if not err:
                    err = (result.stdout or "").strip()[:500]
                if not err:
                    err = f"yt-dlp exited with code {result.returncode} (no error message)."
                self.root.after(0, lambda: self._on_fetch_error(err))
                return

            # yt-dlp -j may return one JSON object or NDJSON lines for playlists.
            lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
            if not lines:
                self.root.after(0, lambda: self._on_fetch_error("No data returned from yt-dlp."))
                return
            info = json.loads(lines[0])
            formats_raw = info.get("formats", [])

            # Detect if the URL points to a playlist / series so the user knows
            # they can enable "traverse" to grab all of them.
            is_playlist = bool(info.get("playlist_count")) or bool(info.get("playlist_id"))
            if is_playlist:
                n = info.get("playlist_count", "?")
                self.root.after(0, lambda n=n: self._log(
                    f"Playlist / series detected ({n} videos). "
                    f"Enable 'traverse' to download all."))

            # Build a user-friendly list
            seen = set()
            choices = []
            for f in formats_raw:
                fmt_id = f.get("format_id", "")
                ext = f.get("ext", "")
                h = f.get("height")
                vcodec = f.get("vcodec", "none")
                acodec = f.get("acodec", "none")
                filesize = f.get("filesize") or f.get("filesize_approx") or 0
                size_str = self._human_size(filesize) if filesize else "?"

                # Only show entries that have video
                if vcodec == "none" or not h:
                    continue
                has_audio = acodec != "none"
                label = f"{h}p | {ext} | {size_str} | {'video+audio' if has_audio else 'video only (no sound)'}"
                key = (h, ext, has_audio)
                if key not in seen:
                    seen.add(key)
                    choices.append((label, fmt_id, h, has_audio))

            # Sort: highest resolution first, prefer video+audio
            choices.sort(key=lambda x: (x[2], x[3]), reverse=True)

            # Add options at top: best quality, then best video+audio, then best video only
            best_va = max((c for c in choices if c[3]), key=lambda x: x[2], default=None)
            best_v = max(choices, key=lambda x: x[2], default=None)
            final = [("Best Quality (auto, video+audio)", "bestvideo+bestaudio/best", 99999, True)]
            if best_va:
                final.append((f"Best Video+Audio ({best_va[2]}p)", f"{best_va[1]}+bestaudio/{best_va[1]}", best_va[2], True))
            if best_v and (not best_va or best_v[1] != best_va[1]):
                final.append((f"Best Video Only ({best_v[2]}p)", best_v[1], best_v[2], False))
            final.extend(choices)
            self.formats = final
            labels = [c[0] for c in final]

            self.root.after(0, lambda: self._on_fetch_done(labels))

        except FileNotFoundError:
            self.root.after(0, lambda: self._on_fetch_error(
                "yt-dlp not found. Please run:  pip install yt-dlp"))
        except Exception as e:
            self.root.after(0, lambda: self._on_fetch_error(str(e)))

    def _on_fetch_done(self, labels):
        self.combo_quality["values"] = labels
        if labels:
            # Prefer the user's last-selected quality label (if any) so they don't
            # have to re-pick their favourite resolution every single run.
            prev = getattr(self, "_last_quality_label", "") or ""
            target_idx = 0
            if prev:
                for i, lab in enumerate(labels):
                    if lab == prev:
                        target_idx = i
                        break
                else:
                    # Exact label not found — fall back to the same resolution tier
                    # (e.g. "1080p" of a different format is still a valid 1080p pick)
                    m = re.search(r"(\d+)p", prev)
                    if m:
                        want_height = m.group(1) + "p"
                        for i, lab in enumerate(labels):
                            if want_height in lab:
                                target_idx = i
                                break
            self.combo_quality.current(target_idx)
        self.btn_fetch.configure(state="normal")
        self._set_status(f"Found {len(labels)} quality options")
        self._log(f"Found {len(labels)} quality options. Select one and click Download.")

    def _on_fetch_error(self, err):
        self.btn_fetch.configure(state="normal")
        self._set_status("Error fetching formats")
        self._log(f"ERROR: {err}")
        messagebox.showerror("Error", f"Could not fetch formats:\n{err}{self._error_hint(err)}")

    def _on_download_error(self, err):
        self.downloading = False
        self.btn_download.configure(state="normal")
        self._set_status("Download failed")
        self._log(f"ERROR: {err}")
        messagebox.showerror("Error", f"Download failed:\n{err}{self._error_hint(err)}")

    @staticmethod
    def _error_hint(err):
        """Return a friendly hint for known yt-dlp errors."""
        if not err:
            return ""
        err_lower = err.lower()
        if "could not copy" in err_lower and "cookie" in err_lower:
            return (
                "\n\n[解决方案]"
                "\n1. 关闭 Chrome 浏览器后重试（任务管理器结束 chrome.exe）"
                "\n2. 或切换 Cookies 为 '不使用'"
                "\n3. 或安装扩展 'Get cookies.txt LOCALLY' 导出 Cookie 文件"
            )
        if "failed to decrypt" in err_lower or "dpapi" in err_lower:
            return "\n\n[问题] Chrome v127+ 启用了 AppBound 加密，无法直接读取 Cookie\n[解决] 安装扩展 'Get cookies.txt LOCALLY' 手动导出 Cookie 文件"
        if "sign in to confirm" in err_lower or "bot" in err_lower or "403" in err_lower:
            return (
                "\n\n[YouTube 反爬虫] 你的 IP 被临时限制（常见）"
                "\n解决方案："
                "\n  1. 输入代理地址 (如 http://127.0.0.1:7890) 后重试"
                "\n  2. 安装 'Get cookies.txt LOCALLY' 扩展导出 Cookie 文件"
                "\n  3. 等待 24-72 小时后自动恢复"
            )
        if "no supported javascript runtime" in err_lower:
            return "\n\n[建议] 请安装 Node.js (https://nodejs.org)"
        if "412" in err_lower or "precondition failed" in err_lower:
            return "\n\n[建议] B站风控：关闭所有浏览器后重试，或使用 Cookie 文件"
        return ""

    @staticmethod
    def _human_size(b):
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    # ------------------------------------------------------------------ playlist rename
    def _get_playlist_entries(self, url):
        """Fetch playlist entries (id, index, title) without downloading.

        Returns a list of (video_id, playlist_index, title) tuples, or None
        if the URL is not a playlist or the fetch fails.
        """
        try:
            cmd = [
                self._get_ytdlp_cmd(),
                "--flat-playlist",
                "--print", "%(id)s\t%(playlist_index)s\t%(title)s",
                "--no-warnings",
                "--yes-playlist",
            ]
            cmd.extend(self._proxy_options())
            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=90, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                self._log(f"Could not fetch playlist info: {(result.stderr or '').strip()[:200]}")
                return None

            entries = []
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t", 2)
                if len(parts) == 3:
                    vid, idx_str, title = parts
                    idx_str = idx_str.strip()
                    if not idx_str:
                        continue
                    # Keep the original (zero-padded) string so renames match
                    # the format yt-dlp uses for %(playlist_index)s.
                    entries.append((vid, idx_str, title))
            return entries if entries else None
        except Exception as e:
            self._log(f"Playlist info fetch error: {e}")
            return None

    @staticmethod
    def _sanitize_title(title):
        """Mimic yt-dlp's filename sanitisation on Windows.

        yt-dlp strips characters that are illegal in Windows filenames
        (< > : " / \\ | ? *) and trims leading/trailing spaces and dots.
        """
        name = re.sub(r'[<>:"/\\|?*]', '', title)
        name = re.sub(r'[\x00-\x1f]', '', name)
        name = name.strip().rstrip('.').strip()
        return name

    def _rename_existing_playlist_files(self, url, save_dir):
        """Rename previously-downloaded playlist files with sequence numbers.

        For each video in the playlist, looks for a matching file on disk
        (by sanitised title) and renames it to '<index>.<title>.<ext>' so
        that the whole series stays in order.  This does NOT depend on the
        download archive — files downloaded before the archive feature was
        added are renamed too.
        """
        entries = self._get_playlist_entries(url)
        if not entries:
            self._log("No playlist detected; skipping rename step.")
            return

        video_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4a", ".mp3", ".opus", ".flv"}
        # Snapshot the directory once.
        try:
            dir_files = os.listdir(save_dir)
        except OSError as e:
            self._log(f"Cannot list save directory: {e}")
            return

        renamed = 0
        for vid, idx_str, title in entries:
            sanitized = self._sanitize_title(title)
            if not sanitized:
                continue

            # Skip if a file with this index prefix already exists.
            prefix = f"{idx_str}."
            already_done = any(
                fn.startswith(prefix) and os.path.splitext(fn)[1].lower() in video_exts
                for fn in dir_files
            )
            if already_done:
                continue

            # Find the matching file on disk (by sanitised title).
            for fn in dir_files:
                base, ext = os.path.splitext(fn)
                if ext.lower() not in video_exts:
                    continue
                # Match exact sanitised title, or a title that starts with it
                # (covers cases where yt-dlp appended extra info to the name).
                if base == sanitized or base.startswith(sanitized):
                    old_path = os.path.join(save_dir, fn)
                    new_name = f"{idx_str}.{fn}"
                    new_path = os.path.join(save_dir, new_name)
                    try:
                        os.rename(old_path, new_path)
                        renamed += 1
                        self._log(f"Renamed: {fn}  ->  {new_name}")
                        # Update the snapshot so we don't match this file again.
                        dir_files.remove(fn)
                        dir_files.append(new_name)
                    except OSError as e:
                        self._log(f"WARNING: Could not rename {fn}: {e}")
                    break

        if renamed:
            self._log(f"Renamed {renamed} existing file(s) with sequence numbers.")
        else:
            self._log("No files needed renaming.")

    # ------------------------------------------------------------------ download
    def _start_download(self):
        url = self.url_var.get().strip()
        save_dir = self.dir_var.get().strip()

        if not url:
            messagebox.showwarning("Warning", "Please enter a URL.")
            return
        if not self._validate_url(url):
            messagebox.showwarning("Warning", "URL not recognised.")
            return
        if not os.path.isdir(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create directory:\n{e}")
                return

        if not self.formats:
            messagebox.showinfo("Info", "Please fetch qualities first.")
            return

        idx = self.combo_quality.current()
        if idx < 0:
            idx = 0
        fmt_id = self.formats[idx][1]

        traverse = self.traverse_var.get()
        self.downloading = True
        self.btn_download.configure(state="disabled")
        self.progress_var.set(0)
        self._set_status("Downloading...")
        self._log(f"Starting download: {url}")
        self._log(f"Format: {self.formats[idx][0]}")
        self._log(f"Traverse series: {traverse}")
        self._log(f"Save to: {save_dir}")

        threading.Thread(target=self._download_thread,
                         args=(url, fmt_id, save_dir, traverse), daemon=True).start()

    def _download_thread(self, url, fmt_id, save_dir, traverse):
        try:
            # When traversing a series, prefix filenames with the playlist index
            # (1.标题.mp4, 2.标题.mp4, ...) so episodes stay ordered.
            # Also rename any previously-downloaded files to match this scheme.
            if traverse:
                self._log("Checking for previously downloaded files to rename...")
                self._rename_existing_playlist_files(url, save_dir)
                output_template = os.path.join(save_dir, "%(playlist_index)s.%(title)s.%(ext)s")
            else:
                output_template = os.path.join(save_dir, "%(title)s.%(ext)s")

            # If format is video-only, append best audio so yt-dlp auto-merges
            fmt_info = next((f for f in self.formats if f[1] == fmt_id), None)
            if fmt_info and not fmt_info[3]:  # has_audio = False
                download_fmt = f"{fmt_id}+bestaudio/{fmt_id}"
            else:
                download_fmt = fmt_id

            archive_path = os.path.join(save_dir, ".yt-dlp-archive.txt")
            cmd = [
                self._get_ytdlp_cmd(),
                "-f", download_fmt,
                "--merge-output-format", "mp4",
                "-o", output_template,
                "--newline",
                "--no-colors",
                # stdout is piped (not a TTY) so yt-dlp would hide the progress
                # bar by default.  --progress forces it to emit progress lines
                # regardless of output destination.
                "--progress",
                # Use a custom progress template so the progress line is
                # machine-parseable and never clashes with --print markers.
                # Output format: __PROG__ 45.2
                "--progress-template", "download:__PROG__ %(progress._percent_str)s",
                # Retry transient network errors instead of failing immediately.
                "--retries", "15",
                "--fragment-retries", "15",
                "--retry-sleep", "fragment:exp=1::30",
                "--retry-sleep", "http:exp=1::30",
                "--socket-timeout", "45",
                # Skip videos already downloaded (resume support for playlists).
                "--download-archive", archive_path,
                # Never overwrite an existing file on disk either.
                "--no-overwrites",
                # Resume partially downloaded .part files (yt-dlp default, but
                # make it explicit).  When a download is interrupted (network
                # drop, power loss, etc.), yt-dlp keeps the .part file and
                # resumes from the same byte offset on the next run using HTTP
                # Range requests — so a 50% download doesn't restart from 0%.
                "--continue",
                # In playlist mode, keep going if one video fails — don't abort
                # the entire 200+ video series because of a single transient error.
                "--ignore-errors",
                # Markers for tracking when each item starts / finishes.
                # Use TAB as separator so titles with spaces don't confuse parsing.
                "--print", "before_dl:__DL__\t%(id)s\t%(playlist_index)s\t%(title)s",
                "--print", "after_move:__DONE__\t%(id)s\t%(playlist_index)s\t%(title)s",
            ]
            # Bilibili-specific headers to avoid HTTP 412
            cmd.extend(self._bilibili_options(url))
            # YouTube needs a JS runtime for full format extraction
            cmd.extend(self._youtube_options(url))
            # Browser cookies for authentication (YouTube bot / Bilibili VIP)
            cmd.extend(self._cookies_options())
            # Proxy for bypassing IP blocking
            cmd.extend(self._proxy_options())
            # Traverse series (playlist / multi-part / collection)
            cmd.append("--yes-playlist" if traverse else "--no-playlist")
            cmd.append(url)

            self._log(f"Running: {' '.join(cmd[:6])} ...")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace")

            done_ids = set()            # video IDs that finished successfully
            started_items = []          # (id, index, title) tuples for started downloads
            last_error_lines = []       # most recent error-ish lines for reporting
            any_progress_seen = False   # for diagnostic log at the end

            for line in process.stdout:
                line_stripped = line.rstrip("\r\n")
                raw = line_stripped.strip()
                if not raw:
                    continue

                # 1) Dedicated progress line (from --progress-template).
                #    Format: "__PROG__  45.2%" (with optional spaces/percent sign).
                if raw.startswith("__PROG__"):
                    m = re.search(r"([\d.]+)", raw[len("__PROG__"):])
                    if m:
                        pct = min(float(m.group(1)), 99.9)
                        self.root.after(0, lambda p=pct: self.progress_var.set(p))
                        self.root.after(0, lambda p=pct: self._set_status(f"Downloading... {p:.1f}%"))
                        if not any_progress_seen:
                            self.root.after(0, lambda: self._log("[progress] 收到进度条输出 ✓"))
                            any_progress_seen = True
                    continue

                # 1b) Fallback progress parsing: the default [download] N% line
                #     (in case the progress template didn't kick in for any reason).
                m = re.search(r"\[download\]\s+([\d.]+)%", line_stripped)
                if m:
                    pct = min(float(m.group(1)), 99.9)
                    self.root.after(0, lambda p=pct: self.progress_var.set(p))
                    self.root.after(0, lambda p=pct: self._set_status(f"Downloading... {p:.1f}%"))
                    if not any_progress_seen:
                        self.root.after(0, lambda: self._log("[progress] 收到进度条输出 ✓ (from [download] line)"))
                        any_progress_seen = True
                    # Don't `continue` here — still log the progress line as usual.

                # 2) Item-started marker (TAB separated, from --print before_dl).
                if raw.startswith("__DL__\t") or raw.startswith("__DL__ "):
                    parts = raw.split("\t")
                    if len(parts) >= 4:
                        started_items.append((parts[1].strip(), parts[2].strip(), parts[3].strip()))
                    self._log(raw)
                    # New video starting — reset per-video progress to 0 so the
                    # bar clearly shows 0% -> 100% instead of lingering.
                    self.root.after(0, lambda: self.progress_var.set(0))
                    continue

                # 3) Item-finished marker (TAB separated, from --print after_move).
                if raw.startswith("__DONE__\t") or raw.startswith("__DONE__ "):
                    parts = raw.split("\t")
                    if len(parts) >= 2:
                        done_ids.add(parts[1].strip())
                    # When a video finishes, reset the per-video progress bar
                    # to 0 so the next video shows 0% -> 100% clearly.
                    self.root.after(0, lambda: self.progress_var.set(0))
                    self._log(raw)
                    continue

                # Remember error-looking lines for the final summary.
                raw_lower = raw.lower()
                if any(k in raw_lower for k in ("error", "warning:", "timed out",
                                                "connection reset", "forbidden",
                                                "not available", "failed",
                                                "http error 4", "http error 5")):
                    last_error_lines.append(raw)
                    if len(last_error_lines) > 40:
                        last_error_lines.pop(0)
                self.root.after(0, lambda l=raw: self._log(l))

            process.wait()

            # Diagnostics — this tells us if progress output was ever seen so
            # the user can tell whether the bar was genuinely stuck or just
            # that the download finished very fast.
            if not any_progress_seen:
                self.root.after(0, lambda: self._log(
                    "[progress] ⚠ 未收到任何进度输出。如果视频实际上在下载，请把日志发给开发者。"
                ))

            # Determine which (if any) items failed.  For a single-video URL,
            # returncode==0 is accurate enough; for playlists we cross-check
            # started_items against done_ids so a single failure won't look
            # like the whole batch failed.
            failed_items = [(vid, idx, title) for (vid, idx, title) in started_items
                            if vid not in done_ids]

            total_started = len(started_items)
            total_done = len(done_ids.intersect(vid for (vid, _, _) in started_items)) \
                if started_items else (0 if process.returncode else 0)

            # Fallback for single-video (non-traverse) mode
            if not traverse and not started_items:
                if process.returncode == 0:
                    self.root.after(0, self._on_download_done)
                else:
                    err_msg = "yt-dlp exited with error."
                    if last_error_lines:
                        err_msg += "\n\n最近的错误信息:\n" + "\n".join(last_error_lines[-10:])
                    self.root.after(0, lambda: self._on_download_error(err_msg))
                return

            # Playlist / traverse summary
            if process.returncode == 0 and not failed_items:
                self.root.after(0, self._on_download_done)
            else:
                total_success = (total_started - len(failed_items)) if started_items else (
                    0 if process.returncode else 1)

                summary_parts = []
                if failed_items:
                    summary_parts.append(f"失败项目 ({len(failed_items)}):")
                    for vid, idx, title in failed_items[:20]:
                        tag = f"#{idx}" if idx else vid
                        summary_parts.append(f"  - {tag} {title}")
                    if len(failed_items) > 20:
                        summary_parts.append(f"  ... 还有 {len(failed_items) - 20} 个")
                if last_error_lines:
                    summary_parts.append("\n最近的错误日志:")
                    summary_parts.extend(last_error_lines[-8:])

                hint = ""
                if any("timed out" in l.lower() or "connection" in l.lower() for l in last_error_lines):
                    hint = "\n\n[网络问题] 建议：稍后重试下载，已下载内容会被自动跳过。"
                elif any("403" in l or "forbidden" in l.lower() or "bot" in l.lower() for l in last_error_lines):
                    hint = "\n\n[YouTube 风控] 建议：使用代理或配置 Cookie 文件后重试。"

                final_msg = (
                    f"yt-dlp 下载完成 (成功: {total_success}, 失败: {len(failed_items)})."
                    f"{hint}\n\n" + "\n".join(summary_parts)
                )
                # Even on partial failure, call the done callback so the UI
                # becomes responsive again; then show the summary on top.
                self.root.after(0, lambda: self._on_download_partial(final_msg))

        except FileNotFoundError:
            self.root.after(0, lambda: self._on_download_error(
                "yt-dlp not found. Please run:  pip install yt-dlp"))
        except Exception as e:
            self.root.after(0, lambda: self._on_download_error(str(e)))

    def _on_download_partial(self, summary):
        """Called when a playlist download finishes with some failures.

        Resets UI state like _on_download_done but also shows the detailed
        failure summary so the user knows which videos to retry.
        """
        self.downloading = False
        self.btn_download.configure(state="normal")
        self.progress_var.set(100)
        self._set_status("Download finished (部分失败).")
        self._log("Download finished — 部分项目失败，请查看上方日志。")
        messagebox.showwarning("Download (部分失败)", summary)

    def _on_download_done(self):
        self.downloading = False
        self.btn_download.configure(state="normal")
        self.progress_var.set(100)
        self._set_status("Download complete!")
        self._log("Download complete!")
        messagebox.showinfo("Success", "Video downloaded successfully!")


# ------------------------------------------------------------------ main
def main():
    root = tk.Tk()
    app = VideoDownloader(root)
    root.mainloop()


if __name__ == "__main__":
    main()
