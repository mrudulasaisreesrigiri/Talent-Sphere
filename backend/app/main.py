from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.deps import close_db
from app.models.models import User, UserRole
from app.core.security import get_password_hash

# Import View Blueprint
from app.routes.views import views_bp

# Import Flask REST API Blueprints
from app.api.auth import auth_bp
from app.api.users import users_bp
from app.api.documents import documents_bp
from app.api.exams import exams_bp
from app.api.announcements import announcements_bp
from app.api.notifications import notifications_bp
from app.api.chat import chat_bp
from app.api.ai_commands import ai_commands_bp
from app.api.search import search_bp
from app.api.analytics import analytics_bp
from app.api.audit_logs import audit_logs_bp
from app.api.study_plans import study_plans_bp

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["JWT_SECRET_KEY"] = settings.SECRET_KEY

    # Configure CORS for localhost:5173 (React Vite) and localhost:8000 (Flask Backend)
    CORS(
        app,
        resources={r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "*"
            ]
        }},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    # Initialize Flask-JWT-Extended
    JWTManager(app)

    # Register app context teardown to close DB sessions
    app.teardown_appcontext(close_db)

    # Register View Blueprint (Jinja2 HTML Pages)
    app.register_blueprint(views_bp)

    # Register REST API Blueprints under /api
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(documents_bp, url_prefix="/api/documents")
    app.register_blueprint(exams_bp, url_prefix="/api/exams")
    app.register_blueprint(announcements_bp, url_prefix="/api/announcements")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(ai_commands_bp, url_prefix="/api/ai-commands")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(audit_logs_bp, url_prefix="/api/audit-logs")
    app.register_blueprint(study_plans_bp, url_prefix="/api/study-plans")

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "online", "app": settings.PROJECT_NAME, "version": "1.0.0"}), 200

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"detail": "An internal server error occurred. Please contact system admin."}), 500

    @app.errorhandler(404)
    def not_found_error(e):
        return jsonify({"detail": "Resource not found"}), 404

    # Seed Super Admin if needed
    init_db_and_seed()

    return app

def init_db_and_seed():
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_user:
            initial_admin = User(
                email="admin@talentsphere.com",
                full_name="System Super Administrator",
                password_hash=get_password_hash("Admin@123456"),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(initial_admin)
            db.commit()
            print("Successfully seeded Super Admin user: admin@talentsphere.com / Admin@123456")
        db.close()
    except Exception as e:
        print(f"Database startup notice: {e}")

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT, debug=True)
