from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Email, Optional
from models import User
import re

def validate_question_text(form, field):
    """Валідатор для тексту питання"""
    text = field.data.strip()
    
    # Перевірка на мінімальну довжину
    if len(text) < 5:
        raise ValidationError('Текст питання повинен містити принаймні 5 символів')
    
    # Перевірка на повторювані символи (більше 5 підряд)
    if re.search(r'(.)\1{4,}', text):
        raise ValidationError('Текст питання не може містити більше 4 однакових символів підряд')
    
    # Перевірка на осмислений текст (не тільки одні й ті ж символи)
    unique_chars = set(text.lower().replace(' ', ''))
    if len(unique_chars) < 3:
        raise ValidationError('Текст питання повинен містити принаймні 3 різні символи (наприклад: "Чи сподобалась їжа?")')
    
    # Перевірка на наявність принаймні однієї літери
    if not re.search(r'[а-яА-Яa-zA-Z]', text):
        raise ValidationError('Текст питання повинен містити принаймні одну літеру')

class LoginForm(FlaskForm):
    """Форма входу для адміна та менеджерів"""
    login = StringField('Логін', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=4)])

class UserCreateForm(FlaskForm):
    """Форма створення менеджера закладу"""
    login = StringField('Логін', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=4, message='Пароль повинен містити мінімум 4 символи')])
    restaurant_name = StringField('Назва закладу', validators=[DataRequired(), Length(max=200)])
    city = StringField('Місто', validators=[DataRequired(), Length(max=100)])
    
    def validate_email_address(self, email_address):
        """Валідація email адреси"""
        if self.email_enabled.data and not email_address.data:
            raise ValidationError('Email адреса обов\'язкова, якщо увімкнені email сповіщення')
    
    def validate_login(self, login):
        user = User.query.filter_by(login=login.data).first()
        if user:
            raise ValidationError('Користувач з таким логіном вже існує')
    
    def validate_password(self, password):
        # Перевірка політики паролів: мінімум 4 символи, букви + цифри
        if len(password.data) < 4:
            raise ValidationError('Пароль повинен містити мінімум 4 символи')
        
        has_letter = any(c.isalpha() for c in password.data)
        has_digit = any(c.isdigit() for c in password.data)
        
        if not (has_letter and has_digit):
            raise ValidationError('Пароль повинен містити букви та цифри')

class UserEditForm(FlaskForm):
    """Форма редагування менеджера закладу"""
    login = StringField('Логін', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Новий пароль (залиште порожнім, щоб не змінювати)', validators=[Length(min=0, max=120)])
    restaurant_name = StringField('Назва закладу', validators=[DataRequired(), Length(max=200)])
    city = StringField('Місто', validators=[DataRequired(), Length(max=100)])
    is_active = BooleanField('Активний')
    
    def __init__(self, original_user, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)
        self.original_user = original_user
    
    def validate_login(self, login):
        if login.data != self.original_user.login:
            user = User.query.filter_by(login=login.data).first()
            if user:
                raise ValidationError('Користувач з таким логіном вже існує')
    
    def validate_password(self, password):
        if password.data:  # Тільки якщо пароль введено
            if len(password.data) < 4:
                raise ValidationError('Пароль повинен містити мінімум 4 символи')
            
            has_letter = any(c.isalpha() for c in password.data)
            has_digit = any(c.isdigit() for c in password.data)
            
            if not (has_letter and has_digit):
                raise ValidationError('Пароль повинен містити букви та цифри')

class UserForm(FlaskForm):
    """Форма редагування менеджера закладу"""
    login = StringField('Логін', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[Length(min=0, max=120)])
    restaurant_name = StringField('Назва закладу', validators=[DataRequired(), Length(max=200)])
    city = StringField('Місто', validators=[DataRequired(), Length(max=100)])
    bot_token = StringField('Токен Telegram бота', validators=[Length(max=200)])
    email_address = StringField('Email адреса', validators=[Optional(), Email(message='Введіть коректну email адресу'), Length(max=120)])
    email_enabled = BooleanField('Увімкнути email сповіщення', default=False)
    is_active = BooleanField('Активний', default=True)
    
    def __init__(self, original_user=None, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.original_user = original_user
    
    def validate_login(self, login):
        if self.original_user:
            # Редагування - перевіряємо тільки якщо логін змінився
            if login.data != self.original_user.login:
                user = User.query.filter_by(login=login.data).first()
                if user:
                    raise ValidationError('Користувач з таким логіном вже існує')
        else:
            # Створення - завжди перевіряємо
            user = User.query.filter_by(login=login.data).first()
            if user:
                raise ValidationError('Користувач з таким логіном вже існує')
    
    def validate_password(self, password):
        # Для нового користувача пароль обов'язковий
        if not self.original_user and not password.data:
            raise ValidationError('Пароль обов\'язковий для нового користувача')
        
        # Якщо пароль введено, перевіряємо політику
        if password.data:
            if len(password.data) < 4:
                raise ValidationError('Пароль повинен містити мінімум 4 символи')
            
            has_letter = any(c.isalpha() for c in password.data)
            has_digit = any(c.isdigit() for c in password.data)
            
            if not (has_letter and has_digit):
                raise ValidationError('Пароль повинен містити букви та цифри')

class QuestionForm(FlaskForm):
    """Форма створення/редагування питання"""
    question_text = TextAreaField('Текст питання', validators=[DataRequired(), Length(max=500), validate_question_text])
    question_type = SelectField('Тип питання', 
                               choices=[('yes_no', 'Так/Ні + коментар'), ('manual', 'Ручний ввід')],
                               default='yes_no',
                               validators=[DataRequired()])
    is_active = BooleanField('Активне', default=True)

class SurveyForm(FlaskForm):
    """Форма опитування для клієнтів"""
    waiter_name = StringField('Ім\'я офіціанта', validators=[DataRequired(), Length(max=100)])
    overall_score = IntegerField('Загальне враження (1-10)', validators=[DataRequired(), NumberRange(min=1, max=10)])
    
    def __init__(self, questions=None, *args, **kwargs):
        super(SurveyForm, self).__init__(*args, **kwargs)
        
        if questions:
            # Динамічно додаємо поля для кожного питання
            for question in questions:
                # Поле для відповіді Так/Ні
                answer_field_name = f'answer_{question.id}'
                setattr(self, answer_field_name, SelectField(
                    question.question_text,
                    choices=[('1', 'Так'), ('0', 'Ні')],
                    validators=[DataRequired()],
                    coerce=int
                ))
                
                # Поле для коментаря
                comment_field_name = f'comment_{question.id}'
                setattr(self, comment_field_name, TextAreaField(
                    'Коментар (необов\'язково)',
                    validators=[Length(max=500)]
                ))

class BotTokenForm(FlaskForm):
    """Форма для управління токеном бота"""
    bot_token = StringField('Токен бота', validators=[DataRequired()], 
                           render_kw={"placeholder": "Введіть токен Telegram бота"})
    submit = SubmitField('Зберегти токен')

class DateFilterForm(FlaskForm):
    """Форма для фільтрації за датами"""
    start_date = StringField('Дата початку (YYYY-MM-DD)', validators=[Length(max=10)])
    end_date = StringField('Дата кінця (YYYY-MM-DD)', validators=[Length(max=10)])
    
    def validate_start_date(self, start_date):
        if start_date.data:
            try:
                from datetime import datetime
                datetime.strptime(start_date.data, '%Y-%m-%d')
            except ValueError:
                raise ValidationError('Неправильний формат дати. Використовуйте YYYY-MM-DD')
    
    def validate_end_date(self, end_date):
        if end_date.data:
            try:
                from datetime import datetime
                datetime.strptime(end_date.data, '%Y-%m-%d')
            except ValueError:
                raise ValidationError('Неправильний формат дати. Використовуйте YYYY-MM-DD')