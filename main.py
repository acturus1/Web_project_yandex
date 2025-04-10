import os
import re
import shutil
from datetime import datetime
from functools import wraps
from flask import Flask, Blueprint, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from transliterate import translit
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import click
from convert import convert_md_to_html

# Конфигурация приложения
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Настройки базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'base_d')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'database.db')

os.makedirs(DATABASE_DIR, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки загрузки файлов
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Константы
ALLOWED_TAGS = ['Python', 'Flask', 'SQLite', 'Web Development', 'Tutorial']
DEFAULT_AVATAR = 'default_avatar.jpg'

# Вспомогательные функции
def sanitize_filename(filename):
    """Очищает имя файла, преобразует кириллицу и удаляет недопустимые символы."""
    filename = translit(filename, 'ru', reversed=True)
    return re.sub(r'[^\w\-]', '_', filename)

def allowed_file(filename):
    """Проверяет, что расширение файла разрешено."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_article_to_file(path, content):
    """Сохраняет содержимое статьи в файл с обработкой ошибок."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        app.logger.error(f"Ошибка при сохранении файла: {e}")
        raise

def admin_required(f):
    """Декоратор для проверки прав администратора."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    avatar = db.Column(db.String(200), default=DEFAULT_AVATAR)
    is_admin = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    tag = db.Column(db.String(50), nullable=False)
    registered = db.Column(db.Boolean, nullable=False)
    path = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='article', lazy=True, 
                             order_by="Comment.created_at.desc()")
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

# API Blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/articles', methods=['GET'])
def get_all_articles():
    """Получить список всех статей"""
    sort_by = request.args.get('sort_by', 'date')
    
    query = Article.query
    
    if sort_by == 'views':
        articles = query.order_by(Article.views.desc()).all()
    elif sort_by == 'likes':
        articles = query.order_by(Article.likes_count.desc()).all()
    elif sort_by == 'title':
        articles = query.order_by(Article.name.asc()).all()
    else: 
        articles = query.order_by(Article.created_at.desc()).all()
    
    articles_data = [{
        'id': article.id,
        'title': article.name,
        'author': article.author,
        'tag': article.tag,
        'views': article.views,
        'likes': article.likes_count,
        'created_at': article.created_at.isoformat(),
        'registered_only': article.registered
    } for article in articles]
    
    return jsonify({
        'articles': articles_data,
        'sort_by': sort_by,
        'total': len(articles)
    })

@api_bp.route('/articles/<int:article_id>', methods=['GET'])
def get_article_details(article_id):
    """Получить полную информацию о статье"""
    article = Article.query.get_or_404(article_id)
    
    return jsonify({
        'id': article.id,
        'title': article.name,
        'author': article.author,
        'tag': article.tag,
        'views': article.views,
        'likes': article.likes_count,
        'created_at': article.created_at.isoformat(),
        'registered_only': article.registered,
        'comments_count': len(article.comments)}
    )

# Пользователи 
@api_bp.route('/users', methods=['GET'])
def get_all_users():
    """Получить список всех пользователей с сортировкой"""
    sort_by = request.args.get('sort_by', 'username')
    
    query = User.query
    
    if sort_by == 'articles':
        subquery = db.session.query(
            Article.author,
            db.func.count(Article.id).label('articles_count')
        ).group_by(Article.author).subquery()
        
        users = query.outerjoin(
            subquery, 
            User.username == subquery.c.author
        ).order_by(db.desc('articles_count')).all()
    else: 
        users = query.order_by(User.username.asc()).all()
    
    users_data = [{
        'id': user.id,
        'username': user.username,
        'is_admin': user.is_admin,
        'articles_count': Article.query.filter_by(author=user.username).count()
    } for user in users]
    
    return jsonify({
        'users': users_data,
        'sort_by': sort_by,
        'total': len(users)
    })

# Теги
@api_bp.route('/tags', methods=['GET'])
def get_all_tags():
    """Получить список тегов с сортировкой по популярности"""
    tags_data = []
    
    for tag in ALLOWED_TAGS:
        count = Article.query.filter_by(tag=tag).count()
        tags_data.append({
            'name': tag,
            'articles_count': count
        })
    
    tags_data.sort(key=lambda x: x['articles_count'], reverse=True)
    
    return jsonify(tags_data)

app.register_blueprint(api_bp, url_prefix='/api')

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Маршруты приложения
@app.route('/')
def index():
    """Главная страница со списком статей."""
    sort_by = request.args.get('sort', 'newest')
    
    # Фильтрация статей для неавторизованных пользователей
    query = Article.query if current_user.is_authenticated else Article.query.filter_by(registered=False)
    
    # Сортировка статей
    if sort_by == 'views':
        articles = query.order_by(Article.views.desc()).all()
    elif sort_by == 'oldest':
        articles = query.order_by(Article.created_at.asc()).all()
    elif sort_by == 'likes':
        articles = query.order_by(Article.likes_count.desc()).all()
    else:  # По умолчанию - новые сначала
        articles = query.order_by(Article.created_at.desc()).all()
        
    return render_template('index.html', articles=articles, current_sort=sort_by)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь уже существует')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Успешная регистрация')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Выход из системы."""
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    """Перенаправление на профиль текущего пользователя."""
    return redirect(url_for('user_profile', username=current_user.username))

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Загрузка аватара пользователя."""
    if 'avatar' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

    file = request.files['avatar']
    
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

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

    # Генерация имени файла
    extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f"avatar_{current_user.id}.{extension}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Удаление старого аватара (если не дефолтный)
    if current_user.avatar != DEFAULT_AVATAR:
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
        app.logger.error(f"Ошибка загрузки аватара: {str(e)}")

    return redirect(url_for('profile'))

@app.route('/user/<username>')
def user_profile(username):
    """Страница профиля пользователя."""
    user = User.query.filter_by(username=username).first_or_404()
    
    # Получение статей пользователя с учетом доступа
    articles_query = Article.query.filter_by(author=username)
    if not current_user.is_authenticated:
        articles_query = articles_query.filter_by(registered=False)
    
    articles = articles_query.all()
    return render_template('profile.html', 
                         user=user, 
                         articles=articles,
                         is_owner=current_user == user)

@app.route('/add_article', methods=['GET', 'POST'])
@login_required
def add_article():
    """Добавление новой статьи."""
    if request.method == 'POST':
        name = request.form['name']
        tag = request.form['tag']
        text = request.form['text']
        registered = 'registered' in request.form
        
        if tag not in ALLOWED_TAGS:
            flash('Недопустимый тег. Выберите из списка.')
            return redirect(url_for('add_article'))
        
        # Создание пути для сохранения статьи
        time_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        sanitized_name = sanitize_filename(name)
        path = f"articles/{time_str}_{sanitized_name}-{current_user.username}/main.md"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Сохранение статьи
        save_article_to_file(path, text)
        convert_md_to_html(path)
        
        # Добавление статьи в базу данных
        new_article = Article(
            author=current_user.username,
            name=name,
            tag=tag,
            registered=registered,
            path=path
        )
        db.session.add(new_article)
        db.session.commit()
        
        flash('Статья успешно добавлена')
        return redirect(url_for('index'))
    
    return render_template('add_article.html', allowed_tags=ALLOWED_TAGS)

@app.route('/edit_article/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_article(id):
    """Редактирование существующей статьи."""
    article = Article.query.get_or_404(id)
    
    if article.author != current_user.username:
        flash('Вы не автор этой статьи')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        article.name = request.form['name']
        article.tag = request.form['tag']
        article.registered = 'registered' in request.form
        
        if article.tag not in ALLOWED_TAGS:
            flash('Неверный тег, пожалуйста выберите из разрешенных')
            return redirect(url_for('edit_article', id=article.id))
        
        # Обновление содержимого статьи
        save_article_to_file(article.path, request.form['text'])
        convert_md_to_html(article.path)
        db.session.commit()
        
        flash('Статья успешно обновленна')
        return redirect(url_for('index'))
    
    # Чтение текущего содержимого статьи
    with open(article.path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return render_template('edit_article.html', 
                         article=article, 
                         content=content, 
                         allowed_tags=ALLOWED_TAGS)

@app.route('/delete_article/<int:id>', methods=['POST'])
@login_required
def delete_article(id):
    """Удаление статьи."""
    article = Article.query.get_or_404(id)
    
    if article.author != current_user.username:
        flash('Вы должны быть автором чтобы удалить эту статью')
        return redirect(url_for('index'))
    
    # Удаление файлов статьи
    try:
        os.remove(article.path)
        html_path = article.path.rstrip(".md") + ".html"
        if os.path.exists(html_path):
            os.remove(html_path)
    except Exception as e:
        app.logger.error(f"Ошибка удаления файлов статьи: {str(e)}")
    
    # Удаление статьи из базы данных
    db.session.delete(article)
    db.session.commit()
    
    flash('Статья успешно удаленна')
    return redirect(url_for('index'))

@app.route('/article/<int:id>')
def view_article(id):
    """Просмотр статьи."""
    article = Article.query.get_or_404(id)
    
    # Проверка доступа к закрытым статьям
    if article.registered and not current_user.is_authenticated:
        flash('Для просмотра этой статьи войдите в систему')
        return redirect(url_for('login'))
    
    # Учет просмотров
    if current_user.is_authenticated:
        # Для авторизованных пользователей
        view_exists = ArticleView.query.filter_by(
            user_id=current_user.id,
            article_id=article.id
        ).first()
    else:
        # Для анонимных пользователей
        cookie_name = f'article_view_{article.id}'
        view_exists = request.cookies.get(cookie_name)
    
    # Увеличение счетчика просмотров
    if not view_exists:
        article.views += 1
        
        if current_user.is_authenticated:
            db.session.add(ArticleView(
                user_id=current_user.id,
                article_id=article.id
            ))
        
        db.session.commit()
    
    # Чтение содержимого статьи
    html_path = article.path.rstrip(".md") + ".html"
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        app.logger.error(f"Ошибка чтения файла статьи: {str(e)}")
        content = "<p>Ошибка загрузки содержимого статьи</p>"
    
    # Создание ответа с кукой для анонимных пользователей
    response = make_response(render_template(
        'view_article.html', 
        article=article, 
        content=content
    ))
    
    if not current_user.is_authenticated and not view_exists:
        response.set_cookie(
            f'article_view_{article.id}', 
            '1', 
            max_age=86400*7  # Кука на 7 дней
        )
    
    return response

@app.route('/tag/<string:tag>')
def articles_by_tag(tag):
    """Фильтрация статей по тегу."""
    articles = Article.query.filter_by(tag=tag).all()
    return render_template('index.html', articles=articles)

# Админ-панель
@app.route('/admin/articles')
@admin_required
def admin_articles():
    """Админ-панель: управление статьями."""
    articles = Article.query.all()
    users = User.query.all()
    return render_template('admin/articles.html', 
                         articles=articles,
                         users=users)

@app.route('/admin/delete_article/<int:id>', methods=['POST'])
@admin_required
def admin_delete_article(id):
    """Админ-панель: удаление статьи."""
    article = Article.query.get_or_404(id)
    
    try:
        # Удаление директории статьи
        article_dir = os.path.dirname(article.path)
        if os.path.exists(article_dir):
            shutil.rmtree(article_dir)
        
        db.session.delete(article)
        db.session.commit()
        flash('Статья удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении статьи', 'error')
        app.logger.error(f"Ошибка удаления статьи: {str(e)}")
    
    return redirect(url_for('admin_articles'))

@app.route('/admin/edit_article/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_article(id):
    """Админ-панель: редактирование статьи."""
    article = Article.query.get_or_404(id)
    
    if request.method == 'POST':
        article.name = request.form['name']
        article.tag = request.form['tag']
        article.registered = 'registered' in request.form
        
        save_article_to_file(article.path, request.form['text'])
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

# Комментарии
@app.route('/add_comment/<int:article_id>', methods=['POST'])
@login_required
def add_comment(article_id):
    """Добавление комментария к статье."""
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
    """Удаление комментария."""
    comment = Comment.query.get_or_404(comment_id)
    
    if current_user.id != comment.user_id and not current_user.is_admin:
        flash('Вы не можете удалить этот комментарий', 'error')
        return redirect(url_for('view_article', id=comment.article_id))
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Комментарий удален', 'success')
    return redirect(url_for('view_article', id=comment.article_id))

# Лайки
@app.route('/like_article/<int:article_id>', methods=['POST'])
@login_required
def like_article(article_id):
    """Обработка лайков/анлайков статей."""
    article = Article.query.get_or_404(article_id)
    
    like = ArticleLike.query.filter_by(
        user_id=current_user.id,
        article_id=article.id
    ).first()
    
    if like:
        # Удаление лайка
        db.session.delete(like)
        article.likes_count -= 1
        status = 'unliked'
    else:
        # Добавление лайка
        new_like = ArticleLike(
            user_id=current_user.id,
            article_id=article.id
        )
        db.session.add(new_like)
        article.likes_count += 1
        status = 'liked'
    
    db.session.commit()
    return jsonify({'status': status, 'likes': article.likes_count})

# CLI команды
@app.cli.command("create-admin")
@click.argument("username")
def create_admin(username):
    """Назначение прав администратора."""
    user = User.query.filter_by(username=username).first()
    
    if not user:
        click.echo(f"Пользователь {username} не найден")
        return
        
    user.is_admin = True
    db.session.commit()
    click.echo(f"Пользователь {username} теперь администратор")

@app.cli.command("list-users")
def list_users():
    """Список всех пользователей."""
    users = User.query.all()
    for user in users:
        status = "Админ" if user.is_admin else "Обычный"
        click.echo(f"{user.id}: {user.username} ({status})")

@app.cli.command("delete-user")
@click.argument("username")
def delete_user(username):
    """Удаление пользователя."""
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
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
