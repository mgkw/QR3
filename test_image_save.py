#!/usr/bin/env python3
import requests
import json
import base64
import os

def test_image_save():
    """اختبار حفظ الصور"""
    
    # إنشاء صورة تجريبية بسيطة (1x1 pixel أسود)
    test_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAHAfQ4zOQAAAABJRU5ErkJggg=="
    
    # بيانات الاختبار
    test_data = {
        "barcode": "TEST123",
        "image_data": f"data:image/png;base64,{test_image_data}"
    }
    
    try:
        print("🧪 اختبار حفظ الصورة...")
        
        # إرسال طلب لحفظ الصورة
        response = requests.post(
            'http://localhost:5000/api/telegram/upload-image',
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                filename = result.get('filename')
                print(f"✅ تم حفظ الصورة بنجاح: {filename}")
                
                # التحقق من وجود الملف
                filepath = os.path.join('static/images', filename)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    print(f"📁 الملف موجود - الحجم: {size} بايت")
                    return True
                else:
                    print("❌ الملف غير موجود على القرص")
                    return False
            else:
                print(f"❌ فشل في حفظ الصورة: {result.get('error', 'خطأ غير محدد')}")
                return False
        else:
            print(f"❌ خطأ HTTP: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ في الاختبار: {e}")
        return False

if __name__ == "__main__":
    # التحقق من أن مجلد الصور موجود
    images_dir = 'static/images'
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
        print(f"📁 تم إنشاء مجلد: {images_dir}")
    
    # تشغيل الاختبار
    result = test_image_save()
    
    if result:
        print("\n🎉 الاختبار نجح! الصور تحفظ بشكل صحيح")
    else:
        print("\n❌ الاختبار فشل! هناك مشكلة في حفظ الصور")
    
    # عرض محتويات مجلد الصور
    print(f"\n📂 محتويات مجلد {images_dir}:")
    try:
        files = os.listdir(images_dir)
        if files:
            for file in files:
                filepath = os.path.join(images_dir, file)
                size = os.path.getsize(filepath)
                print(f"  📄 {file} - {size} بايت")
        else:
            print("  (فارغ)")
    except Exception as e:
        print(f"  خطأ في قراءة المجلد: {e}") 