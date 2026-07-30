# 📋 ดัชนีเอกสาร — ระบบติดตามแผนงานและงบประมาณ

ระบบติดตามแผนงานและงบประมาณ สำนักวิทยบริการ มหาวิทยาลัยนครพนม
(Project Plan & Budget Tracking System — Academic Resource Center, NPU)

- **Repository:** [azimuthotg/projects_tracker](https://github.com/azimuthotg/projects_tracker)
- **Production:** https://lib.npu.ac.th/projects/
- **Tech Stack:** Django 5.1 / Python 3.12 / MySQL 8 / Tailwind CSS / LINE Messaging API
- **Deploy:** Windows Server + IIS (ARR) + Waitress + NSSM

---

## 📚 เอกสารหลัก

| เอกสาร | รูปแบบ | คำอธิบาย |
|---|---|---|
| คู่มือการใช้งานระบบติดตามโครงการ | `.docx` / `.pdf` | คู่มือผู้ใช้ทั่วไป **ฉบับที่ 2** — 20 บท 46 หน้า 33 ภาพ (16:9) ครอบคลุมทุกฟีเจอร์ ภาษาสำหรับผู้ไม่มีพื้นฐาน |
| รายงานการพัฒนาระบบ SDLC | `.docx` / `.pdf` | รายงานกระบวนการพัฒนาระบบตามแนวทาง SDLC |
| ข้อเสนอโครงการ_ระบบติดตามแผนงาน | `.docx` | เอกสารข้อเสนอโครงการเริ่มต้น |
| [คู่มือการ Deploy](deployment_guide.md) | `.md` | ขั้นตอนติดตั้งบน Windows Server + IIS |

> หมายเหตุ: ไฟล์ `.docx` / `.pdf` ของคู่มือและ SDLC ไม่ได้ track ใน git (ขนาดใหญ่) — เก็บไว้ในเครื่อง/server เท่านั้น

---

## 🛠️ สคริปต์สร้างเอกสาร

| ไฟล์ | คำอธิบาย |
|---|---|
| `build_manual_v2.py` | **สร้างคู่มือฉบับที่ 2** — ไม่ใช้ bullet, ตัวอักษรสีดำล้วน, หัวตารางเทาอ่อนจัดกึ่งกลาง, ภาพ 16:9 พร้อมคำบรรยาย |
| `capture_screens.py` | แคป screenshot อัตโนมัติด้วย Playwright ที่ 1600×900 scale 2 (16:9) — เปิดดูหน้าจอแบบ GET เท่านั้น |
| `build_manual.py` | สร้างคู่มือฉบับที่ 1 (รูปแบบเดิม มี bullet และสีน้ำเงิน) — เก็บไว้อ้างอิง |
| `build_sdlc_report.py` | สร้างรายงาน SDLC (.docx) |
| `screenshots_v2/` | ภาพหน้าจอ 3200×1800 (16:9) 32 ไฟล์ ใช้ประกอบคู่มือฉบับที่ 2 |
| `screenshots/` | ภาพหน้าจอชุดเดิม (01_login → 14_budget_transfer) ใช้ประกอบคู่มือฉบับที่ 1 และรายงาน SDLC |

---

## 🚀 Timeline การพัฒนา

| วันที่ | Progress Log | สรุป |
|---|---|---|
| 30 ก.ค. 2569 | [progress_2026-07-30.md](progress_2026-07-30.md) | ปรับปรุงคู่มือการใช้งานเป็นฉบับที่ 2 — ตัด bullet/สีออกทั้งเล่ม · ขยายจาก 14 เป็น 20 บท · แคป screenshot ใหม่ 32 ภาพเป็น 16:9 · สคริปต์ `build_manual_v2.py` + `capture_screens.py` |
| 7 มิ.ย. 2569 | [progress_2026-06-07.md](progress_2026-06-07.md) | เพิ่ม `/health/` endpoint สำหรับ NMS Agent monitoring · สร้าง INDEX.md · นำ progress logs/build scripts เข้า git |
| 14 พ.ค. 2569 | [progress_2026-05-14.md](progress_2026-05-14.md) | RBAC review ทั้งระบบ · role "ผู้บริหาร" (executive) · ระบบแบบฟอร์ม (DocumentTemplate) · collapsible sidebar · LINE manual trigger + badge |
| 5 พ.ค. 2569 | [progress_2026-05-05.md](progress_2026-05-05.md) | PDF รายงาน landscape · Executive Dashboard การ์ดงบตามแผนก · แก้ยอดโครงการ non-แผนก |

---

## 🧩 ภาพรวมระบบ (Apps)

| App | หน้าที่ |
|---|---|
| `accounts` | Auth (NPU AD + local), UserProfile, Department, LINE linking, RBAC, Audit Log |
| `projects` | FiscalYear, Project, Activity CRUD, Timeline (Gantt), DocumentTemplate (แบบฟอร์ม) |
| `budget` | Expense recording & approval, BudgetTransfer, signals (budget alert) |
| `notifications` | LINE service (Push/Flex), notification log, manual trigger |
| `reports` | Budget/Expense reports, Excel/PDF export (ReportLab + THSarabunNew) |
| `dashboard` | Dashboard ตาม role (รวม Executive Dashboard) |

---

## 👥 RBAC (สิทธิ์ผู้ใช้)

| Role | Slug | ขอบเขต |
|---|---|---|
| เจ้าหน้าที่ | `staff` | ดูโครงการในแผนก · จัดการกิจกรรมที่รับผิดชอบ |
| เจ้าหน้าที่แผน | `planner` | ทุกโครงการในแผนก |
| หัวหน้างาน | `head` | ทุกโครงการในแผนก + อนุมัติเบิกจ่าย |
| ผู้บริหาร | `executive` | อ่านอย่างเดียว ข้ามทุกแผนก |
| ผู้ดูแลระบบ | `admin` | ทุกโครงการ ทุกแผนก + จัดการผู้ใช้ |

---

## 📊 ภาพรวม Phase

| Phase | สถานะ |
|---|---|
| Phase 1 — Foundation (models, auth, RBAC) | ✅ |
| Phase 2 — Core CRUD (project/activity/expense/approval) | ✅ |
| Phase 2.5 — NPU AD Auth | ✅ |
| Phase 2.6–2.7 — UI, Delete workflow, Comments, My Tasks, Budget Transfer | ✅ |
| Phase 3 — LINE Notifications | ✅ |
| Phase 4 — UI/UX + Reports (Excel/PDF) + Timeline | ✅ |
| Phase 5 — User Manual (ฉบับที่ 1) + SDLC Report | ✅ |
| Phase 5.1 — User Manual ฉบับที่ 2 (20 บท, 16:9, ไม่มี bullet) | ✅ |
| Deploy — IIS Production (lib.npu.ac.th) | ✅ |
| Monitoring — `/health/` endpoint (NMS) | ✅ |

---

*อัปเดตล่าสุด: 30 กรกฎาคม 2569*
