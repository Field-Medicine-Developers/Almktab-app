#!/bin/bash
cd "$(dirname "$0")"
echo "فتح واجهة التنصيب والتشغيل..."
if [ -x "./.venv/bin/python" ]; then
  exec "./.venv/bin/python" setup_gui.py
fi
exec python3 setup_gui.py
