"""多语言支持 — 自动检测系统语言, 回退中文"""
import json
import os
import ctypes


def _get_system_lang() -> str:
    """获取 Windows 系统 UI 语言"""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # lang_id: 1033=en, 1041=ja, 1042=ko, 2052=zh-CN, 1028=zh-TW
        lang_map = {1033: "en", 1041: "ja", 1042: "ko",
                    2052: "zh", 1028: "zh"}
        return lang_map.get(lang_id & 0xFFFF, "zh")
    except Exception:
        return "zh"


_lang_data = {}
_lang = "zh"


def load():
    global _lang_data, _lang
    _lang = _get_system_lang()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
        _lang_data = all_data.get(_lang, all_data.get("zh", {}))
    except Exception:
        _lang_data = {}


def t(key: str, **kwargs) -> str:
    """取翻译文本, 支持 {name} 占位符"""
    text = _lang_data.get(key, key)
    if kwargs:
        for k, v in kwargs.items():
            text = text.replace("{" + k + "}", str(v))
    return text


def current_lang() -> str:
    return _lang


load()
