#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 7: 권한 시스템 모니터링
운영 중 권한 사용 모니터링 및 리포트 생성
"""

import logging
from datetime import datetime, timedelta
import psycopg2
import json
import os
from collections import Counter, defaultdict

class PermissionMonitor:
    def __init__(self):
        self.setup_logging()
        self.suspicious_threshold = 5  # 5회 이상 거부시 의심
        self.time_window = 300  # 5분 내

    def setup_logging(self):
        """로깅 설정"""
        # 로그 디렉토리 생성
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # 권한 모니터 전용 로거
        self.logger = logging.getLogger('permission_monitor')
        self.logger.setLevel(logging.INFO)

        # 파일 핸들러
        fh = logging.FileHandler('logs/permission_monitor.log', encoding='utf-8')
        fh.setLevel(logging.INFO)

        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)

        self.logger.addHandler(fh)

    def get_db_connection(self):
        """데이터베이스 연결"""
        try:
            return psycopg2.connect(
                host='localhost',
                database='portal_db',
                user='postgres',
                password='postgres'
            )
        except:
            # 연결 실패시 None 반환
            return None

    def log_access(self, emp_id, route, role, granted, ip_address=None):
        """접근 로그 기록"""
        status = "GRANTED" if granted else "DENIED"

        # 파일 로그
        log_msg = f"{status} - User: {emp_id}, Role: {role}, Route: {route}"
        if ip_address:
            log_msg += f", IP: {ip_address}"

        if granted:
            self.logger.info(log_msg)
        else:
            self.logger.warning(log_msg)

        # DB 로그 (access_audit_log 테이블)
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO access_audit_log
                    (emp_id, accessed_menu, action, success, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (emp_id, route, 'ACCESS', granted, ip_address))
                conn.commit()
                cursor.close()
            except Exception as e:
                self.logger.error(f"DB logging failed: {e}")
            finally:
                conn.close()

    def get_recent_denials(self, hours=24):
        """최근 거부된 접근 조회"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emp_id, accessed_menu, created_at, ip_address
                FROM access_audit_log
                WHERE success = false
                  AND created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT 100
            """, (hours,))

            denials = []
            for row in cursor.fetchall():
                denials.append({
                    'emp_id': row[0],
                    'route': row[1],
                    'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else '',
                    'ip': row[3]
                })

            cursor.close()
            conn.close()
            return denials

        except Exception as e:
            self.logger.error(f"Failed to get denials: {e}")
            return []

    def get_user_activity(self, emp_id, days=7):
        """특정 사용자 활동 조회"""
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            cursor = conn.cursor()

            # 전체 접근 횟수
            cursor.execute("""
                SELECT COUNT(*)
                FROM access_audit_log
                WHERE emp_id = %s
                  AND created_at > NOW() - INTERVAL '%s days'
            """, (emp_id, days))
            total_access = cursor.fetchone()[0]

            # 거부된 접근 횟수
            cursor.execute("""
                SELECT COUNT(*)
                FROM access_audit_log
                WHERE emp_id = %s
                  AND success = false
                  AND created_at > NOW() - INTERVAL '%s days'
            """, (emp_id, days))
            denied_access = cursor.fetchone()[0]

            # 가장 많이 접근한 메뉴
            cursor.execute("""
                SELECT accessed_menu, COUNT(*) as cnt
                FROM access_audit_log
                WHERE emp_id = %s
                  AND created_at > NOW() - INTERVAL '%s days'
                GROUP BY accessed_menu
                ORDER BY cnt DESC
                LIMIT 5
            """, (emp_id, days))

            top_menus = []
            for menu, count in cursor.fetchall():
                top_menus.append({'menu': menu, 'count': count})

            cursor.close()
            conn.close()

            return {
                'emp_id': emp_id,
                'period_days': days,
                'total_access': total_access,
                'denied_access': denied_access,
                'denial_rate': f"{(denied_access/total_access*100):.1f}%" if total_access > 0 else "0%",
                'top_menus': top_menus
            }

        except Exception as e:
            self.logger.error(f"Failed to get user activity: {e}")
            return {}

    def daily_report(self):
        """일일 권한 사용 리포트"""
        conn = self.get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            report_date = datetime.now().strftime('%Y-%m-%d')

            # 1. 오늘 전체 접근 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as granted,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as denied
                FROM access_audit_log
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            stats = cursor.fetchone()
            total, granted, denied = stats if stats else (0, 0, 0)

            # 2. 가장 활발한 사용자 TOP 5
            cursor.execute("""
                SELECT emp_id, COUNT(*) as cnt
                FROM access_audit_log
                WHERE DATE(created_at) = CURRENT_DATE
                GROUP BY emp_id
                ORDER BY cnt DESC
                LIMIT 5
            """)
            top_users = cursor.fetchall()

            # 3. 가장 많이 거부된 라우트
            cursor.execute("""
                SELECT accessed_menu, COUNT(*) as cnt
                FROM access_audit_log
                WHERE DATE(created_at) = CURRENT_DATE
                  AND success = false
                GROUP BY accessed_menu
                ORDER BY cnt DESC
                LIMIT 5
            """)
            denied_routes = cursor.fetchall()

            # 4. 권한 변경 이력
            cursor.execute("""
                SELECT emp_id, menu_code, updated_by, updated_at
                FROM user_menu_permissions
                WHERE DATE(updated_at) = CURRENT_DATE
                ORDER BY updated_at DESC
                LIMIT 10
            """)
            permission_changes = cursor.fetchall()

            cursor.close()
            conn.close()

            # 리포트 생성
            report = f"""
=====================================
DAILY PERMISSION REPORT
Date: {report_date}
=====================================

📊 ACCESS STATISTICS
--------------------
Total Requests: {total}
Granted: {granted} ({granted/total*100:.1f}% if total > 0 else 0%)
Denied: {denied} ({denied/total*100:.1f}% if total > 0 else 0%)

👤 TOP ACTIVE USERS
-------------------"""

            for emp_id, count in top_users:
                report += f"\n  • {emp_id}: {count} requests"

            report += "\n\n🚫 MOST DENIED ROUTES\n---------------------"
            for route, count in denied_routes:
                report += f"\n  • {route}: {count} denials"

            report += "\n\n🔄 PERMISSION CHANGES\n----------------------"
            for emp_id, menu, by, at in permission_changes[:5]:
                report += f"\n  • {emp_id}: {menu} by {by or 'System'} at {at.strftime('%H:%M')}"

            report += "\n\n====================================="

            # 리포트 저장
            report_file = f"reports/daily_permission_{report_date}.txt"
            os.makedirs('reports', exist_ok=True)
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)

            self.logger.info(f"Daily report generated: {report_file}")
            return report

        except Exception as e:
            self.logger.error(f"Failed to generate daily report: {e}")
            return None

    def check_suspicious_activity(self):
        """의심스러운 활동 감지"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()

            # 최근 5분 내 5회 이상 거부된 사용자
            cursor.execute("""
                SELECT emp_id, COUNT(*) as denial_count,
                       array_agg(DISTINCT accessed_menu) as denied_routes
                FROM access_audit_log
                WHERE success = false
                  AND created_at > NOW() - INTERVAL '5 minutes'
                GROUP BY emp_id
                HAVING COUNT(*) >= %s
            """, (self.suspicious_threshold,))

            suspicious_users = []
            for emp_id, count, routes in cursor.fetchall():
                suspicious_users.append({
                    'emp_id': emp_id,
                    'denial_count': count,
                    'denied_routes': routes,
                    'alert_level': 'HIGH' if count >= 10 else 'MEDIUM'
                })

                # 경고 로그
                self.logger.warning(
                    f"SUSPICIOUS ACTIVITY - User: {emp_id}, "
                    f"Denials: {count} in 5 minutes, Routes: {routes}"
                )

            cursor.close()
            conn.close()

            return suspicious_users

        except Exception as e:
            self.logger.error(f"Failed to check suspicious activity: {e}")
            return []

    def get_stats_summary(self):
        """통계 요약"""
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            cursor = conn.cursor()

            # 오늘 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as granted
                FROM access_audit_log
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            today = cursor.fetchone()

            # 이번 주 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as granted
                FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            week = cursor.fetchone()

            # 활성 사용자 수
            cursor.execute("""
                SELECT COUNT(DISTINCT emp_id)
                FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            active_users = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return {
                'today': {
                    'total': today[0] if today else 0,
                    'granted': today[1] if today else 0,
                    'success_rate': f"{(today[1]/today[0]*100):.1f}%" if today and today[0] > 0 else "0%"
                },
                'week': {
                    'total': week[0] if week else 0,
                    'granted': week[1] if week else 0,
                    'success_rate': f"{(week[1]/week[0]*100):.1f}%" if week and week[0] > 0 else "0%"
                },
                'active_users_24h': active_users
            }

        except Exception as e:
            self.logger.error(f"Failed to get stats summary: {e}")
            return {}


# CLI 도구
def main():
    """CLI 인터페이스"""
    monitor = PermissionMonitor()

    print("\n" + "="*50)
    print("PERMISSION MONITOR")
    print("="*50)

    while True:
        print("\n1. Generate Daily Report")
        print("2. Check Suspicious Activity")
        print("3. View Recent Denials")
        print("4. Check User Activity")
        print("5. View Statistics Summary")
        print("0. Exit")

        choice = input("\nSelect option: ")

        if choice == '1':
            report = monitor.daily_report()
            if report:
                print(report)
            else:
                print("Failed to generate report")

        elif choice == '2':
            suspicious = monitor.check_suspicious_activity()
            if suspicious:
                print("\n⚠️ SUSPICIOUS ACTIVITY DETECTED:")
                for user in suspicious:
                    print(f"  • {user['emp_id']}: {user['denial_count']} denials "
                          f"[{user['alert_level']}]")
            else:
                print("No suspicious activity detected")

        elif choice == '3':
            hours = input("Hours to look back (default 24): ") or "24"
            denials = monitor.get_recent_denials(int(hours))
            if denials:
                print(f"\nRecent Denials (last {hours} hours):")
                for denial in denials[:10]:
                    print(f"  • {denial['time']} - {denial['emp_id']}: {denial['route']}")
            else:
                print("No denials found")

        elif choice == '4':
            emp_id = input("Enter employee ID: ")
            days = input("Days to analyze (default 7): ") or "7"
            activity = monitor.get_user_activity(emp_id, int(days))
            if activity:
                print(f"\nUser Activity Report: {emp_id}")
                print(f"  Period: {activity.get('period_days', 0)} days")
                print(f"  Total Access: {activity.get('total_access', 0)}")
                print(f"  Denied: {activity.get('denied_access', 0)} "
                      f"({activity.get('denial_rate', '0%')})")
                if activity.get('top_menus'):
                    print("  Top Menus:")
                    for menu in activity['top_menus']:
                        print(f"    • {menu['menu']}: {menu['count']}")
            else:
                print("No activity found")

        elif choice == '5':
            stats = monitor.get_stats_summary()
            if stats:
                print("\nStatistics Summary")
                print("-" * 30)
                print(f"Today: {stats['today']['total']} requests, "
                      f"{stats['today']['success_rate']} success")
                print(f"Week: {stats['week']['total']} requests, "
                      f"{stats['week']['success_rate']} success")
                print(f"Active Users (24h): {stats['active_users_24h']}")
            else:
                print("No statistics available")

        elif choice == '0':
            break
        else:
            print("Invalid option")

    print("\nMonitor stopped.")


if __name__ == "__main__":
    main()