#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppName=PsychAid
AppVersion={#MyAppVersion}
AppPublisher=PsychAid
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\PsychAid
DefaultGroupName=PsychAid
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=PsychAid-windows-x64-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=PsychAid
UninstallDisplayIcon={app}\PsychAid.exe
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\PsychAid\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\PsychAid"; Filename: "{app}\PsychAid.exe"
Name: "{autodesktop}\PsychAid"; Filename: "{app}\PsychAid.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 runtime..."; Check: NeedsWebView2; Flags: waituntilterminated
Filename: "{app}\PsychAid.exe"; Description: "Launch PsychAid"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2Version(const RootKey: Integer; const SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and
    (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
const
  WebView2ClientKey = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Wow6432ClientKey = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
begin
  if HasWebView2Version(HKLM, WebView2Wow6432ClientKey) then
  begin
    Result := False;
    Exit;
  end;

  if HasWebView2Version(HKLM, WebView2ClientKey) then
  begin
    Result := False;
    Exit;
  end;

  if HasWebView2Version(HKCU, WebView2ClientKey) then
  begin
    Result := False;
    Exit;
  end;

  Result := True;
end;
