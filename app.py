from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import os
import json

app = Flask(__name__)

# Configuration de la base de données
# Pour développement local (SQLite)
if os.environ.get('FLASK_ENV') == 'production':
    # Pour production - utiliser PostgreSQL sur Railway/Render
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///visitors.db')
else:
    # Pour développement local
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///visitors.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'votre-cle-secrete-dev')

db = SQLAlchemy(app)

# Modèles de base de données
class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    page = db.Column(db.String(200), nullable=False)
    action = db.Column(db.String(50), default='VISIT')
    referrer = db.Column(db.String(500), nullable=True)
    host = db.Column(db.String(100), nullable=True)
    method = db.Column(db.String(10), nullable=True)
    platform = db.Column(db.String(100), nullable=True)
    browser = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(100), nullable=True)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

def get_client_ip():
    """Obtenir l'adresse IP réelle du client"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.environ.get('REMOTE_ADDR', 'Unknown')

def parse_user_agent(user_agent_string):
    """Parser simple pour extraire navigateur et plateforme"""
    ua = user_agent_string.lower() if user_agent_string else ''
    
    # Détecter le navigateur
    if 'chrome' in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua:
        browser = 'Safari'
    elif 'edge' in ua:
        browser = 'Edge'
    else:
        browser = 'Unknown'
    
    # Détecter la plateforme
    if 'windows' in ua:
        platform = 'Windows'
    elif 'mac' in ua:
        platform = 'macOS'
    elif 'linux' in ua:
        platform = 'Linux'
    elif 'android' in ua:
        platform = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        platform = 'iOS'
    else:
        platform = 'Unknown'
    
    return browser, platform

def log_visitor(page, action="VISIT"):
    """Enregistrer une visite en base de données"""
    try:
        ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        browser, platform = parse_user_agent(user_agent)
        
        visitor = Visitor(
            session_id=session.get('session_id', str(uuid.uuid4())),
            ip_address=ip,
            user_agent=user_agent,
            page=page,
            action=action,
            referrer=request.referrer,
            host=request.host,
            method=request.method,
            platform=platform,
            browser=browser
        )
        
        db.session.add(visitor)
        db.session.commit()
        
        # Log pour debug
        app.logger.info(f"VISITOR LOGGED: {ip} - {action} - {page}")
        
    except Exception as e:
        app.logger.error(f"Error logging visitor: {e}")
        db.session.rollback()

@app.before_request
def before_request():
    """Middleware pour chaque requête"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Ne pas logger les fichiers statiques et l'admin en boucle
    if not request.path.startswith('/static') and request.path != '/admin/logs':
        log_visitor(request.path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/portfolio')
def portfolio():
    log_visitor('/portfolio', 'PORTFOLIO_VIEW')
    return render_template('portfolio.html')

@app.route('/about')
def about():
    log_visitor('/about', 'ABOUT_VIEW')
    return render_template('about.html')

@app.route('/contact')
def contact():
    log_visitor('/contact', 'CONTACT_VIEW')
    return render_template('contact.html')

@app.route('/contact', methods=['POST'])
def contact_submit():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        # Sauvegarder le message
        contact_msg = ContactMessage(
            name=name,
            email=email,
            message=message,
            ip_address=get_client_ip()
        )
        
        db.session.add(contact_msg)
        db.session.commit()
        
        log_visitor('/contact', f'CONTACT_SUBMIT:{name}')
        
        return jsonify({'status': 'success', 'message': 'Message envoyé avec succès!'})
    except Exception as e:
        app.logger.error(f"Error saving contact message: {e}")
        return jsonify({'status': 'error', 'message': 'Erreur lors de l\'envoi'})

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin/logs')
def admin_logs():
    try:
        # Récupérer les 100 derniers logs
        visitors = Visitor.query.order_by(Visitor.timestamp.desc()).limit(100).all()
        
        logs = []
        for visitor in visitors:
            logs.append({
                'id': visitor.id,
                'session_id': visitor.session_id,
                'ip': visitor.ip_address,
                'user_agent': visitor.user_agent,
                'timestamp': visitor.timestamp.isoformat(),
                'page': visitor.page,
                'action': visitor.action,
                'referrer': visitor.referrer,
                'host': visitor.host,
                'method': visitor.method,
                'platform': visitor.platform,
                'browser': visitor.browser
            })
        
        total_visits = Visitor.query.count()
        unique_visitors = db.session.query(Visitor.ip_address).distinct().count()
        
        return jsonify({
            'logs': logs,
            'total': total_visits,
            'unique_visitors': unique_visitors
        })
    except Exception as e:
        app.logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': 'Erreur lors de la récupération des logs'})

@app.route('/admin/stats')
def admin_stats():
    try:
        # Statistiques avancées
        total_visits = Visitor.query.count()
        unique_visitors = db.session.query(Visitor.ip_address).distinct().count()
        total_messages = ContactMessage.query.count()
        
        # Top pages
        top_pages = db.session.query(
            Visitor.page, 
            db.func.count(Visitor.page).label('count')
        ).group_by(Visitor.page).order_by(db.desc('count')).limit(10).all()
        
        # Top navigateurs
        top_browsers = db.session.query(
            Visitor.browser, 
            db.func.count(Visitor.browser).label('count')
        ).group_by(Visitor.browser).order_by(db.desc('count')).limit(5).all()
        
        # Visites par heure (dernières 24h)
        from sqlalchemy import text
        hourly_visits = db.session.execute(text("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM visitor 
            WHERE timestamp >= datetime('now', '-24 hours')
            GROUP BY hour
            ORDER BY hour
        """)).fetchall()
        
        return jsonify({
            'total_visits': total_visits,
            'unique_visitors': unique_visitors,
            'total_messages': total_messages,
            'top_pages': [{'page': p[0], 'count': p[1]} for p in top_pages],
            'top_browsers': [{'browser': b[0], 'count': b[1]} for b in top_browsers],
            'hourly_visits': [{'hour': h[0], 'count': h[1]} for h in hourly_visits]
        })
    except Exception as e:
        app.logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': 'Erreur lors de la récupération des statistiques'})

@app.route('/admin/messages')
def admin_messages():
    try:
        messages = ContactMessage.query.order_by(ContactMessage.timestamp.desc()).all()
        
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'name': msg.name,
                'email': msg.email,
                'message': msg.message,
                'ip_address': msg.ip_address,
                'timestamp': msg.timestamp.isoformat(),
                'read': msg.read
            })
        
        return jsonify({'messages': messages_data})
    except Exception as e:
        app.logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': 'Erreur lors de la récupération des messages'})

@app.route('/admin/export')
def export_logs():
    try:
        visitors = Visitor.query.order_by(Visitor.timestamp.desc()).all()
        
        data = []
        for visitor in visitors:
            data.append({
                'id': visitor.id,
                'session_id': visitor.session_id,
                'ip_address': visitor.ip_address,
                'user_agent': visitor.user_agent,
                'timestamp': visitor.timestamp.isoformat(),
                'page': visitor.page,
                'action': visitor.action,
                'referrer': visitor.referrer,
                'host': visitor.host,
                'method': visitor.method,
                'platform': visitor.platform,
                'browser': visitor.browser
            })
        
        from flask import make_response
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=visitor_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    except Exception as e:
        app.logger.error(f"Error exporting logs: {e}")
        return jsonify({'error': 'Erreur lors de l\'export'})

# Routes pour servir les templates (même code que précédemment)
def create_templates():
    """Créer les templates HTML - même code que dans la version précédente"""
    # [Le code des templates reste identique à la version précédente]
    pass

# Initialisation de la base de données
def init_db():
    """Initialiser la base de données"""
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables created successfully")

if __name__ == '__main__':
    # Créer les templates
    create_templates()
    
    # Initialiser la base de données
    init_db()
    
    print("🚀 Serveur démarré avec base de données")
    print("📊 Admin: http://localhost:5000/admin")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
