import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from convert import convert_md_to_html 
import re
from transliterate import translit  # Установите библиотеку: pip install transliterate
from werkzeug.security import generate_password_hash, check_password_hash

def sanitize_filename(filename):
    # Транслитерируем кириллицу в латиницу
    filename = translit(filename, 'ru', reversed=True)
    # Удаляем все недопустимые символы (оставляем только буквы, цифры, дефисы и подчеркивания)
    filename = re.sub(r'[^\w\-]', '_', filename)
    return filename

# Создаем директорию для базы данных
try:
    os.mkdir('base_d')
except Exception:
    pass

# Определяем базовую директорию и путь к базе данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'base_d', 'database.db')

# Создаем Flask-приложение
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Секретный ключ для сессий
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'  # Путь к базе данных
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем отслеживание изменений

# Инициализируем SQLAlchemy и LoginManager
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Страница входа по умолчанию

# Разрешенные теги для статей
ALLOWED_TAGS = ['Python', 'Flask', 'SQLite', 'Web Development', 'Tutorial']

# Функция для декодировки
def fix_encoding(text):
    try:
        return text.encode('windows-1251').decode('utf-8')
    except:
        return text
    
def save_article_to_file(path, content):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор пользователя
    username = db.Column(db.String(80), unique=True, nullable=False)  # Имя пользователя
    password = db.Column(db.String(120), nullable=False)  # Пароль пользователя

# Модель статьи
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор статьи
    author = db.Column(db.String(80), nullable=False)  # Автор статьи
    name = db.Column(db.String(120), nullable=False)  # Название статьи
    tag = db.Column(db.String(50), nullable=False)  # Тег статьи
    registered = db.Column(db.Boolean, nullable=False)  # Доступна ли статья только зарегистрированным пользователям
    path = db.Column(db.String(200), nullable=False)  # Путь к файлу статьи

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # Возвращает пользователя по его ID

# Главная страница
@app.route('/')
def index():
    if current_user.is_authenticated:
        articles = Article.query.all()
    else:
        articles = Article.query.filter_by(registered=False).all()
    return render_template('index.html', articles=articles)

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        # Проверяем хеш пароля
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль')
    return render_template('login.html')  

# Страница регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь уже существует')
            return redirect(url_for('register'))
        # Хешируем пароль
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Успешная регистрация')
        return redirect(url_for('login'))
    return render_template('register.html')

# Выход из системы
@app.route('/logout')
@login_required
def logout():
    logout_user()  # Выход пользователя
    return redirect(url_for('index'))

# Добавление статьи
@app.route('/add_article', methods=['GET', 'POST'])
@login_required
def add_article():
    if request.method == 'POST':
        name = request.form['name']
        tag = request.form['tag']
        if tag not in ALLOWED_TAGS:
            flash('Недопустимый тег. Выберите из списка.')
            return redirect(url_for('add_article'))
        text = request.form['text']
        registered = 'registered' in request.form
        time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        # Очищаем имя статьи
        sanitized_name = sanitize_filename(name)
        
        # Создаем путь к файлу
        path = f"articles/{time}_{sanitized_name}-{current_user.username}/main.md"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Сохраняем файл в UTF-8
        save_article_to_file(path, text)
        
        # Конвертируем Markdown в HTML
        convert_md_to_html(path)
        
        # Сохраняем статью в базе данных
        new_article = Article(author=current_user.username, name=name, tag=tag, registered=registered, path=path)
        db.session.add(new_article)
        db.session.commit()
        
        flash('Статья успешно добавлена')
        return redirect(url_for('index'))
    return render_template('add_article.html', allowed_tags=ALLOWED_TAGS)

# Редактирование статьи
@app.route('/edit_article/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_article(id):
    article = Article.query.get_or_404(id)  # Получаем статью по ID или возвращаем 404
    if article.author != current_user.username:
        flash('Вы не автор этой статьи')  # Сообщение, если пользователь не автор статьи
        return redirect(url_for('index'))
    if request.method == 'POST':
        article.name = request.form['name']
        article.tag = request.form['tag']
        if article.tag not in ALLOWED_TAGS:
            flash('Неверный тег, пожалуйста выберите из разрешенных')
            return redirect(url_for('edit_article', id=article.id))
        article.registered = 'registered' in request.form  # Обновляем поле registered
        text = request.form['text']
        with open(article.path, 'w') as f:
            f.write(text)  # Обновляем текст статьи в файле
        db.session.commit()
        convert_md_to_html(article.path)  # Конвертируем Markdown в HTML
        flash('Статья успешно обновленна')  # Сообщение об успешном обновлении статьи
        return redirect(url_for('index'))
    with open(article.path, 'r') as f:
        content = f.read()  # Читаем текущий текст статьи
    return render_template('edit_article.html', article=article, content=content, allowed_tags=ALLOWED_TAGS)

# Удаление статьи
@app.route('/delete_article/<int:id>', methods=['POST'])
@login_required
def delete_article(id):
    article = Article.query.get_or_404(id)  # Получаем статью по ID или возвращаем 404
    if article.author != current_user.username:
        flash('Вы должны быть автором чтобы удалить эту статью')  # Сообщение, если пользователь не автор статьи
        return redirect(url_for('index'))
    os.remove(article.path)  # Удаляем файл статьи
    path_to_html = article.path.rstrip(".md") + ".html"
    if os.path.exists(path_to_html):
        os.remove(path_to_html)  # Удаляем HTML-файл, если он существует
    db.session.delete(article)  # Удаляем статью из базы данных
    db.session.commit()
    flash('Статья успешно удаленна')  # Сообщение об успешном удалении статьи
    return redirect(url_for('index'))

# Просмотр статьи
@app.route('/article/<int:id>')
def view_article(id):
    article = Article.query.get_or_404(id)
    if article.registered and not current_user.is_authenticated:
        flash('Для просмотра этой статьи войдите в систему')
        return redirect(url_for('login'))
    path_to_html = article.path.rstrip(".md") + ".html"
    with open(path_to_html, 'r', encoding='utf-8') as f:
        content = f.read()
    content = fix_encoding(content)  # Исправляем кодировку
    return render_template('view_article.html', article=article, content=content)

# Фильтрация статей по тегу
@app.route('/tag/<string:tag>')
def articles_by_tag(tag):
    articles = Article.query.filter_by(tag=tag).all()  # Получаем все статьи с указанным тегом
    return render_template('index.html', articles=articles)

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы в базе данных, если они не существуют
    app.run(host='0.0.0.0', port=5000, debug=True)
