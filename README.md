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
1. انقر مرتين على **`run.vbs`** (بدون نافذة CMD)، أو **`run.bat`**.
2. إذا لم يكن Python موجوداً: سيتم تحميله وتثبيته تلقائياً مع **PATH**.
3. من واجهة التنصيب يمكنك أيضاً يدوياً:
   - **تحميل Python**
   - **تثبيت Python + PATH**
   - **إعدادات PATH/Aliases** (عطّل اختصارات Microsoft Store)
   - ثم **تنصيب المتطلبات** → **تشغيل البرنامج**

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

- المسح على **ويندوز** عبر **WIA** أولاً (مدمج في النظام)، ثم TWAIN عند الحاجة.
- لا تستخدم Python من Microsoft Store إن أمكن؛ ثبّته من python.org عبر `run.bat` / واجهة التنصيب.
- بعد التحديث: من واجهة التنصيب اضغط **تنصيب المتطلبات** لتثبيت `pywin32`.
- عند الفحص ستظهر أجهزة مثل `[WIA] ...` — اخترها للمسح.
- حجم الطلب الإجمالي محدود تقريباً بـ 30MB من جهة السيرفر.

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
