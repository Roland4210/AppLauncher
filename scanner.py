"""
Phase 1: 软件扫描器
==================
扫描 Windows 系统中安装的软件，来源：
  1. 注册表卸载信息
  2. 开始菜单快捷方式 (.lnk → 解析为 exe)
  3. 常见安装目录 (扫 exe)

输出: JSON 文件，每条记录包含名称、exe路径、来源
"""

import os
import json
import struct
import subprocess
import winreg
from datetime import datetime
import i18n; T = i18n.t

# ============================================================
#  工具函数
# ============================================================

def _resolve_shortcuts_batch(lnk_paths: list[str]) -> dict[str, str]:
    """批量解析 .lnk 快捷方式 (一次 PowerShell 调用) → {lnk_path: target}"""
    if not lnk_paths:
        return {}

    # 构建批处理脚本 (普通字符串，$ 是 PowerShell 变量，{ 直接写)
    script_lines = ['$ws=New-Object -ComObject WScript.Shell']
    for i, p in enumerate(lnk_paths):
        safe = p.replace("'", "''")
        line = (
            "$t=$ws.CreateShortcut('" + safe + "').TargetPath;"
            "if($t){Write-Host('RESULT" + str(i) + "='+$t)}"
        )
        script_lines.append(line)
    script = ";".join(script_lines)

    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        targets = {}
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("RESULT") and "=" in line:
                # "RESULT0=C:\path\to\target.exe"
                prefix, target = line.split("=", 1)
                idx_str = prefix.replace("RESULT", "")
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                if 0 <= idx < len(lnk_paths) and target and os.path.isfile(target):
                    targets[lnk_paths[idx]] = target
        return targets
    except Exception:
        return {}


def _find_exes(root: str, max_depth: int = 2) -> list[str]:
    """递归查找目录中的 .exe 文件"""
    exes = []
    try:
        for entry in os.scandir(root):
            if entry.is_file() and entry.name.lower().endswith(".exe"):
                exes.append(entry.path)
            elif entry.is_dir() and max_depth > 0 and not entry.name.startswith("."):
                exes.extend(_find_exes(entry.path, max_depth - 1))
    except (PermissionError, OSError):
        pass
    return exes


# PE 文件的子系统类型
IMAGE_SUBSYSTEM_WINDOWS_GUI = 2   # 有窗口的主程序
IMAGE_SUBSYSTEM_WINDOWS_CUI = 3   # 控制台程序 (通常是 helper/工具)


def _is_gui_app(exe_path: str) -> bool | None:
    """读 PE 头，判断是否是 GUI 程序。失败时返回 None（不确定）"""
    try:
        with open(exe_path, "rb") as f:
            # DOS 头 → 找到 PE 签名位置
            dos = f.read(64)
            if len(dos) < 64 or dos[:2] != b"MZ":
                return None
            pe_offset = struct.unpack("<I", dos[0x3C:0x40])[0]

            # 跳到 PE 签名
            f.seek(pe_offset)
            if f.read(4) != b"PE\x00\x00":
                return None

            # COFF 头 (20) + Optional 头前 70 字节
            f.read(20)
            opt = f.read(70)
            if len(opt) < 70:
                return None

            # PE32 和 PE32+ 的 Subsystem 都在 offset 68
            subsystem = struct.unpack("<H", opt[68:70])[0]
            return subsystem == IMAGE_SUBSYSTEM_WINDOWS_GUI
    except Exception:
        return None


def _exe_name(path: str) -> str:
    """提取 exe 文件名 (不含扩展名)"""
    return os.path.splitext(os.path.basename(path))[0]


# ============================================================
#  来源1: 注册表
# ============================================================

REGISTRY_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def scan_registry() -> list[dict]:
    """扫描注册表 → 返回软件列表"""
    apps = []

    for hive, subkey in REGISTRY_PATHS:
        try:
            key = winreg.OpenKey(hive, subkey)
        except OSError:
            continue

        i = 0
        while True:
            try:
                sk_name = winreg.EnumKey(key, i)
                i += 1
            except OSError:
                break

            try:
                app_key = winreg.OpenKey(key, sk_name)
            except OSError:
                continue

            try:
                info = _read_reg_entry(app_key)
            finally:
                winreg.CloseKey(app_key)

            if info:
                apps.append(info)

        winreg.CloseKey(key)

    return apps


def _read_reg_entry(key) -> dict | None:
    """读一个注册表子键"""
    def gv(n):
        try:
            v = winreg.QueryValueEx(key, n)[0]
            if isinstance(v, int):
                return str(v)
            if isinstance(v, list):
                return v[0] if v else ""
            if not isinstance(v, str):
                return str(v) if v is not None else None
            return v
        except OSError:
            return None

    name = gv("DisplayName")
    if not name:
        return None

    install_path = gv("InstallLocation") or gv("InstallDir") or ""
    icon = gv("DisplayIcon") or ""

    return {
        "name": name.strip(),
        "version": gv("DisplayVersion") or "",
        "publisher": gv("Publisher") or "",
        "install_path": install_path,
        "display_icon": icon,
        "uninstall_string": gv("UninstallString") or "",
    }


# ============================================================
#  来源2: 开始菜单快捷方式 (.lnk)
# ============================================================

START_MENU_DIRS = [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
]


def scan_shortcuts() -> list[dict]:
    """扫描所有开始菜单 .lnk，批量解析 exe 路径"""
    # 收集所有候选 .lnk
    lnk_files = []
    for base_dir in START_MENU_DIRS:
        if not os.path.isdir(base_dir):
            continue
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                if not f.lower().endswith(".lnk"):
                    continue
                if "uninstall" in f.lower() or "卸载" in f:
                    continue
                lnk_files.append(os.path.join(root, f))

    # 批量解析 (一次 PowerShell, 比逐个解析快 50+ 倍)
    targets = _resolve_shortcuts_batch(lnk_files)

    results = []
    for lnk_path in lnk_files:
        target = targets.get(lnk_path)
        if target:
            tlower = target.lower()
            if "\\windows\\system32\\" in tlower or "\\windows\\syswow64\\" in tlower:
                continue
            results.append({
                "name": os.path.splitext(os.path.basename(lnk_path))[0],
                "exe_path": target,
                "shortcut_path": lnk_path,
            })

    return results


# ============================================================
#  来源3: 扫描安装目录 (找绿色/便携软件)
# ============================================================

# 排除目录: 这些目录名下的 exe 不认为是用户软件
SYSTEM_DIR_NAMES = {
    # Windows 系统
    "windows", "windows defender", "internet explorer", "windows mail",
    "windows nt", "windows media player", "windows photo viewer",
    "windows portable devices", "windows security", "windowsapps",
    "windowspowershell", "windows kits", "package cache",
    # 系统容器（不是软件，是组织目录）
    "program files", "program files (x86)", "programdata",
    "users", "user", "documents and settings",
    "public", "default", "desktop", "downloads",
    # 开发工具链
    "microsoft sql server", "microsoft analysis services",
    "microsoft asp.net", "microsoft.net", "microsoft sdks",
    "microsoft visual studio", "reference assemblies", "msbuild",
    "dotnet", "common7", "iis", "iis express",
    # 驱动和硬件
    "drivers", "driver", "intel", "amd", "nvidia", "realtek",
    "dell", "hp", "lenovo", "msi", "asrock", "gigabyte",
    # 通用
    "node_modules", ".git", "__pycache__", "logs", "temp", "tmp",
    "cache", ".idea", ".vscode", "install", "common files",
    "$recycle.bin", "system volume information", "recovery",
    "boot", "efi", "perflogs", "python",
    # Microsoft 子目录（不是独立软件）
    "microsoft", "microsoft shared", "microsoft edge", "microsoft office",
    "microsoft onedrive", "microsoft teams",
}


def load_config(config_path: str = "scan_config.json") -> dict:
    """读取配置文件（可选）"""
    if not os.path.isfile(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_all_scan_roots() -> list[str]:
    """自动发现所有需要扫描的根目录。

    策略:
      1. 所有盘符的根目录 (C:\, D:\, E:\...) 的子目录
      2. 常见安装位置
      3. 用户的 Desktop / Downloads（很多人放绿色软件）
    不会全盘递归，只扫描每个目录的下一级。
    """
    roots = set()

    # 1. 所有盘符
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.isdir(drive):
            roots.add(drive)

    # 2. 固定安装位置
    roots.add(os.path.expandvars(r"%ProgramFiles%"))
    roots.add(os.path.expandvars(r"%ProgramFiles(x86)%"))
    roots.add(os.path.expandvars(r"%LOCALAPPDATA%\Programs"))

    # 3. 用户常用目录
    for var in [r"%USERPROFILE%\Desktop", r"%USERPROFILE%\Downloads",
                r"%APPDATA%", r"%LOCALAPPDATA%"]:
        path = os.path.expandvars(var)
        if os.path.isdir(path):
            roots.add(path)

    return sorted(roots)


def scan_directories(config: dict = None) -> list[dict]:
    """自动扫描系统中所有可启动的软件。不需要用户配置目录。"""
    if config is None:
        config = {}

    results = []
    seen_names = set()
    seen_exe_paths = set()

    max_depth = config.get("scan_depth", 3)
    extra_dirs = [os.path.normpath(d) for d in config.get("extra_scan_dirs", [])]

    # 收集所有扫描起点
    scan_roots = _get_all_scan_roots()
    for extra in extra_dirs:
        if extra not in scan_roots:
            scan_roots.append(extra)

    for root in scan_roots:
        if not os.path.isdir(root):
            continue

        try:
            # 如果是盘符根目录 (C:\)，扫描其子目录而非自身
            if len(root) == 3 and root[1] == ":":
                for entry in os.scandir(root):
                    if not entry.is_dir():
                        continue
                    if entry.name.lower() in SYSTEM_DIR_NAMES:
                        continue
                    _collect_apps_from_dir(
                        entry.path, max_depth, results,
                        seen_names, seen_exe_paths
                    )
            else:
                # 扫描该目录下的子目录
                for entry in os.scandir(root):
                    if not entry.is_dir():
                        continue
                    if entry.name.lower() in SYSTEM_DIR_NAMES:
                        continue
                    _collect_apps_from_dir(
                        entry.path, max_depth, results,
                        seen_names, seen_exe_paths
                    )
        except (PermissionError, OSError):
            continue

    return results


def _collect_apps_from_dir(path: str, max_depth: int,
                           results: list, seen_names: set, seen_paths: set):
    """从单个目录递归找 exe，找到就记录为一个应用"""
    exes = _find_exes(path, max_depth=max_depth)
    if not exes:
        return

    # 跳过卸载程序文件夹
    if any(w in path.lower() for w in ["uninstall", "unins", "卸载"]):
        return

    dir_name = os.path.basename(path)

    # 选主程序（优先名称匹配 + GUI）
    main_exe = _pick_main_exe(exes, dir_name)

    exe_key = main_exe.lower()
    if exe_key in seen_paths:
        return
    seen_paths.add(exe_key)

    # 跳过工具型 exe
    mname = _exe_name(main_exe).lower()
    if any(skip in mname for skip in
           ["uninstall", "unins", "update", "setup", "crashpad",
            "install", "cleanup", "migrate", "wizard", "troubleshoot",
            "worker", "broker", "elevation", "notifier", "watcher",
            "daemon", "service", "ffmpeg", "elevate", "clipboard",
            "setfta"]):
        return

    if mname in seen_names:
        return
    seen_names.add(mname)

    results.append({
        "name": dir_name,
        "exe_path": main_exe,
        "shortcut_path": "",
    })


# ============================================================
#  合并 & 去重
# ============================================================

def _pick_main_exe(exes: list[str], app_name: str) -> str | None:
    """从一堆 exe 中选出主程序。

    策略（按优先级）:
      1. GUI 程序（PE 头 Subsystem=2）—— 最可靠
      2. 名称精确匹配
      3. 名称包含匹配
      4. GUI 程序中选择最大的
      5. 最大的非 helper exe
      6. 第一个
    """
    if not exes:
        return None

    # 先分类: GUI vs 非 GUI
    gui_exes = [e for e in exes if _is_gui_app(e) is True]

    # 如果有 GUI 程序，优先从里面选
    pool = gui_exes if gui_exes else exes

    app_name_lower = app_name.lower().replace("-", "").replace("_", "")
    name_words = set(app_name_lower.split())  # ["google", "chrome"]

    # 1. 精确名称匹配（无视空格）
    app_name_nospace = app_name_lower.replace(" ", "")
    for exe in pool:
        base = os.path.basename(exe).lower()
        base_noext = base.replace(".exe", "")
        if base_noext == app_name_nospace:
            return exe

    # 2a. 单词精确匹配：exe 名 = 软件名的某个词
    for exe in pool:
        base_noext = os.path.basename(exe).lower().replace(".exe", "")
        for word in name_words:
            if len(word) >= 3 and word == base_noext:
                return exe

    # 2b. 包含匹配
    for exe in pool:
        base_noext = os.path.basename(exe).lower().replace(".exe", "")
        if app_name_nospace in base_noext or base_noext in app_name_nospace:
            return exe
        for word in name_words:
            if len(word) >= 3 and word in base_noext and base_noext.startswith(word):
                return exe

    # 3. 过滤 helper/service 后选最大的
    skip_words = ["helper", "update", "crash", "unins", "setup", "service",
                  "migrate", "wizard", "troubleshoot", "worker", "broker",
                  "elevation", "notifier", "telemetry", "watcher", "daemon",
                  "ffmpeg", "elevate", "clipboard", "setfta"]
    candidates = [e for e in pool if not any(
        w in os.path.basename(e).lower() for w in skip_words
    )]

    if candidates:
        try:
            candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
        except OSError:
            pass
        return candidates[0]

    return pool[0]


def _extract_exes_from_app(app: dict) -> list[str]:
    """从注册表条目中提取所有可能的 exe 路径"""
    exes = []
    seen = set()

    def add(p):
        if p and os.path.isfile(p) and p.lower() not in seen:
            exes.append(p)
            seen.add(p.lower())

    # 1. 从安装目录扫描
    install_path = app.get("install_path", "")
    if install_path and os.path.isdir(install_path):
        for e in _find_exes(install_path, max_depth=2):
            add(e)

    # 2. 从 DisplayIcon 提取
    icon = app.get("display_icon", "")
    if icon:
        # "D:\app\main.exe,0" → 取 exe 部分
        icon_path = icon.strip('"').rsplit(",", 1)[0]
        if icon_path.lower().endswith(".exe"):
            add(icon_path)
        elif icon_path.lower().endswith(".ico"):
            # 同目录下找同名 exe
            icon_dir = os.path.dirname(icon_path)
            if os.path.isdir(icon_dir):
                for e in _find_exes(icon_dir, max_depth=0):
                    add(e)

    # 3. MSI 包、系统组件 → 跳过（无可用 exe）
    uninstall = app.get("uninstall_string", "")
    if uninstall and ("MsiExec.exe" in uninstall and not install_path):
        return []  # 纯 MSI 包，不是用户软件

    return exes


def merge_and_dedupe(registry_apps: list[dict],
                     shortcut_apps: list[dict],
                     dir_apps: list[dict]) -> list[dict]:
    """
    合并三个来源，去重策略:
      - 按 exe 路径去重
      - 注册表信息覆盖目录/快捷方式信息（更完整）
      - 每个应用只保留主程序 exe
    """
    unified = {}

    # --- 第1步: 目录扫描 & 快捷方式 ---
    for src_list, src_label in [(dir_apps, "directory"), (shortcut_apps, "shortcut")]:
        for item in src_list:
            exe_key = item["exe_path"].lower()
            if exe_key not in unified:
                unified[exe_key] = {
                    "name": item["name"],
                    "exe_path": item["exe_path"],
                    "version": "",
                    "publisher": "",
                    "install_path": os.path.dirname(item["exe_path"]),
                    "source": src_label,
                }

    # 构建: 目录 → 快捷方式指向的 exe 列表
    shortcut_exe_by_dir: dict[str, list[str]] = {}
    for sc in shortcut_apps:
        d = os.path.dirname(sc["exe_path"]).lower()
        shortcut_exe_by_dir.setdefault(d, []).append(sc["exe_path"])

    # --- 第2步: 注册表覆盖 ---
    for app in registry_apps:
        reg_exes = _extract_exes_from_app(app)

        # 同目录下的快捷方式 exe 也加入候选池
        install_path = app.get("install_path", "")
        if install_path:
            nearby_scs = shortcut_exe_by_dir.get(install_path.lower(), [])
        else:
            nearby_scs = []
        reg_exes.extend(nearby_scs)

        main_exe = _pick_main_exe(reg_exes, app["name"])
        if not install_path and main_exe:
            install_path = os.path.dirname(main_exe)

        if main_exe:
            exe_key = main_exe.lower()
            if exe_key in unified:
                # 注册表信息覆盖
                unified[exe_key].update({
                    "name": app["name"],
                    "version": app["version"],
                    "publisher": app["publisher"],
                    "install_path": app["install_path"] or unified[exe_key]["install_path"],
                    "source": "registry",
                })
            else:
                unified[exe_key] = {
                    "name": app["name"],
                    "exe_path": main_exe,
                    "version": app["version"],
                    "publisher": app["publisher"],
                    "install_path": install_path,
                    "source": "registry",
                }
        elif install_path and os.path.isdir(install_path):
            # 有安装目录但没找到 exe，保留参考
            key = install_path.lower()
            if key not in unified:
                unified[key] = {
                    "name": app["name"],
                    "exe_path": "",
                    "version": app["version"],
                    "publisher": app["publisher"],
                    "install_path": install_path,
                    "source": "registry_no_exe",
                }

    # 后处理: 同名保留信息最完整的
    results = list(unified.values())
    by_name = {}
    for app in results:
        key = app["name"].lower()
        if key not in by_name:
            by_name[key] = app
        else:
            # 保留有 exe_path 且文件存在的
            old_exe = by_name[key].get("exe_path", "")
            new_exe = app.get("exe_path", "")
            if new_exe and os.path.isfile(new_exe) and (not old_exe or not os.path.isfile(old_exe)):
                by_name[key] = app
            elif app.get("version") and not by_name[key].get("version"):
                by_name[key]["version"] = app["version"]
            elif app.get("install_path") and not by_name[key].get("install_path"):
                by_name[key]["install_path"] = app["install_path"]
    return list(by_name.values())


# ============================================================
#  主流程
# ============================================================

def run_scan(config_path: str = "scan_config.json") -> dict:
    config = load_config(config_path)

    # 自动发现盘符
    drives = [f"{l}:\\" for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{l}:\\")]
    extra = config.get("extra_scan_dirs", [])
    print(f"{T('drives_found')}: {', '.join(drives)}  ({T('auto_discover')})")
    if extra:
        print(T("extra_dirs_count", count=len(extra)))

    print("=" * 50)
    print(f"  {T('scan_title')}")
    print("=" * 50)

    print(f"\n[1/4] {T('scan_registry')}...")
    registry_apps = scan_registry()
    print(f"      {T('scan_result_registry', count=len(registry_apps))}")

    print(f"[2/4] {T('scan_shortcuts')}...")
    shortcut_apps = scan_shortcuts()
    print(f"      {T('scan_result_shortcuts', count=len(shortcut_apps))}")

    print(f"[3/4] {T('scan_dirs')}...")
    dir_apps = scan_directories(config)
    print(f"      {T('scan_result_dirs', count=len(dir_apps))}")

    print(f"[4/4] {T('scan_merge')}...")
    merged = merge_and_dedupe(registry_apps, shortcut_apps, dir_apps)
    print(f"      {T('scan_result_merged', count=len(merged))}")

    # 统计各来源
    sources = {}
    for app in merged:
        s = app.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1

    result = {
        "scan_time": datetime.now().isoformat(),
        "total_apps": len(merged),
        "sources_breakdown": sources,
        "apps": merged,
    }

    return result


def export_json(result: dict, filepath: str = None):
    if filepath is None:
        filepath = "scan_result.json"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"\n{T('scan_export_failed')}: {e}")
        return

    print(f"\n{T('scan_exported')}: {os.path.abspath(filepath)}")
    print(T("scan_result_total", count=result['total_apps']))
    for src, count in result["sources_breakdown"].items():
        print(f"  - {src}: {count}")
    print()


if __name__ == "__main__":
    result = run_scan()
    export_json(result)
