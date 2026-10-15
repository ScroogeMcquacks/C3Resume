# c3resume setup window (Windows). Started by "SETUP - double-click me.bat".
# It only shows a window; the work is done by c3resume.ps1 next to it (the same code as the command line).
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()

$Here = $PSScriptRoot
$Cli = Join-Path $Here "c3resume.ps1"
$PsExe = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
if (-not $PsExe) { $PsExe = "powershell.exe" }
$Texts = Get-Content -LiteralPath (Join-Path $Here "texts.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Langs = @("en", "de")

# ---------------------------------------------------------------- the language: picked last time, else Windows'
$SettingsFile = Join-Path (Join-Path $env:LOCALAPPDATA "c3resume") "settings.json"
$script:Lang = "en"
if ((Get-UICulture).TwoLetterISOLanguageName -eq "de" -or (Get-Culture).TwoLetterISOLanguageName -eq "de") { $script:Lang = "de" }
try {
    if (Test-Path -LiteralPath $SettingsFile) {
        $saved = (Get-Content -LiteralPath $SettingsFile -Raw | ConvertFrom-Json).lang
        if ($Langs -contains $saved) { $script:Lang = $saved }
    }
} catch { }
function Save-Lang {
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $SettingsFile) | Out-Null
        Set-Content -LiteralPath $SettingsFile -Value (@{ lang = $script:Lang } | ConvertTo-Json -Compress) -Encoding ASCII
    } catch { }
}
function T([string]$key, [string]$v = "") { return ($Texts.($script:Lang).$key).Replace("{v}", $v) }

function Run-Cli([string[]]$argList, [bool]$elevated = $false) {
    # runs c3resume.ps1 in a hidden PowerShell, returns @(exitcode, text)
    $quoted = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$Cli`"") + ($argList | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } })
    if ($elevated) {
        $log = [IO.Path]::GetTempFileName()
        # parameter names (-GameDir, -NoHelper) stay bare: quoted, PowerShell would take them for values
        $parts = $argList | ForEach-Object { if ($_ -match '^-[A-Za-z]+$') { $_ } else { "'" + $_.Replace("'", "''") + "'" } }
        $cmd = "& '" + $Cli.Replace("'", "''") + "' " + ($parts -join " ") + " *> '" + $log + "'"
        $p = Start-Process -FilePath $PsExe -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd) -Verb RunAs -WindowStyle Hidden -Wait -PassThru
        $text = ""
        if (Test-Path $log) { $text = Get-Content -LiteralPath $log -Raw; Remove-Item $log -Force }
        return @($p.ExitCode, "$text")
    }
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $PsExe
    $psi.Arguments = ($quoted -join " ")
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = [Diagnostics.Process]::Start($psi)
    $errTask = $proc.StandardError.ReadToEndAsync()
    $out = $proc.StandardOutput.ReadToEnd()
    $proc.WaitForExit()
    return @($proc.ExitCode, ($out + $errTask.Result))
}

function Get-Info([string]$dir) {
    $a = @("info")
    if ($dir -ne "") { $a += @("-GameDir", $dir) }
    $r = Run-Cli $a
    try { return ($r[1].Trim() -split "`n" | Select-Object -Last 1) | ConvertFrom-Json } catch { return $null }
}

# ---------------------------------------------------------------- the window
$W = 680                                            # inner width of the window
$font = New-Object Drawing.Font("Segoe UI", 10)
$small = New-Object Drawing.Font("Segoe UI", 9)
$boldFont = New-Object Drawing.Font("Segoe UI", 10, [Drawing.FontStyle]::Bold)
$form = New-Object Windows.Forms.Form
$form.ClientSize = New-Object Drawing.Size($W, 700)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.Font = $font

function Add-Label([int]$x, [int]$w) {
    $l = New-Object Windows.Forms.Label
    $l.Location = New-Object Drawing.Point($x, 0); $l.Size = New-Object Drawing.Size($w, 20)
    $form.Controls.Add($l); return $l
}
function Add-Button([int]$x, [int]$w, [int]$h) {
    $b = New-Object Windows.Forms.Button
    $b.Location = New-Object Drawing.Point($x, 0); $b.Size = New-Object Drawing.Size($w, $h)
    $form.Controls.Add($b); return $b
}

$title = Add-Label 16 420
$title.Font = $boldFont
$langLabel = Add-Label 440 120
$langLabel.Font = $small
$langLabel.TextAlign = "MiddleRight"
$langBox = New-Object Windows.Forms.ComboBox
$langBox.DropDownStyle = "DropDownList"
$langBox.Location = New-Object Drawing.Point(564, 0); $langBox.Size = New-Object Drawing.Size(100, 26)
foreach ($l in $Langs) { [void]$langBox.Items.Add($Texts.$l.lang_name) }
$form.Controls.Add($langBox)
$about = Add-Label 16 ($W - 32)
$about.ForeColor = [Drawing.Color]::FromArgb(60, 60, 60)
$status = Add-Label 16 ($W - 32)
$status.Font = New-Object Drawing.Font("Segoe UI", 11, [Drawing.FontStyle]::Bold)
$step1 = Add-Label 16 ($W - 32)
$gameBox = New-Object Windows.Forms.TextBox
$gameBox.Location = New-Object Drawing.Point(16, 0); $gameBox.Size = New-Object Drawing.Size(($W - 160), 26); $gameBox.ReadOnly = $true
$form.Controls.Add($gameBox)
$browse = Add-Button ($W - 136) 120 30
$step2 = Add-Label 16 ($W - 32)
$serverBox = New-Object Windows.Forms.TextBox
$serverBox.Location = New-Object Drawing.Point(16, 0); $serverBox.Size = New-Object Drawing.Size(300, 26)
$form.Controls.Add($serverBox)
$helperCheck = New-Object Windows.Forms.CheckBox
$helperCheck.Location = New-Object Drawing.Point(16, 0); $helperCheck.Size = New-Object Drawing.Size(($W - 32), 26)
$helperCheck.Checked = $true
$form.Controls.Add($helperCheck)
$helperText = Add-Label 36 ($W - 52)
$helperText.Font = $small
$install = Add-Button 16 220 46
$install.Font = New-Object Drawing.Font("Segoe UI", 11, [Drawing.FontStyle]::Bold)
$uninstall = Add-Button 248 160 46
$saves = Add-Button 420 200 46
$hint = Add-Label 16 ($W - 32)
$details = New-Object Windows.Forms.TextBox
$details.Location = New-Object Drawing.Point(16, 0); $details.Size = New-Object Drawing.Size(($W - 32), 104)
$details.Multiline = $true; $details.ReadOnly = $true; $details.ScrollBars = "Vertical"
$details.Font = New-Object Drawing.Font("Consolas", 9)
$form.Controls.Add($details)

function Text-Height($label, [string]$text) {
    $flags = [Windows.Forms.TextFormatFlags]::WordBreak
    return [Windows.Forms.TextRenderer]::MeasureText($text, $label.Font, (New-Object Drawing.Size($label.Width, 0)), $flags).Height + 4
}

function Layout {
    # top to bottom; every text gets the height it needs in the current language
    $y = 12
    $title.Top = $y + 4; $langLabel.Top = $y + 4; $langBox.Top = $y
    $y += 36
    $about.Top = $y; $about.Height = Text-Height $about $about.Text; $y += $about.Height + 8
    $status.Top = $y; $status.Height = Text-Height $status $status.Text; $y += $status.Height + 8
    $step1.Top = $y; $step1.Height = Text-Height $step1 $step1.Text; $y += $step1.Height + 2
    $gameBox.Top = $y + 2; $browse.Top = $y; $y += 38
    $step2.Top = $y; $step2.Height = Text-Height $step2 $step2.Text; $y += $step2.Height + 2
    $serverBox.Top = $y; $y += 38
    $helperCheck.Top = $y; $y += 28
    # as high as the longer of the two explanations, so the window does not jump when the box is clicked
    $h = [Math]::Max((Text-Height $helperText (T "helper_on")), (Text-Height $helperText (T "helper_off")))
    $helperText.Top = $y; $helperText.Height = $h; $y += $h + 10
    $install.Top = $y; $uninstall.Top = $y; $saves.Top = $y; $y += 54
    $hint.Top = $y; $hint.Height = Text-Height $hint $hint.Text; $y += $hint.Height + 4
    $details.Top = $y; $y += $details.Height + 14
    $form.ClientSize = New-Object Drawing.Size($W, $y)
}

$script:LastInfo = $null
$script:StatusKey = "st_looking"; $script:StatusV = ""; $script:InstallKey = "install"
$script:HelperTouched = $false

function Show-HelperText {
    if ($helperCheck.Checked) {
        $helperText.Text = T "helper_on"; $helperText.ForeColor = [Drawing.Color]::FromArgb(60, 60, 60)
    } else {
        $helperText.Text = T "helper_off"; $helperText.ForeColor = [Drawing.Color]::FromArgb(140, 70, 0)
    }
}

function Apply-Lang {
    $form.Text = T "window"; $title.Text = T "head"; $langLabel.Text = T "lang_label"
    $about.Text = T "about"
    $step1.Text = T "step1"; $browse.Text = T "change"; $step2.Text = T "step2"
    $helperCheck.Text = T "helper_check"
    Show-HelperText
    $uninstall.Text = T "uninstall"; $saves.Text = T "saves"; $hint.Text = T "close_hint"
    $install.Text = T $script:InstallKey
    $status.Text = T $script:StatusKey $script:StatusV
    Layout
}

function Set-Status([string]$key, $color, [string]$v = "") {
    $script:StatusKey = $key; $script:StatusV = $v
    $status.Text = T $key $v; $status.ForeColor = $color
}

# ---------------------------------------------------------------- behaviour
function Show-State($info) {
    $script:LastInfo = $info
    $green = [Drawing.Color]::FromArgb(0, 120, 40); $orange = [Drawing.Color]::FromArgb(190, 90, 0); $red = [Drawing.Color]::FromArgb(180, 0, 0)
    if (-not $info -or -not $info.found) {
        Set-Status "st_notfound" $red
        $install.Enabled = $false; $uninstall.Enabled = $false; $saves.Enabled = $false
        Layout
        return
    }
    $gameBox.Text = $info.game_dir
    $current = ($info.server -replace ':31523$', '')
    if ($serverBox.Text -eq "" -and $current -ne "138.201.198.174") { $serverBox.Text = $current }   # the official lobby has no !save / !load
    if (-not $script:HelperTouched) {
        # as it is now when installed, else on (recommended)
        if ($info.installed) { $helperCheck.Checked = [bool]($info.helper_installed -or $info.helper) } else { $helperCheck.Checked = $true }
        Show-HelperText
    }
    $install.Enabled = $true; $saves.Enabled = $true
    $uninstall.Enabled = [bool]$info.installed
    $script:InstallKey = "install_again"
    if (-not $info.installed) { Set-Status "st_notinstalled" $orange; $script:InstallKey = "install" }
    elseif (-not $info.intact) { Set-Status "st_reset" $orange }
    elseif ($info.installed_version -ne $info.version) { Set-Status "st_older" $orange "$($info.installed_version)"; $script:InstallKey = "update" }
    elseif ($info.helper) { Set-Status "st_ready" $green "$($info.version)" }
    elseif ($info.helper_installed) { Set-Status "st_nohelper" $orange }
    else { Set-Status "st_ready_manual" $green "$($info.version)" }
    $install.Text = T $script:InstallKey
    Layout
}

function Refresh-State { Show-State (Get-Info $gameBox.Text) }

function Busy([bool]$on) {
    # while working everything is disabled; afterwards Show-State decides which buttons make sense
    if ($on) { foreach ($c in @($install, $uninstall, $saves, $browse, $helperCheck)) { $c.Enabled = $false } }
    else { $browse.Enabled = $true; $helperCheck.Enabled = $true }
    if ($on) { $form.Cursor = [Windows.Forms.Cursors]::WaitCursor } else { $form.Cursor = [Windows.Forms.Cursors]::Default }
    [Windows.Forms.Application]::DoEvents()
}

function Do-Action([string[]]$argList, [string]$doneKey) {
    Busy $true
    $details.Text = T "working"
    [Windows.Forms.Application]::DoEvents()
    $r = Run-Cli $argList
    if ($r[0] -ne 0 -and $r[1] -match "Run as administrator") {
        $ans = [Windows.Forms.MessageBox]::Show((T "admin"), "c3resume", "OKCancel", "Information")
        if ($ans -eq "OK") { $r = Run-Cli $argList $true }
    }
    $details.Text = ($r[1] -replace "`r?`n", "`r`n").Trim()
    Busy $false
    $script:HelperTouched = $false
    Refresh-State
    if ($r[0] -eq 0) { [Windows.Forms.MessageBox]::Show((T $doneKey), "c3resume", "OK", "Information") | Out-Null }
    else { [Windows.Forms.MessageBox]::Show((T "failed"), "c3resume", "OK", "Warning") | Out-Null }
}

$langBox.SelectedIndex = [Array]::IndexOf($Langs, $script:Lang)
$langBox.Add_SelectedIndexChanged({
    $new = $Langs[$langBox.SelectedIndex]
    if ($new -ne $script:Lang) { $script:Lang = $new; Save-Lang; Apply-Lang }
})

$helperCheck.Add_Click({ $script:HelperTouched = $true; Show-HelperText })

$browse.Add_Click({
    $dlg = New-Object Windows.Forms.FolderBrowserDialog
    $dlg.Description = T "pick"
    if ($dlg.ShowDialog() -eq "OK") {
        if (Test-Path -LiteralPath (Join-Path $dlg.SelectedPath "data")) { $gameBox.Text = $dlg.SelectedPath; Refresh-State }
        else { [Windows.Forms.MessageBox]::Show((T "not_c3"), "c3resume") | Out-Null }
    }
})

$install.Add_Click({
    $srv = $serverBox.Text.Trim()
    if ($srv -eq "") { [Windows.Forms.MessageBox]::Show((T "need_server"), "c3resume", "OK", "Warning") | Out-Null; return }
    if ($srv -notmatch '^[A-Za-z0-9.\-]+(:\d{1,5})?$') { [Windows.Forms.MessageBox]::Show((T "bad_server"), "c3resume", "OK", "Warning") | Out-Null; return }
    $a = @("install", "-GameDir", $gameBox.Text, "-Server", $srv)
    if ($helperCheck.Checked) { Do-Action $a "done_install" } else { Do-Action ($a + @("-NoHelper")) "done_install_manual" }
})

$uninstall.Add_Click({
    $ans = [Windows.Forms.MessageBox]::Show((T "confirm_uninstall"), "c3resume", "YesNo", "Question")
    if ($ans -eq "Yes") { Do-Action @("uninstall", "-GameDir", $gameBox.Text) "done_uninstall" }
})

$saves.Add_Click({
    $r = Run-Cli @("saves", "-GameDir", $gameBox.Text)
    if ($r[0] -ne 0) { [Windows.Forms.MessageBox]::Show((T "saves_none"), "c3resume", "OK", "Information") | Out-Null }
})

Apply-Lang
$form.Add_Shown({ Busy $true; $info = Get-Info ""; Busy $false; Show-State $info })
try { [void]$form.ShowDialog() }
catch { [Windows.Forms.MessageBox]::Show("Something went wrong: " + $_.Exception.Message, "c3resume", "OK", "Error") | Out-Null }
