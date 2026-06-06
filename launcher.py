"""
Phase 2: 软件启动器
==================
读取 scan_result.json 和 workflows.json，一键批量启动软件。
"""

import json
import os
import sys
import subprocess
import time
import i18n; T = i18n.t

# Windows GBK 终端兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # 启用 ANSI 颜色支持 (Windows 10 1903+)
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ANSI 颜色
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_GRAY = "\033[90m"
C_YELLOW = "\033[93m"
C_RESET = "\033[0m"


def load_scan_data(filepath: str = "scan_result.json") -> list[dict]:
    """加载扫描结果"""
    if not os.path.isfile(filepath):
        print(T("scan_file_not_found", path=filepath))
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("apps", [])


def load_workflows(filepath: str = "workflows.json") -> dict:
    """加载工作流配置"""
    if not os.path.isfile(filepath):
        print(T("scan_no_workflows_file", path=filepath))
        print(T("scan_create_workflows_hint", path=filepath))
        print(T("scan_reference_example"))
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(T("scan_bad_json_format", path=filepath))
        print(f"  {e}")
        return {}


def find_app(apps: list[dict], query: str) -> dict | None:
    """模糊匹配软件名 → 返回软件条目"""
    q = query.lower().strip()

    # 精确匹配
    for app in apps:
        if app["name"].lower() == q:
            return app

    # 包含匹配
    for app in apps:
        if q in app["name"].lower():
            return app

    # 关键词拆分匹配
    q_words = set(q.split())
    for app in apps:
        app_words = set(app["name"].lower().split())
        if q_words & app_words:
            return app

    return None


def launch_app(app: dict) -> bool:
    """启动单个软件 (控制台程序获得独窗, GUI 不受影响)"""
    exe = app.get("exe_path", "")
    if not exe or not os.path.isfile(exe):
        print(T("skip_no_exe_detail", name=app['name'], path=exe))
        return False

    try:
        flags = 0
        if os.name == "nt":
            flags = 0x00000010  # CREATE_NEW_CONSOLE — GUI忽略, 控制台获新窗

        subprocess.Popen(
            [exe],
            cwd=os.path.dirname(exe),
            creationflags=flags,
        )

        print(f"  {C_GREEN}{T('launched')}:{C_RESET} {C_CYAN}{app['name']}{C_RESET}")
        return True
    except Exception as e:
        print(f"  {T('launch_failed')} {app['name']}: {e}")
        return False


def run_workflow(workflow_name: str):
    """执行一个工作流"""
    apps = load_scan_data()
    if not apps:
        return

    workflows = load_workflows()
    if not workflows:
        return

    wf = workflows.get(workflow_name)
    if wf is None:
        available = ", ".join(workflows.keys())
        print(T("workflow_name_not_found", name=workflow_name))
        print(f"{T('workflow_available')}: {available}")
        return

    mode = wf.get("mode", "parallel")
    delay = wf.get("delay", 0)
    app_names = wf.get("apps", [])

    if not app_names:
        print(T("workflow_name_empty", name=workflow_name))
        return

    mode_label = T("parallel") if mode == "parallel" else T("sequential")
    print(f"\n{'=' * 50}")
    print(f"  {T('starting_workflow')}: {workflow_name}")
    print(f"  {T('mode_label')}: {mode_label}" + (T("mode_interval", delay=delay) if delay else ""))
    print(f"{'=' * 50}\n")

    # 解析软件名 → 找到 exe
    targets = []
    not_found = []

    for name in app_names:
        app = find_app(apps, name)
        if app and app.get("exe_path"):
            targets.append(app)
        else:
            not_found.append(name)

    if not_found:
        print(f"{T('not_found')}: {', '.join(not_found)}")
        print(T("hint_run_apps_list") + "\n")

    if not targets:
        print(T("no_launchable"))
        return

    # 启动
    ok = 0
    for app in targets:
        if launch_app(app):
            ok += 1
            if mode == "sequential":
                time.sleep(1)
        if delay > 0 and mode == "parallel" and ok < len(targets):
            time.sleep(delay)

    print(f"\n{T('launch_complete')}: {ok}/{len(targets)}")


def list_available_apps(show_path: bool = False):
    """列出可启动的软件名 (按字母排序，按来源分组)"""
    apps = load_scan_data()
    if not apps:
        return

    apps.sort(key=lambda a: a["name"].lower())

    grouped = {}
    for app in apps:
        src = app.get("source", "unknown")
        grouped.setdefault(src, []).append(app)

    print(f"\n{T('available_n_soft', count=len(apps))}:\n")

    for src in sorted(grouped):
        print(f"  {C_GRAY}[{src}]{C_RESET}")
        for app in grouped[src]:
            exe = app.get("exe_path", "")
            install = app.get("install_path", "")
            if exe and show_path:
                print(f"    {C_CYAN}{app['name']}{C_RESET}")
                print(f"      {C_GRAY}{os.path.dirname(exe)}{C_RESET}")
            elif not exe:
                print(f"    {C_GRAY}{app['name']} {T('no_exe_label')}{C_RESET}")
            else:
                print(f"    {C_CYAN}{app['name']}{C_RESET}")
        print()

    if not show_path:
        print(T("hint_view_path"))
        print("      " + T("hint_quick_launch"))


def list_workflows():
    """列出所有工作流"""
    workflows = load_workflows()
    if not workflows:
        return

    print(f"\n{T('configured_n_workflows', count=len(workflows))}:\n")
    for name, wf in workflows.items():
        apps = wf.get("apps", [])
        mode = wf.get("mode", "parallel")
        delay = wf.get("delay", 0)
        mode_label = T("parallel") if mode == "parallel" else T("sequential")
        print(f"  {C_CYAN}{name}{C_RESET}")
        print(f"    {T('mode_label')}: {mode_label}" + (T("mode_interval", delay=delay) if delay else ""))
        print(f"    {T('software')}: {', '.join(apps)}")
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "apps":
            list_available_apps()
        elif cmd == "list":
            list_workflows()
        else:
            run_workflow(cmd)
    else:
        print(T("usage"))
        print(T("usage_launcher"))
        print(T("usage_apps"))
        print(T("usage_list"))
