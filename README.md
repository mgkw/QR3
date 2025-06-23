# تأكيد طلبات سبونجي كروب

نظام متقدم لمسح وتتبع الباركودات مع إنتاج تقارير مفصلة ودعم إرسال الصور عبر التليجرام.

## المميزات

- 📱 مسح الباركودات بالكاميرا
- 📊 إحصائيات مفصلة ولوحة تحكم متقدمة
- 🤖 إرسال الصور للتليجرام تلقائياً
- 📈 تتبع الباركودات المكررة
- 💾 قاعدة بيانات SQLite محلية
- 📷 حفظ وعرض صور الباركودات
- 🔄 إعادة إرسال الرسائل الفاشلة
- 📋 تصدير البيانات إلى CSV

## التقنيات المستخدمة

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Database**: SQLite
- **Camera**: MediaDevices API
- **Barcode Detection**: QuaggaJS
- **UI Framework**: Bootstrap + Custom CSS

## التشغيل المحلي

```bash
# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل التطبيق
python app.py
```

الموقع سيعمل على: http://localhost:5000

## الرفع على Render.com

### الخطوات:

1. **إنشاء حساب على [Render.com](https://render.com)**

2. **ربط مستودع GitHub:**
   - اذهب إلى Dashboard
   - اختر "New +" → "Web Service"
   - اربط مستودع GitHub الخاص بك

3. **إعدادات النشر:**
   - **Name**: barcode-scanner
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free

4. **متغيرات البيئة:**
   ```
   FLASK_ENV=production
   PYTHONUNBUFFERED=true
   ```

5. **انقر على "Create Web Service"**

### الملفات المطلوبة للنشر:
- ✅ `requirements.txt` - المتطلبات
- ✅ `app.py` - التطبيق الرئيسي
- ✅ `Procfile` - أوامر التشغيل
- ✅ `render.yaml` - تكوين Render
- ✅ `templates/` - ملفات HTML
- ✅ `static/` - ملفات CSS/JS/الصور

## الاستخدام

### الصفحة الرئيسية
- `/` - واجهة مسح الباركودات

### مراقب التليجرام
- `/telegram-monitor` - مراقبة رسائل التليجرام

### APIs المتاحة
- `GET /api/telegram/stats` - إحصائيات التليجرام
- `GET /api/detailed-stats` - إحصائيات مفصلة
- `POST /api/telegram/log` - تسجيل رسائل التليجرام
- `GET /images/<filename>` - عرض الصور

## قاعدة البيانات

النظام يستخدم SQLite مع الجداول التالية:
- `barcodes` - الباركودات الفريدة
- `scan_history` - تاريخ جميع المسحات
- `telegram_messages` - رسائل التليجرام
- `scan_stats` - إحصائيات يومية

## المطور

تم تطوير هذا المشروع كنظام شامل لتتبع الباركودات مع دعم كامل للتليجرام والتقارير المتقدمة.

---

🚀 **جاهز للرفع على Render.com!** 
