# models.py
from extensions import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # 角色: 'admin', 'teacher', 'student', 'guest'
    role = db.Column(db.String(10), default='student', nullable=False)
    
    # 功能旗標
    is_active = db.Column(db.Boolean, default=True)      
    force_pw_change = db.Column(db.Boolean, default=True) 
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'