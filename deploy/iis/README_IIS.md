# Deploy บน Windows Server 2019 — IIS + HTTPS
## lib.npu.ac.th → Path-based Multi-App

---

## Architecture

```
Internet
   │
   ▼  https://lib.npu.ac.th
┌──────────────────────────────────────────────────────────┐
│  IIS 10.0  (port 80 → redirect HTTPS, port 443 → serve) │
│  SSL cert: *.npu.ac.th (cert2026.pfx / DigiCert)        │
│                                                          │
│  /projects/*  ──── ตัด /projects ──►  127.0.0.1:8000   │
│  /budget/*    ──── ตัด /budget   ──►  127.0.0.1:8001   │
│  /hr/*        ──── ตัด /hr       ──►  127.0.0.1:8002   │
└──────────────────────────────────────────────────────────┘
         │                   │                  │
   ┌─────▼─────┐       ┌─────▼─────┐      ┌────▼──────┐
   │ Waitress  │       │ Waitress  │      │ Waitress  │
   │ App1:8000 │       │ App2:8001 │      │ App3:8002 │
   │ (NSSM)    │       │ (NSSM)    │      │ (NSSM)    │
   └─────┬─────┘       └─────┬─────┘      └────┬──────┘
   ┌─────▼─────┐       ┌─────▼─────┐      ┌────▼──────┐
   │  Django   │       │  Django   │      │  Django   │
   │ SCRIPT=   │       │ SCRIPT=   │      │ SCRIPT=   │
   │ /projects │       │ /budget   │      │ /hr       │
   └───────────┘       └───────────┘      └───────────┘
```

---

## สิ่งที่ต้องเตรียม

| รายการ | สถานะ |
|--------|-------|
| Windows Server 2019 | ✅ มีแล้ว |
| cert2026.pfx (*.npu.ac.th / DigiCert) | ✅ มีแล้ว |
| NSSM + Waitress (Project Tracker) | ✅ รันอยู่แล้ว |
| ARR Module | ⏳ ต้องดาวน์โหลด |
| DNS: lib.npu.ac.th → 110.78.83.102 | ⏳ รอ IT มหาวิทยาลัย |

---

## ขั้นตอนที่ 1 — ติดตั้ง ARR Module

ดาวน์โหลดและติดตั้ง (ฟรี จาก Microsoft):

```
https://www.iis.net/downloads/microsoft/application-request-routing
```

> ARR จะดึง URL Rewrite module มาติดตั้งให้อัตโนมัติ
> หลังติดตั้งแล้ว **ไม่ต้อง reboot** แค่ restart IIS

---

## ขั้นตอนที่ 2 — Import SSL Certificate

เปิด **PowerShell (Admin)**:

```powershell
Import-PfxCertificate `
  -FilePath "C:\projects\project_tracker\cert\cert2026.pfx" `
  -CertStoreLocation Cert:\LocalMachine\My `
  -Password (ConvertTo-SecureString "admina2026*" -AsPlainText -Force) `
  -Exportable
```

ดู Thumbprint ของ cert ที่เพิ่งนำเข้า:

```powershell
Get-ChildItem Cert:\LocalMachine\My |
  Where-Object { $_.Subject -like "*.npu.ac.th*" } |
  Select-Object Thumbprint, Subject, NotAfter |
  Format-Table -AutoSize
```

**จดค่า Thumbprint ไว้** (ตัวอย่าง: `A1B2C3D4E5F67890...`) ใช้ในขั้นตอนถัดไป

---

## ขั้นตอนที่ 3 — รัน Setup Script

```powershell
cd C:\projects\project_tracker

.\deploy\iis\setup_iis.ps1 -CertThumbprint "วาง-THUMBPRINT-ที่นี่"
```

Script จะทำทั้งหมดให้:
- เปิด IIS features
- ตั้งค่า ARR proxy
- สร้าง Website `lib.npu.ac.th`
- ผูก cert กับ port 443
- เปิด Firewall port 80 + 443

---

## ขั้นตอนที่ 4 — แก้ไข .env ของ Project Tracker

แก้ `C:\projects\project_tracker\.env`:

```env
ALLOWED_HOSTS=lib.npu.ac.th,110.78.83.102
HTTPS_ENABLED=True
CSRF_TRUSTED_ORIGINS=https://lib.npu.ac.th
WAITRESS_HOST=127.0.0.1
SCRIPT_NAME=/projects
```

---

## ขั้นตอนที่ 5 — Restart Waitress

```bat
C:\nssm\nssm.exe restart ProjectTracker
```

---

## ขั้นตอนที่ 6 — ทดสอบ (หลัง DNS พร้อม)

```
http://lib.npu.ac.th/projects/     →  ต้อง redirect เป็น https:// อัตโนมัติ
https://lib.npu.ac.th/projects/    →  ต้องเห็นหน้า login 🔒
```

---

## เพิ่ม App ใหม่ในอนาคต

### ตัวอย่าง: เพิ่ม App 2 ที่ /budget/ → port 8001

**1. แก้ web.config** — uncomment ส่วน App2:
```
C:\iis_root\web.config
```
เปิด comment block ที่มีข้อความ `App2 Budget`

**2. ตั้งค่า .env ของ App2:**
```env
SCRIPT_NAME=/budget
WAITRESS_PORT=8001
WAITRESS_HOST=127.0.0.1
```

**3. ติดตั้ง App2 เป็น NSSM service:**
```bat
C:\nssm\nssm.exe install App2Service "C:\projects\app2\venv\Scripts\python.exe" "C:\projects\app2\deploy\waitress_serve.py"
C:\nssm\nssm.exe set App2Service AppDirectory "C:\projects\app2"
C:\nssm\nssm.exe start App2Service
```

**4. Reload IIS:**
```bat
iisreset /restart
```

> ✅ ไม่กระทบ App1 ที่รันอยู่แล้วเลย

---

## แก้ปัญหาที่พบบ่อย

| อาการ | วิธีแก้ |
|-------|---------|
| 502 Bad Gateway | Waitress ไม่ได้รัน → `nssm status ProjectTracker` |
| CSRF Verification Failed | เพิ่ม `CSRF_TRUSTED_ORIGINS=https://lib.npu.ac.th` ใน .env |
| Static files 404 | ตรวจสอบ `SCRIPT_NAME=/projects` ใน .env แล้ว restart |
| Redirect loop | ตรวจสอบ `HTTPS_ENABLED=True` และ `SECURE_SSL_REDIRECT=False` |
| หน้าเว็บขึ้นแต่ link ผิด | ตรวจสอบ `SCRIPT_NAME=/projects` ใน .env |

---

## สรุป URL ที่ใช้งาน

```
https://lib.npu.ac.th/projects/   ←  Project Tracker (ระบบนี้)
https://lib.npu.ac.th/budget/     ←  App 2 (อนาคต)
https://lib.npu.ac.th/hr/         ←  App 3 (อนาคต)
```
