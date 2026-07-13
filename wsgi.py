#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSGI Entry Point for Production Deployment
Flask Portal with PostgreSQL Backend
"""
import os
import sys

# Set production environment
os.environ['APP_ENV'] = 'prod'
os.environ['FLASK_ENV'] = 'production'

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Import Flask app
    from app import app
    
    # Production optimizations
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
    
    # Disable debug mode in production
    app.debug = False
    app.testing = False
    
    if __name__ == "__main__":
        print("🚀 Flask Portal - Production WSGI Server")
        print("📊 Backend: PostgreSQL")
        print("⚡ Server: Waitress")
        print("🔗 URL: http://127.0.0.1:5050")
        
except ImportError as e:
    print(f"❌ Failed to import Flask app: {e}")
    sys.exit(1)