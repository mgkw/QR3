console.log("duplicate image functions loaded"); 

// ==================== نظام الصور المكررة المحسن ====================

console.log("🚀 تحميل نظام الصور المكررة المحسن...");

// دالة جلب الصورة المحفوظة للباركود المكرر
async function fetchBarcodeImage(barcode) {
  try {
    console.log(`🔍 البحث عن صورة محفوظة للباركود: ${barcode}`);
    
    const response = await fetch(`/api/barcode-image/${encodeURIComponent(barcode)}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache'
      }
    });
    
    console.log(`📡 استجابة الخادم: ${response.status} ${response.statusText}`);
    
    if (response.ok) {
      const result = await response.json();
      console.log("📊 بيانات الاستجابة:", result);
      
      if (result.success) {
        console.log(`✅ تم العثور على صورة محفوظة: ${result.image_path}`);
        return result;
      } else {
        console.log(`ℹ️ لا توجد صورة محفوظة للباركود: ${barcode}`);
        return null;
      }
    } else {
      console.log(`⚠️ لم يتم العثور على صورة للباركود: ${barcode} (${response.status})`);
      return null;
    }
  } catch (error) {
    console.error(`❌ خطأ في جلب صورة الباركود ${barcode}:`, error);
    return null;
  }
}

// دالة عرض modal الصورة المكررة المحسنة 
async function showDuplicateBarcodeImage(barcode) {
  console.log("🚨 بدء عرض صورة الباركود المكرر:", barcode);
  
  // البحث عن عناصر Modal
  const modal = document.getElementById('duplicate-image-modal');
  const barcodeElement = document.getElementById('duplicate-barcode');
  const detailsElement = document.getElementById('duplicate-details');
  const imageContainer = document.getElementById('duplicate-image-container');
  
  console.log("🔍 فحص عناصر Modal:", {
    modal: !!modal,
    barcodeElement: !!barcodeElement, 
    detailsElement: !!detailsElement,
    imageContainer: !!imageContainer
  });
  
  // إنشاء Modal إذا لم يكن موجوداً
  if (!modal) {
    console.log("🔨 إنشاء Modal الصورة المكررة...");
    createDuplicateImageModal();
    // إعادة البحث عن العناصر
    const newModal = document.getElementById('duplicate-image-modal');
    const newBarcodeElement = document.getElementById('duplicate-barcode');
    const newDetailsElement = document.getElementById('duplicate-details');
    const newImageContainer = document.getElementById('duplicate-image-container');
    
    if (newModal && newBarcodeElement && newDetailsElement && newImageContainer) {
      return showDuplicateBarcodeImage(barcode); // إعادة استدعاء بعد الإنشاء
    } else {
      console.error("❌ فشل في إنشاء عناصر Modal");
      alert(`❌ خطأ: لا يمكن إنشاء نافذة عرض الصورة!`);
      return;
    }
  }
  
  if (!barcodeElement || !detailsElement || !imageContainer) {
    console.error("❌ بعض عناصر modal الصورة المكررة غير موجودة");
    alert(`❌ خطأ: عناصر Modal غير مكتملة!\nBarcode: ${!!barcodeElement}\nDetails: ${!!detailsElement}\nImage: ${!!imageContainer}`);
    return;
  }
  
  try {
    // إعداد معلومات الباركود
    barcodeElement.textContent = barcode;
    detailsElement.innerHTML = "🔍 جاري البحث عن الصورة المحفوظة...";
    
    // عرض loading مع تحسينات
    imageContainer.innerHTML = `
      <div class="loading" style="padding: 40px; text-align: center;">
        <div class="spinner" style="
          border: 4px solid rgba(255,255,255,0.1);
          border-radius: 50%;
          border-top: 4px solid #4ecdc4;
          width: 40px;
          height: 40px;
          animation: spin 1s linear infinite;
          margin: 0 auto 20px;
        "></div>
        <div style="margin-top: 15px; color: #4ecdc4; font-size: 1.1rem;">جاري تحميل الصورة المحفوظة...</div>
        <div style="font-size: 0.8rem; opacity: 0.7; margin-top: 10px;">الباركود: ${barcode}</div>
        <div style="font-size: 0.7rem; opacity: 0.5; margin-top: 5px;">الرجاء الانتظار...</div>
      </div>
    `;
    
    // عرض الـ modal أولاً
    modal.style.display = 'block';
    modal.style.opacity = '0';
    modal.style.transition = 'opacity 0.3s ease';
    setTimeout(() => modal.style.opacity = '1', 10);
    
    console.log("✅ تم عرض Modal بنجاح");
    
    // جلب الصورة مع timeout محسن
    console.log("📥 بدء جلب بيانات الصورة...");
    const imageData = await Promise.race([
      fetchBarcodeImage(barcode),
      new Promise((_, reject) => setTimeout(() => reject(new Error('انتهت مهلة الانتظار (10 ثوان)')), 10000))
    ]);
    
    console.log("📊 نتيجة جلب الصورة:", imageData);
    
    if (imageData && imageData.success) {
      console.log("✅ تم العثور على صورة، بدء العرض...");
      
      // عرض الصورة مع تفاصيل محسنة
      imageContainer.innerHTML = `
        <div style="margin-bottom: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem;">
            <div><strong>📅 آخر إرسال:</strong></div>
            <div style="color: #4ecdc4;">${imageData.created_datetime || imageData.created_at || 'غير محدد'}</div>
            
            <div><strong>📊 عدد المسحات:</strong></div>
            <div style="color: #00ff88;">${imageData.scan_count || 'غير محدد'} مرة</div>
            
            <div><strong>📱 حالة الإرسال:</strong></div>
            <div style="color: ${imageData.status === 'success' ? '#00ff88' : '#ff6b6b'};">
              ${imageData.status === 'success' ? '✅ تم الإرسال' : '❌ فشل الإرسال'}
            </div>
            
            <div><strong>📂 مسار الملف:</strong></div>
            <div style="color: #ffa726; font-size: 0.8rem; word-break: break-all;">${imageData.image_path || 'غير محدد'}</div>
          </div>
        </div>
        
        <div style="text-align: center;">
          <img id="duplicate-image-display" 
               src="${imageData.image_url}?t=${Date.now()}" 
               alt="صورة الباركود ${barcode}" 
               style="
                 max-width: 100%; 
                 max-height: 350px; 
                 border-radius: 10px;
                 box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                 border: 3px solid #ffa726;
                 transition: all 0.3s ease;
                 cursor: pointer;
               "
               onclick="this.style.maxHeight = this.style.maxHeight === '90vh' ? '350px' : '90vh'"
               onload="console.log('✅ تم تحميل الصورة بنجاح'); this.style.border = '3px solid #00ff88';"
               onerror="handleImageError(this, '${imageData.image_path}');">
          <div id="image-error-message" style="display: none; color: #ff6b6b; text-align: center; padding: 20px; background: rgba(255,107,107,0.1); border-radius: 10px; margin-top: 10px;">
            <div style="font-size: 2rem; margin-bottom: 10px;">❌</div>
            <div>فشل في تحميل الصورة</div>
            <div style="font-size: 0.8rem; opacity: 0.7; margin-top: 5px;">المسار: ${imageData.image_path}</div>
            <button onclick="retryImageLoad('${imageData.image_url}', '${barcode}')" 
                    style="margin-top: 10px; background: #4ecdc4; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer;">
              🔄 إعادة المحاولة
            </button>
          </div>
        </div>
      `;
      
      detailsElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
          <span style="font-size: 1.5rem;">🔄</span>
          <span>تم مسح هذا الباركود من قبل</span>
        </div>
        <div style="font-size: 0.9rem; opacity: 0.8; color: #4ecdc4;">
          ${imageData.scan_count ? `تم مسحه ${imageData.scan_count} مرة` : 'باركود مكرر'}
        </div>
      `;
      
    } else {
      console.log("ℹ️ لم يتم العثور على صورة محفوظة");
      
      // عرض رسالة عدم وجود صورة
      imageContainer.innerHTML = `
        <div style="text-align: center; padding: 40px; background: rgba(255,107,107,0.1); border-radius: 15px; border: 2px dashed #ff6b6b;">
          <div style="font-size: 4rem; margin-bottom: 20px; opacity: 0.7;">📷</div>
          <div style="font-size: 1.2rem; margin-bottom: 15px; color: #ff6b6b; font-weight: bold;">لا توجد صورة محفوظة</div>
          <div style="font-size: 0.9rem; opacity: 0.7; line-height: 1.5;">
            هذا الباركود تم مسحه من قبل، لكن لا توجد صورة محفوظة له في النظام.
            <br><br>
            <span style="color: #ffa726;">💡 نصيحة:</span> الصور تُحفظ تلقائياً مع كل باركود جديد يتم إرساله للتليجرام.
          </div>
          <button onclick="fetchBarcodeImage('${barcode}').then(data => showDuplicateBarcodeImage('${barcode}'))" 
                  style="margin-top: 20px; background: linear-gradient(135deg, #4ecdc4, #44a08d); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer;">
            🔄 البحث مرة أخرى
          </button>
        </div>
      `;
      
      detailsElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
          <span style="font-size: 1.5rem;">⚠️</span>
          <span>باركود مكرر بدون صورة محفوظة</span>
        </div>
        <div style="font-size: 0.9rem; opacity: 0.8; color: #ffa726;">
          تم المسح من قبل، لكن لا توجد صورة
        </div>
      `;
    }
    
    console.log("✅ تم عرض محتوى Modal بنجاح");
    
  } catch (error) {
    console.error("❌ خطأ في عرض صورة الباركود المكرر:", error);
    
    // عرض رسالة خطأ مفصلة
    imageContainer.innerHTML = `
      <div style="text-align: center; padding: 40px; background: rgba(255,107,107,0.1); border-radius: 15px; border: 2px solid #ff6b6b;">
        <div style="font-size: 3rem; margin-bottom: 15px;">⚠️</div>
        <div style="font-size: 1.2rem; margin-bottom: 10px; color: #ff6b6b;">خطأ في تحميل الصورة</div>
        <div style="font-size: 0.9rem; opacity: 0.7; margin-bottom: 15px; word-break: break-all;">${error.message}</div>
        <button onclick="showDuplicateBarcodeImage('${barcode}')" 
                style="background: linear-gradient(135deg, #4ecdc4, #44a08d); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer;">
          🔄 إعادة المحاولة
        </button>
      </div>
    `;
    
    detailsElement.innerHTML = `
      <div style="color: #ff6b6b;">
        ❌ حدث خطأ أثناء جلب بيانات الصورة
      </div>
    `;
  }
}

// دالة إنشاء Modal إذا لم يكن موجوداً
function createDuplicateImageModal() {
  console.log("🔨 إنشاء Modal الصورة المكررة...");
  
  const modal = document.createElement('div');
  modal.id = 'duplicate-image-modal';
  modal.style.cssText = `
    display: none;
    position: fixed;
    z-index: 10000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.8);
    backdrop-filter: blur(5px);
  `;
  
  modal.innerHTML = `
    <div style="
      background: linear-gradient(135deg, #2c3e50, #3498db);
      margin: 2% auto;
      padding: 20px;
      border-radius: 15px;
      width: 90%;
      max-width: 600px;
      max-height: 90vh;
      overflow-y: auto;
      position: relative;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    ">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h2 style="margin: 0; color: #fff; font-size: 1.5rem;">🔄 باركود مكرر</h2>
        <span class="duplicate-close" style="
          color: #ff6b6b;
          font-size: 2rem;
          font-weight: bold;
          cursor: pointer;
          line-height: 1;
          transition: all 0.3s ease;
        " onclick="document.getElementById('duplicate-image-modal').style.display='none'">&times;</span>
      </div>
      
      <div style="margin-bottom: 15px;">
        <strong style="color: #4ecdc4;">الباركود:</strong>
        <span id="duplicate-barcode" style="
          color: #fff;
          font-family: monospace;
          background: rgba(255,255,255,0.1);
          padding: 5px 10px;
          border-radius: 5px;
          margin-left: 10px;
        "></span>
      </div>
      
      <div id="duplicate-details" style="
        margin-bottom: 20px;
        color: #fff;
        opacity: 0.9;
      "></div>
      
      <div id="duplicate-image-container" style="
        min-height: 100px;
        border-radius: 10px;
        background: rgba(255,255,255,0.05);
        padding: 20px;
      "></div>
      
      <div style="text-align: center; margin-top: 20px;">
        <button id="close-duplicate-modal" style="
          background: linear-gradient(135deg, #ff6b6b, #ee5a24);
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 8px;
          cursor: pointer;
          font-size: 1rem;
          transition: all 0.3s ease;
        " onclick="document.getElementById('duplicate-image-modal').style.display='none'">
          ✖️ إغلاق
        </button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  console.log("✅ تم إنشاء Modal الصورة المكررة بنجاح");
}

// دالة معالجة خطأ تحميل الصورة
function handleImageError(imgElement, imagePath) {
  console.error("❌ فشل في تحميل الصورة:", imagePath);
  imgElement.style.display = 'none';
  const errorDiv = document.getElementById('image-error-message');
  if (errorDiv) {
    errorDiv.style.display = 'block';
  }
}

// دالة إعادة محاولة تحميل الصورة
function retryImageLoad(imageUrl, barcode) {
  console.log("🔄 إعادة محاولة تحميل الصورة...");
  const img = document.getElementById('duplicate-image-display');
  const errorDiv = document.getElementById('image-error-message');
  
  if (img && errorDiv) {
    errorDiv.style.display = 'none';
    img.style.display = 'block';
    img.src = `${imageUrl}?retry=${Date.now()}`;
  }
}

// إضافة CSS للرسوم المتحركة
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .duplicate-close:hover {
    color: #ff4757 !important;
    transform: scale(1.1);
  }
  
  #duplicate-image-display:hover {
    transform: scale(1.02);
    box-shadow: 0 6px 20px rgba(0,0,0,0.4);
  }
`;
document.head.appendChild(style);

console.log("✅ تم تحميل نظام الصور المكررة المحسن بنجاح!");

// التأكد من إنشاء Modal عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
  console.log("📋 فحص وجود Modal الصورة المكررة...");
  
  setTimeout(() => {
    const modal = document.getElementById('duplicate-image-modal');
    if (!modal) {
      console.log("🔨 Modal غير موجود، سيتم إنشاؤه...");
      createDuplicateImageModal();
    } else {
      console.log("✅ Modal الصورة المكررة موجود");
    }
  }, 1000);
}); 
