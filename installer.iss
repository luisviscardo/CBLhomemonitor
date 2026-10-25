; Script de Instalação Profissional Inno Setup para o CBLhomemonitor
; Gera o arquivo executável 'CBLhomemonitor_Setup_v1.3.exe'

#define MyAppName "CBLhomemonitor"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "CBL Tecnologia"
#define MyAppURL "https://github.com/luisviscardo/CBLhomemonitor"
#define MyAppExeName "CBLhomemonitor.exe"

[Setup]
AppId={{8B5C3F9D-42A1-4E68-9A7D-CBLHOMEMON13}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=CBLhomemonitor_Setup_v1.3
SetupIconFile=static\img\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar automaticamente com o Windows ao ligar o computador"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
Source: "dist\CBLhomemonitor\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\CBLhomemonitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
