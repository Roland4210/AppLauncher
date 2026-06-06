"""
交互式列表选择器
================
方向键↑↓移动, 空格选中/取消, 回车确认。
纯 Windows 原生 Console API, 零依赖。
"""

import sys
import msvcrt
import ctypes
import i18n; T = i18n.t

# 颜色
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_GRAY = "\033[90m"
C_RESET = "\033[0m"

_kernel32 = ctypes.windll.kernel32

class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


_saved_console_mode = None


def _enable_ansi():
    global _saved_console_mode
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            h = _kernel32.GetStdHandle(-11)
            buf = ctypes.create_string_buffer(4)
            _kernel32.GetConsoleMode(h, buf)
            _saved_console_mode = ctypes.c_uint.from_buffer(buf).value
            _kernel32.SetConsoleMode(h, 7)
        except Exception:
            pass


def _restore_console():
    """恢复原始控制台模式, 避免 input() 卡死"""
    global _saved_console_mode
    if _saved_console_mode is not None:
        try:
            _kernel32.SetConsoleMode(
                _kernel32.GetStdHandle(-11), _saved_console_mode)
        except Exception:
            pass
        _saved_console_mode = None


def _set_cursor_pos(y: int):
    """设置光标到指定行 (列0)"""
    _kernel32.SetConsoleCursorPosition(
        _kernel32.GetStdHandle(-11),
        _COORD(0, y),
    )


def _get_cursor_y() -> int:
    """获取当前光标行号"""
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(
        _kernel32.GetStdHandle(-11), buf)
    return ctypes.c_short.from_buffer(buf, 6).value


def _getch():
    ch = msvcrt.getch()
    if ch == b"\xe0":
        ch2 = msvcrt.getch()
        if ch2 == b"H":
            return "up"
        elif ch2 == b"P":
            return "down"
    elif ch == b"\r":
        return "enter"
    elif ch == b" ":
        return "space"
    elif ch == b"\x1b":
        return "escape"
    elif ch in (b"q", b"Q"):
        return "quit"
    elif ch.isdigit():
        return ch.decode()
    return None


def interactive_select(items: list[str],
                       title: str = "Select Software",
                       multi: bool = True,
                       ) -> list[int]:
    _enable_ansi()

    selected = set()
    cursor = 0
    page_size = 15
    start_y = 0

    if len(items) == 0:
        return []

    def w(s=""):
        """写入一行, 先清到行尾"""
        sys.stdout.write(f"\033[K{s}")
        if s:
            sys.stdout.write("\n")

    def draw():
        nonlocal cursor, start_y

        if start_y > 0:
            _set_cursor_pos(start_y)
        else:
            start_y = _get_cursor_y()

        page = cursor // page_size
        start = page * page_size
        end = min(start + page_size, len(items))

        w(f"  {C_CYAN}{title}{C_RESET}")
        w(f"  {C_GRAY}{'─' * 40}{C_RESET}")
        w(f"  {C_GRAY}  {T('selector_updown')}  {T('selector_space')}  {T('selector_enter')}  {T('selector_quit')}{C_RESET}")
        if not multi:
            w(f"  {C_GRAY}  {T('selector_single')}{C_RESET}")
        w()

        for i in range(start, end):
            if multi:
                mark = f"{C_GREEN}[✓]{C_RESET}" if i in selected else "[ ]"
                pre = f" {mark} "
            else:
                pre = f" {C_GRAY}{i+1:3d}.{C_RESET} "

            text = items[i]
            if len(text) > 60:
                text = text[:57] + "..."

            if i == cursor:
                w(f"  {C_CYAN}>>{pre}{text}{C_RESET}")
            elif i in selected:
                w(f"  {C_GREEN}  {pre}{text}{C_RESET}")
            else:
                w(f"     {pre}{C_GRAY}{text}{C_RESET}")

        w()
        if multi and selected:
            preview = ", ".join(items[i] for i in sorted(selected)[:3])
            if len(selected) > 3:
                preview += f" {T('selector_more_items', count=len(selected))}"
            w(f"  {C_GREEN}{T('selector_selected')}: {preview}{C_RESET}")
        elif multi:
            w(f"  {C_GRAY}{T('selector_none')}{C_RESET}")
        else:
            w()

        # 清到屏底
        sys.stdout.write("\033[J")
        sys.stdout.flush()

    draw()

    try:
        while True:
            key = _getch()

            moved = False
            if key == "up":
                cursor = max(0, cursor - 1)
                moved = True
            elif key == "down":
                cursor = min(len(items) - 1, cursor + 1)
                moved = True
            elif key == "space" and multi:
                if cursor in selected:
                    selected.remove(cursor)
                else:
                    selected.add(cursor)
                moved = True
            elif key == "enter":
                if multi and not selected:
                    selected.add(cursor)
                if multi:
                    return sorted(selected)
                return [cursor]
            elif key == "quit" or key == "escape":
                return []
            elif isinstance(key, str) and key.isdigit() and not multi:
                num = int(key)
                if 1 <= num <= len(items):
                    return [num - 1]

            if moved:
                draw()

        return []
    finally:
        _restore_console()
