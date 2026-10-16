"""Verified updates from the official WinNAT-UI GitHub Releases.

Only published releases are candidates. Download and verify an entire ZIP before
extraction; never execute files downloaded before user confirmation.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPOSITORY = "matiz311/WinNAT-UI"
API_URL = "https://api.github.com/repos/" + REPOSITORY + "/releases/latest"
ASSET_NAME = "WinNAT-UI-Windows.zip"
MAX_ZIP_BYTES = 150 * 1024 * 1024
MAX_EXPANDED_BYTES = 500 * 1024 * 1024
MAX_ENTRIES = 3000
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")


def version_tuple(value):
    matched = VERSION_RE.fullmatch(str(value))
    if not matched:
        raise ValueError("Versione GitHub non valida: " + str(value))
    return tuple(int(n or 0) for n in matched.groups())


def newer(release_tag, installed):
    return version_tuple(release_tag) > version_tuple(installed)


def _request(url, *, timeout=20):
    if not url.startswith("https://api.github.com/") and not url.startswith(
            "https://github.com/" + REPOSITORY + "/releases/download/"):
        raise ValueError("URL aggiornamento non autorizzato.")
    return urllib.request.Request(url, headers={
        "User-Agent": "WinNAT-UI-Updater",
        "Accept": "application/vnd.github+json" if "api.github.com" in url
                  else "application/octet-stream"
    })


def release_info(installed):
    with urllib.request.urlopen(_request(API_URL), timeout=20) as response:
        data = json.load(response)
    tag = data.get("tag_name", "")
    version_tuple(tag)
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("L'ultima release non è una versione stabile pubblicata.")
    assets = [a for a in data.get("assets", []) if a.get("name") == ASSET_NAME]
    if len(assets) != 1:
        raise ValueError("Release senza archivio Windows ufficiale univoco.")
    asset = assets[0]
    url = asset.get("browser_download_url", "")
    expected = ("https://github.com/" + REPOSITORY + "/releases/download/"
                + tag + "/" + ASSET_NAME)
    if url != expected:
        raise ValueError("URL dell'asset non corrispondente alla release ufficiale.")
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise ValueError("GitHub non fornisce un digest SHA256 verificabile per l'archivio.")
    return {"version": tag.lstrip("v"), "tag": tag, "url": url,
            "sha256": digest.split(":", 1)[1].lower(),
            "size": int(asset.get("size") or 0),
            "available": newer(tag, installed),
            "page": data.get("html_url", "")}


def _download(url, target, expected_digest):
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(_request(url), timeout=60) as response, open(target, "wb") as dest:
        # urllib redirects only to GitHub's release asset storage after initial
        # official URL. SHA256 supplied by the GitHub API authenticates the bytes.
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_ZIP_BYTES:
                raise ValueError("Archivio eccessivamente grande.")
            digest.update(block)
            dest.write(block)
    if digest.hexdigest() != expected_digest:
        raise ValueError("SHA256 dell'archivio differente da quello pubblicato su GitHub.")
    return size


def _safe_members(archive):
    members = archive.infolist()
    if len(members) > MAX_ENTRIES:
        raise ValueError("Troppi file nell'archivio.")
    expanded = 0
    files = []
    for member in members:
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if (not name or name.startswith(("/", "\\")) or ":" in name
                or not path.parts or any(p in ("", ".", "..") for p in path.parts)):
            raise ValueError("Percorso ZIP non sicuro: " + name)
        # Windows links and reparse points cannot be allowed in the release.
        mode = (member.external_attr >> 16) & 0xFFFF
        if (mode & 0o170000) == 0o120000:
            raise ValueError("Link simbolico non consentito: " + name)
        expanded += member.file_size
        if expanded > MAX_EXPANDED_BYTES:
            raise ValueError("Archivio espanso troppo grande.")
        files.append((member, path))
    return files


def prepare(info):
    """Stage a verified release outside installation path; no running files touched."""
    if not info.get("available"):
        raise ValueError("Non esiste una versione successiva.")
    temp = Path(tempfile.mkdtemp(prefix="WinNAT-Update-"))
    try:
        archive_path = temp / "package.zip"
        size = _download(info["url"], archive_path, info["sha256"])
        if info.get("size") and size != info["size"]:
            raise ValueError("Dimensione ZIP diversa dai metadati GitHub.")
        staged = temp / "new"
        staged.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            items = _safe_members(archive)
            for entry, path in items:
                target = staged.joinpath(*path.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, open(target, "wb") as dest:
                        shutil.copyfileobj(source, dest)
        exe = staged / "WinNAT-UI.exe"
        if not exe.is_file():
            raise ValueError("La release non contiene WinNAT-UI.exe nella cartella prevista.")
        return temp
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


# This script runs separately while the main EXE exits. Rollback is a directory
# restoration (no network settings are changed by the updater). It runs without
# a console window and draws its own progress window (WinForms) so the user sees
# each phase and the file being copied. Every UI call is best-effort: a UI
# failure is logged and the update continues headless, never aborted.
HELPER_PS = r'''
param(
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$StageRoot,
    [string]$FromVersion = '',
    [string]$ToVersion = '',
    [switch]$NoUi,
    [switch]$NoLaunch,
    # Tests only: close the error window after N seconds instead of waiting.
    [int]$AutoCloseSeconds = 0
)
$ErrorActionPreference = 'Stop'
$backup = Join-Path $StageRoot 'previous'
$source = Join-Path $StageRoot 'new'
$log = Join-Path $StageRoot 'update-log.txt'
$installed = Join-Path $InstallDir 'WinNAT-UI.exe'
$stepNames = @('Chiusura di WinNAT UI', 'Copia di sicurezza della versione installata',
               'Installazione della nuova versione', 'Verifica dei file installati',
               'Avvio di WinNAT UI')
$script:busy = $true
$script:ui = $null
$script:current = 0

function Write-Log([string]$text) {
    try { ((Get-Date -Format o) + '  ' + $text) | Add-Content -LiteralPath $log -Encoding UTF8 } catch { }
}

function Disable-Ui($errorRecord) {
    Write-Log ('UI disattivata: ' + $errorRecord.Exception.Message)
    try { if ($script:ui) { $script:ui.form.Dispose() } } catch { }
    $script:ui = $null
}

function Invoke-Pump {
    if ($script:ui) {
        try { [System.Windows.Forms.Application]::DoEvents() } catch { Disable-Ui $_ }
    }
}

function New-UpdateWindow {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    try {
        Add-Type -Namespace WinNatUi -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);
[DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(System.IntPtr hWnd, int attr, ref int value, int size);
'@
        [WinNatUi.Native]::SetProcessDPIAware() | Out-Null
    } catch { }
    [System.Windows.Forms.Application]::EnableVisualStyles()

    $dark = $false
    try {
        $dark = (Get-ItemPropertyValue -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -Name 'AppsUseLightTheme') -eq 0
    } catch { }
    # Same tokens as winnat_ui/ui_theme.py (LIGHT / DARK).
    $hex = if ($dark) {
        @{ surface = '#1A222E'; text = '#E6EBF2'; muted = '#A3AEBE'; faint = '#748094'; border = '#2C3746';
           accent = '#2BB3BD'; success = '#4CC38A'; danger = '#F2766B' }
    } else {
        @{ surface = '#FFFFFF'; text = '#152033'; muted = '#5B6778'; faint = '#8792A2'; border = '#DDE3EC';
           accent = '#0E7C86'; success = '#1B7F4B'; danger = '#B3261E' }
    }
    $c = @{}
    foreach ($k in $hex.Keys) { $c[$k] = [System.Drawing.ColorTranslator]::FromHtml($hex[$k]) }
    $fNormal = New-Object System.Drawing.Font('Segoe UI', 9.5)
    $fStrong = New-Object System.Drawing.Font('Segoe UI Semibold', 9.5)
    $fTitle = New-Object System.Drawing.Font('Segoe UI Semibold', 13)
    $fSmall = New-Object System.Drawing.Font('Segoe UI', 8.5)
    $fGlyph = New-Object System.Drawing.Font('Segoe UI Symbol', 10)

    $form = New-Object System.Windows.Forms.Form
    $form.SuspendLayout()
    $form.AutoScaleDimensions = New-Object System.Drawing.SizeF(96, 96)
    $form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
    $form.Text = 'Aggiornamento WinNAT UI'
    $form.ClientSize = New-Object System.Drawing.Size(480, 270)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ControlBox = $false
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.TopMost = $true
    $form.BackColor = $c.surface
    $form.ForeColor = $c.text
    $form.Font = $fNormal
    try { $form.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($installed) } catch { }
    $form.Add_FormClosing({ param($s, $e) if ($script:busy) { $e.Cancel = $true } })

    function Add-Label($text, $x, $y, $w, $h, $font, $color) {
        $l = New-Object System.Windows.Forms.Label
        $l.Text = $text
        $l.Location = New-Object System.Drawing.Point($x, $y)
        $l.Size = New-Object System.Drawing.Size($w, $h)
        $l.Font = $font
        $l.ForeColor = $color
        $l.BackColor = [System.Drawing.Color]::Transparent
        $l.AutoEllipsis = $true
        $l.UseMnemonic = $false
        $form.Controls.Add($l)
        return $l
    }

    if ($form.Icon) {
        $pic = New-Object System.Windows.Forms.PictureBox
        $pic.Location = New-Object System.Drawing.Point(24, 22)
        $pic.Size = New-Object System.Drawing.Size(36, 36)
        $pic.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
        $pic.Image = $form.Icon.ToBitmap()
        $form.Controls.Add($pic)
    }
    $title = Add-Label 'Aggiornamento di WinNAT UI' 72 18 384 26 $fTitle $c.text
    $subText = if ($FromVersion -and $ToVersion) { 'Versione ' + $FromVersion + '  →  ' + $ToVersion }
               elseif ($ToVersion) { 'Installazione della versione ' + $ToVersion }
               else { 'Installazione della nuova versione' }
    $sub = Add-Label $subText 72 44 384 20 $fNormal $c.muted

    $steps = @()
    for ($i = 0; $i -lt $stepNames.Count; $i++) {
        $y = 84 + $i * 25
        $g = Add-Label '○' 24 $y 22 22 $fGlyph $c.faint
        $g.AutoEllipsis = $false
        $t = Add-Label $stepNames[$i] 48 ($y + 1) 408 22 $fNormal $c.faint
        $steps += , @{ glyph = $g; text = $t }
    }

    $track = New-Object System.Windows.Forms.Panel
    $track.Location = New-Object System.Drawing.Point(24, 220)
    $track.Size = New-Object System.Drawing.Size(432, 6)
    $track.BackColor = $c.border
    $fill = New-Object System.Windows.Forms.Panel
    $fill.Dock = [System.Windows.Forms.DockStyle]::Left
    $fill.Width = 0
    $fill.BackColor = $c.accent
    $track.Controls.Add($fill)
    $form.Controls.Add($track)
    $detail = Add-Label 'Preparazione…' 24 234 432 22 $fSmall $c.muted

    $buttons = @()
    foreach ($spec in @(@('Chiudi', 368, 88), @('Apri registro', 252, 108), @('Riapri WinNAT UI', 24, 140))) {
        $b = New-Object System.Windows.Forms.Button
        $b.Text = $spec[0]
        $b.Location = New-Object System.Drawing.Point($spec[1], 300)
        $b.Size = New-Object System.Drawing.Size($spec[2], 30)
        $b.Visible = $false
        $b.UseVisualStyleBackColor = $true
        $form.Controls.Add($b)
        $buttons += $b
    }
    $buttons[0].Add_Click({ $script:ui.form.Close() })
    $buttons[1].Add_Click({ try { Start-Process -FilePath 'notepad.exe' -ArgumentList ('"' + $log + '"') } catch { } })
    $buttons[2].Add_Click({
        try { Start-Process -FilePath $installed -WorkingDirectory $InstallDir } catch { }
        $script:ui.form.Close()
    })
    $form.AcceptButton = $buttons[0]

    $form.ResumeLayout($true)
    $form.Show()
    # A hidden launch (SW_HIDE in STARTUPINFO) applies to the first window the
    # process shows: show it again explicitly so the progress is always visible.
    try {
        [WinNatUi.Native]::ShowWindow($form.Handle, 1) | Out-Null
        [WinNatUi.Native]::SetForegroundWindow($form.Handle) | Out-Null
    } catch { $form.Hide(); $form.Show() }
    if ($dark) {
        # Dark title bar (Windows 10 20H1+ / 11), matching the dark palette.
        try { $on = 1; [WinNatUi.Native]::DwmSetWindowAttribute($form.Handle, 20, [ref]$on, 4) | Out-Null } catch { }
    }
    $form.Activate()
    [System.Windows.Forms.Application]::DoEvents()
    return @{ form = $form; c = $c; steps = $steps; track = $track; fill = $fill; detail = $detail;
              title = $title; sub = $sub; buttons = $buttons;
              fNormal = $fNormal; fStrong = $fStrong; fSmall = $fSmall }
}

function Set-Step([int]$index) {
    $script:current = $index
    if ($index -lt $stepNames.Count) { Write-Log ('Fase: ' + $stepNames[$index]) }
    if (-not $script:ui) { return }
    try {
        $u = $script:ui
        for ($k = 0; $k -lt $u.steps.Count; $k++) {
            $s = $u.steps[$k]
            if ($k -lt $index) {
                $s.glyph.Text = '✓'; $s.glyph.ForeColor = $u.c.success
                $s.text.Font = $u.fNormal; $s.text.ForeColor = $u.c.muted
            } elseif ($k -eq $index) {
                $s.glyph.Text = '●'; $s.glyph.ForeColor = $u.c.accent
                $s.text.Font = $u.fStrong; $s.text.ForeColor = $u.c.text
            } else {
                $s.glyph.Text = '○'; $s.glyph.ForeColor = $u.c.faint
                $s.text.Font = $u.fNormal; $s.text.ForeColor = $u.c.faint
            }
        }
    } catch { Disable-Ui $_ }
    Invoke-Pump
}

function Set-Progress([int]$percent, [string]$text) {
    if (-not $script:ui) { return }
    try {
        $u = $script:ui
        $p = [Math]::Max(0, [Math]::Min(100, $percent))
        $u.fill.Width = [int]($u.track.ClientSize.Width * $p / 100)
        $u.detail.Text = $text
    } catch { Disable-Ui $_ }
    Invoke-Pump
}

# .NET directly: no dependency on Get-FileHash, which is missing when the
# inherited PSModulePath points to PowerShell 7 modules.
function Get-Sha256([string]$path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try { return [System.BitConverter]::ToString($sha.ComputeHash($stream)) }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Copy-Tree([string]$from, [string]$to, [int]$pctFrom, [int]$pctTo, [string]$verb) {
    $root = (Get-Item -LiteralPath $from).FullName.TrimEnd('\', '/')
    $files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Force)
    $n = $files.Count
    $i = 0
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($root.Length + 1)
        $dest = Join-Path $to $rel
        $dir = Split-Path -Parent $dest
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
        $i++
        Set-Progress ($pctFrom + [int](($pctTo - $pctFrom) * $i / [Math]::Max($n, 1))) `
            ($verb + ' · file ' + $i + ' di ' + $n + ' · ' + $rel)
    }
    return $n
}

function Show-Result([bool]$ok, [string]$message, [bool]$canReopen) {
    $script:busy = $false
    if (-not $script:ui) { return }
    try {
        $u = $script:ui
        if ($ok) {
            Set-Step $stepNames.Count
            Set-Progress 100 $message
            $u.title.Text = 'Aggiornamento completato'
            $u.title.ForeColor = $u.c.success
            $until = (Get-Date).AddMilliseconds(1800)
            while ((Get-Date) -lt $until -and $script:ui) { Start-Sleep -Milliseconds 50; Invoke-Pump }
            if ($script:ui) { $u.form.Close() }
            return
        }
        $s = $u.steps[[Math]::Min($script:current, $u.steps.Count - 1)]
        $s.glyph.Text = '✕'; $s.glyph.ForeColor = $u.c.danger; $s.text.ForeColor = $u.c.danger
        $u.title.Text = 'Aggiornamento non riuscito'
        $u.title.ForeColor = $u.c.danger
        $u.detail.Font = $u.fNormal
        $u.detail.ForeColor = $u.c.text
        $u.detail.AutoEllipsis = $false
        $u.detail.Size = New-Object System.Drawing.Size($u.track.Width, ($u.buttons[0].Top - $u.detail.Top - 8))
        $u.detail.Text = $message
        $u.form.ClientSize = New-Object System.Drawing.Size($u.form.ClientSize.Width, ($u.buttons[0].Bottom + 18))
        $u.buttons[0].Visible = $true
        $u.buttons[1].Visible = $true
        $u.buttons[2].Visible = $canReopen
        $u.form.ControlBox = $true
        $u.form.TopMost = $false
        $u.form.Activate()
        $limit = if ($AutoCloseSeconds -gt 0) { (Get-Date).AddSeconds($AutoCloseSeconds) } else { [DateTime]::MaxValue }
        while ($script:ui -and $u.form.Visible -and (Get-Date) -lt $limit) { Start-Sleep -Milliseconds 50; Invoke-Pump }
        if ($script:ui -and $u.form.Visible) { $u.form.Close() }
    } catch { Disable-Ui $_ }
}

if (-not $NoUi) {
    try { $script:ui = New-UpdateWindow }
    catch { $script:ui = $null; Write-Log ('Finestra di avanzamento non disponibile: ' + $_.Exception.Message) }
}
Write-Log ('Aggiornamento WinNAT UI ' + $FromVersion + ' -> ' + $ToVersion)
$installStarted = $false
$installCommitted = $false
try {
    Set-Step 0
    Set-Progress 2 'In attesa che WinNAT UI termini…'
    $deadline = (Get-Date).AddSeconds(45)
    while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw 'WinNAT UI è ancora aperta dopo 45 secondi.' }
        Start-Sleep -Milliseconds 150
        Invoke-Pump
    }
    if (-not (Test-Path -LiteralPath (Join-Path $source 'WinNAT-UI.exe'))) {
        throw 'Eseguibile nuovo assente.'
    }

    Set-Step 1
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    # Copy old application files before modifying any installed file.
    $oldCount = Copy-Tree $InstallDir $backup 5 40 'Copia di sicurezza'
    if ($oldCount -lt 1 -or -not (Test-Path -LiteralPath (Join-Path $backup 'WinNAT-UI.exe'))) {
        throw 'Copia di sicurezza non completa: installazione non avviata.'
    }
    Write-Log ('Copia di sicurezza: ' + $oldCount + ' file')

    Set-Step 2
    $installStarted = $true
    $newCount = Copy-Tree $source $InstallDir 40 90 'Installazione'
    Write-Log ('Installati: ' + $newCount + ' file')

    Set-Step 3
    Set-Progress 92 'Controllo di WinNAT-UI.exe…'
    if (-not (Test-Path -LiteralPath $installed)) { throw 'Installazione priva di EXE.' }
    $expected = Get-Sha256 (Join-Path $source 'WinNAT-UI.exe')
    if ((Get-Sha256 $installed) -ne $expected) {
        throw 'WinNAT-UI.exe installato non corrisponde al pacchetto verificato.'
    }
    $installCommitted = $true
} catch {
    $failure = $_.Exception.Message
    Write-Log ('Aggiornamento fallito: ' + $_.Exception.ToString())
    $note = 'La versione installata non è stata modificata.'
    $canReopen = Test-Path -LiteralPath $installed
    if ($installStarted -and -not $installCommitted) {
        Set-Progress 0 'Ripristino della versione precedente…'
        try {
            Copy-Tree $backup $InstallDir 0 100 'Ripristino' | Out-Null
            Write-Log 'Versione precedente ripristinata.'
            $note = 'La versione precedente è stata ripristinata.'
        } catch {
            Write-Log ('Anche il ripristino e fallito: ' + $_.Exception.ToString())
            $note = 'Il ripristino automatico non è riuscito: la copia di sicurezza è in ' + $backup
            $canReopen = $false
        }
    }
    Show-Result $false ($failure + "`r`n" + $note) $canReopen
    exit 1
}

try {
    Set-Step 4
    Set-Progress 97 'Avvio della nuova versione…'
    if (-not $NoLaunch) { Start-Process -FilePath $installed -WorkingDirectory $InstallDir }
    Write-Log 'Aggiornamento completato.'
    $label = if ($ToVersion) { 'WinNAT UI ' + $ToVersion + ' è installata e si sta avviando.' }
             else { 'La nuova versione è installata e si sta avviando.' }
    Show-Result $true $label $false
} catch {
    Write-Log ('Aggiornamento installato, avvio fallito: ' + $_.Exception.ToString())
    Show-Result $false ('Aggiornamento installato, ma WinNAT UI non si è avviata: ' + $_.Exception.Message) $true
    exit 2
}
'''

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def helper_command(script, install_dir, staging, parent_pid, from_version="", to_version=""):
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Sta",
               "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-ParentPid", str(parent_pid),
               "-InstallDir", str(install_dir),
               "-StageRoot", str(staging)]
    if from_version:
        command += ["-FromVersion", str(from_version)]
    if to_version:
        command += ["-ToVersion", str(to_version)]
    return command


def launch(staging, install_dir=None, parent_pid=None, from_version="", to_version=""):
    """Schedule update after process exit; only for a packaged Windows EXE."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise RuntimeError("Aggiornamento automatico disponibile solo nell'EXE Windows installato.")
    install_dir = Path(install_dir or sys.executable).resolve()
    if install_dir.is_file():
        install_dir = install_dir.parent
    staging = Path(staging).resolve()
    if not (staging / "new" / "WinNAT-UI.exe").is_file():
        raise ValueError("Pacchetto staged non valido.")
    script = staging / "apply-update.ps1"
    # BOM: Windows PowerShell 5.1 reads BOM-less scripts as ANSI, which would
    # garble the accented Italian text and symbols shown in the progress window.
    script.write_text(HELPER_PS, encoding="utf-8-sig")
    # Windows PowerShell 5.1 must load its own modules, not PowerShell 7 ones
    # inherited when the app was started from a pwsh terminal.
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    # No console window: the script shows its own progress window instead.
    subprocess.Popen(helper_command(script, install_dir, staging, parent_pid or os.getpid(),
                                    from_version, to_version),
                     env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True,
                     creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
