; WorkMonitor のインストーラー（Inno Setup 6）
; ビルド: iscc /DMyAppVersion=1.2.0 installer.iss  → dist\WorkMonitor-Setup.exe

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "WorkMonitor"
#define MyAppExe "WorkMonitor.exe"

[Setup]
AppId={{6F1C2B7E-4A8D-4C3B-9E21-7D5A0B3F9C41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=kaikomziu
AppPublisherURL=https://kaikomziu.github.io/WorkMonitor/
AppSupportURL=https://github.com/kaikomziu/WorkMonitor/issues
; 管理者の権限なしで、ユーザーのフォルダにインストールする
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
OutputDir=dist
OutputBaseFilename=WorkMonitor-Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 起動中なら閉じるよう案内する（アプリの二重起動防止と同じ名前）
AppMutex=WorkMonitor_SingleInstance
CloseApplications=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作る"; GroupDescription: "ショートカット:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "mods\modreadme.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; アプリが登録する自動起動を、アンインストール時に消す（インストール時は作らない）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#MyAppName}"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "WorkMonitor を起動する"; Flags: nowait postinstall skipifsilent

[Messages]
japanese.FinishedLabel=WorkMonitor のインストールが完了しました。%n%n記録と設定は「AppData\Roaming\WorkMonitor」に保存されます（アンインストールしても残ります）。
