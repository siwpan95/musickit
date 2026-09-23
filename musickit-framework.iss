; musickit 框架安装包（S7 · 2026-08-25，pywallpaper 样板同款）
; 编译：ISCC.exe musickit-framework.iss  →  installer\musickit-framework-setup-1.0.0.exe

#define MyAppName "musickit 框架"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "siwpan"

[Setup]
AppId={{B7E4D2F0-8C51-4A9E-B3D7-MUSICKITFRM01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\musickit-framework
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=musickit-framework-setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\music\styles
UninstallDisplayName={#MyAppName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Files]
; 2026-09-23 去本地化：源目录不再写死（原 G:\_job\framework_stage 已失效）。
; 由 build_framework.py 用 /DStageDir=<暂存目录> 传入；未传时回落到 iss 同级的 framework_stage。
#ifndef StageDir
  #define StageDir AddBackslash(SourcePath) + "framework_stage"
#endif
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\musickit 环境诊断"; Filename: "{app}\doctor.bat"; WorkingDir: "{app}"
Name: "{group}\musickit 一键链"; Filename: "{app}\chain.bat"; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
