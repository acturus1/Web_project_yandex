import os
from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from convert import convert_md_to_html 
import re
from transliterate import translit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import click
from functools import wraps
import shutil

def sanitize_filename(filename):
    # Переводим кириллицу в латиницу
    filename = translit(filename, 'ru', reversed=True)
    # Удаляем все недопустимые символы оставляем только буквы, цифры, дефисы и подчеркивания
    filename = re.sub(r'[^\w\-]', '_', filename)
    return filename

# Создаем директорию для базы данных

os.makedirs('base_d', exist_ok=True)

# Определяем базовую директорию и путь к базе данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'base_d', 'database.db')

# Создаем Flask-приложение
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Секретный ключ для сессий
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'  # Путь к базе данных
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем отслеживание изменений

# Добавляем настройки для загрузки файлов
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

# Создаем директорию для аватарок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    avatar = db.Column(db.String(200), default='default_avatar.jpg') # Аватар пользователя
    is_admin = db.Column(db.Boolean, default=False) # Права суперпользователя(админчика)
    comments = db.relationship('Comment', backref='author', lazy=True)

# Модель статьи
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор статьи
    author = db.Column(db.String(80), nullable=False)  # Автор статьи
    name = db.Column(db.String(120), nullable=False)  # Название статьи
    tag = db.Column(db.String(50), nullable=False)  # Тег статьи
    registered = db.Column(db.Boolean, nullable=False)  # Доступна ли статья только зарегистрированным пользователям
    path = db.Column(db.String(200), nullable=False)  # Путm к файлу статьи
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='article', lazy=True, order_by="Comment.created_at.desc()")
    views = db.Column(db.Integer, default=0)
    likes_count = db.Column(db.Integer, default=0)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'))

class ArticleView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'))
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'article_id', name='uix_user_article'),
    )

class ArticleLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # Возвращает пользователя по его ID

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Главная страница
@app.route('/')
def index():
    sort_by = request.args.get('sort', 'newest')
    
    query = Article.query if current_user.is_authenticated else Article.query.filter_by(registered=False)
    
    if sort_by == 'views':
        articles = query.order_by(Article.views.desc()).all()
    elif sort_by == 'oldest':
        articles = query.order_by(Article.created_at.asc()).all()
    elif sort_by == 'likes':
        articles = query.order_by(Article.likes_count.desc()).all()
    else: 
        articles = query.order_by(Article.created_at.desc()).all()
    if current_user.is_authenticated:
        articles = Article.query.all()
    else:
        articles = Article.query.filter_by(registered=False).all()
    return render_template('index.html', 
                         articles=articles,
                         current_sort=sort_by)

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

@app.route('/profile')
@login_required
def profile():
    return redirect(url_for('user_profile', username=current_user.username))

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

    file = request.files['avatar']
    
    # Проверка на пустой файл
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

    # Проверка типа файла
    if not allowed_file(file.filename):
        flash('Разрешены только файлы: png, jpg, jpeg, gif', 'error')
        return redirect(url_for('profile'))

    # Проверка размера файла
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > app.config['MAX_CONTENT_LENGTH']:
        flash('Файл слишком большой (максимум 2MB)', 'error')
        return redirect(url_for('profile'))

    # Генерация безопасного имени файла
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"avatar_{current_user.id}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Удаление старого аватара (если не дефолтный)
    if current_user.avatar != 'default_avatar.jpg':
        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_user.avatar)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)

    # Сохранение нового файла
    try:
        file.save(filepath)
        current_user.avatar = filename
        db.session.commit()
        flash('Аватар успешно обновлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при сохранении аватара', 'error')
        app.logger.error(f"Error saving avatar: {str(e)}")

    return redirect(url_for('profile'))

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    articles_query = Article.query.filter_by(author=username)
    
    # Фильтрация статей для неавторизованных пользователей
    if not current_user.is_authenticated:
        articles_query = articles_query.filter_by(registered=False)
    
    articles = articles_query.all()
    return render_template('profile.html', 
                         user=user, 
                         articles=articles,
                         is_owner=current_user == user)

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
    
    # Проверка доступа к закрытым статьям
    if article.registered and not current_user.is_authenticated:
        flash('Для просмотра этой статьи войдите в систему')
        return redirect(url_for('login'))
    
    # Проверка уникальности просмотра
    if current_user.is_authenticated:
        # Для авторизованных пользователей - проверка в базе данных
        view_exists = db.session.query(
            db.exists().where(
                (ArticleView.user_id == current_user.id) & 
                (ArticleView.article_id == article.id)
            )
        ).scalar()
    else:
        # Для анонимных пользователей - проверка куки
        cookie_name = f'article_view_{article.id}'
        view_exists = request.cookies.get(cookie_name)
    
    # Увеличиваем счетчик только для уникальных просмотров
    if not view_exists:
        article.views += 1
        db.session.commit()
        
        # Запоминаем просмотр
        if current_user.is_authenticated:
            new_view = ArticleView(user_id=current_user.id, article_id=article.id)
            db.session.add(new_view)
            db.session.commit()
    
    # Чтение содержимого статьи
    path_to_html = article.path.rstrip(".md") + ".html"
    with open(path_to_html, 'r', encoding='utf-8') as f:
        content = f.read()
    content = fix_encoding(content)
    
    # Создаем ответ и устанавливаем куку для анонимных пользователей
    response = make_response(render_template(
        'view_article.html', 
        article=article, 
        content=content
    ))
    
    if not current_user.is_authenticated and not view_exists:
        response.set_cookie(f'article_view_{article.id}', '1', max_age=86400*7)  # Кука на 7 дней
    
    return response

# Фильтрация статей по тегу
@app.route('/tag/<string:tag>')
def articles_by_tag(tag):
    articles = Article.query.filter_by(tag=tag).all()  # Получаем все статьи с указанным тегом
    return render_template('index.html', articles=articles)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/articles')
@admin_required
def admin_articles():
    articles = Article.query.all()
    users = User.query.all()
    return render_template('admin/articles.html', 
                         articles=articles,
                         users=users)

@app.route('/admin/delete_article/<int:id>', methods=['POST'])
@admin_required
def admin_delete_article(id):
    article = Article.query.get_or_404(id)
    # Удаление файлов статьи
    article_dir = os.path.dirname(article.path)
    if os.path.exists(article_dir):
        shutil.rmtree(article_dir)
    db.session.delete(article)
    db.session.commit()
    flash('Статья удалена', 'success')
    return redirect(url_for('admin_articles'))

@app.route('/admin/edit_article/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_article(id):
    article = Article.query.get_or_404(id)
    if request.method == 'POST':
        # Обновление данных статьи
        article.name = request.form['name']
        article.tag = request.form['tag']
        article.registered = 'registered' in request.form
        # Сохранение изменений в файл
        with open(article.path, 'w', encoding='utf-8') as f:
            f.write(request.form['text'])
        convert_md_to_html(article.path)
        db.session.commit()
        flash('Статья обновлена', 'success')
        return redirect(url_for('admin_articles'))
    
    with open(article.path, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('admin/edit_article.html',
                         article=article,
                         content=content,
                         allowed_tags=ALLOWED_TAGS)

@app.route('/add_comment/<int:article_id>', methods=['POST'])
@login_required
def add_comment(article_id):
    article = Article.query.get_or_404(article_id)
    text = request.form.get('text')
    
    if not text:
        flash('Комментарий не может быть пустым', 'error')
        return redirect(url_for('view_article', id=article_id))
    
    new_comment = Comment(
        text=text,
        user_id=current_user.id,
        article_id=article_id
    )
    db.session.add(new_comment)
    db.session.commit()
    
    flash('Комментарий добавлен', 'success')
    return redirect(url_for('view_article', id=article_id))

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    if current_user.id != comment.user_id and not current_user.is_admin:
        flash('Вы не можете удалить этот комментарий', 'error')
        return redirect(url_for('view_article', id=comment.article_id))
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Комментарий удален', 'success')
    return redirect(url_for('view_article', id=comment.article_id))

@app.route('/toggle_comment/<int:comment_id>')
@admin_required
def toggle_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = not comment.is_approved
    db.session.commit()
    return redirect(url_for('view_article', id=comment.article_id))

@app.route('/like_article/<int:article_id>', methods=['POST'])
@login_required
def like_article(article_id):
    article = Article.query.get_or_404(article_id)
    
    like = ArticleLike.query.filter_by(
        user_id=current_user.id,
        article_id=article.id
    ).first()
    
    if like:
        db.session.delete(like)
        article.likes_count -= 1
        db.session.commit()
        return jsonify({'status': 'unliked', 'likes': article.likes_count})
    else:
        new_like = ArticleLike(
            user_id=current_user.id,
            article_id=article.id
        )
        db.session.add(new_like)
        article.likes_count += 1
        db.session.commit()
        return jsonify({'status': 'liked', 'likes': article.likes_count})

@app.cli.command("create-admin")
@click.argument("username")
def create_admin(username):
    """Назначение прав администратора"""
    user = User.query.filter_by(username=username).first()
    
    if not user:
        click.echo(f"Пользователь {username} не найден")
        return
        
    user.is_admin = True
    db.session.commit()
    click.echo(f"Пользователь {username} теперь администратор")

@app.cli.command("list-users")
def list_users():
    """Список всех пользователей"""
    users = User.query.all()
    for user in users:
        status = "Админ" if user.is_admin else "Обычный"
        click.echo(f"{user.id}: {user.username} ({status})")

@app.cli.command("delete-user")
@click.argument("username")
def delete_user(username):
    """Удаление пользователя"""
    user = User.query.filter_by(username=username).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        click.echo(f"Пользователь {username} удален")
    else:
        click.echo(f"Пользователь {username} не найден")


# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы в базе данных, если они не существуют
    app.run(host='0.0.0.0', port=5000, debug=True)
