# Start-C3Server.ps1
#
# Starts the C3Resume multiplayer server natively on Windows 11:
#   - the lobby server      server\sich_c3.lua   (Lua 5.1.5 + LuaSocket, runtime\lua51) on TCP 31523 + UDP 31523
#   - the save service      server\c3saves_server.py (Python 3)                          on TCP 31524
#
# Persistent data lives OUTSIDE the project (no OneDrive sync of big saves), by default in
# %LOCALAPPDATA%\C3ResumeServer. The project folder is only read, never written:
# server\sich_c3.lua is copied to <data>\sich.lua and run from there, because the server keeps its
# .store files (config.store, register.store) next to the script it runs.
#
# Usage (normal use is the .cmd next to this file):
#   Start-C3Server.cmd                     start and keep running until Ctrl+C
#   Start-C3Server.cmd -Stop               ask a running server in the same data folder to stop
#   Start-C3Server.cmd -DataDir D:\C3Data  use another data folder
#
# Exit codes: 0 stopped normally / on request, 1 startup error, 2 already running,
#             3 a port is in use, 4 the runtime or a server file is missing, 5 a child process died.

param(
    [string]$DataDir = "",
    [switch]$Stop,
    [switch]$NoColor,
    [switch]$Diag
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------- fixed values (same as server\start_server.sh)

$LobbyPort    = 31523
$SavesPort    = 31524
$MutexName    = "Local\C3ResumeServer"
$StopFile     = "stop.request"
# ---------------------------------------------------------------- output helpers

function Test-LauncherRunning {
    $m = $null
    try {
        return [bool][Threading.Mutex]::TryOpenExisting($MutexName, [ref]$m)
    } catch {
        return $false
    } finally {
        if ($null -ne $m) { try { $m.Dispose() } catch { } }
    }
}

# ---------------------------------------------------------------- (the script body is at the end of this file, after the helpers)

function Write-Line([string]$text, [string]$color) {
    if ($script:UseColor -and $color) { Write-Host $text -ForegroundColor $color } else { Write-Host $text }
}
function Step([string]$text) { Write-Line $text "Gray" }
function Ok([string]$text)   { Write-Line ("  [ok] " + $text) "Green" }
function Info([string]$text) { Write-Line ("       " + $text) "Gray" }
function Warn([string]$text) { Write-Line ("  [!!] " + $text) "Yellow" }
function Err([string]$text)  { Write-Line ("  [XX] " + $text) "Red" }

# ---------------------------------------------------------------- small helpers

function Test-TcpConnect([int]$port, [int]$timeoutMs) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($timeoutMs)) { $c.Close(); return $false }
        $c.EndConnect($iar)
        $c.Close()
        return $true
    } catch { return $false }
}

function Test-TcpPortFree([int]$port) {
    # false when something already answers on the port, or when it cannot be bound
    if (Test-TcpConnect $port 300) { return $false }
    $l = $null
    try {
        $l = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Any, $port)
        $l.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($null -ne $l) { try { $l.Stop() } catch { } }
    }
}

function Test-UdpPortFree([int]$port) {
    $u = $null
    try {
        $u = New-Object Net.Sockets.UdpClient($port)
        return $true
    } catch {
        return $false
    } finally {
        if ($null -ne $u) { try { $u.Close() } catch { } }
    }
}

function Read-SharedText([string]$path) {
    # a redirected stdout file is still held open by the child process: read it with shared access
    if (-not (Test-Path -LiteralPath $path)) { return "" }
    try {
        $fs = New-Object IO.FileStream($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            $sr = New-Object IO.StreamReader($fs)
            try { return $sr.ReadToEnd() } finally { $sr.Close() }
        } finally { $fs.Close() }
    } catch { return "" }
}

function Show-LogTail([string]$path, [int]$count) {
    $text = Read-SharedText $path
    if ($text.Trim() -eq "") { Info ("(no output in " + (Split-Path -Leaf $path) + ")"); return }
    foreach ($ln in (@($text -split "`r?`n") | Where-Object { $_.Trim() -ne "" } | Select-Object -Last $count)) {
        Info ("  | " + $ln.TrimEnd())
    }
}

function Start-NewLog([string]$path) {
    # keep the previous run's log as <name>.1: a restart must not throw the last run away
    try {
        if (-not (Test-Path -LiteralPath $path)) { return }
        if ((Get-Item -LiteralPath $path).Length -gt 0) {
            Move-Item -LiteralPath $path -Destination ($path + ".1") -Force
        } else {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    } catch { }
}

function Get-LanAddresses {
    $out = @()
    try {
        $out = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                 Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
                 ForEach-Object { $_.IPAddress + "  (" + $_.InterfaceAlias + ")" })
    } catch {
        try {
            $out = @([Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName()) |
                     Where-Object { $_.AddressFamily -eq "InterNetwork" -and -not [Net.IPAddress]::IsLoopback($_) } |
                     ForEach-Object { $_.IPAddressToString })
        } catch { }
    }
    return @($out | Sort-Object -Unique)
}

function Get-FreeBytes([long]$bytes) {
    if ($bytes -ge 1GB) { return ("{0:N1} GB" -f ($bytes / 1GB)) }
    if ($bytes -ge 1MB) { return ("{0:N1} MB" -f ($bytes / 1MB)) }
    return ("{0:N0} KB" -f ($bytes / 1KB))
}

function Test-ChildAlive($proc) {
    if ($null -eq $proc) { return $false }
    try { return -not $proc.HasExited } catch { return $false }
}

# ---------------------------------------------------------------- Python 3

function Invoke-Native([string]$exe, [string[]]$arguments) {
    # Native tools write to stderr for normal output too (e.g. "lua -v"), which PowerShell would
    # turn into a terminating error while $ErrorActionPreference is "Stop".
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe @arguments 2>&1
        $code = $LASTEXITCODE
        return @{
            Code = $code
            Output = @(@($out) | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ -ne "" })
        }
    } catch {
        return @{ Code = -1; Output = @($_.Exception.Message) }
    } finally {
        $ErrorActionPreference = $old
    }
}

function Find-Python {
    $cands = @()
    $g = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($g) { $cands += @{ Exe = $g.Source; Pre = @("-3") } }
    foreach ($n in @("python.exe", "python3.exe")) {
        $g = Get-Command $n -ErrorAction SilentlyContinue
        if ($g) { $cands += @{ Exe = $g.Source; Pre = @() } }
    }
    foreach ($c in $cands) {
        $a = @($c.Pre) + @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])")
        $r = Invoke-Native $c.Exe $a
        $v = ($r.Output -join " ")
        $m = [regex]::Match($v, "^(\d+)\.(\d+)\.(\d+)$")
        if (-not ($r.Code -eq 0 -and $m.Success -and [int]$m.Groups[1].Value -eq 3 -and [int]$m.Groups[2].Value -ge 6)) { continue }
        # Start the interpreter itself, not the py.exe launcher: then the tracked process IS the
        # save service, with no extra parent process left behind.
        $ex = Invoke-Native $c.Exe (@($c.Pre) + @("-c", "import sys; print(sys.executable)"))
        $real = ($ex.Output -join "").Trim()
        if ($ex.Code -eq 0 -and $real -ne "" -and (Test-Path -LiteralPath $real)) {
            return @{ Exe = $real; Pre = @(); Version = $v }
        }
        return @{ Exe = $c.Exe; Pre = @($c.Pre); Version = $v }
    }
    return $null
}

# ---------------------------------------------------------------- Job Object
# The job kills the two child processes when this launcher dies (window closed, Task Manager,
# Ctrl+Break). Together with the tracked list below, no other lua.exe/python.exe is ever touched.

function Initialize-JobObject {
    $cs = @'
using System;
using System.Runtime.InteropServices;

public static class C3Job
{
    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr attributes, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint infoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private const int JobObjectExtendedLimitInformation = 9;
    private const uint JobObjectLimitKillOnJobClose = 0x2000;

    public static IntPtr CreateKillOnClose()
    {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) { return IntPtr.Zero; }
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        info.BasicLimitInformation.LimitFlags = JobObjectLimitKillOnJobClose;
        int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        IntPtr buffer = Marshal.AllocHGlobal(length);
        try
        {
            Marshal.StructureToPtr(info, buffer, false);
            if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, buffer, (uint)length))
            {
                CloseHandle(job);
                return IntPtr.Zero;
            }
        }
        finally { Marshal.FreeHGlobal(buffer); }
        return job;
    }

    public static bool Assign(IntPtr job, IntPtr process)
    {
        if (job == IntPtr.Zero || process == IntPtr.Zero) { return false; }
        return AssignProcessToJobObject(job, process);
    }
}
'@
    Add-Type -TypeDefinition $cs -ErrorAction Stop
}

# ---------------------------------------------------------------- tracked child processes

$script:Children = @()
$script:Job = $null

function Start-Tracked([string]$exe, [string]$arguments, [string]$cwd, [string]$outLog, [string]$errLog, [string]$label) {
    $p = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $cwd `
                       -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
                       -PassThru -WindowStyle Hidden
    $start = $null
    try { $start = $p.StartTime } catch { }
    $script:Children += [pscustomobject]@{ Proc = $p; StartTime = $start; Name = $p.ProcessName; Label = $label }
    Ok ($label + " started (PID " + $p.Id + ")")
    if ($null -ne $script:Job) {
        try {
            if (-not [C3Job]::Assign($script:Job, $p.Handle)) {
                Warn ($label + ": could not be added to the cleanup job (still tracked by this window)")
            }
        } catch {
            Warn ($label + ": cleanup job unavailable (" + $_.Exception.Message + ")")
        }
    }
    return $p
}

function Stop-TrackedChildren {
    foreach ($c in @($script:Children)) {
        if ($null -eq $c) { continue }
        $p = $c.Proc
        try {
            if ($p.HasExited) { continue }
            $live = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
            if ($null -eq $live) { continue }
            if ($live.ProcessName -ne $c.Name) { continue }
            if ($null -ne $c.StartTime) {
                if ([math]::Abs(($live.StartTime - $c.StartTime).TotalSeconds) -gt 1) { continue }
            }
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            for ($i = 0; $i -lt 30 -and -not $p.HasExited; $i++) { Start-Sleep -Milliseconds 100 }
            if ($p.HasExited) { Info ($c.Label + " stopped (PID " + $p.Id + ")") }
            else { Warn ($c.Label + " (PID " + $p.Id + ") is still running") }
        } catch { }
    }
}

# =============================================================================== main body

$LauncherDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($LauncherDir)) { $LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = Split-Path -Parent $LauncherDir

$RuntimeDir = Join-Path $Root "runtime\lua51"
$LuaExe     = Join-Path $RuntimeDir "lua.exe"
$SichSrc    = Join-Path $Root "server\sich_c3.lua"
$SavesPy    = Join-Path $Root "server\c3saves_server.py"

if ($DataDir -eq "") { $Data = Join-Path $env:LOCALAPPDATA "C3ResumeServer" }
else { $Data = [IO.Path]::GetFullPath($DataDir) }

$LuaPath    = $RuntimeDir + "\?.lua;" + $RuntimeDir + "\?\init.lua"
$LuaCpath   = $RuntimeDir + "\?.dll"
$DataSich   = Join-Path $Data "sich.lua"
$DataConfig = Join-Path $Data "config.store"
$DataSaves  = Join-Path $Data "saves"
$StopPath   = Join-Path $Data $StopFile
$LuaOut     = Join-Path $Data "server.log"
$LuaErr     = Join-Path $Data "server.err.log"
$SavesOut   = Join-Path $Data "saves.log"
$SavesErr   = Join-Path $Data "saves.err.log"

# ---------------------------------------------------------------- -Diag : is the save service reachable?

if ($Diag) {
    Write-Line "C3Resume save-service check" "Cyan"
    Info ("data: " + $Data)
    $ok = $true
    if (-not (Test-Path -LiteralPath $Data)) {
        Err ("data folder missing: " + $Data)
        $ok = $false
    } else {
        foreach ($f in @($DataSich, $DataConfig)) {
            if (Test-Path -LiteralPath $f) { Ok ("present: " + (Split-Path -Leaf $f)) }
            else { Err ("missing: " + (Split-Path -Leaf $f)); $ok = $false }
        }
        $saveCount = 0
        if (Test-Path -LiteralPath $DataSaves) {
            $saveCount = @(Get-ChildItem -LiteralPath $DataSaves -Filter "*.map.gz" -File -ErrorAction SilentlyContinue).Count
        }
        Info ("saves on disk: " + $saveCount)
        foreach ($n in @("index.txt", "meta.txt", "wanted.txt", "helpers.txt")) {
            $f = Join-Path $DataSaves $n
            if (Test-Path -LiteralPath $f) { Info ("  " + $n + "  " + (Get-Item -LiteralPath $f).Length + " B") }
            else { Info ("  " + $n + "  (missing)") }
        }
    }
    if (Test-TcpConnect $SavesPort 1500) { Ok ("TCP " + $SavesPort + " accepts connections") }
    else { Err ("TCP " + $SavesPort + " does not answer - is the server running?"); $ok = $false }
    if ($ok) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:" + $SavesPort + "/c3/list") -TimeoutSec 10
            if ($r.StatusCode -eq 200) {
                Ok "GET /c3/list -> HTTP 200"
                $listLines = @(($r.Content -split "`n") | Where-Object { $_ -ne "" })
                Info ("saves listed by the service: " + $listLines.Count)
                foreach ($ln in ($listLines | Select-Object -First 5)) { Info ("  " + $ln.TrimEnd()) }
            } else {
                Err ("GET /c3/list -> HTTP " + $r.StatusCode)
                $ok = $false
            }
        } catch {
            Err ("GET /c3/list failed: " + $_.Exception.Message)
            $ok = $false
        }
    }
    if ($ok) { Ok "the save service is reachable"; exit 0 }
    Err "the save service is NOT reachable"
    exit 1
}

# ---------------------------------------------------------------- -Stop

if ($Stop) {
    if (-not (Test-LauncherRunning)) {
        Write-Line "No C3Resume server is running." "Yellow"
        Info ("data folder: " + $Data)
        exit 0
    }
    New-Item -ItemType Directory -Force -Path $Data | Out-Null
    Set-Content -LiteralPath $StopPath -Value ((Get-Date).ToString("s")) -Encoding ASCII
    Step "Asked the running server to stop ..."
    $gone = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if (-not (Test-LauncherRunning)) { $gone = $true; break }
    }
    if ($gone) { Ok "the server stopped"; exit 0 }
    Err "the server is still running after 20 s. Close its window."
    exit 1
}

# ---------------------------------------------------------------- single instance
# Taking the mutex must be one atomic step. A "does it exist?" check followed by "create it"
# would let two windows start at the same moment, both pass the check and fight for the ports.

$Mutex = $null
$isFirstInstance = $true
try {
    $Mutex = New-Object System.Threading.Mutex($false, $MutexName)
    try {
        $isFirstInstance = $Mutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $isFirstInstance = $true
    }
} catch {
    Warn ("the single-instance mutex is unavailable: " + $_.Exception.Message)
    $Mutex = $null
    $isFirstInstance = $true
}

if (-not $isFirstInstance) {
    Err "the C3Resume server is already running in another window."
    Info "Two servers would fight for the same ports."
    Info "Stop the other one with Ctrl+C, or run:  Start-C3Server.cmd -Stop"
    exit 2
}

Write-Line ""
Write-Line "C3Resume server for Cossacks 3" "Cyan"
Write-Line "===============================" "Cyan"
Info ("project:  " + $Root)
Info ("data:     " + $Data)
if ($Data -like "*OneDrive*") {
    Warn "the data folder is inside OneDrive - big saves should not be synced."
    Warn "Start with -DataDir <folder outside OneDrive>, or use the default %LOCALAPPDATA%\C3ResumeServer."
}
Write-Line ""

$script:ExitCode = 0

try {
    do {
        # ------------------------------------------------------------ 1) files
        Step "1. files"
        $missing = @()
        foreach ($f in @(
            $LuaExe,
            (Join-Path $RuntimeDir "lua51.dll"),
            (Join-Path $RuntimeDir "socket.lua"),
            (Join-Path $RuntimeDir "socket\core.dll"),
            $SichSrc,
            $SavesPy)) {
            if (-not (Test-Path -LiteralPath $f)) { $missing += $f }
        }
        if ($missing.Count -gt 0) {
            Err "these files are missing:"
            foreach ($f in $missing) { Info $f }
            Info ""
            Info "The Lua runtime is built with:  powershell -ExecutionPolicy Bypass -File runtime\build-lua51.ps1"
            $script:ExitCode = 4
            break
        }
        Ok "runtime\lua51 and the server files are there"

        $py = Find-Python
        if ($null -eq $py) {
            Err "Python 3.6 or newer not found (py.exe / python.exe)."
            Info "Install Python 3 from python.org and make sure 'py' or 'python' is on PATH."
            $script:ExitCode = 4
            break
        }
        Ok ("Python " + $py.Version + "  " + $py.Exe)

        # Lua + LuaSocket, probed in exactly the environment the server will get
        $oldLuaPath1 = $env:LUA_PATH
        $oldLuaCpath1 = $env:LUA_CPATH
        try {
            $env:LUA_PATH = $LuaPath
            $env:LUA_CPATH = $LuaCpath
            $probe = Invoke-Native $LuaExe @("-e", "io.write(_VERSION, ' + ', require('socket')._VERSION)")
        } finally {
            $env:LUA_PATH = $oldLuaPath1
            $env:LUA_CPATH = $oldLuaCpath1
        }
        $probeText = ($probe.Output -join " ")
        if ($probe.Code -ne 0 -or $probeText -notlike "Lua 5.1*") {
            Err ("Lua/LuaSocket do not work: " + $probeText)
            Info "Rebuild the runtime with:  powershell -ExecutionPolicy Bypass -File runtime\build-lua51.ps1"
            $script:ExitCode = 4
            break
        }
        Ok ("Lua      " + $probeText)

        # ------------------------------------------------------------ 2) ports
        Step "2. ports"
        $busy = @()
        if (-not (Test-TcpPortFree $LobbyPort)) { $busy += ("TCP " + $LobbyPort + "  (lobby server)") }
        if (-not (Test-TcpPortFree $SavesPort)) { $busy += ("TCP " + $SavesPort + "  (save service)") }
        if (-not (Test-UdpPortFree $LobbyPort)) { $busy += ("UDP " + $LobbyPort + "  (LAN echo of the lobby)") }
        if ($busy.Count -gt 0) {
            Err "these ports are already in use:"
            foreach ($b in $busy) { Info ("  " + $b) }
            Write-Line ""
            Info "Nothing was started. Either another C3Resume server is still running,"
            Info "or another program holds the port. Check with:"
            Info ("  netstat -ano | findstr :" + $LobbyPort)
            Info ("  netstat -ano | findstr :" + $SavesPort)
            Info "If only UDP 31523 is taken, add  echo = false,  to config.store (no LAN auto-discovery)."
            $script:ExitCode = 3
            break
        }
        Ok ("TCP " + $LobbyPort + ", TCP " + $SavesPort + " and UDP " + $LobbyPort + " are free")

        # ------------------------------------------------------------ 3) data folder
        Step "3. data folder"
        New-Item -ItemType Directory -Force -Path $Data | Out-Null
        foreach ($sub in @("saves", "recordings")) {
            New-Item -ItemType Directory -Force -Path (Join-Path $Data $sub) | Out-Null
        }
        Ok ("saves and recordings under " + $Data)

        # A stop.request from an earlier run is stale (this window holds the single-instance mutex).
        # It is dropped HERE, before the server starts: a request that arrives later - also during
        # startup - is left alone and honoured by the run loop below.
        if (Test-Path -LiteralPath $StopPath) {
            Remove-Item -LiteralPath $StopPath -Force -ErrorAction SilentlyContinue
            Info "stale stop.request removed"
        }

        $srcHash = (Get-FileHash -LiteralPath $SichSrc -Algorithm SHA256).Hash
        $dstHash = ""
        if (Test-Path -LiteralPath $DataSich) { $dstHash = (Get-FileHash -LiteralPath $DataSich -Algorithm SHA256).Hash }
        if ($srcHash -ne $dstHash) {
            Copy-Item -LiteralPath $SichSrc -Destination $DataSich -Force
            Ok "server\sich_c3.lua copied to <data>\sich.lua (the source file stays untouched)"
        } else {
            Info "sich.lua in the data folder is already up to date"
        }

        if (-not (Test-Path -LiteralPath $DataConfig)) {
            # The same configuration server\start_server.sh writes on a Linux server.
            # The parser (xstore.load in sich_c3.lua) does loadfile() + setfenv() and expects a
            # returned table, so this file is plain Lua and may use io.output() and friends.
            $cfgText = @"
-- generated once by launcher\Start-C3Server.ps1; edit it here to change settings
-- (start_server.sh uses io.stdout:setvbuf("line"); on Windows that is block buffering for a
--  redirected stdout, so the log files would stay empty until the buffer fills - "no" writes
--  every line at once, which is what that line intends)
io.stdout:setvbuf("no")
return {
`thost = "*",
`tport = $LobbyPort,
`tlog  = { level = "info", output = io.output() },
`techo = nil,

`t-- every packet of every started room is recorded here (QLREC1 files); paths are inside the data folder
`trecordings = "recordings",
`tmatchlog   = "matches.jsonl",
`tstatus     = "status.json",

`t-- chat commands: !pause !unpause !save !autosave !saves !load !help ...
`t-- the autosave interval: add  autosave_seconds = 300,  inside commands = { ... }
`tcommands = { bot = { nick = "C3Lab" }, saves_dir = "saves" },
}
"@
            [IO.File]::WriteAllText($DataConfig, $cfgText, (New-Object Text.ASCIIEncoding))
            Ok "config.store created (same content as server\start_server.sh writes)"
        } else {
            Info "config.store already exists and is used as it is (edit it to change settings)"
        }

        foreach ($logFile in @($LuaOut, $LuaErr, $SavesOut, $SavesErr)) { Start-NewLog $logFile }

        # ------------------------------------------------------------ 4) cleanup job
        $script:Job = $null
        try {
            Initialize-JobObject
            $h = [C3Job]::CreateKillOnClose()
            if ($h.Equals([IntPtr]::Zero)) { Warn "the cleanup job could not be created (the tracked list is still used)" }
            else { $script:Job = $h }
        } catch {
            Warn ("the cleanup job is unavailable: " + $_.Exception.Message)
        }

        # ------------------------------------------------------------ 5) save service (TCP 31524)
        Step "4. starting the two server processes"
        $pyArgs = (($py.Pre -join " ") + ' -u "' + $SavesPy + '" --dir "' + $DataSaves + '" --port ' + $SavesPort).Trim()
        $pSaves = Start-Tracked $py.Exe $pyArgs $Data $SavesOut $SavesErr "save service (TCP $SavesPort)"

        # ------------------------------------------------------------ 6) lobby (TCP + UDP 31523)
        $oldLuaPath = $env:LUA_PATH
        $oldLuaCpath = $env:LUA_CPATH
        try {
            $env:LUA_PATH = $LuaPath
            $env:LUA_CPATH = $LuaCpath
            $pLua = Start-Tracked $LuaExe '"sich.lua"' $Data $LuaOut $LuaErr "lobby server (TCP/UDP $LobbyPort)"
        } finally {
            $env:LUA_PATH = $oldLuaPath
            $env:LUA_CPATH = $oldLuaCpath
        }

        # ------------------------------------------------------------ 7) readiness (TCP, never log text)
        Step "5. waiting until both services accept connections"
        $deadline = (Get-Date).AddSeconds(30)
        $lobbyUp = $false
        $savesUp = $false
        $died = $null
        while ((Get-Date) -lt $deadline) {
            if (-not $lobbyUp) { $lobbyUp = Test-TcpConnect $LobbyPort 300 }
            if (-not $savesUp) { $savesUp = Test-TcpConnect $SavesPort 300 }
            if ($lobbyUp -and $savesUp) { break }
            if (-not (Test-ChildAlive $pLua)) { $died = "the lobby server exited during startup"; break }
            if (-not (Test-ChildAlive $pSaves)) { $died = "the save service exited during startup"; break }
            Start-Sleep -Milliseconds 300
        }
        if ($null -eq $died -and -not $lobbyUp) { $died = ("the lobby server does not accept connections on TCP " + $LobbyPort + " (30 s)") }
        if ($null -eq $died -and -not $savesUp) { $died = ("the save service does not accept connections on TCP " + $SavesPort + " (30 s)") }
        if ($null -ne $died) {
            Err $died
            Write-Line ""
            Step "server.err.log"
            Show-LogTail $LuaErr 12
            Step "server.log"
            Show-LogTail $LuaOut 8
            Step "saves.err.log"
            Show-LogTail $SavesErr 12
            $script:ExitCode = 5
            break
        }
        Ok ("lobby accepts connections on TCP " + $LobbyPort)
        Ok ("save service accepts connections on TCP " + $SavesPort)

        # ------------------------------------------------------------ 8) save service HTTP
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:" + $SavesPort + "/c3/list") -TimeoutSec 10
            if ($resp.StatusCode -eq 200) { Ok ("GET /c3/list -> HTTP 200 (" + $resp.Content.Length + " bytes)") }
            else { Warn ("GET /c3/list -> HTTP " + $resp.StatusCode) }
        } catch {
            Warn ("GET /c3/list failed: " + $_.Exception.Message)
        }

        # ------------------------------------------------------------ 9) status
        $saveCount = 0
        if (Test-Path -LiteralPath $DataSaves) {
            $saveCount = @(Get-ChildItem -LiteralPath $DataSaves -Filter "*.map.gz" -File -ErrorAction SilentlyContinue).Count
        }
        Write-Line ""
        Write-Line "  ---- server is running, keep this window open ----" "Green"
        Write-Line ""
        Write-Line ("  lobby (sich_c3.lua)  TCP " + $LobbyPort + " + UDP " + $LobbyPort + "   PID " + $pLua.Id)
        Write-Line ("  save service         TCP " + $SavesPort + "                PID " + $pSaves.Id)
        Write-Line ("  saves on the server  " + $saveCount)
        Write-Line ("  logs                 " + $LuaOut + "  (+ .err.log), " + $SavesOut + "  (+ .err.log)")
        Write-Line ""
        $lan = @(Get-LanAddresses)
        if ($lan.Count -eq 0) {
            Warn "no LAN IPv4 address found - only this PC (127.0.0.1) can connect"
        } else {
            Write-Line "  LAN address(es) of this PC:" "Cyan"
            foreach ($a in $lan) { Write-Line ("    " + $a) }
            $firstIp = (($lan[0]) -split "\s+")[0]
            Write-Line ""
            Write-Line ("  the other players need this in data\resources\servers.dat:") "Cyan"
            Write-Line "      section.begin"
            Write-Line ("          * = " + $firstIp + ":" + $LobbyPort)
            Write-Line "      section.end"
            Write-Line ("  this PC itself can use 127.0.0.1:" + $LobbyPort + " or the address above")
        }
        Write-Line ""
        Write-Line "  If players on other PCs cannot connect, open these ports once in an admin prompt" "Cyan"
        Write-Line "  (this launcher never changes the firewall):" "Cyan"
        Write-Line '      netsh advfirewall firewall add rule name="C3Resume lobby TCP 31523" dir=in action=allow protocol=TCP localport=31523'
        Write-Line '      netsh advfirewall firewall add rule name="C3Resume saves TCP 31524" dir=in action=allow protocol=TCP localport=31524'
        Write-Line '      netsh advfirewall firewall add rule name="C3Resume echo UDP 31523" dir=in action=allow protocol=UDP localport=31523'
        Write-Line ""
        Info "Stop with Ctrl+C, or with:  Start-C3Server.cmd -Stop"

        # ------------------------------------------------------------ 10) run until stop
        $keysOk = $false
        try { [void][Console]::KeyAvailable; $keysOk = $true } catch { $keysOk = $false }
        if ($keysOk) { try { [Console]::TreatControlCAsInput = $true } catch { $keysOk = $false } }

        $reason = $null
        while ($true) {
            if (Test-Path -LiteralPath $StopPath) { $reason = "stop was requested"; break }
            if (-not (Test-ChildAlive $pLua)) {
                $reason = "the lobby server stopped"
                try { $reason = $reason + " (exit code " + $pLua.ExitCode + ")" } catch { }
                $script:ExitCode = 5
                break
            }
            if (-not (Test-ChildAlive $pSaves)) {
                $reason = "the save service stopped"
                try { $reason = $reason + " (exit code " + $pSaves.ExitCode + ")" } catch { }
                $script:ExitCode = 5
                break
            }
            if ($keysOk) {
                try {
                    if ([Console]::KeyAvailable) {
                        $k = [Console]::ReadKey($true)
                        if ($k.Key -eq [ConsoleKey]::C -and (($k.Modifiers -band [ConsoleModifiers]::Control) -ne 0)) {
                            $reason = "Ctrl+C"
                            break
                        }
                    }
                } catch { $keysOk = $false }
            }
            Start-Sleep -Milliseconds 500
        }

        Write-Line ""
        Step ("stopping: " + $reason)
        if ($script:ExitCode -ne 0) {
            Step "server.err.log"
            Show-LogTail $LuaErr 12
            Step "server.log"
            Show-LogTail $LuaOut 8
        }
    } while ($false)
} finally {
    if (Test-Path -LiteralPath $StopPath) { Remove-Item -LiteralPath $StopPath -Force -ErrorAction SilentlyContinue }
    Stop-TrackedChildren
    if ($null -ne $Mutex) {
        try { $Mutex.ReleaseMutex() } catch { }
        try { $Mutex.Dispose() } catch { }
    }
    Write-Line ""
}

Write-Line ("C3Resume server stopped (exit code " + $script:ExitCode + ").")
exit $script:ExitCode

