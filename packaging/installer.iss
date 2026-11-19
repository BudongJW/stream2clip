; Inno Setup script for the Windows installer.
;
; Built by `python packaging/build_windows.py --installer` (needs Inno Setup 6.1 or newer: ISCC.exe on PATH
; or in Program Files). The first page asks for the language: Korean, Japanese or English. The choice is the
; language of the installer and, through language.txt next to the programs, of the app itself
; (see stream2clip/i18n.py; a language chosen later in the app wins).
;
; Installs for the current user without administrator rights. ffmpeg is not included: when none is found
; on the PC, a task (ticked by default) downloads the build pinned in stream2clip/tools.py, checked against
; its SHA-256, and the installed program takes ffmpeg.exe and ffprobe.exe out of it into the user's tools
; folder. Without a connection the programs are installed all the same and the app offers the download again.

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
#ifndef FfmpegUrl
  #error The pinned ffmpeg build is missing: build with packaging/build_windows.py, which passes /DFfmpegUrl, /DFfmpegFile, /DFfmpegSha256 and /DFfmpegSize
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
ko.FfmpegTask=ffmpeg 내려받기 (녹화와 영상 변환에 필요, {#FfmpegSize} MB)
ja.FfmpegTask=ffmpeg をダウンロード (録画と動画の変換に必要、{#FfmpegSize} MB)
en.FfmpegTask=Download ffmpeg (needed for recording and video conversion, {#FfmpegSize} MB)
ko.FfmpegPage=ffmpeg 내려받는 중
ja.FfmpegPage=ffmpeg をダウンロード中
en.FfmpegPage=Downloading ffmpeg
ko.FfmpegPageNote=ffmpeg.org가 안내하는 Windows용 빌드를 GitHub에서 내려받는 중. 인터넷 속도에 따라 몇 분 소요.
ja.FfmpegPageNote=ffmpeg.org が案内する Windows 用ビルドを GitHub からダウンロード中。回線速度によっては数分かかります。
en.FfmpegPageNote=Fetching the Windows build that ffmpeg.org links to from GitHub. This can take a few minutes.
ko.FfmpegInstalling=ffmpeg 설치 중
ja.FfmpegInstalling=ffmpeg をインストール中
en.FfmpegInstalling=Installing ffmpeg
ko.FfmpegFailed=ffmpeg를 내려받지 못함. 설치는 계속 진행. 설치 후 앱 시작 화면의 ffmpeg 내려받기 버튼으로 다시 시도 가능.
ja.FfmpegFailed=ffmpeg をダウンロードできませんでした。インストールは続行します。インストール後、アプリの開始画面の ffmpeg ダウンロードボタンで再試行できます。
en.FfmpegFailed=ffmpeg could not be downloaded. The installation goes on. Afterwards, the download button on the app's start window tries again.
ko.FfmpegNote=ffmpeg 없음. 녹화와 영상 변환에 필요. 앱 시작 화면의 ffmpeg 내려받기 버튼으로 설치 가능.
ja.FfmpegNote=ffmpeg がありません。録画と動画の変換に必要です。アプリの開始画面の ffmpeg ダウンロードボタンでインストールできます。
en.FfmpegNote=ffmpeg is missing. Recording and video conversion need it. The download button on the app's start window installs it.

[Tasks]
Name: "ffmpeg"; Description: "{cm:FfmpegTask}"; Check: FfmpegMissing
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\stream2clip"; Filename: "{app}\stream2clip-gui.exe"
Name: "{autodesktop}\stream2clip"; Filename: "{app}\stream2clip-gui.exe"; Tasks: desktopicon

[Run]
; The installed program checks the archive against the pinned SHA-256 once more and takes the two programs out of it.
Filename: "{app}\stream2clip.exe"; Parameters: "setup --ffmpeg --no-obs --from ""{tmp}\{#FfmpegFile}"""; StatusMsg: "{cm:FfmpegInstalling}"; Flags: runhidden; Tasks: ffmpeg; Check: FfmpegFetched
Filename: "{app}\stream2clip-gui.exe"; Description: "{cm:StartApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\language.txt"
; The downloaded ffmpeg (stream2clip.ffmpeg.tools_dir) goes away with the programs.
Type: files; Name: "{%USERPROFILE}\.cache\stream2clip\tools\ffmpeg.exe"
Type: files; Name: "{%USERPROFILE}\.cache\stream2clip\tools\ffprobe.exe"
Type: files; Name: "{%USERPROFILE}\.cache\stream2clip\tools\ffmpeg-LICENSE.txt"
Type: dirifempty; Name: "{%USERPROFILE}\.cache\stream2clip\tools"

[Code]
var
  DownloadPage: TDownloadWizardPage;
  FfmpegArchiveReady: Boolean;

function BesideThePrograms: Boolean;
begin
  Result := False;
  try
    Result := FileExists(AddBackslash(WizardDirValue) + 'ffmpeg.exe');
  except
    { asked before the wizard knows the folder }
  end;
end;

function FfmpegMissing: Boolean;
begin
  { The places stream2clip looks in: on PATH, fetched earlier into the tools folder, put next to the programs. }
  Result := (FileSearch('ffmpeg.exe', GetEnv('PATH')) = '')
    and not FileExists(ExpandConstant('{%USERPROFILE}\.cache\stream2clip\tools\ffmpeg.exe'))
    and not BesideThePrograms;
end;

function FfmpegFetched: Boolean;
begin
  Result := FfmpegArchiveReady;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('FfmpegPage'), CustomMessage('FfmpegPageNote'), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected('ffmpeg') then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('{#FfmpegUrl}', '{#FfmpegFile}', '{#FfmpegSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        FfmpegArchiveReady := True;
      except
        { No connection, a file that is not the pinned one, or cancelled: the programs are installed all the same. }
        Log('ffmpeg was not downloaded: ' + GetExceptionMessage);
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox(CustomMessage('FfmpegFailed') + #13#10 + #13#10 + AddPeriod(GetExceptionMessage), mbInformation, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { The app reads this file: it starts in the language chosen here. }
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\language.txt'), ActiveLanguage, False);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { ffmpeg is a separate program: when there still is none, the last page says where to get it. }
  if (CurPageID = wpFinished) and FfmpegMissing then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10 + #13#10 + CustomMessage('FfmpegNote');
end;
