from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string
import json
from enum import Enum

db = SQLAlchemy()

class NotificationStatus(Enum):
    """Статуси сповіщень"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"

class User(UserMixin, db.Model):
    """Модель для менеджерів закладів"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    restaurant_name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    bot_token = db.Column(db.String(200), nullable=True)
    telegram_group_id = db.Column(db.String(50), nullable=True)  # ID групи Telegram для сповіщень
    telegram_group_name = db.Column(db.String(200), nullable=True)  # Назва групи Telegram
    telegram_group_link = db.Column(db.String(200), nullable=True)  # Посилання на групу Telegram
    telegram_group_enabled = db.Column(db.Boolean, default=False, nullable=False)  # Увімкнути групові сповіщення
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
    
    def get_notification_settings(self):
        """Отримати налаштування сповіщень для користувача"""
        return NotificationSettings.query.filter_by(user_id=self.id).all()
    
    def has_valid_telegram_settings(self):
        """Перевірити, чи є валідні налаштування Telegram"""
        return (self.bot_token and 
                self.telegram_group_enabled and 
                self.telegram_group_id)
    
    def has_valid_email_settings(self):
        """Перевірити, чи є валідні налаштування email"""
        return (self.email_enabled and 
                self.email_address)

    def __repr__(self):
        return f'<User {self.login}>'


class NotificationSettings(db.Model):
    """Модель для налаштувань сповіщень користувача"""
    __tablename__ = 'notification_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(20), nullable=False)  # 'telegram', 'email', 'webhook'
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    settings_json = db.Column(db.Text, nullable=True)  # JSON з налаштуваннями
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    max_retries = db.Column(db.Integer, default=3, nullable=False)
    last_error = db.Column(db.Text, nullable=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notification_settings')
    
    def get_settings(self):
        """Отримати налаштування як словник"""
        if self.settings_json:
            return json.loads(self.settings_json)
        return {}
    
    def set_settings(self, settings_dict):
        """Встановити налаштування з словника"""
        self.settings_json = json.dumps(settings_dict)
    
    def increment_retry(self, error_message=None):
        """Збільшити лічильник повторних спроб"""
        self.retry_count += 1
        if error_message:
            self.last_error = error_message
        self.updated_at = datetime.utcnow()
    
    def reset_retry(self):
        """Скинути лічильник повторних спроб"""
        self.retry_count = 0
        self.last_error = None
        self.last_success_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def can_retry(self):
        """Перевірити, чи можна повторити спробу"""
        return self.retry_count < self.max_retries
    
    def __repr__(self):
        return f'<NotificationSettings {self.user_id}:{self.notification_type}>'


class NotificationQueue(db.Model):
    """Модель для черги сповіщень"""
    __tablename__ = 'notification_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=True)
    notification_type = db.Column(db.String(20), nullable=False)  # 'telegram', 'email', 'webhook'
    message_content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default=NotificationStatus.PENDING.value, nullable=False)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    max_retries = db.Column(db.Integer, default=3, nullable=False)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)  # Додаткові дані
    dedup_key = db.Column(db.String(255), nullable=True, unique=False)  # Ключ ідемпотентності
    locked_at = db.Column(db.DateTime, nullable=True)  # Час захоплення задачі воркером
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notification_queue')
    survey = db.relationship('Survey', backref='notifications')
    
    def get_metadata(self):
        """Отримати метадані як словник"""
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}
    
    def set_metadata(self, metadata_dict):
        """Встановити метадані з словника"""
        self.metadata_json = json.dumps(metadata_dict)
    
    def mark_as_sent(self):
        """Позначити як відправлене"""
        self.status = NotificationStatus.SENT.value
        self.sent_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_as_failed(self, error_message):
        """Позначити як невдале"""
        self.status = NotificationStatus.FAILED.value
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
    
    def increment_retry(self, error_message=None):
        """Збільшити лічильник повторних спроб"""
        self.retry_count += 1
        if error_message:
            self.error_message = error_message
        
        if self.retry_count < self.max_retries:
            self.status = NotificationStatus.RETRYING.value
            # Експоненційна затримка: 2^retry_count хвилин
            delay_minutes = 2 ** self.retry_count
            self.scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
        else:
            self.status = NotificationStatus.FAILED.value
        
        self.updated_at = datetime.utcnow()
    
    def can_retry(self):
        """Перевірити, чи можна повторити спробу"""
        return (self.retry_count < self.max_retries and 
                self.status in [NotificationStatus.PENDING.value, NotificationStatus.RETRYING.value])
    
    def is_ready_for_processing(self):
        """Перевірити, чи готове для обробки"""
        return (self.status in [NotificationStatus.PENDING.value, NotificationStatus.RETRYING.value] and
                self.scheduled_at <= datetime.utcnow())
    
    def __repr__(self):
        return f'<NotificationQueue {self.id}:{self.notification_type}:{self.status}>'

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

class Admin(db.Model):
    """Модель для адміністраторів"""
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Встановити хешований пароль"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Перевірити пароль"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Admin {self.login}>'


class AdminSettings(db.Model):
    """Модель для налаштувань адміністратора"""
    __tablename__ = 'admin_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.String(20), default='string', nullable=False)  # string, boolean, integer, json
    description = db.Column(db.Text, nullable=True)
    is_sensitive = db.Column(db.Boolean, default=False, nullable=False)  # Для паролів та токенів
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Отримати налаштування за ключем"""
        setting = cls.query.filter_by(setting_key=key).first()
        if not setting:
            return default
        
        # Конвертуємо значення відповідно до типу
        if setting.setting_type == 'boolean':
            return setting.setting_value.lower() in ('true', '1', 'yes', 'on') if setting.setting_value else False
        elif setting.setting_type == 'integer':
            try:
                return int(setting.setting_value) if setting.setting_value else default
            except (ValueError, TypeError):
                return default
        elif setting.setting_type == 'json':
            try:
                return json.loads(setting.setting_value) if setting.setting_value else default
            except (json.JSONDecodeError, TypeError):
                return default
        else:  # string
            return setting.setting_value if setting.setting_value else default
    
    @classmethod
    def set_setting(cls, key, value, setting_type='string', description=None, is_sensitive=False):
        """Встановити налаштування"""
        setting = cls.query.filter_by(setting_key=key).first()
        
        # Конвертуємо значення в рядок відповідно до типу
        if setting_type == 'boolean':
            str_value = str(bool(value)).lower()
        elif setting_type == 'integer':
            str_value = str(int(value)) if value is not None else None
        elif setting_type == 'json':
            str_value = json.dumps(value) if value is not None else None
        else:  # string
            str_value = str(value) if value is not None else None
        
        if setting:
            setting.setting_value = str_value
            setting.setting_type = setting_type
            setting.description = description
            setting.is_sensitive = is_sensitive
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(
                setting_key=key,
                setting_value=str_value,
                setting_type=setting_type,
                description=description,
                is_sensitive=is_sensitive
            )
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @classmethod
    def get_alert_settings(cls):
        """Отримати всі налаштування алертів"""
        return {
            'alert_email': cls.get_setting('alert_email', ''),
            'alert_telegram_bot_token': cls.get_setting('alert_telegram_bot_token', ''),
            'alert_telegram_chat_id': cls.get_setting('alert_telegram_chat_id', ''),
            'alert_email_enabled': cls.get_setting('alert_email_enabled', False),
            'alert_telegram_enabled': cls.get_setting('alert_telegram_enabled', False),
        }
    
    @classmethod
    def set_alert_settings(cls, settings):
        """Встановити налаштування алертів"""
        cls.set_setting('alert_email', settings.get('alert_email', ''), 'string', 
                       'Email адреса для критичних алертів', False)
        cls.set_setting('alert_telegram_bot_token', settings.get('alert_telegram_bot_token', ''), 'string', 
                       'Токен Telegram бота для алертів', True)
        cls.set_setting('alert_telegram_chat_id', settings.get('alert_telegram_chat_id', ''), 'string', 
                       'ID чату Telegram для алертів', False)
        cls.set_setting('alert_email_enabled', settings.get('alert_email_enabled', False), 'boolean', 
                       'Увімкнути email алерти', False)
        cls.set_setting('alert_telegram_enabled', settings.get('alert_telegram_enabled', False), 'boolean', 
                       'Увімкнути Telegram алерти', False)
    
    def __repr__(self):
        return f'<AdminSettings {self.setting_key}={self.setting_value}>'