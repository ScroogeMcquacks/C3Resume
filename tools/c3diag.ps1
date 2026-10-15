# c3diag.ps1 - c3resume diagnostics for Windows: why does this PC not get the save files?
# Collects everything about the save helper and its connection to the server into ONE report on the desktop:
#   c3resume-diagnose.txt   -> send that file to your host.
# Reads no passwords and no profile.cfg; your user name is replaced by <user> in the report.
#
# Run it:  right-click this file > "Run with PowerShell"
#     or:  powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\c3diag.ps1"
# It takes about 1-2 minutes (it downloads the newest save once as a speed test and deletes it again).

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Report = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { Write-Host $s; $Report.Add($s) }
function Section([string]$t) { Say ""; Say ("==== " + $t) }
function Safe([scriptblock]$b) { try { & $b } catch { Say ("  ERROR: " + $_.Exception.Message) } }

$HelperHome = Join-Path $env:LOCALAPPDATA "c3resume"
$Startup = Join-Path ([Environment]::GetFolderPath("Startup")) "c3resume-helper.vbs"
$GameDir = $null
$ServerHost = $null

Section "1. System"
Safe {
    Say ("  Time:        " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"))
    Say ("  Windows:     " + [Environment]::OSVersion.VersionString + "  64-bit: " + [Environment]::Is64BitOperatingSystem)
    Say ("  PowerShell:  " + $PSVersionTable.PSVersion.ToString())
    Say ("  Exec policy: " + (Get-ExecutionPolicy))
}

Section "2. c3resume installation and the save helper"
Safe {
    if (Test-Path -LiteralPath $HelperHome) {
        Say "  Helper folder: $HelperHome"
        Get-ChildItem -LiteralPath $HelperHome -File | ForEach-Object { Say ("    {0,-24} {1,10} bytes  {2}" -f $_.Name, $_.Length, $_.LastWriteTime) }
        $me = Join-Path $HelperHome "c3resume.ps1"
        if (Test-Path -LiteralPath $me) {
            $v = Select-String -LiteralPath $me -Pattern '^\$Version = "(.*)"' | Select-Object -First 1
            if ($v) { Say ("  Helper version: " + $v.Matches[0].Groups[1].Value) }
        } else { Say "  PROBLEM: c3resume.ps1 is missing in the helper folder - run the setup again (Install)." }
    } else { Say "  No helper folder: the save helper was never installed on this PC." }
    if (Test-Path -LiteralPath $Startup) {
        $vbs = Get-Content -LiteralPath $Startup -Raw
        Say "  Autostart file: $Startup"
        Say ("    " + $vbs.Trim())
        $m = [regex]::Match($vbs, '-GameDir ""(.*?)""')
        if ($m.Success) { $script:GameDir = $m.Groups[1].Value }
    } else { Say "  No autostart file: the save helper is NOT installed. If that was not on purpose: run the setup, tick the save helper box, click Install. (Without it, saves are copied by hand.)" }
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction SilentlyContinue |
               Where-Object { $_.CommandLine -like "*c3resume*helper*" })
    if ($procs.Count -gt 0) {
        foreach ($p in $procs) { Say ("  Helper RUNNING: process " + $p.ProcessId + ", started " + $p.CreationDate) }
        if ($procs.Count -gt 1) { Say "  NOTE: more than one helper process." }
    } else { Say "  PROBLEM: the helper is NOT running." }
}

Section "3. Game folder and server address"
Safe {
    if (-not $GameDir) {
        $cands = @()
        foreach ($lib in @("${env:ProgramFiles(x86)}\Steam\steamapps\common\Cossacks 3", "$env:ProgramFiles\Steam\steamapps\common\Cossacks 3")) { if (Test-Path -LiteralPath $lib) { $cands += $lib } }
        if ($cands.Count -gt 0) { $script:GameDir = $cands[0] }
    }
    if ($GameDir -and (Test-Path -LiteralPath $GameDir)) {
        Say "  Game folder: $GameDir"
        $sd = Join-Path $GameDir "data\resources\servers.dat"
        if (Test-Path -LiteralPath $sd) {
            $txt = Get-Content -LiteralPath $sd -Raw
            Say ("  servers.dat: " + ($txt -replace "`r?`n", " | "))
            $m = [regex]::Match($txt, '=\s*([A-Za-z0-9.\-]+)')
            if ($m.Success) { $script:ServerHost = $m.Groups[1].Value }
        } else { Say "  PROBLEM: servers.dat not found." }
        $mf = Join-Path $GameDir "c3backup\manifest.json"
        if (Test-Path -LiteralPath $mf) { Say ("  Installed c3resume version: " + (Get-Content -LiteralPath $mf -Raw | ConvertFrom-Json).version) }
        else { Say "  PROBLEM: c3resume is not installed in this game folder (no c3backup\manifest.json)." }
    } else { Say "  PROBLEM: game folder not found." }
    if ($ServerHost) { Say "  Server: $ServerHost (lobby port 31523, save service port 31524)" }
}

Section "4. Saved-games folders (where the helper puts the downloaded saves)"
Safe {
    $docs = [Environment]::GetFolderPath("MyDocuments")
    if (-not $docs) { $docs = Join-Path $env:USERPROFILE "Documents" }
    Say "  Documents folder (Windows): $docs"
    if ($docs -like "*OneDrive*") { Say "  NOTE: Documents is inside OneDrive. If OneDrive is paused or the files are 'online only', saves can be missing." }
    $prof = Join-Path $docs "cossacks\profiles"
    if (Test-Path -LiteralPath $prof) {
        foreach ($p in @(Get-ChildItem -LiteralPath $prof -Directory)) {
            $sv = Join-Path $p.FullName "saves"
            if (Test-Path -LiteralPath $sv) {
                $maps = @(Get-ChildItem -LiteralPath $sv -Filter "qladder_*.map" -File | Sort-Object LastWriteTime -Descending)
                Say ("  Profile folder '" + $p.Name + "': saves folder OK, " + $maps.Count + " c3resume saves")
                foreach ($f in ($maps | Select-Object -First 5)) { Say ("    {0}  {1,8:N0} MB  {2}" -f $f.Name, ($f.Length / 1MB), $f.LastWriteTime) }
                $tmpfiles = @(Get-ChildItem -LiteralPath $sv -File | Where-Object { $_.Name -like "*.c3tmp" -or $_.Name -like "*.c3gz" })
                if ($tmpfiles.Count -gt 0) { Say ("    NOTE: " + $tmpfiles.Count + " unfinished download(s) here (.c3tmp/.c3gz) - a download broke off.") }
                $probe = Join-Path $sv "c3diag-write-test.tmp"
                try { Set-Content -LiteralPath $probe -Value "test"; Remove-Item -LiteralPath $probe -Force; Say "    Writing into this folder: OK" }
                catch { Say ("    PROBLEM: PowerShell cannot write here: " + $_.Exception.Message) }
            } else { Say ("  Profile folder '" + $p.Name + "': no saves folder yet (the helper creates it when it downloads)") }
        }
    } else { Say "  PROBLEM: $prof does not exist - start Cossacks 3 once (with this Windows user)." }
    try {
        $cfa = (Get-MpPreference -ErrorAction Stop).EnableControlledFolderAccess
        Say ("  Windows Defender 'Controlled folder access': " + @("off", "ON (blocks unknown programs from writing to Documents!)", "audit only")[[int]$cfa])
        $ev = @(Get-WinEvent -LogName "Microsoft-Windows-Windows Defender/Operational" -MaxEvents 300 -ErrorAction Stop |
                Where-Object { $_.Id -eq 1123 -or $_.Id -eq 1124 } | Select-Object -First 5)
        foreach ($e in $ev) { Say ("    blocked: " + $e.TimeCreated + "  " + (($e.Message -split "`n" | Where-Object { $_ -match "Path|Process|Pfad|Prozess" }) -join " ").Trim()) }
    } catch { Say "  (Defender settings not readable - other antivirus? Then check its blocked/quarantine list for powershell.exe.)" }
}

if ($ServerHost) {
    Section "5. Network connection to the server ($ServerHost)"
    Safe {
        foreach ($port in 31523, 31524) {
            $t = Test-NetConnection -ComputerName $ServerHost -Port $port -WarningAction SilentlyContinue
            Say ("  TCP port {0}: {1}   (from {2} via {3})" -f $port, $(if ($t.TcpTestSucceeded) { "reachable" } else { "NOT REACHABLE" }), $t.SourceAddress.IPAddress, $t.InterfaceAlias)
        }
    }
    Safe {
        $pings = @(Test-Connection -ComputerName $ServerHost -Count 6 -ErrorAction SilentlyContinue)
        if ($pings.Count -gt 0) {
            $ms = @($pings | ForEach-Object { if ($_.ResponseTime -ne $null) { $_.ResponseTime } else { $_.Latency } })
            Say ("  Ping: {0} of 6 answered, {1} ms average, {2} ms max" -f $pings.Count, [int](($ms | Measure-Object -Average).Average), (($ms | Measure-Object -Maximum).Maximum))
        } else { Say "  Ping: no answer (can be normal if ping is blocked)" }
    }
    Safe {
        $uri = "http://${ServerHost}:31524/c3/list"
        $proxy = [System.Net.WebRequest]::GetSystemWebProxy().GetProxy([Uri]$uri)
        if ($proxy -and $proxy.AbsoluteUri -and $proxy.AbsoluteUri -ne ([Uri]$uri).AbsoluteUri) { Say ("  PROBLEM: Windows sends web requests to the server through a PROXY: " + $proxy.AbsoluteUri) }
        else { Say "  Proxy: none (good)" }
        $wh = (netsh winhttp show proxy) -join " "
        Say ("  WinHTTP proxy: " + ($wh -replace '\s+', ' ').Trim())
    }
    Safe {
        $ts = Get-Command tailscale -ErrorAction SilentlyContinue
        if (-not $ts -and (Test-Path "$env:ProgramFiles\Tailscale\tailscale.exe")) { $ts = "$env:ProgramFiles\Tailscale\tailscale.exe" }
        if ($ts) {
            Say "  Tailscale: installed"
            Say ("    " + ((& $ts ping -c 4 $ServerHost 2>&1) -join "`n    "))
            Say "    ('via DERP' = traffic goes through a relay server = slow. 'via <ip>' = direct = good.)"
        }
    }

    Section "6. The save service (what the helper sees)"
    $list = $null
    Safe {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://${ServerHost}:31524/c3/list" -TimeoutSec 20
        $sw.Stop()
        $text = $r.Content
        if ($text -is [byte[]]) { $text = [Text.Encoding]::ASCII.GetString($text) }
        $script:list = @($text -split "`n" | Where-Object { $_.Trim() -ne "" })
        Say ("  List of saves: HTTP " + $r.StatusCode + " in " + $sw.ElapsedMilliseconds + " ms, " + $list.Count + " saves on the server")
        foreach ($l in ($list | Select-Object -First 5)) {
            $f = $l.Trim() -split "`t"
            Say ("    {0}  {1,6:N1} MB packed{2}" -f $f[0], ([double]$f[1] / 1MB), $(if ($f.Count -ge 4 -and $f[3] -eq "1") { "   <- a !load wants it right now" } else { "" }))
        }
    }
    Safe {
        if ($list -and $list.Count -gt 0) {
            $f = $list[0].Trim() -split "`t"
            $name = $f[0]
            $tmpgz = Join-Path $env:TEMP "c3diag-test.gz"
            Say "  Download test with the newest save ($name, like the helper does it) ..."
            $sw = [Diagnostics.Stopwatch]::StartNew()
            Invoke-WebRequest -UseBasicParsing -Uri "http://${ServerHost}:31524/c3/file/$name" -OutFile $tmpgz -TimeoutSec 900
            $sw.Stop()
            $len = (Get-Item -LiteralPath $tmpgz).Length
            $sec = [Math]::Max(0.1, $sw.Elapsed.TotalSeconds)
            Say ("  Downloaded {0:N1} MB in {1:N1} s = {2:N2} MB/s" -f ($len / 1MB), $sec, ($len / 1MB / $sec))
            if ($len -ne [long]$f[1]) { Say ("  PROBLEM: size differs from the server's list (" + $f[1] + " bytes) - the download broke off.") }
            $in = [IO.File]::OpenRead($tmpgz)
            try {
                $gz = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
                $buf = New-Object byte[] 1048576; $total = 0
                while (($n = $gz.Read($buf, 0, $buf.Length)) -gt 0) { $total += $n }
                Say ("  Unpacked OK: {0:N0} MB (the file is complete)" -f ($total / 1MB))
            } catch { Say ("  PROBLEM: the downloaded file is damaged: " + $_.Exception.Message) }
            finally { $in.Close() }
            Remove-Item -LiteralPath $tmpgz -Force -ErrorAction SilentlyContinue
            if ($sec -gt 60) { Say "  NOTE: the download takes longer than a minute - during !load the server waits only a limited time for every PC." }
        }
    }
}

Section "7. The helper's log (last 80 lines)"
Safe {
    $log = Join-Path $HelperHome "helper.log"
    if (Test-Path -LiteralPath $log) {
        $all = @(Get-Content -LiteralPath $log)
        Say ("  " + $all.Count + " lines; failed downloads: " + @($all | Where-Object { $_ -match "download of .* failed" }).Count +
             "; failed uploads: " + @($all | Where-Object { $_ -match "upload of .* failed" }).Count +
             "; 'not reachable': " + @($all | Where-Object { $_ -match "not reachable" }).Count)
        foreach ($l in ($all | Select-Object -Last 80)) { Say ("  | " + $l) }
    } else { Say "  no helper.log yet" }
}

# the report, without the user name
$text = ($Report -join "`r`n")
if ($env:USERPROFILE) { $text = $text.Replace($env:USERPROFILE, "%USERPROFILE%") }
if ($env:USERNAME) { $text = $text.Replace($env:USERNAME, "<user>") }
$out = Join-Path ([Environment]::GetFolderPath("Desktop")) "c3resume-diagnose.txt"
try { Set-Content -LiteralPath $out -Value $text -Encoding UTF8; Write-Host ""; Write-Host "Report saved: $out  - send this file to your host." -ForegroundColor Green }
catch { Write-Host "Could not save the report ($($_.Exception.Message)) - copy the text above instead." -ForegroundColor Yellow }
if ($Host.Name -eq "ConsoleHost") { Write-Host "Press Enter to close."; [void](Read-Host) }
