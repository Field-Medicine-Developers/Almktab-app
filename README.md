# برنامج المكتبة (Almktab) — أرشفة ويندوز

تطبيق سطح مكتب بـ **Python** لأرشفة وثائق مديرية الخدمات الصحية.

- نفس الـ API المستخدم في نظام الويب: `https://services-api.cmfsa-iq.com`
- بحث / عرض / تعديل / حذف ملفات الأرشيف
- إضافة أرشيف بمسح مباشر من السكنر (TWAIN) أو رفع ملفات من الجهاز

## المتطلبات

- ويندوز 10/11
- Python 3.11 أو أحدث
- تعريف TWAIN للسكنر (مثل Canon DR-C240)

## التثبيت والتشغيل عبر الواجهة (موصى به)

### على macOS
1. افتح مجلد المشروع في Finder.
2. انقر مرتين على **`تشغيل.command`**.
3. من النافذة:
   - **تنصيب المتطلبات**
   - ثم **تشغيل البرنامج**
   - أو مباشرة **تنصيب ثم تشغيل**

إذا منع macOS فتح الملف: كليك يمين → Open → Open.

إذا ظهر خطأ Tk:

```bash
brew install python-tk@3.14
```

### على ويندوز
1. ثبّت Python 3.11+ من [python.org](https://www.python.org/downloads/) مع تفعيل **Add python.exe to PATH**.
2. عطّل اختصارات المتجر إن ظهرت رسالة Microsoft Store:
   - Settings → Apps → Advanced app settings → App execution aliases
   - أوقف `python.exe` و`python3.exe`
3. انقر مرتين على **`run.bat`** (الأفضل)، أو `تشغيل.bat`، أو من PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\run.ps1
   ```
4. من النافذة اختر **تنصيب المتطلبات** ثم **تشغيل البرنامج**.

ملاحظة: المسح من السكنر (TWAIN) يعمل على **ويندوز فقط**. على الماك يمكنك تجربة الدخول والأرشيف ورفع الملفات.

### أوامر طرفية (اختياري)

macOS:

```bash
cd ~/Documents/GitHub/Almktab-app
python3 setup_gui.py
```

ويندوز:

```bat
cd Almktab-app
python setup_gui.py
```

## الاستخدام

1. سجّل الدخول بنفس حساب النظام.
2. من قائمة الأرشيف: ابحث، اعرض الكتاب، عدّل النوع/العدد، أو احذف.
3. من **إضافة أرشيف**:
   - ابحث عن الجريح بالاسم أو الرقم الإحصائي
   - اضغط **فحص السكنر** ثم **مسح من السكنر**
   - أو **رفع ملفات** (صور / PDF)
   - عبّئ نوع الكتاب والعدد لكل ملف ثم **حفظ الأرشيف**

## إعداد اختياري

يمكن تغيير عنوان الـ API عبر متغير بيئة:

```bat
set ALMKTAB_API_BASE_URL=https://services-api.cmfsa-iq.com
python main.py
```

الجلسة (التوكن) تُحفظ في: `%USERPROFILE%\.almktab\session.json`

## بناء ملف exe (اختياري)

```bat
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Almktab --collect-all customtkinter main.py
```

الملف الناتج يظهر في `dist\Almktab\Almktab.exe`.

## ملاحظات السكنر

- المسح يعمل على **ويندوز فقط** عبر مكتبة TWAIN (`pytwain`).
- تأكد أن تعريف السكنر مثبت وأن الجهاز متصل قبل المسح.
- إذا فشل المسح: أعد تشغيل التطبيق، أو افتح واجهة تعريف السكنر وتأكد أنها تظهر في قائمة الأجهزة.
- حجم الطلب الإجمالي محدود تقريباً بـ 30MB من جهة السيرفر؛ استخدم دقة أقل أو صفحات أقل عند الحاجة.

## هيكل المشروع

```
Almktab-app/
  main.py
  requirements.txt
  app/
    config.py
    api/client.py
    scanner/twain_scanner.py
    ui/
      login_window.py
      archive_list.py
      archive_add.py
      widgets.py
    utils/
      session.py
      images.py
```
