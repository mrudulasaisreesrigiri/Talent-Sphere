import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.chdir(backend_dir)

from app.main import app
from app.core.config import settings

if __name__ == "__main__":
    print("==================================================================")
    print("Starting Talent Management Platform for Employee Performance and Career Growth")
    print(f"Application is live at: http://localhost:{settings.PORT}")
    print("==================================================================")
    app.run(host="0.0.0.0", port=settings.PORT, debug=True)
