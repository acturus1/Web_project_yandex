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
