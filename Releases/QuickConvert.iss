; QuickConvert installer (Inno Setup 6)
; Copyright (C) 2026 NullHarp - SPDX-License-Identifier: GPL-3.0-or-later
; build.bat compiles this:
;   ISCC /DAppVersion=1.2.0 installer\QuickConvert.iss
; The right-click menu entries live in menus.iss, generated from
; quickconvert\formats.py by tools\make_installer_menus.py.
#define AppName "QuickConvert"
#define AppExe "QuickConvert.exe"
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif

[Setup]
; Never change AppId: it's how a newer setup finds and upgrades the old one.
AppId={{4BABA964-5816-4AED-81E9-6785B3539EB3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=NullHarp
AppCopyright=Copyright (C) 2026 NullHarp
; Shows the GPLv3 on the first page of the wizard.
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Installs for the current user without admin; the dialog offers "all users" too.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.
OutputBaseFilename=QuickConvert-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Refreshes Explorer so the menus appear/disappear without signing out.
ChangesAssociations=yes
; A conversion running from the right-click menu holds the exe open.
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "menu_convert";  Description: """Convert to"" (images, video, audio, documents, PDF)"; GroupDescription: "Right-click menus:"
Name: "menu_resize";   Description: """Resize image"""; GroupDescription: "Right-click menus:"
Name: "menu_compress"; Description: """Compress video"""; GroupDescription: "Right-click menus:"

[InstallDelete]
; clear the old build's files on upgrade so nothing stale is left behind
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\QuickConvert\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Opens a small window showing status and which document converter (Office/LibreOffice) was found.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

#include "menus.iss"
