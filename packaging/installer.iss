; Inno Setup script for the Windows installer.
;
; Built by `python packaging/build_windows.py --installer` (needs Inno Setup 6: ISCC.exe on PATH or in
; Program Files). The first page asks for the language: Korean, Japanese or English. The choice is the
; language of the installer and, through language.txt next to the programs, of the app itself
; (see stream2clip/i18n.py; a language chosen later in the app wins).
;
; Installs for the current user without administrator rights. ffmpeg is not included.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\stream2clip"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef OutputName
  #define OutputName "stream2clip-" + AppVersion + "-windows-x64-setup"
#endif

[Setup]
AppId={{8C1B7C0E-6C0B-4E6E-9E0B-5D2C1A7E52C1}
AppName=stream2clip
AppVersion={#AppVersion}
AppPublisher=stream2clip
AppPublisherURL=https://budongjw.github.io/stream2clip/
AppSupportURL=https://github.com/BudongJW/stream2clip/issues
DefaultDirName={autopf}\stream2clip
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile=..\assets\brand\app-icons\windows\stream2clip.ico
UninstallDisplayIcon={app}\stream2clip-gui.exe
UninstallDisplayName=stream2clip {#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
UsePreviousLanguage=no

[Languages]
#if FileExists(CompilerPath + "Languages\Korean.isl")
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
#else
; An Inno Setup without the Korean messages: the choice is still offered, the installer's own pages stay English.
Name: "ko"; MessagesFile: "compiler:Default.isl"
#define KoreanFallback
#endif
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

#ifdef KoreanFallback
[LangOptions]
ko.LanguageName=한국어
#endif

[CustomMessages]
ko.DesktopShortcut=바탕 화면에 바로 가기 만들기
ja.DesktopShortcut=デスクトップにショートカットを作成
en.DesktopShortcut=Create a desktop shortcut
ko.StartApp=stream2clip 실행
ja.StartApp=stream2clip を起動
en.StartApp=Start stream2clip
ko.FfmpegNote=영상 변환에는 ffmpeg가 필요합니다. 설치되어 있지 않으면 터미널에서 winget install Gyan.FFmpeg 를 실행하십시오.
ja.FfmpegNote=動画の変換には ffmpeg が必要です。未インストールの場合は、ターミナルで winget install Gyan.FFmpeg を実行してください。
en.FfmpegNote=Video conversion needs ffmpeg. If it is not installed, run winget install Gyan.FFmpeg in a terminal.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\stream2clip"; Filename: "{app}\stream2clip-gui.exe"
Name: "{autodesktop}\stream2clip"; Filename: "{app}\stream2clip-gui.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\stream2clip-gui.exe"; Description: "{cm:StartApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\language.txt"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  { The app reads this file: it starts in the language chosen here. }
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\language.txt'), ActiveLanguage, False);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { ffmpeg is a separate program: say so on the last page. }
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10 + #13#10 + CustomMessage('FfmpegNote');
end;
