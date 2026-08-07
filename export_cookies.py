"""
Chrome Cookie Exporter for yt-dlp
==================================
导出 Chrome 中的 YouTube/Google Cookie 供 yt-dlp 使用。

重要说明：
- Chrome v127+ 引入了 AppBound 加密（v20），普通用户权限无法解密
- 本脚本只能导出 v10 加密的 Cookie（约 14 个）
- 如果导出的 Cookie 不够用，请使用浏览器扩展方案

使用方法：
1. 完全关闭 Chrome（Ctrl+Shift+Esc 打开任务管理器，结束所有 chrome.exe 进程）
2. 双击运行本脚本
3. 生成的 cookies.txt 可在下载器中使用

替代方案（推荐）：
- 安装扩展 "Get cookies.txt LOCALLY" (https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- 在 YouTube 页面点击扩展图标导出
"""
import os, sys, json, base64, tempfile, shutil, sqlite3
import ctypes
import ctypes.wintypes
from Cryptodome.Cipher import AES

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def _crypt_unprotect_data(encrypted_value, is_key=False):
    """Decrypt DPAPI data."""
    entropy = ctypes.c_void_p()
    entropy_ref = ctypes.POINTER(ctypes.c_void_p)(entropy)
    blob_in = DATA_BLOB(len(encrypted_value), ctypes.cast(
        ctypes.create_string_buffer(encrypted_value), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    desc = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    prompt_struct = ctypes.c_void_p()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), ctypes.byref(desc), entropy_ref, None,
        ctypes.byref(prompt_struct), CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
    ):
        raise RuntimeError('Failed to decrypt the cipher text with DPAPI')
    buffer_out = ctypes.create_string_buffer(int(blob_out.cbData))
    ctypes.memmove(buffer_out, blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    if is_key:
        return buffer_out.raw
    else:
        return buffer_out.value


def get_encryption_key():
    """Get the v10 AES key from Chrome's Local State."""
    local_state = os.path.join(
        os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Local State'
    )
    with open(local_state, 'r', encoding='utf-8') as f:
        data = json.load(f)
    encrypted_key = base64.b64decode(data['os_crypt']['encrypted_key'])[5:]
    return _crypt_unprotect_data(encrypted_key, is_key=True)


def decrypt_cookie_v10(encrypted_value, key):
    """Decrypt a Chrome v10 encrypted cookie value."""
    if not encrypted_value or len(encrypted_value) < 15:
        return ''
    if encrypted_value[:3] != b'v10':
        return ''
    enc_stripped = encrypted_value[3:]
    nonce = enc_stripped[:12]
    tag = enc_stripped[-16:]
    ciphertext = enc_stripped[12:-16]
    aes = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        data = aes.decrypt_and_verify(ciphertext, tag)
        if len(data) > 32:
            data = data[32:]
        return data.decode('utf-8', errors='replace')
    except (ValueError, Exception):
        return ''


def main():
    print('=== Chrome Cookie Exporter for yt-dlp ===')
    print()

    # Check Chrome status
    import subprocess
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                          capture_output=True, text=True)
    chrome_running = 'chrome.exe' in result.stdout.lower()
    
    if chrome_running:
        print('WARNING: Chrome is still running!')
        print('         Please close ALL Chrome windows and try again.')
        print('         (Or use the browser extension method instead)')
        print()
        choice = input('Continue anyway? (y/N): ').strip().lower()
        if choice != 'y':
            sys.exit(0)

    # Get key
    try:
        key = get_encryption_key()
        print(f'[OK] v10 AES key: {len(key)} bytes')
    except Exception as e:
        print(f'[ERROR] Cannot get encryption key: {e}')
        sys.exit(1)

    # Copy cookie database
    cookie_file = os.path.join(
        os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default', 'Network', 'Cookies'
    )
    tmp = os.path.join(tempfile.gettempdir(), 'yt_cookies_db')
    try:
        shutil.copy2(cookie_file, tmp)
        print('[OK] Cookie database copied.')
    except PermissionError:
        print('[ERROR] Chrome is locking the database. Close all Chrome windows first.')
        sys.exit(1)

    # Read and export cookies
    conn = sqlite3.connect(tmp)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly "
        "FROM cookies WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google.com%' "
        "OR host_key LIKE '%accounts.google%'"
    )
    rows = cursor.fetchall()

    # Count v10 vs v20
    v10_count = sum(1 for _, _, _, enc, *_ in rows if enc and enc[:3] == b'v10')
    v20_count = sum(1 for _, _, _, enc, *_ in rows if enc and enc[:3] == b'v20')
    print(f'[INFO] Cookie rows: {len(rows)} total ({v10_count} v10, {v20_count} v20)')

    output = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    with open(output, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n')
        f.write('# Exported from Chrome for yt-dlp\n\n')
        count = 0
        for host, name, value, enc_val, path, expires, secure, httponly in rows:
            if not value and enc_val:
                if enc_val[:3] == b'v10':
                    value = decrypt_cookie_v10(enc_val, key)
                # v20 cookies cannot be decrypted without SYSTEM privileges
            if not value:
                continue
            if expires:
                unix_time = int(expires / 1000000) - 11644473600
                if unix_time < 0:
                    unix_time = 0
            else:
                unix_time = 0
            f.write(f'.{host}\tTRUE\t{path}\t{"TRUE" if secure else "FALSE"}\t{unix_time}\t{name}\t{value}\n')
            count += 1

    conn.close()
    try:
        os.remove(tmp)
    except Exception:
        pass

    abs_path = os.path.abspath(output)
    print(f'\n[DONE] Exported {count} cookies to:')
    print(f'       {abs_path}')

    if v20_count > 0:
        print(f'\n[NOTE] {v20_count} v20-encrypted cookies could NOT be decrypted.')
        print('       For full functionality, use the browser extension method:')
        print('       1. Install "Get cookies.txt LOCALLY" from Chrome Web Store')
        print('       2. Open YouTube, click the extension icon to export')
        print('       3. Select the exported file in the downloader')
    
    if count > 0:
        key_names = ['SID', 'HSID', 'SSID', 'SAPISID', 'LOGIN_INFO']
        key_cookies = []
        with open(output, 'r') as f:
            for line in f:
                for kn in key_names:
                    if f'\t{kn}\t' in line:
                        key_cookies.append(kn)
        if key_cookies:
            print(f'\n[OK] Found key auth cookies: {", ".join(key_cookies)}')
        else:
            print(f'\n[WARN] No key auth cookies (SID/HSID/SSID) exported.')
            print('       YouTube may still block some downloads.')

    print()
    print('Usage in downloader:')
    print('  1. Select "Cookie 文件..." in the Cookies dropdown')
    print(f'  2. Choose: {abs_path}')
    print('  3. Paste your YouTube URL and click "Fetch Available Qualities"')


if __name__ == '__main__':
    main()
