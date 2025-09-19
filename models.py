from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Модель для менеджерів закладів"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    restaurant_name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    bot_token = db.Column(db.String(200), nullable=False)
    unique_token = db.Column(db.String(32), unique=True, nullable=False)
    email_address = db.Column(db.String(120), nullable=True)  # Email адреса для сповіщень
    email_enabled = db.Column(db.Boolean, default=False, nullable=False)  # Увімкнути email сповіщення
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    questions = db.relationship('Question', backref='user', lazy=True, cascade='all, delete-orphan')
    surveys = db.relationship('Survey', backref='user', lazy=True, cascade='all, delete-orphan')
    qr_codes = db.relationship('QRCode', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.unique_token:
            self.unique_token = self.generate_unique_token()
    
    def set_password(self, password):
        """Встановити хешований пароль"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Перевірити пароль"""
        return check_password_hash(self.password_hash, password)
    
    def generate_bot_token(self):
        """Генерувати новий токен для бота"""
        self.bot_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        return self.bot_token
    
    def generate_unique_token(self):
        """Генерувати унікальний токен для опитування"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    def get_active_questions(self):
        """Отримати активні питання для цього користувача"""
        return Question.query.filter_by(user_id=self.id, is_active=True).all()
    
    def __repr__(self):
        return f'<User {self.login}>'

class Question(db.Model):
    """Модель для питань опитування"""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='yes_no', nullable=False)  # 'yes_no' або 'manual'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:50]}...>'

class Survey(db.Model):
    """Модель для опитувань (відгуків)"""
    __tablename__ = 'surveys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    waiter_name = db.Column(db.String(100), nullable=False)
    overall_score = db.Column(db.Integer, nullable=False)  # 1-10
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    answers = db.relationship('Answer', backref='survey', lazy=True, cascade='all, delete-orphan')
    
    def get_answers_dict(self):
        """Отримати відповіді у вигляді словника"""
        answers_dict = {}
        for answer in self.answers:
            if answer.answer is not None:
                # Yes/No question
                answers_dict[answer.question.question_text] = {
                    'answer': 'Так' if answer.answer else 'Ні',
                    'comment': answer.comment or ''
                }
            else:
                # Manual input question
                answers_dict[answer.question.question_text] = {
                    'answer': answer.comment or '',
                    'comment': ''
                }
        return answers_dict
    
    def __repr__(self):
        return f'<Survey {self.id}: {self.waiter_name} - {self.overall_score}/10>'

class Answer(db.Model):
    """Модель для відповідей на питання"""
    __tablename__ = 'answers'
    
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer = db.Column(db.Boolean, nullable=False)  # True = Так, False = Ні
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Answer {self.id}: {"Так" if self.answer else "Ні"}>'

class QRCode(db.Model):
    """Модель для зберігання QR-кодів"""
    __tablename__ = 'qr_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    qr_code_data = db.Column(db.LargeBinary, nullable=False)  # PNG data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<QRCode {self.id} for User {self.user_id}>'

class Admin:
    """Клас для роботи з адміністратором (не зберігається в БД)"""
    
    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.is_authenticated = False
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return 'admin'
    
    def check_password(self, password):
        return self.password == password
    
    def __repr__(self):
        return f'<Admin {self.login}>'