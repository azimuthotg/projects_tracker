# Deploy บน Windows Server (Waitress + NSSM)

## สิ่งที่ต้องเตรียม

| รายการ | หมายเหตุ |
|--------|---------|
| Python 3.12+ | https://python.org |
| Git | https://git-scm.com |
| MySQL Client (mysqlclient) | ต้องติดตั้ง Visual C++ Build Tools ก่อน |
| NSSM | https://nssm.cc/download — วางไว้ที่ `C:\nssm\nssm.exe` |

---

## ขั้นตอนติดตั้ง (ครั้งแรก)

### 1. Clone และ setup

```bat
cd C:\projects
git clone https://github.com/azimuthotg/projects_tracker.git project_tracker
cd project_tracker
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. สร้างไฟล์ .env

```bat
copy deploy\.env.production.example .env
```
แก้ไขค่าใน `.env` ให้ตรงกับ server จริง (SECRET_KEY, DB_*, ALLOWED_HOSTS)

**สร้าง SECRET_KEY:**
```bat
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. ทดสอบ settings

```bat
venv\Scripts\python manage.py check --settings=config.settings.production
```

### 4. ติดตั้ง Service (รันในฐานะ Administrator)

แก้ไข path ใน `deploy\install_service.bat` บรรทัดแรกให้ตรงกับ server แล้วรัน:

```bat
deploy\install_service.bat
```

script จะทำครบ: collectstatic → migrate → ติดตั้ง NSSM → start service

---

## คำสั่งจัดการ Service

```bat
:: เริ่ม / หยุด / รีสตาร์ท
C:\nssm\nssm.exe start ProjectTracker
C:\nssm\nssm.exe stop ProjectTracker
C:\nssm\nssm.exe restart ProjectTracker

:: ดูสถานะ
C:\nssm\nssm.exe status ProjectTracker

:: ถอนการติดตั้ง
C:\nssm\nssm.exe stop ProjectTracker
C:\nssm\nssm.exe remove ProjectTracker confirm
```

---

## อัปเดต (หลัง deploy แล้ว)

```bat
cd C:\projects\project_tracker
git pull
venv\Scripts\activate
pip install -r requirements.txt
venv\Scripts\python manage.py migrate --settings=config.settings.production
venv\Scripts\python manage.py collectstatic --noinput --settings=config.settings.production
C:\nssm\nssm.exe restart ProjectTracker
```

---

## โครงสร้างไฟล์หลัง deploy

```
C:\projects\project_tracker\
├── .env                  ← สร้างเอง (ห้าม commit)
├── logs\
│   ├── service_stdout.log
│   └── service_stderr.log
├── media\                ← ไฟล์ที่ user upload (PDF documents)
└── static\collected\     ← static files (สร้างโดย collectstatic)
```

---

## ปัญหาที่พบบ่อย

**mysqlclient ติดตั้งไม่ได้**
→ ติดตั้ง [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) ก่อน

**Service ขึ้นแต่เข้าเว็บไม่ได้**
→ ดู log ที่ `logs\service_stderr.log`
→ ตรวจสอบ Firewall: อนุญาต port 8000 inbound

**Static files ไม่แสดง (404)**
→ รัน `collectstatic` ใหม่แล้ว restart service

**`ALLOWED_HOSTS` error**
→ เพิ่ม IP หรือ domain ของ server ใน `.env`
