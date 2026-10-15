# c3resume - save a running Cossacks 3 multiplayer match and continue it later.   (Windows installer)
#
# Changes a few of the game's own script files on THIS computer; the originals are kept in
# <game folder>\c3backup and come back with "uninstall". Nothing from the game is shipped with it.
# Works with the Windows PowerShell 5.1 that every Windows 10/11 has. The .bat files next to it run it.
#
#   powershell -ExecutionPolicy Bypass -File c3resume.ps1 install [-Server 1.2.3.4] [-NoHelper] [-Diag] [-GameDir "D:\...\Cossacks 3"]
#   (-NoHelper: without the save helper - saves are then copied by hand)
#   powershell -ExecutionPolicy Bypass -File c3resume.ps1 uninstall | status | saves | helper [-Once]
param(
    [Parameter(Position = 0)][string]$Command = "install",
    [string]$Server = "",
    [string]$GameDir = "",
    [switch]$Diag,
    [switch]$NoHelper,
    [switch]$Once
)
$ErrorActionPreference = "Stop"
$Version = "2.2"
$BackupDir = "c3backup"
$ServersDat = "data/resources/servers.dat"
$MenuAix = "data/gui/menu.aix"
$Latin1 = [Text.Encoding]::GetEncoding(28591)        # one byte per character, like the Python installer

function Fail([string]$msg) { Write-Host ""; Write-Host $msg -ForegroundColor Red; exit 1 }
function P([string]$rel) { return (Join-Path $script:Game ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)) }
function ReadText([string]$path) { return $Latin1.GetString([IO.File]::ReadAllBytes($path)) }
function WriteText([string]$path, [string]$text) { [IO.File]::WriteAllBytes($path, $Latin1.GetBytes($text)) }
function Sha([byte[]]$bytes) {
    $h = [Security.Cryptography.SHA256]::Create()
    return ([BitConverter]::ToString($h.ComputeHash($bytes))).Replace("-", "").ToLower()
}
function ShaFile([string]$path) { if (Test-Path -LiteralPath $path) { return Sha ([IO.File]::ReadAllBytes($path)) } else { return "" } }

function Find-Game {
    if ($GameDir -ne "") { return $GameDir }
    $libs = @()
    foreach ($key in @("HKCU:\Software\Valve\Steam", "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam", "HKLM:\SOFTWARE\Valve\Steam")) {
        try {
            $item = Get-ItemProperty -Path $key -ErrorAction Stop
            foreach ($name in @("SteamPath", "InstallPath")) {
                if ($item.$name) { $libs += ($item.$name -replace '/', '\') }
            }
        } catch { }
    }
    $libs += @("${env:ProgramFiles(x86)}\Steam", "$env:ProgramFiles\Steam")
    $more = @()
    foreach ($l in $libs) {
        $vdf = Join-Path $l "steamapps\libraryfolders.vdf"
        if (Test-Path -LiteralPath $vdf) {
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $more += ($m.Groups[1].Value -replace '\\\\', '\')
            }
        }
    }
    foreach ($l in ($libs + $more)) {
        $g = Join-Path $l "steamapps\common\Cossacks 3"
        if (Test-Path -LiteralPath (Join-Path $g "data")) { return $g }
    }
    if ($Command -eq "info") { return "" }
    Write-Host "I could not find the Cossacks 3 folder."
    Write-Host "In Steam: right-click Cossacks 3 > Manage > Browse local files, copy that folder's path and paste it here."
    $typed = (Read-Host "Cossacks 3 folder").Trim().Trim('"')
    if ($typed -ne "" -and (Test-Path -LiteralPath (Join-Path $typed "data"))) { return $typed }
    Fail "That is not the Cossacks 3 folder (it has no 'data' folder inside). Nothing was changed."
}

function Load-Manifest {
    $m = @{ files = @{}; created = @(); applied = @() }
    $mp = P "$BackupDir/manifest.json"
    if (Test-Path -LiteralPath $mp) {
        $j = Get-Content -LiteralPath $mp -Raw | ConvertFrom-Json
        if ($j.files) { foreach ($pr in $j.files.PSObject.Properties) { $m.files[$pr.Name] = @{ orig_sha = $pr.Value.orig_sha; patched_sha = $pr.Value.patched_sha } } }
        if ($j.created) { $m.created = @($j.created) }
        if ($j.applied) { $m.applied = @($j.applied) }
        if ($j.version) { $m.version = $j.version }
        if ($j.when) { $m.when = $j.when }
    }
    return $m
}

function Save-Manifest($m) {
    $dir = P $BackupDir
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $text = $m | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText((P "$BackupDir/manifest.json"), $text, (New-Object Text.UTF8Encoding($false)))
}

function Backup-Once([string]$rel) {
    $src = P $rel; $bk = P "$BackupDir/$rel"
    if ((Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $bk)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $bk) | Out-Null
        Copy-Item -LiteralPath $src -Destination $bk -Force
    }
}

function Undo-Files($m, [bool]$quiet) {
    foreach ($rel in @($m.files.Keys)) {
        $info = $m.files[$rel]; $p = P $rel; $bk = P "$BackupDir/$rel"
        $now = ShaFile $p
        if ($now -eq $info.patched_sha -and (Test-Path -LiteralPath $bk)) {
            Copy-Item -LiteralPath $bk -Destination $p -Force
            if (-not $quiet) { Write-Host "  restored $rel" }
        } elseif ($now -ne $info.orig_sha) {
            Write-Host "  left alone (changed by something else, e.g. a game update): $rel"
        }
    }
    foreach ($rel in $m.created) {
        $p = P $rel
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force; if (-not $quiet) { Write-Host "  removed  $rel" } }
    }
    $m.files = @{}; $m.created = @(); $m.applied = @()
}

function Enabled-Mods {
    $ini = P "mods/mods.ini"
    $out = @()
    if (-not (Test-Path -LiteralPath $ini)) { return $out }
    foreach ($blk in [regex]::Matches((ReadText $ini), '(?s)struct\.begin(.*?)struct\.end')) {
        $b = $blk.Groups[1].Value
        $d = [regex]::Match($b, '(?m)^\s*dir\s*=\s*(.+?)\s*$')
        $dis = [regex]::Match($b, '(?m)^\s*dis\s*=\s*(\w+)')
        if ($d.Success -and -not ($dis.Success -and $dis.Groups[1].Value -eq "True")) {
            $out += , @($d.Groups[1].Value.Trim(), (Join-Path $script:Game ($d.Groups[1].Value.Trim() -replace '[\\/]', [IO.Path]::DirectorySeparatorChar)))
        }
    }
    return , $out          # the comma keeps a list of one mod from being unrolled
}

function Disable-Mods($dirs) {
    Backup-Once "mods/mods.ini"
    $ini = P "mods/mods.ini"
    $text = [regex]::Replace((ReadText $ini), '(?s)struct\.begin.*?struct\.end', {
        param($mt)
        $blk = $mt.Value
        $d = [regex]::Match($blk, '(?m)^\s*dir\s*=\s*(.+?)\s*$')
        if ($d.Success -and ($dirs -contains $d.Groups[1].Value.Trim())) {
            $blk = [regex]::Replace($blk, '(?m)(^\s*dis\s*=\s*)\w+', '${1}True')
        }
        return $blk
    })
    WriteText $ini $text
}

function Set-Server([string]$addr) {
    if ($addr -notmatch '^[A-Za-z0-9.\-]+(:\d{1,5})?$') { Fail "'$addr' does not look like a server address (example: 192.168.1.20)." }
    if ($addr -notmatch ':') { $addr += ":31523" }
    Backup-Once $ServersDat
    WriteText (P $ServersDat) "section.begin`r`n* = $addr`r`nsection.end`r`n"
    Write-Host "The game now uses the lobby server $addr (uninstall puts the old setting back)."
}

function Do-Install {
    $all = Get-Content -LiteralPath (Join-Path $PSScriptRoot "patches.json") -Raw | ConvertFrom-Json
    if ($Diag) { $data = $all.diag } else { $data = $all.normal }
    $m = Load-Manifest
    if ($m.files.Count -gt 0 -or $m.created.Count -gt 0) { Undo-Files $m $true }
    $targets = @($data.patches | ForEach-Object { $_.file } | Sort-Object -Unique)
    foreach ($rel in $targets) { if (-not (Test-Path -LiteralPath (P $rel))) { Fail "PROBLEM: $rel is missing in the game folder. Nothing was changed." } }
    $clash = @()
    foreach ($mod in (Enabled-Mods)) {
        foreach ($rel in ($targets + @($data.newfiles | ForEach-Object { $_.file }))) {
            if (Test-Path -LiteralPath (Join-Path $mod[1] ($rel -replace '/', [IO.Path]::DirectorySeparatorChar))) { $clash += $mod[0] }
        }
    }
    $clash = @($clash | Sort-Object -Unique)
    $work = @{}
    foreach ($p in $data.patches) {
        $rel = $p.file
        if ($work.ContainsKey($rel)) { $text = $work[$rel] } else { $text = ReadText (P $rel) }
        if ($text.Contains("`r`n")) { $nl = "`r`n" } else { $nl = "`n" }
        $anchor = $p.anchor.Replace("`n", $nl); $repl = $p.replace.Replace("`n", $nl)
        $n = ([regex]::Matches($text, [regex]::Escape($anchor))).Count
        if ($n -ne 1) { Fail "PROBLEM: the game file $rel is not what this mod expects (part '$($p.name)' found $n times).`nMaybe the game was updated. Nothing was changed." }
        $work[$rel] = $text.Replace($anchor, $repl)
    }
    if ($clash.Count -gt 0) {
        Disable-Mods $clash
        Write-Host "Switched off these mods because they replace the same game files (uninstall turns them back on):"
        foreach ($d in $clash) { Write-Host "    $d" }
    }
    if ((ReadText (P $MenuAix)).Contains("`r`n")) { $nlNew = "`r`n" } else { $nlNew = "`n" }
    foreach ($rel in $work.Keys) {
        $path = P $rel; $bk = P "$BackupDir/$rel"
        $old = [IO.File]::ReadAllBytes($path)
        if (-not (Test-Path -LiteralPath $bk) -or ((ShaFile $bk) -ne (Sha $old))) {
            New-Item -ItemType Directory -Force -Path (Split-Path $bk) | Out-Null
            Copy-Item -LiteralPath $path -Destination $bk -Force
        }
        $new = $Latin1.GetBytes($work[$rel])
        [IO.File]::WriteAllBytes($path, $new)
        $m.files[$rel] = @{ orig_sha = (Sha $old); patched_sha = (Sha $new) }
        Save-Manifest $m                                   # so uninstall works even if a later step fails
    }
    foreach ($f in $data.newfiles) {
        WriteText (P $f.file) ($f.content.Replace("`n", $nlNew))
        $m.created += $f.file
        Save-Manifest $m
    }
    $m.applied = @(@($data.patches | ForEach-Object { $_.name }) + @("readload") | Sort-Object -Unique)
    $m.version = $Version
    $m.when = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Save-Manifest $m
    if ($Server -ne "") { Set-Server $Server }
    if ($NoHelper) {
        if ((Helper-Installed) -or (Helper-Running)) { Helper-Remove }
        Write-Host "Installed WITHOUT the save helper: saves are not shared automatically. To continue a match, the host"
        Write-Host "sends the save file to every player, who puts it into their saves folder (see the README)."
    } else { Helper-Install }
    Write-Host ""
    Write-Host "c3resume $Version is installed in: $script:Game" -ForegroundColor Green
    Write-Host "Restart the game if it is running. Everybody in a match needs the same version."
}

function Do-Uninstall {
    if (-not (Test-Path -LiteralPath (P $BackupDir))) { Write-Host "c3resume is not installed - nothing to do."; return }
    $m = Load-Manifest
    Undo-Files $m $false
    foreach ($rel in @("mods/mods.ini", $ServersDat, "cossacks.ini")) {
        $bk = P "$BackupDir/$rel"
        if (Test-Path -LiteralPath $bk) { Copy-Item -LiteralPath $bk -Destination (P $rel) -Force; Write-Host "  restored $rel" }
    }
    Remove-Item -LiteralPath (P $BackupDir) -Recurse -Force
    Helper-Remove
    Write-Host "c3resume is removed - the game files are original again. Restart the game if it is running." -ForegroundColor Green
}

function Do-Status {
    Write-Host "game folder: $script:Game"
    $m = Load-Manifest
    if ($m.files.Count -eq 0) { Write-Host "c3resume is NOT installed."; return }
    $bad = @()
    foreach ($rel in $m.files.Keys) { if ((ShaFile (P $rel)) -ne $m.files[$rel].patched_sha) { $bad += $rel } }
    foreach ($rel in $m.created) { if (-not (Test-Path -LiteralPath (P $rel))) { $bad += $rel } }
    Write-Host "c3resume $($m.version) installed $($m.when)"
    if ($bad.Count -gt 0) {
        Write-Host "BUT these files were changed back (Steam 'verify' or a game update?) - run the installer again:" -ForegroundColor Yellow
        foreach ($rel in $bad) { Write-Host "    $rel" }
    } else { Write-Host "all files OK." -ForegroundColor Green }
    if (Test-Path -LiteralPath (P $ServersDat)) {
        $srv = [regex]::Matches((ReadText (P $ServersDat)), '=\s*(\S+)') | ForEach-Object { $_.Groups[1].Value }
        Write-Host ("lobby server: " + ($srv -join ", "))
    }
    if (Helper-Running) { Write-Host "save-sync helper: running" }
    elseif (Helper-Installed) { Write-Host "save-sync helper: set up, but NOT running (log in again, or run the installer again)" -ForegroundColor Yellow }
    else { Write-Host "save-sync helper: not installed (saves are copied by hand)" }
}

function Saves-Dirs([bool]$create = $false) {
    # the saved-games folders of every game profile; with $create also the (new) "saves" folder of a profile that
    # never saved yet - a player who never was host still needs one for downloads
    $docs = [Environment]::GetFolderPath("MyDocuments")
    if ($env:C3RESUME_DOCS) { $docs = $env:C3RESUME_DOCS }        # (for tests)
    $profiles = Join-Path $docs (Join-Path "cossacks" "profiles")
    if ($create) {
        foreach ($p in @(Get-ChildItem -LiteralPath $profiles -Directory -ErrorAction SilentlyContinue)) {
            $sv = Join-Path $p.FullName "saves"
            if (-not (Test-Path -LiteralPath $sv)) { New-Item -ItemType Directory -Path $sv -ErrorAction SilentlyContinue | Out-Null }
        }
    }
    return , @(Get-ChildItem -Path (Join-Path $profiles (Join-Path "*" "saves")) -Directory -ErrorAction SilentlyContinue)
}

function Do-Saves {
    $dirs = Saves-Dirs
    if ($dirs.Count -eq 0) { $dirs = Saves-Dirs $true }        # never saved yet: make the folder (for a copied save)
    if ($dirs.Count -eq 0) { Fail "No saves folder yet: start Cossacks 3 once and make a player profile, then try again." }
    foreach ($d in $dirs) { Write-Host $d.FullName }
    if ($env:OS -eq "Windows_NT") { Start-Process explorer.exe $dirs[0].FullName }
}

# ================================================================================ save-sync helper
# On !save only the host's game saves ("qladder_..."). The host's helper uploads that file to the lobby's
# save service right away. On !load the server marks the save as wanted, and every player's helper downloads
# it then (only then), so that all machines load the host's file - also on a PC that was not in the match.
$SyncName = '^qladder_(auto_)?\d{8}_\d{4,6}_\d{1,4}min$'      # auto_: the autosave
$FilesPort = 31524
$ProgressPreference = "SilentlyContinue"            # Invoke-WebRequest is very slow with its progress bar

function Helper-Home { if ($env:C3RESUME_HOME) { return $env:C3RESUME_HOME } return (Join-Path $env:LOCALAPPDATA "c3resume") }
function Helper-Log([string]$msg) {
    $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $msg
    Write-Host $line
    try { Add-Content -LiteralPath (Join-Path (Helper-Home) "helper.log") -Value $line } catch { }
}
function Server-Host {
    if (-not (Test-Path -LiteralPath (P $ServersDat))) { return $null }
    $mt = [regex]::Match((ReadText (P $ServersDat)), '=\s*([A-Za-z0-9.\-]+)')
    if ($mt.Success) { return $mt.Groups[1].Value } else { return $null }
}
# files are packed / unpacked piece by piece: the save of a long match is several 100 MB
function Gzip-File([string]$src, [string]$dst) {
    $in = [IO.File]::OpenRead($src)
    try {
        $out = [IO.File]::Create($dst)
        try {
            $gz = New-Object IO.Compression.GZipStream($out, [IO.Compression.CompressionMode]::Compress)
            $in.CopyTo($gz, 1048576); $gz.Close()
        } finally { $out.Close() }
    } finally { $in.Close() }
}
function Gunzip-File([string]$src, [string]$dst) {
    $in = [IO.File]::OpenRead($src)
    try {
        $gz = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
        $out = [IO.File]::Create($dst)
        try { $gz.CopyTo($out, 1048576) } finally { $out.Close(); $gz.Close() }
    } finally { $in.Close() }
}

function Sync-Once($since, $seen) {
    $h = Server-Host
    if (-not $h) { return }
    $base = "http://${h}:$FilesPort/c3"
    $remote = @{}
    try {
        $text = (Invoke-WebRequest -UseBasicParsing -Uri "$base/list" -TimeoutSec 10).Content
        if ($text -is [byte[]]) { $text = $Latin1.GetString($text) }
        foreach ($line in ($text -split "`n")) {
            $f = $line.Trim() -split "`t"
            if ($f.Count -ge 2 -and $f[0] -match $SyncName) { $remote[$f[0]] = ($f.Count -ge 4 -and $f[3] -eq "1") }   # True: a !load needs it now
        }
    } catch {
        if ($seen["_down"] -ne $_.Exception.Message) { Helper-Log "save service at $base not reachable ($($_.Exception.Message)) - will keep trying" }
        $seen["_down"] = $_.Exception.Message
        $seen["_fails"] = 1 + [int]$seen["_fails"]
        return
    }
    $seen.Remove("_down")
    $seen["_fails"] = 0
    $dirs = Saves-Dirs
    $autos = @($remote.Keys | Where-Object { $_ -like "qladder_auto_*" } | Sort-Object)
    $newest = ""
    if ($autos.Count -gt 0) {                                            # the server keeps one autosave: drop the replaced ones
        $newest = $autos[-1]
        foreach ($d in $dirs) {
            foreach ($f in @(Get-ChildItem -LiteralPath $d.FullName -Filter "qladder_auto_*.map" -File -ErrorAction SilentlyContinue)) {
                $stem = [IO.Path]::GetFileNameWithoutExtension($f.Name)
                if (($stem -match $SyncName) -and ([string]::CompareOrdinal($stem, $newest) -lt 0) -and -not $remote[$stem]) {   # not while a !load needs it
                    try { Remove-Item -LiteralPath $f.FullName -Force; Helper-Log "removed the older autosave $($f.Name)" } catch { }
                }
            }
        }
    }
    foreach ($d in $dirs) {                                              # upload the host's new saves
        foreach ($f in @(Get-ChildItem -LiteralPath $d.FullName -Filter "qladder_*.map" -File -ErrorAction SilentlyContinue)) {
            $name = [IO.Path]::GetFileNameWithoutExtension($f.Name)
            if (($name -notmatch $SyncName) -or $remote.ContainsKey($name)) { continue }
            if (($name -like "qladder_auto_*") -and ([string]::CompareOrdinal($name, $newest) -lt 0)) { continue }   # replaced already
            $age = ((Get-Date) - $f.LastWriteTime).TotalSeconds
            $steady = ($seen[$f.FullName] -eq $f.Length) -or $seen["_once"]
            if ($f.LastWriteTime -lt $since -or $age -lt 3 -or -not $steady) { $seen[$f.FullName] = $f.Length; continue }
            if (-not $seen.ContainsKey("_failed")) { $seen["_failed"] = @{} }
            $failed = $seen["_failed"]
            if ($failed.ContainsKey($name) -and ((Get-Date) - $failed[$name]).TotalSeconds -lt 120) { continue }   # after a failure: again in 2 minutes
            $tmpgz = Join-Path (Helper-Home) "upload.gz.tmp"
            try {
                Gzip-File $f.FullName $tmpgz
                $packed = (Get-Item -LiteralPath $tmpgz).Length
                Invoke-WebRequest -UseBasicParsing -Method Put -Uri "$base/file/$name" -InFile $tmpgz -ContentType "application/gzip" -TimeoutSec 900 | Out-Null
                $remote[$name] = $false
                $failed.Remove($name)
                Helper-Log ("uploaded $name (" + [int]($packed / 1MB) + " MB packed, " + [int]($f.Length / 1MB) + " MB unpacked)")
            } catch {
                $failed[$name] = Get-Date
                Helper-Log ("upload of $name (" + [int]($f.Length / 1MB) + " MB) failed: $($_.Exception.Message) - trying again in 2 minutes")
            } finally { Remove-Item -LiteralPath $tmpgz -Force -ErrorAction SilentlyContinue }
        }
    }
    $want = @($remote.Keys | Where-Object { $remote[$_] } | Sort-Object)
    if ($want.Count -gt 0) { $dirs = Saves-Dirs $true }
    foreach ($name in $want) {                                           # download what a !load needs and is missing
        foreach ($d in $dirs) {
            $target = Join-Path $d.FullName "$name.map"
            if (Test-Path -LiteralPath $target) { continue }
            $tmpgz = Join-Path $d.FullName "$name.c3gz"
            $tmp = Join-Path $d.FullName "$name.c3tmp"
            try {
                Invoke-WebRequest -UseBasicParsing -Uri "$base/file/$name" -OutFile $tmpgz -TimeoutSec 900
                Gunzip-File $tmpgz $tmp
                Move-Item -LiteralPath $tmp -Destination $target -Force
                Helper-Log ("downloaded $name (" + [int]((Get-Item -LiteralPath $target).Length / 1MB) + " MB) into $($d.FullName)")
            } catch { Helper-Log "download of $name failed: $($_.Exception.Message)" }
            finally {
                Remove-Item -LiteralPath $tmpgz -Force -ErrorAction SilentlyContinue
                Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Do-Helper {
    $home2 = Helper-Home
    New-Item -ItemType Directory -Force -Path $home2 | Out-Null
    $mutex = New-Object Threading.Mutex($false, "c3resume-helper")
    if (-not $Once -and -not $mutex.WaitOne(0)) { Write-Host "the save-sync helper is already running."; return }
    $state = Join-Path $home2 "state.json"
    $since = (Get-Date).AddMinutes(-10)
    if (Test-Path -LiteralPath $state) {
        $v = (Get-Content -LiteralPath $state -Raw | ConvertFrom-Json).since
        if ($v -is [DateTime]) { $since = $v } else { $since = [DateTime]::Parse($v, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind) }
    }
    else { @{ since = $since.ToString("o") } | ConvertTo-Json | Set-Content -LiteralPath $state }
    Helper-Log "save-sync helper $Version started for $script:Game"
    $seen = @{}
    if ($Once) { $seen["_once"] = $true }
    while ($true) {
        try { Sync-Once $since $seen } catch { Helper-Log "problem: $($_.Exception.Message)" }
        if ($Once) { return }
        Start-Sleep -Seconds ([Math]::Min(60, 5 * [Math]::Pow(2, [Math]::Min([int]$seen["_fails"], 4))))   # slower while unreachable
    }
}

function Helper-Running {
    $mx = $null
    if ([Threading.Mutex]::TryOpenExisting("c3resume-helper", [ref]$mx)) { $mx.Dispose(); return $true }
    return $false
}

function Startup-File { return (Join-Path ([Environment]::GetFolderPath("Startup")) "c3resume-helper.vbs") }

function Helper-Installed {
    # set up to start with Windows (it may still not be running right now)
    if ($env:OS -ne "Windows_NT") { return $false }
    return (Test-Path -LiteralPath (Startup-File))
}

function Stop-Helpers {
    # every running helper (also an older version: an update must not leave the old code running until the next login)
    try {
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" |
            Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*c3resume.ps1*helper*" } |
            ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }
    } catch { }
    for ($i = 0; $i -lt 20 -and (Helper-Running); $i++) { Start-Sleep -Milliseconds 250 }
}

function Helper-Install {
    if ($env:OS -ne "Windows_NT") { return }
    $home2 = Helper-Home
    New-Item -ItemType Directory -Force -Path $home2 | Out-Null
    $me = Join-Path $home2 "c3resume.ps1"
    if ($PSCommandPath -ne $me) {
        Copy-Item -LiteralPath $PSCommandPath -Destination $me -Force
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "patches.json") -Destination (Join-Path $home2 "patches.json") -Force
    }
    $args1 = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$me`" helper -GameDir `"$script:Game`""
    $vbs = 'CreateObject("WScript.Shell").Run "powershell.exe ' + $args1.Replace('"', '""') + '", 0, False'
    Set-Content -LiteralPath (Startup-File) -Value $vbs -Encoding ASCII
    Stop-Helpers                                                          # an older helper may still be running
    Start-Process -FilePath "wscript.exe" -ArgumentList "`"$(Startup-File)`"" -WindowStyle Hidden
    for ($i = 0; $i -lt 40 -and -not (Helper-Running); $i++) { Start-Sleep -Milliseconds 250 }   # the window checks next
    Write-Host "The save-sync helper runs now (invisible) and starts by itself at every Windows login."
    Write-Host "Its log: $(Join-Path $home2 'helper.log')"
}

function Helper-Remove {
    if ($env:OS -ne "Windows_NT") { return }
    $sf = Startup-File
    if (Test-Path -LiteralPath $sf) { Remove-Item -LiteralPath $sf -Force }
    Stop-Helpers
    Write-Host "The save-sync helper is stopped and removed from the Windows start."
}

function Do-Info {
    $info = [ordered]@{ version = $Version; game_dir = "$script:Game"; found = $false; installed = $false;
                        installed_version = ""; intact = $false; server = ""; helper = (Helper-Running);
                        helper_installed = (Helper-Installed) }
    if ($script:Game -ne "" -and (Test-Path -LiteralPath (Join-Path $script:Game "data"))) {
        $info.found = $true
        $m = Load-Manifest
        if ($m.files.Count -gt 0) {
            $info.installed = $true
            $info.installed_version = "$($m.version)"
            $ok = $true
            foreach ($rel in $m.files.Keys) { if ((ShaFile (P $rel)) -ne $m.files[$rel].patched_sha) { $ok = $false } }
            foreach ($rel in $m.created) { if (-not (Test-Path -LiteralPath (P $rel))) { $ok = $false } }
            $info.intact = $ok
        }
        if (Test-Path -LiteralPath (P $ServersDat)) {
            $mt = [regex]::Match((ReadText (P $ServersDat)), '=\s*([A-Za-z0-9.\-]+(:\d+)?)')
            if ($mt.Success) { $info.server = $mt.Groups[1].Value }
        }
    }
    Write-Output ($info | ConvertTo-Json -Compress)
}

$script:Game = Find-Game
if ($Command -eq "info") { Do-Info; exit 0 }
$legacy = P "$BackupDir/mods.ini"                     # the lab tool c3mod.py kept mods.ini here
if ((Test-Path -LiteralPath $legacy) -and -not (Test-Path -LiteralPath (P "$BackupDir/mods/mods.ini"))) {
    New-Item -ItemType Directory -Force -Path (P "$BackupDir/mods") | Out-Null
    Move-Item -LiteralPath $legacy -Destination (P "$BackupDir/mods/mods.ini")
}
try {
    switch ($Command.ToLower()) {
        "install" { Do-Install }
        "uninstall" { Do-Uninstall }
        "status" { Do-Status }
        "saves" { Do-Saves }
        "helper" { Do-Helper }
        default { Fail "unknown command '$Command' (install, uninstall, status, saves, helper)" }
    }
} catch [UnauthorizedAccessException] {
    Fail "Windows did not allow changing the game files. Close the game, then right-click the .bat file and choose 'Run as administrator'."
} catch {
    Fail ("Something went wrong: " + $_.Exception.Message)
}
