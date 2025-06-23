from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import time
import base64
import os
import csv
import io
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

DB_FILE = "barcode_data.db"
TELEGRAM_DB_FILE = "telegram_tracker.db"
IMAGES_DIR = "static/images"

# إنشاء مجلد الصور إذا لم يكن موجوداً
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)
    print(f"📁 تم إنشاء مجلد الصور: {IMAGES_DIR}")

# إنشاء قاعدة البيانات من الصفر
def init_db():
    """إنشاء قاعدة البيانات والجداول إذا لم تكن موجودة"""
    try:
        print("🗄️ تهيئة قاعدة البيانات...")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # تفعيل الـ Foreign Keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # إنشاء جدول الباركودات الرئيسي (للباركودات الفريدة)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                first_scan_timestamp INTEGER NOT NULL,
                last_scan_timestamp INTEGER NOT NULL,
                scan_count INTEGER DEFAULT 1,
                barcode_type TEXT DEFAULT 'unknown',
                data_type TEXT DEFAULT 'mixed',
                length INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # إنشاء جدول تاريخ جميع عمليات المسح (حتى المكررة)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                barcode_type TEXT DEFAULT 'unknown',
                data_type TEXT DEFAULT 'mixed',
                length INTEGER DEFAULT 0,
                is_duplicate BOOLEAN DEFAULT 0,
                last_scan_before INTEGER DEFAULT NULL,
                scan_number INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # إنشاء جدول الإطارات الفاشلة
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_data TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                error_reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # إنشاء جدول إحصائيات المسح
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date DATE DEFAULT CURRENT_DATE,
                total_scans INTEGER DEFAULT 0,
                successful_scans INTEGER DEFAULT 0,
                failed_scans INTEGER DEFAULT 0,
                duplicate_scans INTEGER DEFAULT 0,
                unique_barcodes INTEGER DEFAULT 0,
                qr_codes INTEGER DEFAULT 0,
                regular_barcodes INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scan_date)
            )
            """)
            
            # ==================== جداول التليجرام ====================
            
            # جدول رسائل التليجرام
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                message_id TEXT,
                chat_id TEXT,
                caption TEXT,
                image_size INTEGER,
                file_name TEXT,
                retry_count INTEGER DEFAULT 0,
                response_time INTEGER,
                error_code TEXT,
                error_message TEXT,
                data_type TEXT DEFAULT 'mixed',
                bot_token TEXT,
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT
            )
            """)
            
            # جدول إحصائيات التليجرام اليومية
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT CURRENT_DATE,
                total_messages INTEGER DEFAULT 0,
                success_messages INTEGER DEFAULT 0,
                failed_messages INTEGER DEFAULT 0,
                pending_messages INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0,
                total_image_size INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
            """)
            
            # جدول أخطاء التليجرام الشائعة
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_code TEXT,
                error_message TEXT,
                error_count INTEGER DEFAULT 1,
                first_occurrence DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_occurrence DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(error_code, error_message)
            )
            """)
            
            # إنشاء فهارس لتحسين الأداء
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_barcode ON barcodes(barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON barcodes(last_scan_timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_count ON barcodes(scan_count)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_barcode ON scan_history(barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_timestamp ON scan_history(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_date ON scan_stats(scan_date)")
            
            # فهارس التليجرام
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_status ON telegram_messages(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_timestamp ON telegram_messages(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_barcode ON telegram_messages(barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_date ON telegram_daily_stats(date)")
            
            conn.commit()
            print("✅ تم إنشاء قاعدة البيانات والجداول بنجاح")
            
    except Exception as e:
        print(f"❌ خطأ في إنشاء قاعدة البيانات: {str(e)}")
        raise

# ==================== دوال التليجرام ====================

def log_telegram_message(barcode, status='pending', **kwargs):
    """تسجيل رسالة تليجرام في قاعدة البيانات"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # البيانات الأساسية
            data = {
                'barcode': barcode,
                'status': status,
                'timestamp': int(time.time()),
                'message_id': kwargs.get('message_id'),
                'chat_id': kwargs.get('chat_id'),
                'caption': kwargs.get('caption'),
                'image_size': kwargs.get('image_size'),
                'file_name': kwargs.get('file_name'),
                'retry_count': kwargs.get('retry_count', 0),
                'response_time': kwargs.get('response_time'),
                'error_code': kwargs.get('error_code'),
                'error_message': kwargs.get('error_message'),
                'data_type': kwargs.get('data_type', 'mixed'),
                'bot_token': kwargs.get('bot_token')
            }
            
            # إدراج الرسالة
            cursor.execute("""
            INSERT INTO telegram_messages 
            (barcode, status, message_id, chat_id, caption, image_size, file_name,
             retry_count, response_time, error_code, error_message, data_type, 
             bot_token, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['barcode'], data['status'], data['message_id'], 
                data['chat_id'], data['caption'], data['image_size'],
                data['file_name'], data['retry_count'], data['response_time'],
                data['error_code'], data['error_message'], data['data_type'],
                data['bot_token'], data['timestamp']
            ))
            
            message_id = cursor.lastrowid
            
            # تحديث الإحصائيات اليومية
            update_telegram_daily_stats(cursor, status, data.get('response_time'), data.get('image_size'))
            
            # تسجيل الأخطاء إذا وجدت
            if status == 'failed' and data.get('error_code'):
                log_telegram_error(cursor, data['error_code'], data['error_message'])
            
            conn.commit()
            print(f"📝 تم تسجيل رسالة تليجرام: {barcode} - {status}")
            return message_id
            
    except Exception as e:
        print(f"❌ خطأ في تسجيل رسالة التليجرام: {str(e)}")
        return None

def update_telegram_daily_stats(cursor, status, response_time=None, image_size=None):
    """تحديث الإحصائيات اليومية للتليجرام"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # إنشاء سجل اليوم إذا لم يكن موجوداً
    cursor.execute("""
    INSERT OR IGNORE INTO telegram_daily_stats (date) VALUES (?)
    """, (today,))
    
    # تحديث العدادات
    if status == 'success':
        cursor.execute("""
        UPDATE telegram_daily_stats 
        SET success_messages = success_messages + 1,
            total_messages = total_messages + 1
        WHERE date = ?
        """, (today,))
    elif status == 'failed':
        cursor.execute("""
        UPDATE telegram_daily_stats 
        SET failed_messages = failed_messages + 1,
            total_messages = total_messages + 1
        WHERE date = ?
        """, (today,))
    elif status == 'pending':
        cursor.execute("""
        UPDATE telegram_daily_stats 
        SET pending_messages = pending_messages + 1,
            total_messages = total_messages + 1
        WHERE date = ?
        """, (today,))
    
    # تحديث متوسط وقت الاستجابة
    if response_time:
        cursor.execute("""
        UPDATE telegram_daily_stats 
        SET avg_response_time = (
            SELECT AVG(response_time) 
            FROM telegram_messages 
            WHERE date(datetime(timestamp, 'unixepoch')) = ? 
            AND response_time IS NOT NULL
        )
        WHERE date = ?
        """, (today, today))
    
    # تحديث إجمالي حجم الصور
    if image_size:
        cursor.execute("""
        UPDATE telegram_daily_stats 
        SET total_image_size = total_image_size + ?
        WHERE date = ?
        """, (image_size, today))

def log_telegram_error(cursor, error_code, error_message):
    """تسجيل أخطاء التليجرام"""
    cursor.execute("""
    INSERT OR REPLACE INTO telegram_errors 
    (error_code, error_message, error_count, first_occurrence, last_occurrence)
    VALUES (
        ?, ?, 
        COALESCE((SELECT error_count FROM telegram_errors WHERE error_code = ? AND error_message = ?), 0) + 1,
        COALESCE((SELECT first_occurrence FROM telegram_errors WHERE error_code = ? AND error_message = ?), CURRENT_TIMESTAMP),
        CURRENT_TIMESTAMP
    )
    """, (error_code, error_message, error_code, error_message, error_code, error_message))

# دوال مساعدة للتليجرام
def log_successful_telegram(barcode, message_id, chat_id, caption, image_size, response_time):
    """تسجيل رسالة تليجرام ناجحة"""
    return log_telegram_message(
        barcode=barcode,
        status='success',
        message_id=message_id,
        chat_id=chat_id,
        caption=caption,
        image_size=image_size,
        response_time=response_time
    )

def log_failed_telegram(barcode, error_code, error_message, retry_count=0, response_time=None):
    """تسجيل رسالة تليجرام فاشلة"""
    return log_telegram_message(
        barcode=barcode,
        status='failed',
        error_code=error_code,
        error_message=error_message,
        retry_count=retry_count,
        response_time=response_time
    )

# ==================== Routes الأصلية ====================

def reset_database():
    """مسح جميع البيانات وإعادة إنشاء الجداول"""
    try:
        print("🔄 إعادة تعيين قاعدة البيانات...")
        
        # حذف ملف قاعدة البيانات إذا كان موجوداً
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
            print("🗑️ تم حذف قاعدة البيانات القديمة")
        
        # إنشاء قاعدة البيانات من جديد
        init_db()
        print("✅ تم إعادة إنشاء قاعدة البيانات بنجاح")
        
    except Exception as e:
        print(f"❌ خطأ في إعادة تعيين قاعدة البيانات: {str(e)}")
        raise

def get_db_info():
    """الحصول على معلومات قاعدة البيانات"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # عدد الباركودات
            cursor.execute("SELECT COUNT(*) FROM barcodes")
            total_barcodes = cursor.fetchone()[0]
            
            # عدد الإطارات الفاشلة
            cursor.execute("SELECT COUNT(*) FROM failed_frames")
            failed_frames = cursor.fetchone()[0]
            
            # إحصائيات اليوم
            today = time.strftime('%Y-%m-%d')
            cursor.execute("SELECT * FROM scan_stats WHERE scan_date = ?", (today,))
            today_stats = cursor.fetchone()
            
            return {
                "total_barcodes": total_barcodes,
                "failed_frames": failed_frames,
                "today_stats": today_stats,
                "database_size": os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
            }
            
    except Exception as e:
        print(f"❌ خطأ في الحصول على معلومات قاعدة البيانات: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_barcode', methods=['POST'])
def add_barcode():
    try:
        data = request.json
        barcode = data.get("barcode")
        
        if not barcode:
            return jsonify({"error": "Barcode is required"}), 400

        # تنظيف البيانات
        barcode = barcode.strip()
        timestamp = int(time.time())
        
        # تحديد نوع البيانات
        is_numeric = barcode.isdigit()
        data_type = "numeric" if is_numeric else "mixed"
        barcode_length = len(barcode)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # التحقق من وجود الباركود من قبل
            cursor.execute("""
            SELECT id, first_scan_timestamp, last_scan_timestamp, scan_count 
            FROM barcodes WHERE barcode = ?
            """, (barcode,))
            existing_barcode = cursor.fetchone()
            
            is_duplicate = existing_barcode is not None
            last_scan_before = None
            scan_number = 1
            
            if is_duplicate:
                # الباركود موجود من قبل - تحديث المعلومات
                last_scan_before = existing_barcode[2]  # آخر مرة مسح
                scan_number = existing_barcode[3] + 1   # عدد المرات + 1
                
                cursor.execute("""
                UPDATE barcodes 
                SET last_scan_timestamp = ?,
                    scan_count = scan_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE barcode = ?
                """, (timestamp, barcode))
                
                print(f"🔄 باركود مكرر: {barcode} (المرة رقم: {scan_number})")
            else:
                # باركود جديد
                cursor.execute("""
                INSERT INTO barcodes 
                (barcode, first_scan_timestamp, last_scan_timestamp, scan_count, data_type, length)
                VALUES (?, ?, ?, 1, ?, ?)
                """, (barcode, timestamp, timestamp, data_type, barcode_length))
                
                print(f"✅ باركود جديد: {barcode} (طول: {barcode_length}, نوع: {data_type})")
            
            # حفظ سجل المسح في جدول التاريخ
            cursor.execute("""
            INSERT INTO scan_history 
            (barcode, timestamp, barcode_type, data_type, length, is_duplicate, last_scan_before, scan_number)
            VALUES (?, ?, 'unknown', ?, ?, ?, ?, ?)
            """, (barcode, timestamp, data_type, barcode_length, is_duplicate, last_scan_before, scan_number))
            
            # تحديث إحصائيات اليوم
            today = time.strftime('%Y-%m-%d')
            
            if is_duplicate:
                # إحصائيات الباركود المكرر
                cursor.execute("""
                INSERT OR IGNORE INTO scan_stats (scan_date, total_scans, successful_scans, duplicate_scans)
                VALUES (?, 1, 1, 1)
                """, (today,))
                
                cursor.execute("""
                UPDATE scan_stats 
                SET total_scans = total_scans + 1,
                    successful_scans = successful_scans + 1,
                    duplicate_scans = duplicate_scans + 1
                WHERE scan_date = ?
                """, (today,))
            else:
                # إحصائيات الباركود الجديد
                cursor.execute("""
                INSERT OR IGNORE INTO scan_stats (scan_date, total_scans, successful_scans, unique_barcodes)
                VALUES (?, 1, 1, 1)
                """, (today,))
                
                cursor.execute("""
                UPDATE scan_stats 
                SET total_scans = total_scans + 1,
                    successful_scans = successful_scans + 1,
                    unique_barcodes = unique_barcodes + 1
                WHERE scan_date = ?
                """, (today,))
            
            conn.commit()
            
        # إعداد الاستجابة
        response = {
            "message": "Barcode processed successfully", 
            "barcode": barcode,
            "length": barcode_length,
            "type": data_type,
            "is_duplicate": is_duplicate,
            "scan_number": scan_number
        }
        
        if is_duplicate:
            # إضافة معلومات عن آخر مسح
            import datetime
            last_scan_datetime = datetime.datetime.fromtimestamp(last_scan_before)
            time_difference = timestamp - last_scan_before
            
            # تحويل الفرق الزمني إلى نص مفهوم
            if time_difference < 60:
                time_ago = f"منذ {time_difference} ثانية"
            elif time_difference < 3600:
                minutes = time_difference // 60
                time_ago = f"منذ {minutes} دقيقة"
            elif time_difference < 86400:
                hours = time_difference // 3600
                time_ago = f"منذ {hours} ساعة"
            else:
                days = time_difference // 86400
                time_ago = f"منذ {days} يوم"
            
            response.update({
                "last_scan_timestamp": last_scan_before,
                "last_scan_datetime": last_scan_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "time_ago": time_ago,
                "total_scans": scan_number
            })
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ خطأ في حفظ الباركود: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_barcodes', methods=['GET'])
def get_barcodes():
    try:
        limit = request.args.get('limit', 10, type=int)
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT barcode, first_scan_timestamp, last_scan_timestamp, data_type, length FROM barcodes
            ORDER BY last_scan_timestamp DESC LIMIT ?
            """, (limit,))
            data = cursor.fetchall()
            
        print(f"📊 تم استرجاع {len(data)} باركود من قاعدة البيانات")
        return jsonify(data), 200
        
    except Exception as e:
        print(f"❌ خطأ في استرجاع الباركودات: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/save_failed_frame', methods=['POST'])
def save_failed_frame():
    try:
        data = request.json
        image_data = data.get("image")
        error_reason = data.get("reason", "Unknown error")
        
        if not image_data:
            return jsonify({"error": "Image data is required"}), 400

        timestamp = int(time.time())
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO failed_frames (image_data, timestamp, error_reason)
            VALUES (?, ?, ?)
            """, (image_data, timestamp, error_reason))
            
            # تحديث إحصائيات الفشل
            today = time.strftime('%Y-%m-%d')
            cursor.execute("""
            INSERT OR IGNORE INTO scan_stats (scan_date, failed_scans)
            VALUES (?, 1)
            """, (today,))
            
            cursor.execute("""
            UPDATE scan_stats 
            SET failed_scans = failed_scans + 1
            WHERE scan_date = ?
            """, (today,))
            
            conn.commit()
            
        return jsonify({"message": "Failed frame saved"}), 200
        
    except Exception as e:
        print(f"❌ خطأ في حفظ الإطار الفاشل: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        db_info = get_db_info()
        if not db_info:
            return jsonify({"error": "Unable to get database info"}), 500
            
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # إجمالي الباركودات
            total_barcodes = db_info["total_barcodes"]
            
            # الباركودات اليوم
            today_start = int(time.time()) - (24 * 60 * 60)
            cursor.execute("SELECT COUNT(*) FROM barcodes WHERE last_scan_timestamp >= ?", (today_start,))
            today_barcodes = cursor.fetchone()[0]
            
            # آخر باركود
            cursor.execute("SELECT barcode, last_scan_timestamp FROM barcodes ORDER BY last_scan_timestamp DESC LIMIT 1")
            last_barcode = cursor.fetchone()
            
            # إحصائيات الأنواع
            cursor.execute("SELECT data_type, COUNT(*) FROM barcodes GROUP BY data_type")
            type_stats = dict(cursor.fetchall())
            
        stats = {
            "total": total_barcodes,
            "today": today_barcodes,
            "last_barcode": last_barcode[0] if last_barcode else None,
            "last_time": last_barcode[1] if last_barcode else None,
            "failed_frames": db_info["failed_frames"],
            "database_size_kb": round(db_info["database_size"] / 1024, 2),
            "type_breakdown": type_stats,
            "today_stats": db_info["today_stats"]
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        print(f"❌ خطأ في استرجاع الإحصائيات: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/reset_database', methods=['POST'])
def reset_db_endpoint():
    """إعادة تعيين قاعدة البيانات (مسح جميع البيانات)"""
    try:
        reset_database()
        return jsonify({"message": "Database reset successfully"}), 200
    except Exception as e:
        print(f"❌ خطأ في إعادة تعيين قاعدة البيانات: {str(e)}")
        return jsonify({"error": "Failed to reset database"}), 500

@app.route('/barcode_history/<barcode>', methods=['GET'])
def get_barcode_history(barcode):
    """الحصول على تاريخ مسح باركود معين"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # معلومات الباركود الأساسية
            cursor.execute("""
            SELECT id, first_scan_timestamp, last_scan_timestamp, scan_count, data_type, length
            FROM barcodes WHERE barcode = ?
            """, (barcode,))
            barcode_info = cursor.fetchone()
            
            if not barcode_info:
                return jsonify({"error": "Barcode not found"}), 404
            
            # تاريخ جميع عمليات المسح
            cursor.execute("""
            SELECT timestamp, is_duplicate, last_scan_before, scan_number, created_at
            FROM scan_history 
            WHERE barcode = ?
            ORDER BY timestamp DESC
            """, (barcode,))
            scan_history = cursor.fetchall()
            
        import datetime
        
        # تحويل التواريخ إلى تنسيق مقروء
        history_formatted = []
        for scan in scan_history:
            scan_datetime = datetime.datetime.fromtimestamp(scan[0])
            history_formatted.append({
                "timestamp": scan[0],
                "datetime": scan_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "is_duplicate": bool(scan[1]),
                "last_scan_before": scan[2],
                "scan_number": scan[3],
                "created_at": scan[4]
            })
        
        first_scan = datetime.datetime.fromtimestamp(barcode_info[1])
        last_scan = datetime.datetime.fromtimestamp(barcode_info[2])
        
        result = {
            "barcode": barcode,
            "first_scan": {
                "timestamp": barcode_info[1],
                "datetime": first_scan.strftime('%Y-%m-%d %H:%M:%S')
            },
            "last_scan": {
                "timestamp": barcode_info[2],
                "datetime": last_scan.strftime('%Y-%m-%d %H:%M:%S')
            },
            "total_scans": barcode_info[3],
            "data_type": barcode_info[4],
            "length": barcode_info[5],
            "scan_history": history_formatted
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"❌ خطأ في الحصول على تاريخ الباركود: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/duplicate_barcodes', methods=['GET'])
def get_duplicate_barcodes():
    """الحصول على قائمة الباركودات المكررة"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # الباركودات التي تم مسحها أكثر من مرة
            cursor.execute("""
            SELECT barcode, first_scan_timestamp, last_scan_timestamp, scan_count, data_type, length
            FROM barcodes 
            WHERE scan_count > 1
            ORDER BY scan_count DESC, last_scan_timestamp DESC
            LIMIT ?
            """, (limit,))
            duplicates = cursor.fetchall()
            
        import datetime
        
        result = []
        for barcode_data in duplicates:
            first_scan = datetime.datetime.fromtimestamp(barcode_data[1])
            last_scan = datetime.datetime.fromtimestamp(barcode_data[2])
            
            result.append({
                "barcode": barcode_data[0],
                "first_scan": {
                    "timestamp": barcode_data[1],
                    "datetime": first_scan.strftime('%Y-%m-%d %H:%M:%S')
                },
                "last_scan": {
                    "timestamp": barcode_data[2],
                    "datetime": last_scan.strftime('%Y-%m-%d %H:%M:%S')
                },
                "scan_count": barcode_data[3],
                "data_type": barcode_data[4],
                "length": barcode_data[5]
            })
        
        return jsonify({
            "duplicate_barcodes": result,
            "total_duplicates": len(result)
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في الحصول على الباركودات المكررة: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/recent_scans', methods=['GET'])
def get_recent_scans():
    """الحصول على آخر عمليات المسح (تشمل المكررة)"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT barcode, timestamp, is_duplicate, last_scan_before, scan_number, data_type, length
            FROM scan_history 
            ORDER BY timestamp DESC
            LIMIT ?
            """, (limit,))
            recent_scans = cursor.fetchall()
            
        import datetime
        
        result = []
        for scan in recent_scans:
            scan_datetime = datetime.datetime.fromtimestamp(scan[1])
            
            scan_info = {
                "barcode": scan[0],
                "timestamp": scan[1],
                "datetime": scan_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "is_duplicate": bool(scan[2]),
                "scan_number": scan[4],
                "data_type": scan[5],
                "length": scan[6]
            }
            
            if scan[2] and scan[3]:  # إذا كان مكرر وله مسح سابق
                last_scan_datetime = datetime.datetime.fromtimestamp(scan[3])
                time_difference = scan[1] - scan[3]
                
                if time_difference < 60:
                    time_ago = f"{time_difference} ثانية"
                elif time_difference < 3600:
                    minutes = time_difference // 60
                    time_ago = f"{minutes} دقيقة"
                elif time_difference < 86400:
                    hours = time_difference // 3600
                    time_ago = f"{hours} ساعة"
                else:
                    days = time_difference // 86400
                    time_ago = f"{days} يوم"
                
                scan_info["last_scan_before"] = {
                    "timestamp": scan[3],
                    "datetime": last_scan_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    "time_ago": time_ago
                }
            
            result.append(scan_info)
        
        return jsonify({
            "recent_scans": result,
            "total_scans": len(result)
        }), 200
        
    except Exception as e:
        print(f"❌ خطأ في الحصول على آخر عمليات المسح: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/delete_barcode/<barcode>', methods=['DELETE'])
def delete_barcode(barcode):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # حذف من جدول الباركودات الرئيسي
            cursor.execute("DELETE FROM barcodes WHERE barcode = ?", (barcode,))
            barcode_deleted = cursor.rowcount > 0
            
            # حذف من تاريخ المسح
            cursor.execute("DELETE FROM scan_history WHERE barcode = ?", (barcode,))
            history_deleted = cursor.rowcount
            
            if barcode_deleted:
                conn.commit()
                print(f"🗑️ تم حذف الباركود: {barcode} (مع {history_deleted} سجل مسح)")
                return jsonify({
                    "message": "Barcode deleted successfully",
                    "history_records_deleted": history_deleted
                }), 200
            else:
                return jsonify({"error": "Barcode not found"}), 404
                
    except Exception as e:
        print(f"❌ خطأ في حذف الباركود: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/database_info', methods=['GET'])
def database_info():
    """الحصول على معلومات مفصلة عن قاعدة البيانات"""
    try:
        db_info = get_db_info()
        if not db_info:
            return jsonify({"error": "Unable to get database info"}), 500
            
        return jsonify(db_info), 200
        
    except Exception as e:
        print(f"❌ خطأ في الحصول على معلومات قاعدة البيانات: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# معالج الأخطاء
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def init_app():
    """تهيئة التطبيق وقاعدة البيانات"""
    try:
        # التحقق من وجود المجلد
        db_dir = os.path.dirname(DB_FILE)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print("📁 تم إنشاء مجلد قاعدة البيانات")

        # التحقق من وجود قاعدة البيانات
        if not os.path.exists(DB_FILE):
            print("📂 قاعدة البيانات غير موجودة، سيتم إنشاؤها...")
            init_db()
        else:
            print("📂 قاعدة البيانات موجودة، التحقق من الجداول...")
            init_db()  # للتأكد من وجود جميع الجداول
        
        # عرض معلومات قاعدة البيانات
        db_info = get_db_info()
        if db_info:
            print(f"📊 إجمالي الباركودات: {db_info['total_barcodes']}")
            print(f"📊 حجم قاعدة البيانات: {round(db_info['database_size']/1024, 2)} KB")
            
        return True
    except Exception as e:
        print(f"❌ خطأ في تهيئة التطبيق: {str(e)}")
        return False

# ==================== Routes التليجرام ====================

@app.route('/telegram-monitor')
def telegram_monitor():
    """صفحة مراقبة التليجرام"""
    return render_template('telegram_monitor.html')

@app.route('/api/telegram/stats')
def get_telegram_stats():
    """الحصول على إحصائيات التليجرام"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as success,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                AVG(response_time) as avg_response_time,
                SUM(image_size) as total_image_size
            FROM telegram_messages
            """)
            
            stats = cursor.fetchone()
            
            result = {
                'total': stats[0] or 0,
                'success': stats[1] or 0,
                'failed': stats[2] or 0,
                'pending': stats[3] or 0,
                'avg_response_time': round(stats[4] or 0, 2),
                'total_image_size': stats[5] or 0
            }
            
            return jsonify(result)
            
    except Exception as e:
        print(f"❌ خطأ في استرجاع إحصائيات التليجرام: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/messages')
def get_telegram_messages():
    """الحصول على رسائل التليجرام مع المرشحات"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            where_conditions = []
            params = []
            
            if request.args.get('status'):
                where_conditions.append("status = ?")
                params.append(request.args.get('status'))
            
            if request.args.get('date_from'):
                date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
                where_conditions.append("timestamp >= ?")
                params.append(int(date_from.timestamp()))
            
            if request.args.get('date_to'):
                date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
                date_to = date_to.replace(hour=23, minute=59, second=59)
                where_conditions.append("timestamp <= ?")
                params.append(int(date_to.timestamp()))
            
            if request.args.get('barcode'):
                where_conditions.append("barcode LIKE ?")
                params.append(f"%{request.args.get('barcode')}%")
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            cursor.execute(f"""
            SELECT * FROM telegram_messages
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT 100
            """, params)
            
            columns = [description[0] for description in cursor.description]
            messages = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return jsonify(messages)
            
    except Exception as e:
        print(f"❌ خطأ في استرجاع رسائل التليجرام: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/test')
def test_telegram_connection():
    """اختبار اتصال التليجرام"""
    try:
        import requests
        
        bot_token = "7668051564:AAFdFqSd0CKrlSOyPKyFwf-xHi791lcsC_U"
        
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            return jsonify({
                'success': True,
                'bot_info': bot_info.get('result', {}),
                'message': 'اتصال ناجح بالتليجرام'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'خطأ في الاتصال: {response.status_code}',
                'message': 'فشل في الاتصال بالتليجرام'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'خطأ في اختبار الاتصال'
        })

@app.route('/api/telegram/log', methods=['POST'])
def log_telegram_api():
    """API لتسجيل رسائل التليجرام من JavaScript"""
    try:
        data = request.json
        
        barcode = data.get('barcode')
        status = data.get('status', 'pending')
        
        if not barcode:
            return jsonify({'error': 'الباركود مطلوب'}), 400
        
        message_id = log_telegram_message(
            barcode=barcode,
            status=status,
            message_id=data.get('message_id'),
            chat_id=data.get('chat_id'),
            caption=data.get('caption'),
            image_size=data.get('image_size'),
            file_name=data.get('file_name'),
            retry_count=data.get('retry_count', 0),
            response_time=data.get('response_time'),
            error_code=data.get('error_code'),
            error_message=data.get('error_message'),
            data_type=data.get('data_type', 'mixed'),
            image_path=data.get('image_path')
        )
        
        return jsonify({
            'success': True,
            'message_id': message_id,
            'message': 'تم تسجيل رسالة التليجرام'
        })
        
    except Exception as e:
        print(f"❌ خطأ في API تسجيل التليجرام: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/upload-image', methods=['POST'])
def upload_barcode_image():
    """رفع صورة باركود جديدة"""
    try:
        data = request.json
        barcode = data.get('barcode')
        image_data = data.get('image_data')
        
        if not barcode or not image_data:
            return jsonify({'error': 'الباركود وبيانات الصورة مطلوبان'}), 400
        
        filename = save_barcode_image(barcode, image_data)
        if filename:
            return jsonify({
                'success': True,
                'filename': filename,
                'url': f'/images/{filename}',
                'message': 'تم حفظ الصورة بنجاح'
            })
        else:
            return jsonify({'error': 'فشل في حفظ الصورة'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/resend/<int:message_id>', methods=['POST'])
def resend_telegram_message(message_id):
    """إعادة إرسال رسالة تليجرام"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT barcode, caption, image_path, chat_id
            FROM telegram_messages 
            WHERE id = ?
            """, (message_id,))
            
            message = cursor.fetchone()
            if not message:
                return jsonify({'error': 'الرسالة غير موجودة'}), 404
            
            barcode, caption, image_path, chat_id = message
            
            if not image_path or not os.path.exists(os.path.join(IMAGES_DIR, image_path)):
                return jsonify({'error': 'صورة الرسالة غير موجودة'}), 404
            
            new_message_id = log_telegram_message(
                barcode=barcode,
                status='pending',
                caption=f"[إعادة إرسال] {caption or ''}",
                chat_id=chat_id or '-1002439956600',
                retry_count=1,
                image_path=image_path
            )
            
            return jsonify({
                'success': True,
                'message': 'تم تسجيل طلب إعادة الإرسال',
                'new_message_id': new_message_id,
                'barcode': barcode,
                'image_path': image_path
            })
            
    except Exception as e:
        print(f"❌ خطأ في إعادة إرسال الرسالة: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/images/<filename>')
def serve_image(filename):
    """عرض صورة باركود"""
    try:
        filepath = os.path.join(IMAGES_DIR, filename)
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/jpeg')
        else:
            return jsonify({'error': 'صورة غير موجودة'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detailed-stats', methods=['GET'])
def get_detailed_stats():
    """الحصول على إحصائيات مفصلة شاملة"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM barcodes")
            total_barcodes = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(scan_count) FROM barcodes")
            total_scans = cursor.fetchone()[0] or 0
            
            cursor.execute("""
            SELECT barcode, scan_count, data_type 
            FROM barcodes 
            ORDER BY scan_count DESC 
            LIMIT 10
            """)
            top_scanned = cursor.fetchall()
            
            cursor.execute("""
            SELECT data_type, COUNT(*), SUM(scan_count) 
            FROM barcodes 
            GROUP BY data_type
            """)
            type_stats = cursor.fetchall()
            
            daily_stats = []
            for i in range(7):
                date_start = int((datetime.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
                date_end = date_start + 86400
                
                cursor.execute("""
                SELECT COUNT(*) 
                FROM barcodes 
                WHERE first_scan_timestamp >= ? AND first_scan_timestamp < ?
                """, (date_start, date_end))
                
                count = cursor.fetchone()[0]
                date_str = datetime.fromtimestamp(date_start).strftime('%Y-%m-%d')
                daily_stats.append({'date': date_str, 'count': count})
            
            detailed_stats = {
                'summary': {
                    'total_barcodes': total_barcodes,
                    'total_scans': total_scans,
                    'avg_scans_per_barcode': round(total_scans / max(total_barcodes, 1), 2)
                },
                'top_scanned': [
                    {
                        'barcode': row[0],
                        'scan_count': row[1],
                        'data_type': row[2]
                    } for row in top_scanned
                ],
                'type_breakdown': [
                    {
                        'type': row[0] or 'غير محدد',
                        'unique_count': row[1],
                        'total_scans': row[2]
                    } for row in type_stats
                ],
                'daily_stats': list(reversed(daily_stats))
            }
            
            return jsonify(detailed_stats)
            
    except Exception as e:
        print(f"❌ خطأ في الإحصائيات المفصلة: {str(e)}")
        return jsonify({'error': str(e)}), 500

# تهيئة التطبيق عند استيراده
init_app()

if __name__ == '__main__':
    print("🚀 بدء تشغيل خادم ماسح الباركود...")
    print("🌐 الرابط: http://localhost:5000")
    print("🤖 مراقب التليجرام: http://localhost:5000/telegram-monitor")
    app.run(debug=True, host='0.0.0.0')
