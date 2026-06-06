"""
AppLauncher - 主入口
====================
交互式命令行界面，双击 启动.bat 运行。
"""

import os
import sys
import json
import scanner
import launcher
import selector
import i18n; T = i18n.t


def _atomic_write_json(filepath, data):
    """原子写 JSON — 防止崩溃时损坏文件"""
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filepath)


C_CYAN = launcher.C_CYAN
C_GREEN = launcher.C_GREEN
C_GRAY = launcher.C_GRAY
C_YELLOW = launcher.C_YELLOW
C_RED = "\033[91m"
C_RESET = launcher.C_RESET


def show_menu():
    print()
    print(f"{C_CYAN}{'=' * 40}{C_RESET}")
    print(f"    {C_CYAN}{T('app_title')}{C_RESET}")
    print(f"{C_CYAN}{'=' * 40}{C_RESET}")
    print()
    print(f"  {C_GREEN}1{C_RESET}. {C_CYAN}{T('menu_scan')}{C_RESET}    {C_GRAY}({T('menu_scan_hint')}){C_RESET}")
    print(f"  {C_GREEN}2{C_RESET}. {C_CYAN}{T('menu_browse')}{C_RESET}    {C_GRAY}({T('menu_browse_hint')}){C_RESET}")
    print(f"  {C_GREEN}3{C_RESET}. {C_CYAN}{T('menu_launch')}{C_RESET}    {C_GRAY}({T('menu_launch_hint')}){C_RESET}")
    print(f"  {C_GREEN}4{C_RESET}. {C_RED}{T('menu_kill')}{C_RESET}    {C_GRAY}({T('menu_kill_hint')}){C_RESET}")
    print(f"  {C_GREEN}5{C_RESET}. {C_CYAN}{T('menu_workflow')}{C_RESET}  {C_GRAY}({T('menu_workflow_hint')}){C_RESET}")
    print(f"  {C_GRAY}0. {T('menu_exit')}{C_RESET}")
    print()
    return input(f"{C_GRAY}{T('please_select')}{C_RESET} [0-5]: ").strip()


def menu_scan():
    print()
    result = scanner.run_scan()
    scanner.export_json(result)
    input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")


def menu_apps():
    launcher.list_available_apps(show_path=True)
    input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")


# ===== 软件启动子菜单 =====

def menu_launch():
    while True:
        print()
        print(f"  {C_CYAN}--- {T('launch_title')} ---{C_RESET}")
        print(f"  {C_GREEN}1{C_RESET}. {C_CYAN}{T('quick_launch')}{C_RESET}    {C_GRAY}({T('quick_launch_hint')}){C_RESET}")
        print(f"  {C_GREEN}2{C_RESET}. {C_CYAN}{T('workflow_launch')}{C_RESET}  {C_GRAY}({T('workflow_launch_hint')}){C_RESET}")
        print(f"  {C_GRAY}0. {T('return_main')}{C_RESET}")
        print()
        choice = input(f"{T('please_select')} [0-2]: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            menu_quick_launch()
        elif choice == "2":
            menu_workflow_launch()
        else:
            print(T("invalid_choice"))


def menu_quick_launch():
    apps = launcher.load_scan_data()
    if not apps:
        input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")
        return

    valid_apps = [a for a in apps if a.get("exe_path")]
    valid_apps.sort(key=lambda a: a["name"].lower())
    names = [a["name"] for a in valid_apps]

    selected = selector.interactive_select(
        names,
        title=T("select_to_launch"),
        multi=False,
    )

    if not selected:
        return

    app = valid_apps[selected[0]]
    print()
    launcher.launch_app(app)
    input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")


def menu_workflow_launch():
    workflows = launcher.load_workflows()
    if not workflows:
        input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")
        return

    print()
    print(f"{T('available_workflows')}:")
    names = list(workflows.keys())
    for i, name in enumerate(names, 1):
        wf = workflows[name]
        apps = wf.get("apps", [])
        mode = wf.get("mode", "parallel")
        mode_label = T("parallel") if mode == "parallel" else T("sequential")
        app_list = ", ".join(apps)
        print(f"  {C_GRAY}{i}.{C_RESET} {C_CYAN}{name}{C_RESET} {C_GRAY}[{mode_label}]{C_RESET}")
        print(f"     {C_GRAY}-> {app_list}{C_RESET}")

    print()
    choice = input(f"{T('please_select')} [1-{len(names)}] (q={T('back')}): ").strip()
    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(names):
            launcher.run_workflow(names[idx])
    except ValueError:
        print(T("invalid_choice"))

    input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")


# ===== 关闭软件 =====

def menu_kill():
    apps = launcher.load_scan_data()
    if not apps:
        input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")
        return

    import subprocess
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        running = set()
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.replace('"', "").split(",")
                if len(parts) >= 1 and parts[0].strip().lower().endswith(".exe"):
                    running.add(parts[0].strip().lower())
    except Exception:
        running = set()

    matched = []
    for app in apps:
        exe = app.get("exe_path", "")
        if not exe:
            continue
        exe_name = os.path.basename(exe).lower()
        if exe_name in running:
            matched.append((app, exe_name))

    if not matched:
        print(f"\n{C_GRAY}{T('no_running_soft')}{C_RESET}")
        input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")
        return

    print(f"\n{C_YELLOW}{T('running_n_soft', count=len(matched))}{C_RESET}\n")
    for i, (app, exe_name) in enumerate(matched, 1):
        print(f"  {C_GRAY}{i}.{C_RESET} {C_CYAN}{app['name']}{C_RESET} {C_GRAY}({exe_name}){C_RESET}")
    print(f"  {C_GRAY}0. {T('back')}{C_RESET}")

    print()
    choice = input(f"{T('input_num_kill')}: ").strip()
    if choice == "0" or not choice:
        return

    choice = choice.replace("\uff0c", ",")
    targets = []
    for part in choice.split(","):
        part = part.strip()
        try:
            idx = int(part) - 1
            if 0 <= idx < len(matched):
                targets.append(matched[idx])
        except ValueError:
            for app, exe_name in matched:
                if part.lower() in app["name"].lower() or part.lower() in exe_name:
                    targets.append((app, exe_name))
                    break

    if not targets:
        print(f"{C_YELLOW}{T('no_match_process')}{C_RESET}")
        input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")
        return

    print(f"\n{C_YELLOW}{T('closing')}{C_RESET}")
    killed = 0
    for app, exe_name in targets:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", exe_name],
                capture_output=True, timeout=10,
            )
            print(f"  {C_GREEN}{T('killed')}{C_RESET} {C_CYAN}{app['name']}{C_RESET}")
            killed += 1
        except Exception as e:
            print(f"  {C_RED}{T('kill_failed')}{C_RESET} {app['name']}: {e}")

    print(f"\n{T('kill_done')}: {killed}/{len(targets)}")
    input(f"\n{C_GRAY}{T('press_enter_return')}{C_RESET}")


# ===== 管理工作流 =====

def menu_manage_workflows():
    while True:
        print()
        print(f"  {C_CYAN}--- {T('workflow_mgmt')} ---{C_RESET}")
        print(f"  {C_GREEN}1{C_RESET}. {C_CYAN}{T('view_workflows')}{C_RESET} {C_GRAY}{T('view_workflows_hint')}{C_RESET}")
        print(f"  {C_GREEN}2{C_RESET}. {C_CYAN}{T('create_workflow')}{C_RESET} {C_GRAY}{T('create_workflow_hint')}{C_RESET}")
        print(f"  {C_GREEN}3{C_RESET}. {C_RED}{T('delete_workflow')}{C_RESET} {C_GRAY}{T('delete_workflow_hint')}{C_RESET}")
        print(f"  {C_GRAY}0. {T('return_main')}{C_RESET}")
        print()
        choice = input(f"{T('please_select')} [0-3]: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            launcher.list_workflows()
            input(f"\n{C_GRAY}{T('press_enter_continue')}{C_RESET}")
        elif choice == "2":
            create_workflow_interactive()
        elif choice == "3":
            delete_workflow()
        else:
            print(T("invalid_choice"))


def create_workflow_interactive():
    apps = launcher.load_scan_data()
    if not apps:
        print(T("no_scan_first"))
        return

    valid_apps = [a for a in apps if a.get("exe_path")]
    valid_apps.sort(key=lambda a: a["name"].lower())
    names = [a["name"] for a in valid_apps]

    selected_idx = selector.interactive_select(
        names,
        title=T("select_soft_join"),
        multi=True,
    )

    if not selected_idx:
        print(f"\n{C_GRAY}{T('cancelled')}{C_RESET}")
        return

    app_names = [valid_apps[i]["name"] for i in selected_idx]

    print(f"\n{C_GREEN}{T('selected_n_soft', count=len(app_names))}{C_RESET}")
    for n in app_names:
        print(f"  {C_CYAN}{n}{C_RESET}")

    print()
    name = input(f"{T('workflow_name_prompt')}: ").strip()
    if not name:
        return

    mode = input(f"{T('launch_mode_prompt')}: ").strip().lower()
    mode = "sequential" if mode == "s" else "parallel"

    delay = 0
    if mode == "parallel":
        try:
            delay = int(input(f"{T('delay_prompt')}: ").strip() or "0")
        except ValueError:
            delay = 0

    workflows = launcher.load_workflows()
    if name in workflows:
        print(f"\n{C_YELLOW}{T('workflow_name_exists', name=name)}{C_RESET}")
        confirm = input(f"{T('overwrite_prompt')}: ").strip().lower()
        if confirm != "y":
            print(f"{C_GRAY}{T('cancelled')}{C_RESET}")
            return

    workflows[name] = {"apps": app_names, "mode": mode, "delay": delay}
    _atomic_write_json("workflows.json", workflows)
    print(f"\n{C_GREEN}{T('workflow_name_saved', name=name)}{C_RESET}")


def delete_workflow():
    workflows = launcher.load_workflows()
    if not workflows:
        print(T("no_workflow"))
        return

    print()
    names = list(workflows.keys())
    for i, name in enumerate(names, 1):
        print(f"  {C_GRAY}{i}.{C_RESET} {C_CYAN}{name}{C_RESET}")

    choice = input(f"\n{T('delete_confirm')} [1-{len(names)}] (q={T('back')}): ").strip()
    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(names):
            name = names[idx]
            del workflows[name]
            _atomic_write_json("workflows.json", workflows)
            print(f"{C_GREEN}{T('workflow_name_deleted', name=name)}{C_RESET}")
    except ValueError:
        print(T("invalid_choice"))


# ===== 主程序 =====

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "scan":
            menu_scan()
        elif cmd == "apps":
            menu_apps()
        elif cmd == "launch" and len(sys.argv) > 2:
            launcher.run_workflow(sys.argv[2])
        elif cmd == "launch":
            launcher.run_workflow("")
        elif cmd == "quick":
            menu_quick_launch()
        elif cmd == "kill":
            menu_kill()
        elif cmd == "help":
            print(f"{T('help_commands')}: scan | apps | quick | launch <name> | kill")
        return

    if not os.path.exists("scan_result.json"):
        print(T("first_scan"))
        result = scanner.run_scan()
        scanner.export_json(result)

    while True:
        choice = show_menu()

        if choice == "1":
            menu_scan()
        elif choice == "2":
            menu_apps()
        elif choice == "3":
            menu_launch()
        elif choice == "4":
            menu_kill()
        elif choice == "5":
            menu_manage_workflows()
        elif choice == "0":
            print(T("goodbye"))
            break
        else:
            print(T("invalid_choice"))


if __name__ == "__main__":
    main()
