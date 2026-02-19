#Requires -RunAsAdministrator
<#
.SYNOPSIS
    ติดตั้ง IIS สำหรับ lib.npu.ac.th — Path-based routing, Multi-app
    รันใน PowerShell (Admin): .\deploy\iis\setup_iis.ps1

.PARAMETER CertThumbprint
    Thumbprint ของ SSL Certificate *.npu.ac.th
    ดูได้จาก: certlm.msc > Personal > Certificates > double-click > Details > Thumbprint

.EXAMPLE
    .\deploy\iis\setup_iis.ps1 -CertThumbprint "A1B2C3D4E5F6..."
#>
param(
    [string]$CertThumbprint = "",
    [string]$IisRootDir     = "C:\iis_root",
    [string]$ProjectDir     = "C:\projects\project_tracker"
)

$SiteName = "lib.npu.ac.th"
$AppPool  = "NPU-Apps"
$Domain   = "lib.npu.ac.th"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  IIS Setup — lib.npu.ac.th (Path-based Multi-App)   ║" -ForegroundColor Cyan
Write-Host "║  Windows Server 2019                                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Step  { param($n,$msg) Write-Host "`n[$n] $msg" -ForegroundColor Yellow }
function OK    { param($msg)    Write-Host "  ✓ $msg"   -ForegroundColor Green  }
function Skip  { param($msg)    Write-Host "  - $msg (มีอยู่แล้ว)" -ForegroundColor Gray }
function Warn  { param($msg)    Write-Host "  ! $msg"   -ForegroundColor Red    }
function Info  { param($msg)    Write-Host "  i $msg"   -ForegroundColor Cyan   }

# ── 1. IIS Windows Features ────────────────────────────────────────
Step "1/7" "เปิดใช้งาน IIS Windows Features"

$features = @(
    "IIS-WebServer", "IIS-WebServerManagementTools", "IIS-ManagementConsole",
    "IIS-CommonHttpFeatures", "IIS-HttpErrors", "IIS-HttpRedirect",
    "IIS-StaticContent", "IIS-Security", "IIS-RequestFiltering",
    "IIS-Performance", "IIS-HttpCompressionStatic",
    "IIS-HealthAndDiagnostics", "IIS-HttpLogging"
)
foreach ($f in $features) {
    $s = (Get-WindowsOptionalFeature -Online -FeatureName $f -EA SilentlyContinue).State
    if ($s -ne "Enabled") {
        Enable-WindowsOptionalFeature -Online -FeatureName $f -NoRestart | Out-Null
        OK $f
    } else { Skip $f }
}

# ── 2. ตรวจสอบ ARR ────────────────────────────────────────────────
Step "2/7" "ตรวจสอบ ARR (Application Request Routing) Module"

Import-Module WebAdministration -ErrorAction Stop

try {
    Get-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" `
        -Filter "system.webServer/proxy" -Name "enabled" -EA Stop | Out-Null
    OK "ARR Module พร้อมใช้งาน"
} catch {
    Warn "ยังไม่ได้ติดตั้ง ARR Module!"
    Write-Host ""
    Write-Host "  ดาวน์โหลด ARR ก่อน แล้วรัน script ใหม่:" -ForegroundColor Yellow
    Write-Host "  https://www.iis.net/downloads/microsoft/application-request-routing" -ForegroundColor Cyan
    Read-Host "`nกด Enter เพื่อออก"
    exit 1
}

# ── 3. ตั้งค่า ARR + Server Variables ────────────────────────────
Step "3/7" "ตั้งค่า ARR Proxy และ Server Variables"

Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/proxy" -Name "enabled" -Value $true
Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/proxy" -Name "preserveHostHeader" -Value $true
OK "เปิดใช้งาน ARR Proxy"

# อนุญาต server variables ที่ใช้ใน web.config
$vars = @("HTTP_X_FORWARDED_PROTO", "HTTP_X_REAL_IP")
$existing = (Get-WebConfiguration -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/rewrite/allowedServerVariables").Collection.name

foreach ($v in $vars) {
    if ($existing -notcontains $v) {
        Add-WebConfiguration -PSPath "MACHINE/WEBROOT/APPHOST" `
            -Filter "system.webServer/rewrite/allowedServerVariables" `
            -Value @{ name = $v }
        OK "เพิ่ม Server Variable: $v"
    } else { Skip "Server Variable: $v" }
}

# ── 4. สร้าง IIS Root + คัดลอก web.config ────────────────────────
Step "4/7" "เตรียมโฟลเดอร์ IIS Root"

if (-not (Test-Path $IisRootDir)) {
    New-Item -ItemType Directory -Path $IisRootDir | Out-Null
    OK "สร้าง $IisRootDir"
} else { Skip $IisRootDir }

Copy-Item "$ProjectDir\deploy\iis\web.config" "$IisRootDir\web.config" -Force
OK "คัดลอก web.config → $IisRootDir"

# ── 5. Application Pool + Website ────────────────────────────────
Step "5/7" "สร้าง Application Pool และ IIS Website"

if (Test-Path "IIS:\Sites\$SiteName")    { Remove-Website   -Name $SiteName }
if (Test-Path "IIS:\AppPools\$AppPool") { Remove-WebAppPool -Name $AppPool  }

New-WebAppPool -Name $AppPool | Out-Null
Set-ItemProperty "IIS:\AppPools\$AppPool" -Name "managedRuntimeVersion" -Value ""
Set-ItemProperty "IIS:\AppPools\$AppPool" -Name "startMode"             -Value "AlwaysRunning"
Set-ItemProperty "IIS:\AppPools\$AppPool" -Name "processModel.idleTimeout" -Value "00:00:00"
OK "สร้าง App Pool: $AppPool (No Managed Code)"

# HTTP binding (port 80 — IIS redirect ไป HTTPS เอง)
New-Website -Name $SiteName -Port 80 -HostHeader $Domain `
    -PhysicalPath $IisRootDir -ApplicationPool $AppPool | Out-Null
OK "สร้าง Website: $SiteName (port 80, host: $Domain)"

# ── 6. ผูก SSL Certificate ────────────────────────────────────────
Step "6/7" "ผูก SSL Certificate (*.npu.ac.th)"

if ($CertThumbprint -ne "") {
    $thumb = $CertThumbprint.Replace(" ","").ToUpper()
    $cert  = Get-Item "Cert:\LocalMachine\My\$thumb" -EA SilentlyContinue

    if ($cert) {
        New-WebBinding -Name $SiteName -Protocol "https" -Port 443 `
            -HostHeader $Domain -SslFlags 0 | Out-Null

        $binding = Get-WebBinding -Name $SiteName -Protocol "https"
        $binding.AddSslCertificate($thumb, "My")

        OK "ผูก cert: $($cert.Subject) (หมดอายุ: $($cert.NotAfter.ToString('dd/MM/yyyy')))"
        OK "HTTPS binding port 443 พร้อมใช้งาน"
    } else {
        Warn "ไม่พบ cert thumbprint: $thumb"
        Info "ตรวจสอบ: certlm.msc > Personal > Certificates"
    }
} else {
    Info "ไม่ได้ระบุ CertThumbprint"
    Info "ต้องเพิ่ม HTTPS binding ใน IIS Manager ด้วยตนเอง (ดู README_IIS.md)"
}

# ── 7. Firewall ───────────────────────────────────────────────────
Step "7/7" "ตั้งค่า Windows Firewall"

@(
    @{ Name="IIS HTTP (80)";   Port=80  },
    @{ Name="IIS HTTPS (443)"; Port=443 }
) | ForEach-Object {
    if (-not (Get-NetFirewallRule -DisplayName $_.Name -EA SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $_.Name -Direction Inbound `
            -Protocol TCP -LocalPort $_.Port -Action Allow | Out-Null
        OK "เปิด Firewall port $($_.Port)"
    } else { Skip "Firewall port $($_.Port)" }
}

# ปิด port 8000 จากภายนอก (ถ้าเคยเปิดไว้)
@("ProjectTracker Port 8000", "Waitress 8000") | ForEach-Object {
    $r = Get-NetFirewallRule -DisplayName $_ -EA SilentlyContinue
    if ($r) { Remove-NetFirewallRule -DisplayName $_; OK "ปิด Firewall port 8000 (ไม่จำเป็นแล้ว)" }
}

# ── สรุป ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ติดตั้ง IIS เสร็จสมบูรณ์!                          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "URLs ที่ใช้งานได้:" -ForegroundColor Yellow
Write-Host "  https://lib.npu.ac.th/projects/   →  Project Tracker (:8000)" -ForegroundColor Cyan
Write-Host "  (เพิ่ม app อื่นโดยแก้ web.config และ uncomment rules)" -ForegroundColor Gray
Write-Host ""
Write-Host "ขั้นตอนต่อไป:" -ForegroundColor Yellow
Write-Host "  1. แก้ .env: SCRIPT_NAME=/projects, ALLOWED_HOSTS=lib.npu.ac.th" -ForegroundColor White
Write-Host "  2. Restart Waitress: nssm restart ProjectTracker" -ForegroundColor White
Write-Host "  3. ทดสอบ: https://lib.npu.ac.th/projects/" -ForegroundColor White
Write-Host ""
