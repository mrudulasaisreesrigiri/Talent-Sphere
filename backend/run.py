from app.main import app
from app.core.config import settings

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT, debug=True)
