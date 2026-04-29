#!/bin/bash
set -e

echo "============================================"
echo " Multi-Project Voice Agent — Setup (Linux/Mac)"
echo "============================================"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo ""
echo "Setup complete!"
echo ""
echo "Usage:"
echo "  python main.py --project cravehub"
echo "  python main.py --project ecommerce"
echo "  python main.py --project hospital"
echo "  python main.py --project hotel"
echo "  python main.py --project justbill"
