#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrated Monitoring Dashboard - Day 4
통합 모니터링 시스템
"""

from flask import Flask, render_template, jsonify, request
import psycopg2
import configparser
import logging
import json
from datetime import datetime, timedelta
import threading
import time
from collections import deque
import psutil
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MonitoringSystem:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')

        # 메트릭 저장 (최근 1시간)
        self.metrics = {
            'system': deque(maxlen=360),  # 10초마다 샘플링, 1시간 보관
            'database': deque(maxlen=360),
            'application': deque(maxlen=360),
            'alerts': deque(maxlen=100)
        }

        self.thresholds = {
            'cpu_critical': 90,
            'cpu_warning': 70,
            'memory_critical': 90,
            'memory_warning': 80,
            'disk_critical': 90,
            'disk_warning': 80,
            'response_time_critical': 1000,  # ms
            'response_time_warning': 500,
            'error_rate_critical': 5,  # %
            'error_rate_warning': 2
        }

        self.monitoring_thread = None
        self.running = False

    def get_db_connection(self):
        """데이터베이스 연결"""
        if self.config.has_option('DATABASE', 'postgres_dsn'):
            dsn = self.config.get('DATABASE', 'postgres_dsn')
            return psycopg2.connect(dsn)
        else:
            return psycopg2.connect(
                host='localhost',
                database='portal_db',
                user='postgres',
                password='postgres'
            )

    def collect_system_metrics(self):
        """시스템 메트릭 수집"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'network_bytes_sent': psutil.net_io_counters().bytes_sent,
                'network_bytes_recv': psutil.net_io_counters().bytes_recv,
                'process_count': len(psutil.pids())
            }

            # 알림 체크
            self.check_system_alerts(metrics)

            return metrics
        except Exception as e:
            logger.error(f"System metrics collection failed: {e}")
            return None

    def collect_database_metrics(self):
        """데이터베이스 메트릭 수집"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            metrics = {'timestamp': datetime.now().isoformat()}

            # 1. 연결 수
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stat_activity
            """)
            metrics['connection_count'] = cursor.fetchone()[0]

            # 2. 활성 쿼리 수
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE state = 'active'
            """)
            metrics['active_queries'] = cursor.fetchone()[0]

            # 3. 캐시 히트율
            cursor.execute("""
                SELECT
                    sum(heap_blks_hit)::float / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100
                FROM pg_statio_user_tables
            """)
            metrics['cache_hit_ratio'] = cursor.fetchone()[0] or 0

            # 4. 데이터베이스 크기
            cursor.execute("""
                SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
            """)
            metrics['database_size_mb'] = cursor.fetchone()[0]

            # 5. 트랜잭션 통계
            cursor.execute("""
                SELECT
                    xact_commit,
                    xact_rollback
                FROM pg_stat_database
                WHERE datname = current_database()
            """)
            result = cursor.fetchone()
            metrics['transactions_committed'] = result[0]
            metrics['transactions_rollbacked'] = result[1]

            # 6. 데드락 수
            cursor.execute("""
                SELECT deadlocks FROM pg_stat_database
                WHERE datname = current_database()
            """)
            metrics['deadlocks'] = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return metrics

        except Exception as e:
            logger.error(f"Database metrics collection failed: {e}")
            return None

    def collect_application_metrics(self):
        """애플리케이션 메트릭 수집"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            metrics = {'timestamp': datetime.now().isoformat()}

            # 1. 최근 1분간 요청 수
            cursor.execute("""
                SELECT COUNT(*) FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '1 minute'
            """)
            metrics['requests_per_minute'] = cursor.fetchone()[0]

            # 2. 최근 1분간 실패율
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN success = false THEN 1 END)::float /
                    NULLIF(COUNT(*), 0) * 100 as error_rate
                FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '1 minute'
            """)
            metrics['error_rate'] = cursor.fetchone()[0] or 0

            # 3. 활성 사용자 수
            cursor.execute("""
                SELECT COUNT(DISTINCT emp_id) FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '5 minutes'
            """)
            metrics['active_users'] = cursor.fetchone()[0]

            # 4. 캐시 효율성
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN expires_at > NOW() THEN 1 END)::float /
                    NULLIF(COUNT(*), 0) * 100 as cache_efficiency
                FROM permission_cache
            """)
            metrics['cache_efficiency'] = cursor.fetchone()[0] or 0

            # 5. 평균 응답 시간 (모의)
            metrics['avg_response_time'] = 50 + (metrics['requests_per_minute'] * 0.5)

            # 6. 권한 체크 횟수
            cursor.execute("""
                SELECT COUNT(*) FROM permission_cache
                WHERE created_at > NOW() - INTERVAL '1 minute'
            """)
            metrics['permission_checks_per_minute'] = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            # 알림 체크
            self.check_application_alerts(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Application metrics collection failed: {e}")
            return None

    def check_system_alerts(self, metrics):
        """시스템 알림 체크"""
        if not metrics:
            return

        alerts = []

        if metrics['cpu_percent'] > self.thresholds['cpu_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'SYSTEM',
                'message': f"CPU usage critical: {metrics['cpu_percent']}%"
            })
        elif metrics['cpu_percent'] > self.thresholds['cpu_warning']:
            alerts.append({
                'level': 'WARNING',
                'type': 'SYSTEM',
                'message': f"CPU usage high: {metrics['cpu_percent']}%"
            })

        if metrics['memory_percent'] > self.thresholds['memory_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'SYSTEM',
                'message': f"Memory usage critical: {metrics['memory_percent']}%"
            })
        elif metrics['memory_percent'] > self.thresholds['memory_warning']:
            alerts.append({
                'level': 'WARNING',
                'type': 'SYSTEM',
                'message': f"Memory usage high: {metrics['memory_percent']}%"
            })

        if metrics['disk_percent'] > self.thresholds['disk_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'SYSTEM',
                'message': f"Disk usage critical: {metrics['disk_percent']}%"
            })

        for alert in alerts:
            alert['timestamp'] = datetime.now().isoformat()
            self.metrics['alerts'].append(alert)
            logger.warning(f"Alert: {alert['message']}")

    def check_application_alerts(self, metrics):
        """애플리케이션 알림 체크"""
        if not metrics:
            return

        alerts = []

        if metrics.get('error_rate', 0) > self.thresholds['error_rate_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'APPLICATION',
                'message': f"Error rate critical: {metrics['error_rate']:.1f}%"
            })
        elif metrics.get('error_rate', 0) > self.thresholds['error_rate_warning']:
            alerts.append({
                'level': 'WARNING',
                'type': 'APPLICATION',
                'message': f"Error rate high: {metrics['error_rate']:.1f}%"
            })

        if metrics.get('avg_response_time', 0) > self.thresholds['response_time_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'PERFORMANCE',
                'message': f"Response time critical: {metrics['avg_response_time']:.0f}ms"
            })

        for alert in alerts:
            alert['timestamp'] = datetime.now().isoformat()
            self.metrics['alerts'].append(alert)
            logger.warning(f"Alert: {alert['message']}")

    def monitoring_loop(self):
        """모니터링 루프"""
        while self.running:
            try:
                # 시스템 메트릭
                system_metrics = self.collect_system_metrics()
                if system_metrics:
                    self.metrics['system'].append(system_metrics)

                # 데이터베이스 메트릭
                db_metrics = self.collect_database_metrics()
                if db_metrics:
                    self.metrics['database'].append(db_metrics)

                # 애플리케이션 메트릭
                app_metrics = self.collect_application_metrics()
                if app_metrics:
                    self.metrics['application'].append(app_metrics)

                # 10초 대기
                time.sleep(10)

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(10)

    def start_monitoring(self):
        """모니터링 시작"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return

        self.running = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Monitoring started")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoring stopped")

    def get_current_status(self):
        """현재 상태 요약"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'system': {},
            'database': {},
            'application': {},
            'health': 'UNKNOWN'
        }

        # 최신 메트릭 가져오기
        if self.metrics['system']:
            status['system'] = self.metrics['system'][-1]

        if self.metrics['database']:
            status['database'] = self.metrics['database'][-1]

        if self.metrics['application']:
            status['application'] = self.metrics['application'][-1]

        # 전체 상태 판단
        recent_alerts = [a for a in self.metrics['alerts']
                        if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(minutes=5)]

        critical_alerts = [a for a in recent_alerts if a['level'] == 'CRITICAL']
        warning_alerts = [a for a in recent_alerts if a['level'] == 'WARNING']

        if critical_alerts:
            status['health'] = 'CRITICAL'
        elif warning_alerts:
            status['health'] = 'WARNING'
        else:
            status['health'] = 'HEALTHY'

        status['alert_count'] = {
            'critical': len(critical_alerts),
            'warning': len(warning_alerts)
        }

        return status

    def get_metrics_history(self, metric_type='system', duration_minutes=60):
        """메트릭 히스토리 조회"""
        if metric_type not in self.metrics:
            return []

        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)

        return [m for m in self.metrics[metric_type]
                if datetime.fromisoformat(m['timestamp']) > cutoff_time]

    def generate_health_report(self):
        """상태 리포트 생성"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'status': self.get_current_status(),
            'metrics_summary': {},
            'alerts_summary': {},
            'recommendations': []
        }

        # 메트릭 요약
        for metric_type in ['system', 'database', 'application']:
            if self.metrics[metric_type]:
                recent_metrics = list(self.metrics[metric_type])[-6:]  # 최근 1분
                if recent_metrics:
                    report['metrics_summary'][metric_type] = {
                        'samples': len(recent_metrics),
                        'latest': recent_metrics[-1]
                    }

        # 알림 요약
        recent_alerts = list(self.metrics['alerts'])[-20:]  # 최근 20개
        if recent_alerts:
            report['alerts_summary'] = {
                'total': len(recent_alerts),
                'critical': sum(1 for a in recent_alerts if a['level'] == 'CRITICAL'),
                'warning': sum(1 for a in recent_alerts if a['level'] == 'WARNING'),
                'recent': recent_alerts[-5:]  # 최근 5개
            }

        # 권장사항
        if report['status']['health'] == 'CRITICAL':
            report['recommendations'].append("Immediate attention required - system in critical state")
            report['recommendations'].append("Check recent alerts for specific issues")
        elif report['status']['health'] == 'WARNING':
            report['recommendations'].append("Monitor system closely - warning thresholds exceeded")

        return report


# Flask 라우트
monitor = MonitoringSystem()

@app.route('/api/monitoring/status')
def get_status():
    """현재 상태 API"""
    return jsonify(monitor.get_current_status())

@app.route('/api/monitoring/metrics/<metric_type>')
def get_metrics(metric_type):
    """메트릭 히스토리 API"""
    duration = request.args.get('duration', 60, type=int)
    metrics = monitor.get_metrics_history(metric_type, duration)
    return jsonify(metrics)

@app.route('/api/monitoring/alerts')
def get_alerts():
    """알림 목록 API"""
    alerts = list(monitor.metrics['alerts'])[-50:]  # 최근 50개
    return jsonify(alerts)

@app.route('/api/monitoring/report')
def get_health_report():
    """상태 리포트 API"""
    return jsonify(monitor.generate_health_report())

@app.route('/monitoring')
def monitoring_dashboard():
    """모니터링 대시보드 페이지"""
    return render_template('monitoring_dashboard.html')


def create_monitoring_cli():
    """CLI 모드 실행"""
    monitor = MonitoringSystem()
    monitor.start_monitoring()

    print("=" * 70)
    print("Integrated Monitoring System - Day 4")
    print("=" * 70)

    try:
        while True:
            time.sleep(30)  # 30초마다 상태 출력

            status = monitor.get_current_status()
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] System Status: {status['health']}")

            if status.get('system'):
                print(f"  CPU: {status['system'].get('cpu_percent', 0):.1f}%")
                print(f"  Memory: {status['system'].get('memory_percent', 0):.1f}%")
                print(f"  Disk: {status['system'].get('disk_percent', 0):.1f}%")

            if status.get('database'):
                print(f"  DB Connections: {status['database'].get('connection_count', 0)}")
                print(f"  Cache Hit Ratio: {status['database'].get('cache_hit_ratio', 0):.1f}%")

            if status.get('application'):
                print(f"  Requests/min: {status['application'].get('requests_per_minute', 0)}")
                print(f"  Error Rate: {status['application'].get('error_rate', 0):.1f}%")
                print(f"  Active Users: {status['application'].get('active_users', 0)}")

            if status.get('alert_count'):
                if status['alert_count']['critical'] > 0:
                    print(f"  CRITICAL ALERTS: {status['alert_count']['critical']}")
                if status['alert_count']['warning'] > 0:
                    print(f"  Warning Alerts: {status['alert_count']['warning']}")

    except KeyboardInterrupt:
        print("\nShutting down monitoring...")
        monitor.stop_monitoring()
        print("Monitoring stopped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--web':
        # Web 서버 모드
        monitor.start_monitoring()
        app.run(host='0.0.0.0', port=5001, debug=False)
    else:
        # CLI 모드
        create_monitoring_cli()