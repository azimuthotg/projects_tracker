#!/usr/bin/env python3
"""capture_screens.py — จับภาพหน้าจอระบบเป็นอัตราส่วน 16:9 สำหรับคู่มือการใช้งาน

ขนาดภาพ 1600x900 (16:9) เรนเดอร์ที่ความละเอียด 2 เท่า ได้ไฟล์ 3200x1800
เลือกขนาดนี้เพราะตารางกว้างยังแสดงครบทุกคอลัมน์ และตัวอักษรในภาพยังอ่านออกเมื่อพิมพ์ลงกระดาษ

วิธีใช้
    1. เปิด dev server:  venv/bin/python manage.py runserver 127.0.0.1:8099
    2. ตั้งค่า SHOT_SESSION_COOKIE ถ้าต้องการข้ามหน้าล็อกอิน มิฉะนั้นจะล็อกอินด้วย USER/PASSWORD
    3. รัน:  venv/bin/python docs/capture_screens.py

หมายเหตุ: สคริปต์นี้เปิดดูหน้าจอ (GET) เท่านั้น ไม่บันทึกหรือแก้ไขข้อมูลใด ๆ
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get('SHOT_BASE', 'http://127.0.0.1:8099')
USER = 'admin'
PASSWORD = 'admin1234'
SESSION_COOKIE = os.environ.get('SHOT_SESSION_COOKIE', '')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots_v2')

VIEW = {'width': 1600, 'height': 900}
SCALE = 2

# (ชื่อไฟล์, path, จุดที่เลื่อนไป, การกระทำก่อนถ่าย)
#   จุดที่เลื่อนไป: None = บนสุด | 'text=...' = เลื่อนให้ข้อความนั้นอยู่ใกล้ขอบบน | ทศนิยม = สัดส่วนความสูงของหน้า
SHOTS = [
    ('01_login',                '/accounts/login/',                        None,                       None),
    ('02_dashboard',            '/',                                       None,                       None),
    ('03_dashboard_attention',  '/',                                       'text=รายการที่ต้องติดตาม',  None),
    ('04_project_list',         '/projects/',                              None,                       None),
    ('05_project_list_expand',  '/projects/',                              0.15,                       'expand'),
    ('06_project_detail',       '/projects/13/',                           None,                       None),
    ('07_project_activities',   '/projects/13/',                           'text=เพิ่มกิจกรรม',         None),
    ('08_project_form',         '/projects/create/',                       None,                       None),
    ('09_activity_detail',      '/projects/4/activities/6/',               None,                       None),
    ('10_activity_expenses',    '/projects/4/activities/6/',               'h3:has-text("รายการเบิกจ่าย")', None),
    ('11_activity_form',        '/projects/4/activities/create/',          None,                       None),
    ('12_expense_form',         '/budget/create/6/',                       None,                       None),
    ('13_expense_list',         '/budget/',                                None,                       None),
    ('14_approval_list',        '/budget/approvals/',                      None,                       None),
    ('15_expense_approve',      '/budget/33/approve/',                     None,                       None),
    ('16_activity_report',      '/projects/11/activities/17/',             'text=รายงานกิจกรรมย่อย',    None),
    ('17_activity_report_form', '/projects/activities/17/reports/create/', None,                       None),
    ('18_my_tasks',             '/my-tasks/',                              None,                       None),
    ('19_timeline',             '/projects/timeline/',                     None,                       None),
    ('20_budget_transfer',      '/projects/4/budget-transfer/',            None,                       None),
    ('21_transfer_history',     '/projects/4/budget-transfer/history/',    None,                       None),
    ('22_forms_list',           '/projects/forms/',                        None,                       None),
    ('23_budget_report',        '/reports/budget/',                        None,                       None),
    ('24_budget_report_table',  '/reports/budget/',                        0.22,                       None),
    ('25_expense_report',       '/reports/expenses/',                      None,                       None),
    ('26_project_report',       '/reports/project/13/',                    None,                       None),
    ('27_executive',            '/executive/',                             None,                       None),
    ('27b_executive_ranking',   '/executive/',                             0.45,                       None),
    ('28_profile',              '/accounts/profile/',                      None,                       None),
    ('29_line_notify',          '/projects/13/',                           None,                       'line-modal'),
    ('30_delete_request',       '/projects/16/delete-request/',            None,                       None),
]


def do_action(page, action):
    if action == 'expand':
        for btn in page.query_selector_all('[onclick*="toggleActivities"]')[:3]:
            try:
                btn.click()
            except Exception:
                pass
        page.wait_for_timeout(400)
    elif action == 'line-modal':
        el = page.query_selector('text=ส่งแจ้งเตือน LINE')
        if el:
            el.click()
            page.wait_for_timeout(600)


def do_scroll(page, target):
    if target is None:
        return
    if isinstance(target, float):
        height = page.evaluate('document.body.scrollHeight')
        page.evaluate(f'window.scrollTo(0, {int(height * target)})')
    else:
        el = page.query_selector(target)
        if el:
            box = el.bounding_box()
            if box:
                page.evaluate(f"window.scrollTo(0, {max(0, int(box['y']) - 60)})")
    page.wait_for_timeout(400)


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEW, device_scale_factor=SCALE)
        page.set_default_timeout(60000)

        page.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
        page.screenshot(path=os.path.join(OUT, '01_login.png'))
        print('  01_login')

        if SESSION_COOKIE:
            page.context.add_cookies([{
                'name': 'sessionid', 'value': SESSION_COOKIE,
                'domain': '127.0.0.1', 'path': '/',
            }])
        else:
            page.fill('input[name="username"]', USER)
            page.fill('input[name="password"]', PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')

        page.goto(BASE + '/', wait_until='networkidle')
        if '/accounts/login' in page.url:
            print('ERROR: เข้าสู่ระบบไม่สำเร็จ', file=sys.stderr)
            sys.exit(1)

        for name, path, target, action in SHOTS:
            if name == '01_login':
                continue
            try:
                page.goto(BASE + path, wait_until='networkidle')
                page.wait_for_timeout(700)
                do_action(page, action)
                do_scroll(page, target)
                page.screenshot(path=os.path.join(OUT, f'{name}.png'))
                print(f'  {name}')
            except Exception as e:
                print(f'  !! {name}: {e}', file=sys.stderr)

        browser.close()
    print(f'\nเสร็จสิ้น — ไฟล์อยู่ที่ {OUT}')


if __name__ == '__main__':
    main()
