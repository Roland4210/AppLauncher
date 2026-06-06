# AppLauncher

Windows software manager — scan, launch, kill.

[English](#english) | [中文](#中文) | [日本語](#日本語)

---

## English

### Features
- **Scan** — auto-discover all drives, registry, Start Menu
- **Launch** — interactive picker or workflow batch launch
- **Kill** — force terminate running processes

### Quick Start
Download `AppLauncher.exe` from [Releases](../../releases) and run.

Or from source:
```bash
git clone https://github.com/Roland4210/AppLauncher.git
cd AppLauncher
python main.py
```

### Requirements
- Windows 10+
- Python 3.11+ (source only)

### Package
```bash
pip install pyinstaller
pyinstaller --onefile --console --name AppLauncher main.py
```

### Privacy
`scan_result.json` and `workflows.json` stay local.

---

## 中文

### 功能
- **扫描** — 自动发现所有盘符 + 注册表 + 开始菜单
- **启动** — 交互式选择单个启动，或工作流一键批量启动
- **关闭** — 强制结束正在运行的软件进程

### 快速开始
下载 [Releases](../../releases) 中的 `AppLauncher.exe`，双击运行。

或从源码：
```bash
git clone https://github.com/Roland4210/AppLauncher.git
cd AppLauncher
python main.py
```

### 环境
- Windows 10+
- Python 3.11+（源码运行）

### 打包
```bash
pip install pyinstaller
pyinstaller --onefile --console --name AppLauncher main.py
```

### 隐私
扫描结果和工作流配置仅保存在本地，不会上传。

---

## 日本語

### 機能
- **検索** — 全ドライブ + レジストリ + スタートメニューを自動検出
- **起動** — インタラクティブ選択、またはワークフローで一括起動
- **終了** — 実行中のプロセスを強制終了

### クイックスタート
[Releases](../../releases) から `AppLauncher.exe` をダウンロードして実行。

ソースから：
```bash
git clone https://github.com/Roland4210/AppLauncher.git
cd AppLauncher
python main.py
```

### 要件
- Windows 10+
- Python 3.11+（ソース実行時のみ）

---

## Author

这个项目是我用 AI 跑出来的，我只学过基础的 Python 语法。平时重度玩游戏，开模拟器→开脚本很麻烦，所以特别看重"工作流"功能。

如有建议或想提 Issue 都很欢迎，也可以通过以下方式联系我：
- 邮箱：2145657268@qq.com
- Bilibili：319079174（罗兰J士）

希望本项目对你有帮助 : )
ps：其实我更推荐下载AppLauncher_Setup_1.0.exe,因为另一个方式下载的话会把配置文件乱拉
