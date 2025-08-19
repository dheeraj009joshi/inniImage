import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory
from flask_wtf import FlaskForm
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from mongoengine import connect
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import json
    # Register blueprints
from routes.index import index_bp
from routes.auth import auth_bp
from routes.study_creation import study_creation_bp
from routes.study_participation import study_participation_bp
from routes.dashboard import dashboard_bp
from routes.api import api_bp
    

# Import configuration
from config import config

# Import models
from models.user import User
from models.study import Study, RatingScale, StudyElement, ClassificationQuestion, IPEDParameters
from models.study_draft import StudyDraft
from models.response import StudyResponse, TaskSession

# Import forms
from forms.auth import LoginForm, RegistrationForm, PasswordResetRequestForm, PasswordResetForm, ProfileUpdateForm
from forms.study import (
    Step1aBasicDetailsForm, Step1bStudyTypeForm, Step1cRatingScaleForm,
    Step2cIPEDParametersForm, Step3aTaskGenerationForm, Step3bLaunchForm
)

# Initialize extensions
login_manager = LoginManager()
csrf = CSRFProtect()
cache = Cache()

def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize database connection with performance optimizations
    connect(
        host=app.config['MONGODB_SETTINGS']['host'],
        maxPoolSize=100,  # Increased for better concurrency
        minPoolSize=20,   # Increased minimum connections
        maxIdleTimeMS=60000,  # Keep connections alive longer
        serverSelectionTimeoutMS=2000,  # Faster server selection
        connectTimeoutMS=2000,  # Faster connection
        socketTimeoutMS=5000,  # Reasonable socket timeout
        waitQueueTimeoutMS=2000,  # Faster queue timeout
        maxConnecting=20,  # Limit concurrent connections
        retryWrites=True,  # Enable retry for writes
        retryReads=True,   # Enable retry for reads
        w='majority',      # Write concern
        readPreference='primaryPreferred'  # Read preference
    )
    
    # Configure session management FIRST (before CSRF)
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600 * 24 * 30  # 30 days
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Initialize extensions
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'basic'  # Changed from 'strong' to 'basic'
    
    # Performance optimizations
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
    app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable auto-reload in production
    app.config['JSON_SORT_KEYS'] = False  # Faster JSON serialization
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # Faster JSON responses
    
    # Additional performance optimizations
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_EXTENSIONS'] = ['.jpg', '.png', '.gif', '.jpeg', '.webp']
    app.config['UPLOAD_PATH'] = 'uploads'
    
    # Enable compression for better performance (only if available)
    try:
        from flask_compress import Compress
        Compress(app)
        print("✅ Compression enabled")
    except ImportError:
        print("⚠️ Flask-Compress not available, skipping compression")
    
    # Exclude study participation routes from CSRF protection (they are anonymous/public)
    # This needs to be done after the blueprint is registered
    
    # Quick database connection test (skip heavy optimizations for faster startup)
    with app.app_context():
        try:
            from mongoengine import get_db
            db = get_db()
            # Just test basic connectivity
            db.command('ping', maxTimeMS=500)
            print("✅ Database connected")
        except Exception as e:
            print(f"⚠️ Database connection warning: {e}")
            print("Continuing with standard connection...")

    app.register_blueprint(index_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(study_creation_bp)
    app.register_blueprint(study_participation_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    
    # CSRF protection is enabled for all routes including study participation
    # Forms will include proper CSRF tokens
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = User.objects(_id=user_id).first()
            if user:
                print(f"✅ User loaded: {user.username}")
            else:
                print(f"⚠️ User not found: {user_id}")
            return user
        except Exception as e:
            print(f"❌ Error loading user {user_id}: {e}")
            return None
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200
    
        # Session debug endpoint
    @app.route('/debug/session')
    def debug_session():
        """Debug endpoint to check session state."""
        if current_user.is_authenticated:
            return jsonify({
                'authenticated': True,
                'user_id': str(current_user._id),
                'username': current_user.username,
                'session_keys': list(session.keys()),
                'session_id': session.get('_id'),
                'permanent': session.permanent
            })
        else:
            return jsonify({
                'authenticated': False,
                'session_keys': list(session.keys()),
                'session_id': session.get('_id'),
                'permanent': session.permanent
            })

    @app.route('/test-redirect')
    def test_redirect():
        """Test basic redirect functionality."""
        return redirect(url_for('index.index'))

    @app.route('/test-simple')
    def test_simple():
        """Simple test endpoint."""
        return jsonify({'status': 'ok', 'message': 'Simple redirect test'})

    @app.route('/test-login-simulate')
    def test_login_simulate():
        """Simulate login redirect scenario."""
        return redirect(url_for('auth.login', next='/dashboard/studies/test-id'))

    @app.route('/test-form-submit', methods=['GET', 'POST'])
    def test_form_submit():
        """Test form submission without authentication."""
        class TestForm(FlaskForm):
            pass
        
        form = TestForm()
        
        if request.method == 'POST':
            print(f"Form submitted with data: {request.form}")
            print(f"Session keys: {list(session.keys())}")
            print(f"CSRF token in form: {form.csrf_token.data}")
            print(f"CSRF token in request: {request.form.get('csrf_token')}")
            print(f"Session CSRF token: {session.get('csrf_token')}")
            return jsonify({'status': 'success', 'data': dict(request.form)})
        
        print(f"Rendering form. Session keys: {list(session.keys())}")
        print(f"Form CSRF token: {form.csrf_token.data}")
        print(f"Session CSRF token: {session.get('csrf_token')}")
        return render_template('test_form.html', form=form)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    

    
    # Note: Main routes are handled by blueprints
    # / -> index_bp.index()
    # /about -> about route (to be added)
    # /contact -> contact route (to be added)
    
    @app.route('/.well-known/appspecific/com.chrome.devtools.json')
    def chrome_devtools_config():
        """Handle Chrome DevTools configuration request to prevent 404 errors."""
        return '', 204  # No Content

    @app.route('/favicon.ico')
    def favicon():
        """Handle favicon request to prevent 404 errors."""
        return '', 204  # No Content

    @app.route('/robots.txt')
    def robots():
        """Handle robots.txt request to prevent 404 errors."""
        return '', 204  # No Content

    @app.route('/sitemap.xml')
    def sitemap():
        """Handle sitemap request to prevent 404 errors."""
        return '', 204  # No Content
    
    # File upload helper
    def allowed_file(filename):
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    
    def save_uploaded_file(file, study_id):
        """Save uploaded file and return file path."""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Create unique filename
            unique_filename = f"{study_id}_{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            return unique_filename
        return None
    
    # Register template filters
    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        return value.strftime(format)
    
    @app.template_filter('format_duration')
    def format_duration_filter(seconds):
        if seconds is None:
            return "0s"
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    


    @app.before_request
    def log_request_info():
        """Log request information for debugging and monitoring."""
        # Skip logging for common static file requests and health checks
        if request.path.startswith('/static/') or request.path in ['/favicon.ico', '/robots.txt', '/sitemap.xml', '/.well-known/appspecific/com.chrome.devtools.json']:
            return
        
        # Log only non-static requests
        print(f"[{datetime.utcnow().isoformat()}] {request.method} {request.path} - {request.remote_addr}")

    @app.before_request
    def optimize_request():
        """Optimize request handling for better performance."""
        # Add request start time for performance monitoring
        request.start_time = datetime.utcnow()
        
        # Skip optimization for static files
        if request.path.startswith('/static/'):
            return
        
        # Add performance headers
        request.performance_headers = {
            'X-Request-Start': str(request.start_time.timestamp()),
            'X-Request-ID': str(uuid.uuid4())
        }

    @app.after_request
    def add_security_headers(response):
        """Add security and performance headers to all responses."""
        # Add cache headers for static files
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Vary'] = 'Accept-Encoding'
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Add performance headers
        response.headers['Connection'] = 'keep-alive'
        
        # Add performance monitoring headers
        if hasattr(request, 'start_time'):
            response_time = (datetime.utcnow() - request.start_time).total_seconds() * 1000
            response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
        
        if hasattr(request, 'performance_headers'):
            for key, value in request.performance_headers.items():
                response.headers[key] = value
        
        return response

    # Add static file optimization
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """Optimized static file serving with caching."""
        response = send_from_directory('static', filename)
        if filename.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico')):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Vary'] = 'Accept-Encoding'
            
            # Add compression for text files
            if filename.endswith(('.css', '.js')):
                response.headers['Content-Encoding'] = 'gzip'
        
        return response
    
    return app

def create_tables():
    """Create database tables/indexes with performance optimization."""
    app = create_app()
    with app.app_context():
        try:
            # Create basic indexes only (skip complex ones for faster startup)
            print("🔄 Creating basic indexes...")
            User.ensure_indexes()
            Study.ensure_indexes()
            StudyDraft.ensure_indexes()
            StudyResponse.ensure_indexes()
            TaskSession.ensure_indexes()
            print("✅ Basic indexes created")
            
            # Skip complex index creation for faster startup
            # These can be created later in production if needed
            
        except Exception as e:
            print(f"⚠️ Index creation warning: {e}")
            print("Continuing with basic setup...")
