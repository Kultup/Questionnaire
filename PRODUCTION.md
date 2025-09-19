# Що замінити в .env для продакшену

## Обов'язкові зміни:

```env
# Замість:
SECRET_KEY=your-super-secret-key-change-this-in-production
# Поставити:
SECRET_KEY=ваш-унікальний-32-символьний-ключ

# Замість:
FLASK_ENV=development
FLASK_DEBUG=True
DEBUG=True
# Поставити:
FLASK_ENV=production
FLASK_DEBUG=False
DEBUG=False


# Замість:
DOMAIN=localhost
BASE_URL=http://localhost:5000
# Поставити:
DOMAIN=ваш-домен.com
BASE_URL=https://ваш-домен.com

# Замість:
MAIL_USERNAME=
MAIL_PASSWORD=
# Поставити:
MAIL_USERNAME=ваш-email@gmail.com
MAIL_PASSWORD=ваш-пароль-додатку
```