# คู่มือการติดตั้งระบบติดตามโครงการ
## สำนักวิทยบริการ มหาวิทยาลัยนครพนม

**เวอร์ชัน:** 1.0
**วันที่:** 19 กุมภาพันธ์ 2569
**ผู้จัดทำ:** งานเทคนิคสารสนเทศและการจัดการทรัพยากร

---

## สารบัญ

1. [ภาพรวมระบบ](#1-ภาพรวมระบบ)
2. [สิ่งที่ต้องเตรียม](#2-สิ่งที่ต้องเตรียม)
3. [สถาปัตยกรรมระบบ](#3-สถาปัตยกรรมระบบ)
4. [ขั้นตอนการติดตั้ง](#4-ขั้นตอนการติดตั้ง)
5. [การตั้งค่า Environment](#5-การตั้งค่า-environment)
6. [การติดตั้ง Windows Service](#6-การติดตั้ง-windows-service)
7. [การตั้งค่า IIS](#7-การตั้งค่า-iis)
8. [การทดสอบระบบ](#8-การทดสอบระบบ)
9. [การบำรุงรักษา](#9-การบำรุงรักษา)
10. [การแก้ปัญหาที่พบบ่อย](#10-การแก้ปัญหาที่พบบ่อย)

---

## 1. ภาพรวมระบบ

ระบบติดตามโครงการ (Project Tracker) เป็นเว็บแอปพลิเคชันพัฒนาด้วย **Django 5.1** ให้บริการแก่บุคลากรสำนักวิทยบริการ เพื่อติดตามโครงการ งบประมาณ และกิจกรรมต่างๆ ในแต่ละปีงบประมาณ

**URL ที่ใช้งาน:**
```
https://lib.npu.ac.th/projects/
```

**ข้อมูลเซิร์ฟเวอร์:**

| รายการ | ค่า |
|--------|-----|
| IP Address | 110.78.83.102 |
| Domain | lib.npu.ac.th |
| OS | Windows Server 2019 |
| Path โปรเจ็กต์ | C:\project\project_tracker |
| Port ภายใน | 8000 (Waitress) |

---

## 2. สิ่งที่ต้องเตรียม

### 2.1 ซอฟต์แวร์

| รายการ | เวอร์ชัน | หมายเหตุ |
|--------|----------|---------|
| Windows Server | 2019 | ติดตั้งแล้ว |
| Python | 3.12+ | ต้องติดตั้งก่อน |
| Git | ล่าสุด | สำหรับ pull โค้ด |
| IIS | 10.0 | มากับ Windows Server |
| ARR Module | 3.0 | ดาวน์โหลดจาก Microsoft |
| URL Rewrite Module | 2.1 | ดาวน์โหลดจาก Microsoft |
| NSSM | 2.24 | Non-Sucking Service Manager |

### 2.2 ไฟล์ที่ต้องเตรียม

| ไฟล์ | ที่เก็บ | หมายเหตุ |
|------|---------|---------|
| cert20xx.pfx | C:\project\project_tracker\cert\ | SSL Certificate *.npu.ac.th |
| pxxx.txt | C:\project\project_tracker\cert\ | รหัสผ่าน PFX |
| .env | C:\project\project_tracker\ | ตัวแปร environment |

### 2.3 ข้อมูล DNS
- ต้องประสาน IT กลาง มหาวิทยาลัย ให้ชี้ `lib.npu.ac.th → 110.78.83.102` ก่อนดำเนินการ

---

## 3. สถาปัตยกรรมระบบ

### 3.1 ภาพรวม Path-based Routing

ระบบใช้เทคนิค **Path-based Routing** ซึ่งช่วยให้สามารถรองรับหลายแอปพลิเคชันบน Domain เดียวได้

```
ผู้ใช้งาน (Browser)
        │
        │  https://lib.npu.ac.th/projects/
        ▼
┌─────────────────────────────────────┐
│  IIS 10.0 (Windows Server 2019)     │
│  Port 80  → Redirect ไป HTTPS       │
│  Port 443 → รับ HTTPS Request       │
│                                     │
│  SSL Termination (cert2026.pfx)     │
│  URL Rewrite: /projects/* → :8000  │
└──────────────────┬──────────────────┘
                   │ http://127.0.0.1:8000/
                   ▼
┌─────────────────────────────────────┐
│  Waitress (Python WSGI Server)      │
│  Listen: 127.0.0.1:8000            │
│  Service: ProjectTracker (NSSM)     │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Django Application                 │
│  Settings: config.settings.production│
│  FORCE_SCRIPT_NAME: /projects       │
└─────────────────────────────────────┘
```

### 3.2 การทำงานของ Path-based Routing

1. Browser ส่ง Request: `https://lib.npu.ac.th/projects/dashboard/`
2. IIS รับ Request และ **ตัด prefix `/projects`** ออก
3. IIS ส่งต่อให้ Waitress: `http://127.0.0.1:8000/dashboard/`
4. Django ประมวลผล และสร้าง URL กลับโดยใส่ `/projects` นำหน้าทุก Link (ผ่าน `FORCE_SCRIPT_NAME`)
5. ผู้ใช้เห็น URL ที่ถูกต้อง: `https://lib.npu.ac.th/projects/dashboard/`

---

## 4. ขั้นตอนการติดตั้ง

### 4.1 Clone โค้ดจาก GitHub

เปิด **PowerShell (Administrator)** แล้วรัน:

```powershell
cd C:\
New-Item -ItemType Directory -Path "C:\project" -Force
cd C:\project
git clone https://github.com/azimuthotg/projects_tracker.git project_tracker
cd C:\project\project_tracker
```

### 4.2 สร้าง Virtual Environment และติดตั้ง Dependencies

```powershell
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

### 4.3 ติดตั้ง IIS

```powershell
Install-WindowsFeature -Name `
  Web-Server, Web-WebServer, Web-Common-Http, `
  Web-Static-Content, Web-Http-Errors, Web-Http-Redirect, `
  Web-Health, Web-Http-Logging, `
  Web-Security, Web-Filtering, `
  Web-Performance, Web-Stat-Compression, `
  Web-Mgmt-Tools, Web-Mgmt-Console `
  -IncludeManagementTools
```

> **หมายเหตุ:** บน Windows Server ต้องใช้ `Install-WindowsFeature` เท่านั้น ห้ามใช้ `Enable-WindowsOptionalFeature` (ใช้ได้เฉพาะ Windows Client เท่านั้น)

### 4.4 ติดตั้ง ARR Module

```powershell
New-Item -ItemType Directory -Path "C:\temp" -Force
Invoke-WebRequest `
  -Uri "https://download.microsoft.com/download/E/9/8/E9849D6A-020E-47E4-9FD0-A023E99B54EB/requestRouter_amd64.msi" `
  -OutFile "C:\temp\ARR.msi"
Start-Process msiexec.exe -ArgumentList "/i C:\temp\ARR.msi /quiet" -Wait
```

### 4.5 ติดตั้ง URL Rewrite Module

```powershell
Invoke-WebRequest `
  -Uri "https://download.microsoft.com/download/1/2/8/128E2E22-C1B9-44A4-BE2A-5859ED1D4592/rewrite_amd64_en-US.msi" `
  -OutFile "C:\temp\urlrewrite.msi"
Start-Process msiexec.exe -ArgumentList "/i C:\temp\urlrewrite.msi /quiet" -Wait
iisreset /restart
```

---

## 5. การตั้งค่า Environment

### 5.1 สร้างไฟล์ .env

สร้างไฟล์ `C:\project\project_tracker\.env` โดยมีเนื้อหาดังนี้:

```env
# Django
SECRET_KEY=ใส่-random-key-ที่นี่
ALLOWED_HOSTS=localhost,110.78.83.102,lib.npu.ac.th

# HTTPS
HTTPS_ENABLED=True
CSRF_TRUSTED_ORIGINS=https://lib.npu.ac.th

# Path Prefix
SCRIPT_NAME=/projects

# Database (MySQL)
DB_NAME=projects_tracker
DB_USER=xxxx
DB_PASSWORD=ใส่-รหัสผ่าน-database
DB_HOST=202.xx.xx.xxx
DB_PORT=3306

# Waitress
WAITRESS_HOST=127.0.0.1
WAITRESS_PORT=8000
WAITRESS_THREADS=8

# NPU AD API
NPU_API_BASE_URL=https://xxx.npu.ac.th/vx/ldap/
NPU_API_AUTH_ENDPOINT=auth_and_get_personnel/
NPU_API_TOKEN=ใส่-JWT-token
NPU_API_TIMEOUT=30

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
```

### 5.2 Generate SECRET_KEY

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
C:\project\project_tracker\venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

นำค่าที่ได้ไปใส่ใน `SECRET_KEY=` ในไฟล์ `.env`

### 5.3 Collect Static Files

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
C:\project\project_tracker\venv\Scripts\python.exe C:\project\project_tracker\manage.py collectstatic --noinput
```

### 5.4 Run Database Migrations

```powershell
C:\project\project_tracker\venv\Scripts\python.exe C:\project\project_tracker\manage.py migrate
```

---

## 6. การติดตั้ง Windows Service (NSSM + Waitress)

### 6.1 ติดตั้ง Waitress

```powershell
C:\project\project_tracker\venv\Scripts\pip.exe install waitress
```

### 6.2 ติดตั้ง NSSM

ดาวน์โหลด NSSM จาก [nssm.cc](https://nssm.cc) หรือก็อปจากเครื่อง dev แล้ววางที่ `C:\nssm\nssm.exe`

```powershell
New-Item -ItemType Directory -Path "C:\nssm" -Force
# ก็อป nssm.exe มาวางที่ C:\nssm\nssm.exe
```

### 6.3 สร้าง Service

```powershell
# สร้าง Service
C:\nssm\nssm.exe install ProjectTracker `
  "C:\project\project_tracker\venv\Scripts\python.exe" `
  "C:\project\project_tracker\deploy\waitress_serve.py"

# ตั้งค่า Working Directory
C:\nssm\nssm.exe set ProjectTracker AppDirectory "C:\project\project_tracker"

# ตั้งค่า Django Settings
C:\nssm\nssm.exe set ProjectTracker AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.production"

# ตั้งค่า Log
New-Item -ItemType Directory -Path "C:\project\project_tracker\logs" -Force
C:\nssm\nssm.exe set ProjectTracker AppStdout "C:\project\project_tracker\logs\waitress.log"
C:\nssm\nssm.exe set ProjectTracker AppStderr "C:\project\project_tracker\logs\waitress_error.log"

# Start Service
C:\nssm\nssm.exe start ProjectTracker
```

### 6.4 ตรวจสอบสถานะ Service

```powershell
C:\nssm\nssm.exe status ProjectTracker
# ต้องแสดง: SERVICE_RUNNING
```

---

## 7. การตั้งค่า IIS

### 7.1 Import SSL Certificate

```powershell
Import-PfxCertificate `
  -FilePath "C:\project\project_tracker\cert\cert2026.pfx" `
  -CertStoreLocation Cert:\LocalMachine\My `
  -Password (ConvertTo-SecureString "admina2026*" -AsPlainText -Force) `
  -Exportable
```

### 7.2 ดู Thumbprint

```powershell
Get-ChildItem Cert:\LocalMachine\My |
  Where-Object { $_.Subject -like "*.npu.ac.th*" } |
  Select-Object Thumbprint, Subject, NotAfter |
  Format-Table -AutoSize
```

จดค่า **Thumbprint** ไว้ใช้ในขั้นตอนถัดไป

### 7.3 รัน Setup Script

```powershell
cd C:\project\project_tracker

# แปลง Encoding ก่อน (สำคัญ!)
$path = ".\deploy\iis\setup_iis.ps1"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($path, $content, $utf8Bom)

# รัน Script
.\deploy\iis\setup_iis.ps1 -CertThumbprint "ใส่-THUMBPRINT-ที่นี่"
```

> **สำคัญ:** ต้องแปลง Encoding ก่อนเสมอ เพราะ Script สร้างบน Linux (UTF-8 ไม่มี BOM) แต่ Windows PowerShell อ่านเป็น Windows-1252

### 7.4 เพิ่ม Server Variables (ถ้า Setup Script ทำไม่สำเร็จ)

```powershell
Import-Module WebAdministration

Add-WebConfiguration -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/rewrite/allowedServerVariables" `
    -Value @{ name = "HTTP_X_FORWARDED_PROTO" }

Add-WebConfiguration -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/rewrite/allowedServerVariables" `
    -Value @{ name = "HTTP_X_REAL_IP" }

iisreset /restart
```

### 7.5 Copy web.config

```powershell
New-Item -ItemType Directory -Path "C:\iis_root" -Force
Copy-Item "C:\project\project_tracker\deploy\iis\web.config" "C:\iis_root\web.config" -Force
```

---

## 8. การทดสอบระบบ

### 8.1 ทดสอบ Waitress (ภายใน)

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing
# ต้องได้รับ Response (400 หรือ 302 ถือว่าปกติ)
```

### 8.2 ทดสอบผ่าน Browser

เปิด Browser แล้วเข้า:

| URL | ผลที่คาดหวัง |
|-----|-------------|
| `http://lib.npu.ac.th/projects/` | Redirect ไป HTTPS อัตโนมัติ |
| `https://lib.npu.ac.th/projects/` | แสดงหน้า Login พร้อมแม่กุญแจ 🔒 |

### 8.3 ทดสอบ Login

- Username: `xxxx`
- Password: `xxxxxxx4`
- ต้องเข้าสู่ Dashboard ได้สำเร็จ

---

## 9. การบำรุงรักษา

### 9.1 คำสั่ง Service ที่ใช้บ่อย

```powershell
# ดูสถานะ
C:\nssm\nssm.exe status ProjectTracker

# Restart (หลัง git pull หรือแก้ไข .env)
C:\nssm\nssm.exe restart ProjectTracker

# Stop / Start
C:\nssm\nssm.exe stop ProjectTracker
C:\nssm\nssm.exe start ProjectTracker
```

### 9.2 อัปเดตโค้ด

```powershell
cd C:\project\project_tracker
git pull origin master
C:\project\project_tracker\venv\Scripts\python.exe manage.py migrate
C:\project\project_tracker\venv\Scripts\python.exe manage.py collectstatic --noinput
C:\nssm\nssm.exe restart ProjectTracker
```

### 9.3 ดู Log

```powershell
# Log ทั่วไป
Get-Content "C:\project\project_tracker\logs\waitress.log" -Tail 50

# Log Error
Get-Content "C:\project\project_tracker\logs\waitress_error.log" -Tail 50

# ดู Log แบบ Real-time
Get-Content "C:\project\project_tracker\logs\waitress_error.log" -Wait
```

### 9.4 SSL Certificate

- **หมดอายุ:** xx xxx 2570
- **ต้องต่ออายุก่อน:** อย่างน้อย 30 วัน
- **ไฟล์:** `C:\project\project_tracker\cert\xxxx`
- **รหัสผ่าน:** เก็บใน `C:\project\project_tracker\cert\xxxx`

---

## 10. การแก้ปัญหาที่พบบ่อย

| อาการ | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| **502 Bad Gateway** | Waitress ไม่ได้รัน | `C:\nssm\nssm.exe start ProjectTracker` |
| **400 Bad Request** | `lib.npu.ac.th` ไม่อยู่ใน ALLOWED_HOSTS | แก้ไข `.env` แล้ว restart service |
| **500.19 Config Error** | URL Rewrite ไม่ได้ติดตั้ง | ติดตั้ง URL Rewrite Module |
| **500.50 URL Rewrite Error** | Server Variable ไม่ได้รับอนุญาต | เพิ่ม `HTTP_X_FORWARDED_PROTO` ใน allowedServerVariables |
| **404 หน้า Login** | `FORCE_SCRIPT_NAME` ไม่ทำงาน | ตรวจสอบ `SCRIPT_NAME=/projects` ใน `.env` |
| **Static files หาย** | ยังไม่ได้รัน collectstatic | รัน `manage.py collectstatic --noinput` |
| **CSRF Error** | ไม่มี `CSRF_TRUSTED_ORIGINS` | เพิ่ม `CSRF_TRUSTED_ORIGINS=https://lib.npu.ac.th` ใน `.env` |
| **Script encoding error** | PowerShell อ่าน UTF-8 ผิด | แปลง Encoding ด้วย UTF8 BOM ก่อนรัน script |

---

## ภาคผนวก — โครงสร้างไฟล์สำคัญ

```
C:\project\project_tracker\
├── .env                          ← Environment variables
├── cert\
│   ├── certxxxx.pfx             ← SSL Certificate
│   └── xxxx.txt                 ← รหัสผ่าน PFX
├── config\settings\
│   └── production.py            ← Production settings
├── deploy\
│   ├── waitress_serve.py        ← Entry point สำหรับ Waitress
│   └── iis\
│       ├── web.config           ← IIS Reverse Proxy rules
│       ├── setup_iis.ps1        ← IIS Setup script
│       └── README_IIS.md        ← คู่มือ IIS
├── logs\
│   ├── waitress.log             ← Application log
│   └── waitress_error.log       ← Error log
└── static\collected\            ← Static files (หลัง collectstatic)

C:\iis_root\
└── web.config                   ← IIS website root

C:\nssm\
└── nssm.exe                     ← Service Manager
```

---

*เอกสารนี้จัดทำโดยงานเทคนิคสารสนเทศและการจัดการทรัพยากร สำนักวิทยบริการ มหาวิทยาลัยนครพนม*
