; Inno Setup 安装脚本
; 下载 https://jrsoftware.org/isinfo.php 安装后, 打开此文件 → Compile

#define MyAppName "AppLauncher"
#define MyAppVersion "1.0"
#define MyAppPublisher "Roland"
#define MyAppExeName "AppLauncher.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=.\installer
OutputBaseFilename=AppLauncher_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; 不需要管理员权限
MinVersion=10.0
PrivilegesRequired=lowest

[Files]
Source: "..\dist_output\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\scan_result.json"
Type: filesandordirs; Name: "{app}\workflows.json"
Type: filesandordirs; Name: "{app}\scan_config.json"
