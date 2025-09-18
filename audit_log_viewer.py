#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 7: 감사 로그 조회 도구
권한 시스템 감사 로그를 조회하고 분석하는 도구
"""

import psycopg2
from datetime import datetime, timedelta
import json
from tabulate import tabulate
import pandas as pd

class AuditLogViewer:
    def __init__(self):
        self.conn = None
        self.connect_db()

    def connect_db(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(
                host='localhost',
                database='portal_db',
                user='postgres',
                password='postgres'
            )
        except Exception as e:
            print(f"DB connection failed: {e}")
            self.conn = None

    def get_recent_denials(self, hours=24):
        """최근 거부된 접근 조회"""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                emp_id,
                accessed_menu,
                ip_address,
                created_at
            FROM access_audit_log
            WHERE success = false
              AND created_at > NOW() - INTERVAL '%s hours'
            ORDER BY created_at DESC
            LIMIT 100
        """, (hours,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'Employee ID': row[0],
                'Route': row[1],
                'IP Address': row[2] or 'N/A',
                'Time': row[3].strftime('%Y-%m-%d %H:%M:%S')
            })

        cursor.close()
        return results

    def get_user_activity(self, emp_id, days=7):
        """특정 사용자 활동 조회"""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                accessed_menu,
                action,
                success,
                ip_address,
                created_at
            FROM access_audit_log
            WHERE emp_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
            LIMIT 500
        """, (emp_id, days))

        results = []
        for row in cursor.fetchall():
            results.append({
                'Menu': row[0],
                'Action': row[1],
                'Success': '✓' if row[2] else '✗',
                'IP': row[3] or 'N/A',
                'Time': row[4].strftime('%Y-%m-%d %H:%M:%S')
            })

        cursor.close()
        return results

    def get_permission_changes(self, days=7):
        """권한 변경 이력 조회"""
        if not self.conn:
            return []

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                emp_id,
                menu_code,
                CASE
                    WHEN can_view THEN 'View '
                    ELSE ''
                END ||
                CASE
                    WHEN can_create THEN 'Create '
                    ELSE ''
                END ||
                CASE
                    WHEN can_edit THEN 'Edit '
                    ELSE ''
                END ||
                CASE
                    WHEN can_delete THEN 'Delete'
                    ELSE ''
                END as permissions,
                updated_by,
                updated_at
            FROM user_menu_permissions
            WHERE updated_at > NOW() - INTERVAL '%s days'
              AND updated_at IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 100
        """, (days,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'Employee': row[0],
                'Menu': row[1],
                'Permissions': row[2].strip() or 'None',
                'Changed By': row[3] or 'System',
                'Date': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else 'N/A'
            })

        cursor.close()
        return results

    def get_access_pattern(self, emp_id, days=30):
        """사용자 접근 패턴 분석"""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()

        # 시간대별 접근 패턴
        cursor.execute("""
            SELECT
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as count
            FROM access_audit_log
            WHERE emp_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY hour
            ORDER BY hour
        """, (emp_id, days))

        hourly_pattern = {}
        for hour, count in cursor.fetchall():
            hourly_pattern[int(hour)] = count

        # 요일별 접근 패턴
        cursor.execute("""
            SELECT
                EXTRACT(DOW FROM created_at) as dow,
                COUNT(*) as count
            FROM access_audit_log
            WHERE emp_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY dow
            ORDER BY dow
        """, (emp_id, days))

        days_of_week = ['Sunday', 'Monday', 'Tuesday', 'Wednesday',
                        'Thursday', 'Friday', 'Saturday']
        daily_pattern = {}
        for dow, count in cursor.fetchall():
            daily_pattern[days_of_week[int(dow)]] = count

        # 가장 많이 접근한 메뉴
        cursor.execute("""
            SELECT
                accessed_menu,
                COUNT(*) as count
            FROM access_audit_log
            WHERE emp_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY accessed_menu
            ORDER BY count DESC
            LIMIT 10
        """, (emp_id, days))

        top_menus = []
        for menu, count in cursor.fetchall():
            top_menus.append({'menu': menu, 'count': count})

        cursor.close()

        return {
            'hourly': hourly_pattern,
            'daily': daily_pattern,
            'top_menus': top_menus
        }

    def get_system_overview(self):
        """시스템 전체 개요"""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()

        # 전체 사용자 수
        cursor.execute("SELECT COUNT(DISTINCT emp_id) FROM system_users WHERE is_active = true")
        total_users = cursor.fetchone()[0]

        # 오늘 활성 사용자
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_id)
            FROM access_audit_log
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        today_active = cursor.fetchone()[0]

        # 오늘 전체 요청
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as granted,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as denied
            FROM access_audit_log
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        today_stats = cursor.fetchone()

        # 가장 활발한 시간대
        cursor.execute("""
            SELECT
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as count
            FROM access_audit_log
            WHERE DATE(created_at) = CURRENT_DATE
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """)
        peak_hour = cursor.fetchone()

        cursor.close()

        return {
            'total_users': total_users,
            'today_active': today_active,
            'today_requests': today_stats[0] if today_stats else 0,
            'today_granted': today_stats[1] if today_stats else 0,
            'today_denied': today_stats[2] if today_stats else 0,
            'peak_hour': f"{int(peak_hour[0])}:00" if peak_hour else 'N/A'
        }

    def export_to_csv(self, data, filename):
        """데이터를 CSV로 내보내기"""
        try:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            return True
        except:
            # pandas 없을 경우 수동 처리
            import csv
            if data:
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                return True
        return False

    def close(self):
        """연결 종료"""
        if self.conn:
            self.conn.close()


def print_table(data, title=""):
    """테이블 형태로 출력"""
    if title:
        print(f"\n{title}")
        print("="*len(title))

    if not data:
        print("No data available")
        return

    try:
        print(tabulate(data, headers="keys", tablefmt="simple"))
    except:
        # tabulate 없을 경우 수동 출력
        if isinstance(data, list) and data:
            # 헤더 출력
            headers = list(data[0].keys())
            print(" | ".join(headers))
            print("-" * (len(" | ".join(headers))))
            # 데이터 출력
            for row in data:
                print(" | ".join(str(row.get(h, '')) for h in headers))


def main():
    """CLI 인터페이스"""
    viewer = AuditLogViewer()

    print("\n" + "="*50)
    print("AUDIT LOG VIEWER")
    print("="*50)

    while True:
        print("\n--- MENU ---")
        print("1. View Recent Denials")
        print("2. View User Activity")
        print("3. View Permission Changes")
        print("4. Analyze User Access Pattern")
        print("5. System Overview")
        print("6. Export to CSV")
        print("0. Exit")

        choice = input("\nSelect option: ")

        if choice == '1':
            hours = input("Hours to look back (default 24): ") or "24"
            data = viewer.get_recent_denials(int(hours))
            print_table(data, f"Recent Denials (Last {hours} Hours)")

        elif choice == '2':
            emp_id = input("Enter employee ID: ")
            days = input("Days to look back (default 7): ") or "7"
            data = viewer.get_user_activity(emp_id, int(days))
            print_table(data, f"User Activity: {emp_id} (Last {days} Days)")

        elif choice == '3':
            days = input("Days to look back (default 7): ") or "7"
            data = viewer.get_permission_changes(int(days))
            print_table(data, f"Permission Changes (Last {days} Days)")

        elif choice == '4':
            emp_id = input("Enter employee ID: ")
            days = input("Days to analyze (default 30): ") or "30"
            pattern = viewer.get_access_pattern(emp_id, int(days))

            print(f"\n=== Access Pattern for {emp_id} ({days} days) ===")

            print("\nHourly Pattern:")
            for hour in range(24):
                count = pattern['hourly'].get(hour, 0)
                bar = '█' * (count // 10) if count > 0 else ''
                print(f"  {hour:02d}:00  {bar} ({count})")

            print("\nDaily Pattern:")
            for day, count in pattern['daily'].items():
                bar = '█' * (count // 10) if count > 0 else ''
                print(f"  {day:9s}  {bar} ({count})")

            print("\nTop Accessed Menus:")
            for i, menu_data in enumerate(pattern['top_menus'], 1):
                print(f"  {i}. {menu_data['menu']} ({menu_data['count']} times)")

        elif choice == '5':
            overview = viewer.get_system_overview()
            print("\n=== SYSTEM OVERVIEW ===")
            print(f"Total Users:      {overview['total_users']}")
            print(f"Active Today:     {overview['today_active']}")
            print(f"Today's Requests: {overview['today_requests']}")
            print(f"  - Granted:      {overview['today_granted']}")
            print(f"  - Denied:       {overview['today_denied']}")
            print(f"Peak Hour:        {overview['peak_hour']}")

        elif choice == '6':
            print("\nExport Options:")
            print("1. Recent Denials")
            print("2. User Activity")
            print("3. Permission Changes")

            export_choice = input("Select data to export: ")

            if export_choice == '1':
                hours = input("Hours to look back (default 24): ") or "24"
                data = viewer.get_recent_denials(int(hours))
                filename = f"audit_denials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            elif export_choice == '2':
                emp_id = input("Enter employee ID: ")
                days = input("Days to look back (default 7): ") or "7"
                data = viewer.get_user_activity(emp_id, int(days))
                filename = f"audit_user_{emp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            elif export_choice == '3':
                days = input("Days to look back (default 7): ") or "7"
                data = viewer.get_permission_changes(int(days))
                filename = f"audit_changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            else:
                print("Invalid option")
                continue

            if viewer.export_to_csv(data, filename):
                print(f"✓ Exported to {filename}")
            else:
                print("Export failed")

        elif choice == '0':
            break
        else:
            print("Invalid option")

    viewer.close()
    print("\nViewer closed.")


if __name__ == "__main__":
    main()