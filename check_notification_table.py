import sqlite3

# Підключення до бази даних
conn = sqlite3.connect('instance/feedback_system.db')
cursor = conn.cursor()

# Отримання структури таблиці notification_queue
cursor.execute("PRAGMA table_info(notification_queue)")
columns = cursor.fetchall()

print("Структура таблиці notification_queue:")
for column in columns:
    print(f"  {column[1]} ({column[2]}) - NOT NULL: {column[3]}, DEFAULT: {column[4]}, PK: {column[5]}")

conn.close()