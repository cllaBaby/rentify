from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from math import ceil
from functools import wraps
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, List, Union

# Настройка приложения
app = Flask(__name__)
app.secret_key = os.urandom(24)

csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = os.urandom(24)
# Конфигурация
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or os.urandom(24),
    UPLOAD_FOLDER='static/uploads',
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB
    MYSQL_HOST='localhost',
    MYSQL_USER='root',
    MYSQL_PASSWORD='19710907',
    MYSQL_DB='rentify',
    MYSQL_CURSORCLASS='DictCursor'

)

# Инициализация MySQL
mysql = MySQL(app)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Типы данных
DBResult = Optional[Dict[str, Union[str, int, float, datetime]]]


# ======================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================
@app.template_filter('time_ago')
def time_ago_filter(dt):
    now = datetime.now()
    diff = now - dt

    periods = [
        ('год', 'года', 'лет'),
        ('месяц', 'месяца', 'месяцев'),
        ('день', 'дня', 'дней'),
        ('час', 'часа', 'часов'),
        ('минуту', 'минуты', 'минут')
    ]

    seconds = diff.total_seconds()
    if seconds < 60:
        return "только что"

    for i, (singular, dual, plural) in enumerate(periods):
        if i == 0:  # years
            duration = seconds / (365 * 24 * 60 * 60)
        elif i == 1:  # months
            duration = seconds / (30 * 24 * 60 * 60)
        elif i == 2:  # days
            duration = seconds / (24 * 60 * 60)
        elif i == 3:  # hours
            duration = seconds / (60 * 60)
        else:  # minutes
            duration = seconds / 60

        duration = int(duration)
        if duration > 0:
            if duration % 10 == 1 and duration % 100 != 11:
                return f"{duration} {singular} назад"
            elif 2 <= duration % 10 <= 4 and (duration % 100 < 10 or duration % 100 >= 20):
                return f"{duration} {dual} назад"
            else:
                return f"{duration} {plural} назад"

    return "давно"



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для доступа необходимо войти в систему', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Требуются права администратора', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated


def allowed_file(filename: str) -> bool:
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def is_new(created_at: datetime) -> bool:
    return datetime.now() - created_at < timedelta(days=3)


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))


def validate_password(password: str) -> bool:
    return len(password) >= 8 and any(c.isupper() for c in password) and any(c.isdigit() for c in password)


def save_uploaded_files(files, record_id: int, table: str):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        for file in files:
            if file and allowed_file(file.filename):
                filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                cursor.execute(f'''
                    INSERT INTO {table}_photos ({table}_id, image_url)
                    VALUES (%s, %s)
                ''', (record_id, filename))
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"File upload error: {str(e)}")
        raise
    finally:
        if cursor: cursor.close()


def execute_query(query: str, params: tuple = (), fetch_one: bool = False) -> Union[DBResult, List[DBResult]]:
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone() if fetch_one else cursor.fetchall()
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise
    finally:
        if cursor: cursor.close()


# ======================
# МАРШРУТЫ АУТЕНТИФИКАЦИИ
# ======================

@app.route('/')
def index():
    try:
        # Получаем 3 случайные квартиры
        apartments = execute_query('''
            SELECT a.id, a.title, a.price, a.district, 
                   (SELECT image_url FROM apartment_photos WHERE apartment_id = a.id LIMIT 1) as image_url
            FROM apartments a
            ORDER BY RAND()
            LIMIT 3
        ''')

        # Получаем 3 случайных гаража
        garages = execute_query('''
            SELECT g.id, g.title, g.price, g.district, 
                   (SELECT image_url FROM garage_photos WHERE garage_id = g.id LIMIT 1) as image_url
            FROM garages g
            ORDER BY RAND()
            LIMIT 3
        ''')

        # Для коттеджей (если есть соответствующая таблица)
        cottages = []  # Заглушка, если нет таблицы коттеджей

        unread_count = 0
        if 'user_id' in session:
            unread_count = execute_query(
                'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
                (session['user_id'],),
                fetch_one=True
            )['count']

        return render_template(
            'index.html',
            popular_apartments=apartments,
            popular_garages=garages,
            popular_cottages=cottages,
            unread_count=unread_count
        )
    except Exception as e:
        logger.error(f"Index page error: {str(e)}")
        return render_template('500.html'), 500

@app.route('/about')
def about():
    try:
        unread_count = 0
        if 'user_id' in session:
            unread_result = execute_query(
                'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
                (session['user_id'],),
                fetch_one=True
            )
            unread_count = unread_result['count'] if unread_result else 0

        return render_template('about.html', unread_count=unread_count)
    except Exception as e:
        logger.error(f"About page error: {str(e)}")
        return render_template('500.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Заполните все поля', 'danger')
            return redirect(url_for('login'))

        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['loggedin'] = True

                # Обновляем время последнего входа
                cursor.execute('UPDATE users SET last_login = NOW() WHERE id = %s', (user['id'],))
                mysql.connection.commit()

                flash('Вход выполнен успешно!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Неверный email или пароль', 'danger')
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('Ошибка сервера', 'danger')
        finally:
            cursor.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        errors = []
        if not validate_email(email):
            errors.append('Некорректный email')
        if not validate_password(password):
            errors.append('Пароль должен содержать 8+ символов, цифры и заглавные буквы')
        if len(username) < 3:
            errors.append('Имя пользователя слишком короткое')

        if errors:
            for error in errors: flash(error, 'danger')
            return redirect(url_for('register'))

        try:
            existing_user = execute_query(
                'SELECT id FROM users WHERE email = %s',
                (email,),
                fetch_one=True
            )

            if existing_user:
                flash('Email уже используется', 'danger')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            execute_query(
                '''
                INSERT INTO users (username, email, password_hash, phone, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ''',
                (username, email, hashed_password, phone)
            )
            mysql.connection.commit()

            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash('Ошибка регистрации', 'danger')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# ======================
# МАРШРУТЫ КВАРТИР
# ======================
@app.route('/apartments')
def apartments():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 6

        # Параметры фильтрации
        district = request.args.get('district')
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        sort = request.args.get('sort', 'newest')

        # Базовый запрос для данных
        query = '''
            SELECT a.*, u.username 
            FROM apartments a
            JOIN users u ON a.owner_id = u.id
            WHERE 1=1
        '''
        params = []

        # Фильтры
        if district:
            query += ' AND a.district = %s'
            params.append(district)
        if min_price is not None:
            query += ' AND a.price >= %s'
            params.append(min_price)
        if max_price is not None:
            query += ' AND a.price <= %s'
            params.append(max_price)

        # Сортировка
        if sort == 'price_asc':
            query += ' ORDER BY a.price ASC'
        elif sort == 'price_desc':
            query += ' ORDER BY a.price DESC'
        elif sort == 'area':
            query += ' ORDER BY a.area DESC'
        else:
            query += ' ORDER BY a.created_at DESC'

        # Получаем общее количество (для пагинации)
        count_query = 'SELECT COUNT(*) as total FROM apartments a WHERE 1=1'
        count_params = []

        if district:
            count_query += ' AND a.district = %s'
            count_params.append(district)
        if min_price is not None:
            count_query += ' AND a.price >= %s'
            count_params.append(min_price)
        if max_price is not None:
            count_query += ' AND a.price <= %s'
            count_params.append(max_price)

        total = execute_query(count_query, count_params, fetch_one=True)['total']

        # Получаем данные для текущей страницы
        query += ' LIMIT %s OFFSET %s'
        params.extend([per_page, (page - 1) * per_page])
        apartments_data = execute_query(query, params)

        # Загружаем фотографии для каждого объявления
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        for apartment in apartments_data:
            # Загружаем первую фотографию для превью
            cursor.execute('''
                SELECT image_url FROM apartment_photos 
                WHERE apartment_id = %s 
                ORDER BY id LIMIT 1
            ''', (apartment['id'],))
            photo = cursor.fetchone()
            apartment['photo'] = photo['image_url'] if photo else None

            # Помечаем новые объявления
            apartment['is_new'] = is_new(apartment['created_at'])

        cursor.close()

        # Пагинация
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': ceil(total / per_page),
            'has_prev': page > 1,
            'has_next': page * per_page < total,
            'prev_num': page - 1,
            'next_num': page + 1,
            'iter_pages': lambda: range(1, ceil(total / per_page) + 1)
        }

        return render_template(
            'apartments.html',
            apartments=apartments_data,
            pagination=pagination if pagination['pages'] > 1 else None,
            current_filters=request.args
        )

    except Exception as e:
        logger.error(f"Apartments list error: {str(e)}")
        flash('Ошибка при загрузке объявлений', 'danger')
        return redirect(url_for('index'))


@app.route('/apartment/<int:apartment_id>')
def apartment_detail(apartment_id: int):
    try:
        # Получаем информацию о квартире
        apartment = execute_query('''
            SELECT a.*, u.username, u.phone as owner_phone 
            FROM apartments a
            JOIN users u ON a.owner_id = u.id
            WHERE a.id = %s
        ''', (apartment_id,), fetch_one=True)

        if not apartment:
            flash('Объявление не найдено', 'danger')
            return redirect(url_for('apartments'))

        # Получаем фотографии квартиры
        photos = execute_query(
            'SELECT * FROM apartment_photos WHERE apartment_id = %s',
            (apartment_id,)
        )

        unread_count = 0
        if 'user_id' in session:
            # ИСПРАВЛЕННЫЙ ЗАПРОС - используем property_id вместо apartment_id
            unread_result = execute_query('''
                SELECT COUNT(*) as count FROM notifications 
                WHERE user_id = %s AND property_id = %s AND property_type = 'apartment' AND is_read = 0
            ''', (session['user_id'], apartment_id), fetch_one=True)
            unread_count = unread_result['count'] if unread_result else 0

        return render_template(
            'apartment.html',
            apartment=apartment,
            photos=photos,
            unread_count=unread_count
        )
    except Exception as e:
        logger.error(f"Apartment detail error: {str(e)}")
        flash('Ошибка при загрузке объявления', 'danger')
        return redirect(url_for('apartments'))


@app.route('/apartments/create', methods=['GET', 'POST'])
@login_required
def create_apartment():
    if request.method == 'POST':
        try:
            # Получаем данные формы
            form_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'price': int(request.form.get('price', 0)),
                'rooms': int(request.form.get('rooms', 1)),
                'area': int(request.form.get('area', 0)),
                'floor': request.form.get('floor', '').strip(),
                'address': request.form.get('address', '').strip(),
                'district': request.form.get('district', '').strip(),
                'owner_id': session['user_id']
            }

            # Валидация
            if not all(form_data.values()):
                flash('Все поля обязательны для заполнения', 'danger')
                return redirect(url_for('create_apartment'))

            if form_data['price'] <= 0 or form_data['area'] <= 0:
                flash('Цена и площадь должны быть положительными числами', 'danger')
                return redirect(url_for('create_apartment'))

            # Создаем запись
            execute_query('''
                INSERT INTO apartments 
                (title, description, price, rooms, area, floor, address, district, owner_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ''', tuple(form_data.values()))

            apartment_id = mysql.connection.insert_id()

            # Обрабатываем фото
            if 'photos' in request.files:
                save_uploaded_files(
                    request.files.getlist('photos'),
                    apartment_id,
                    'apartment'
                )

            mysql.connection.commit()
            flash('Объявление успешно опубликовано!', 'success')
            return redirect(url_for('apartment_detail', apartment_id=apartment_id))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Create apartment error: {str(e)}")
            flash('Ошибка при создании объявления', 'danger')
            return redirect(url_for('create_apartment'))

    return render_template('create_apartment.html')


@app.route('/apartment/<int:apartment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_apartment(apartment_id: int):
    try:
        apartment = execute_query(
            'SELECT * FROM apartments WHERE id = %s',
            (apartment_id,),
            fetch_one=True
        )

        if not apartment or apartment['owner_id'] != session['user_id']:
            flash('У вас нет прав для редактирования этого объявления', 'danger')
            return redirect(url_for('apartment'))

        if request.method == 'POST':
            form_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'price': int(request.form.get('price', 0)),
                'rooms': int(request.form.get('rooms', 1)),
                'area': int(request.form.get('area', 0)),
                'floor': request.form.get('floor', '').strip(),
                'address': request.form.get('address', '').strip(),
                'district': request.form.get('district', '').strip(),
                'id': apartment_id
            }

            if not all(form_data.values()):
                flash('Все поля обязательны для заполнения', 'danger')
                return redirect(url_for('edit_apartment', apartment_id=apartment_id))

            execute_query('''
                UPDATE apartments 
                SET title = %s, description = %s, price = %s, rooms = %s, 
                    area = %s, floor = %s, address = %s, district = %s
                WHERE id = %s
            ''', tuple(form_data.values()))

            if 'photos' in request.files:
                save_uploaded_files(
                    request.files.getlist('photos'),
                    apartment_id,
                    'apartment'
                )

            mysql.connection.commit()
            flash('Объявление успешно обновлено!', 'success')
            return redirect(url_for('apartment_detail', apartment_id=apartment_id))

        photos = execute_query(
            'SELECT * FROM apartment_photos WHERE apartment_id = %s',
            (apartment_id,)
        )

        unread_count = execute_query(
            'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
            (session['user_id'],),
            fetch_one=True
        )['count']

        return render_template(
            'edit_apartment.html',
            apartment=apartment,
            photos=photos,
            unread_count=unread_count
        )
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Edit apartment error: {str(e)}")
        flash('Ошибка при редактировании объявления', 'danger')
        return redirect(url_for('apartment'))


@app.route('/apartment/<int:apartment_id>/delete', methods=['POST'])
@login_required
def delete_apartment(apartment_id):
    if request.method == 'POST':
        try:
            # Проверка владельца
            apartment = execute_query(
                'SELECT owner_id FROM apartments WHERE id = %s',
                (apartment_id,),
                fetch_one=True
            )

            if apartment and apartment['owner_id'] == session['user_id']:
                # Удаление фотографий
                photos = execute_query(
                    'SELECT image_url FROM apartment_photos WHERE apartment_id = %s',
                    (apartment_id,)
                )

                for photo in photos:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
                    except OSError as e:
                        logger.error(f"Error deleting photo: {str(e)}")

                # Удаление из БД
                execute_query(
                    'DELETE FROM apartment_photos WHERE apartment_id = %s',
                    (apartment_id,)
                )
                execute_query(
                    'DELETE FROM apartments WHERE id = %s',
                    (apartment_id,)
                )
                mysql.connection.commit()
                flash('Объявление успешно удалено', 'success')

            return redirect(url_for('apartments'))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Delete apartment error: {str(e)}")
            flash('Ошибка при удалении объявления', 'danger')
            return redirect(url_for('apartments'))


@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id: int):
    try:
        photo = execute_query('''
            SELECT p.* FROM apartment_photos p
            JOIN apartments a ON p.apartment_id = a.id
            WHERE p.id = %s AND a.owner_id = %s
        ''', (photo_id, session['user_id']), fetch_one=True)

        if photo:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
            except OSError as e:
                logger.error(f"Error deleting photo: {str(e)}")

            execute_query(
                'DELETE FROM apartment_photos WHERE id = %s',
                (photo_id,)
            )
            mysql.connection.commit()
            flash('Фотография удалена', 'success')

        return redirect(url_for('edit_apartment', apartment_id=photo['apartment_id']))
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Delete photo error: {str(e)}")
        flash('Ошибка при удалении фотографии', 'danger')
        return redirect(url_for('apartment'))


# ======================
# МАРШРУТЫ ГАРАЖЕЙ (аналогично квартирам)
# ======================
@app.route('/garages')
def garages():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 6

        # Параметры фильтрации
        district = request.args.get('district')
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        vehicle_type = request.args.get('vehicle_type')
        has_power = request.args.get('has_power', type=int)

        # Базовый запрос
        query = '''
            SELECT g.*, u.username 
            FROM garages g
            JOIN users u ON g.owner_id = u.id
            WHERE 1=1
        '''
        params = []

        # Фильтры
        if district:
            query += ' AND g.district = %s'
            params.append(district)
        if min_price is not None:
            query += ' AND g.price >= %s'
            params.append(min_price)
        if max_price is not None:
            query += ' AND g.price <= %s'
            params.append(max_price)
        if vehicle_type:
            query += ' AND g.vehicle_type = %s'
            params.append(vehicle_type)
        if has_power is not None:
            query += ' AND g.has_power = %s'
            params.append(1 if has_power else 0)

        # Сортировка по умолчанию
        query += ' ORDER BY g.created_at DESC'

        # Получаем общее количество
        count_query = 'SELECT COUNT(*) as total FROM garages g WHERE 1=1'
        count_params = []

        if district:
            count_query += ' AND g.district = %s'
            count_params.append(district)
        if min_price is not None:
            count_query += ' AND g.price >= %s'
            count_params.append(min_price)
        if max_price is not None:
            count_query += ' AND g.price <= %s'
            count_params.append(max_price)
        if vehicle_type:
            count_query += ' AND g.vehicle_type = %s'
            count_params.append(vehicle_type)
        if has_power is not None:
            count_query += ' AND g.has_power = %s'
            count_params.append(1 if has_power else 0)

        total = execute_query(count_query, count_params, fetch_one=True)['total']

        # Получаем данные для текущей страницы
        query += ' LIMIT %s OFFSET %s'
        params.extend([per_page, (page - 1) * per_page])
        garages_data = execute_query(query, params)

        # Загружаем фотографии для каждого гаража
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        for garage in garages_data:
            cursor.execute('''
                SELECT image_url FROM garage_photos 
                WHERE garage_id = %s 
                ORDER BY id LIMIT 1
            ''', (garage['id'],))
            photo = cursor.fetchone()
            garage['photo'] = photo['image_url'] if photo else None
            garage['is_new'] = is_new(garage['created_at'])

        cursor.close()

        # Пагинация
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': ceil(total / per_page),
            'has_prev': page > 1,
            'has_next': page * per_page < total,
            'prev_num': page - 1,
            'next_num': page + 1,
            'iter_pages': lambda: range(1, ceil(total / per_page) + 1)
        }

        return render_template(
            'garages.html',
            garages=garages_data,
            pagination=pagination if pagination['pages'] > 1 else None,
            current_filters=request.args
        )

    except Exception as e:
        logger.error(f"Garages list error: {str(e)}")
        flash('Ошибка при загрузке гаражей', 'danger')
        return redirect(url_for('index'))


@app.route('/garage/<int:garage_id>')
def garage_detail(garage_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Получаем информацию о гараже
        cursor.execute('''
            SELECT g.*, u.username, u.phone as owner_phone 
            FROM garages g
            JOIN users u ON g.owner_id = u.id
            WHERE g.id = %s
        ''', (garage_id,))
        garage = cursor.fetchone()

        if not garage:
            flash('Гараж не найден', 'danger')
            return redirect(url_for('garages'))

        # Получаем фотографии гаража
        cursor.execute('SELECT * FROM garage_photos WHERE garage_id = %s', (garage_id,))
        photos = cursor.fetchall()

        return render_template('garage_detail.html', garage=garage, photos=photos)
    except Exception as e:
        logger.error(f"Garage detail error: {str(e)}")
        flash('Ошибка при загрузке информации о гараже', 'danger')
        return redirect(url_for('garages'))
    finally:
        cursor.close()


@app.route('/garages/create', methods=['GET', 'POST'])
@login_required
def create_garage():
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            form_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'price': int(request.form.get('price', 0)),
                'area': float(request.form.get('area', 0)),  # Изменено на float
                'address': request.form.get('address', '').strip(),
                'district': request.form.get('district', '').strip(),
                'height': float(request.form.get('height', 0)),
                'has_power': 1 if request.form.get('has_power') == 'on' else 0,  # Исправлено
                'security': request.form.get('security', '').strip(),
                'vehicle_type': request.form.get('vehicle_type', 'car'),
                'owner_id': session['user_id']
            }

            # Валидация данных
            if not all([form_data['title'], form_data['description'], form_data['address'], form_data['district']]):
                flash('Заполните все обязательные поля', 'danger')
                return redirect(url_for('create_garage'))

            if form_data['price'] <= 0 or form_data['area'] <= 0:
                flash('Цена и площадь должны быть положительными числами', 'danger')
                return redirect(url_for('create_garage'))

            cursor = mysql.connection.cursor()

            # Создаем запись о гараже
            cursor.execute('''
                INSERT INTO garages 
                (title, description, price, area, address, district, height, 
                 has_power, security, vehicle_type, owner_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ''', (
                form_data['title'],
                form_data['description'],
                form_data['price'],
                form_data['area'],
                form_data['address'],
                form_data['district'],
                form_data['height'],
                form_data['has_power'],
                form_data['security'],
                form_data['vehicle_type'],
                form_data['owner_id']
            ))
            garage_id = cursor.lastrowid
            # Обрабатываем загруженные фото
            if 'photos' in request.files:
                for file in request.files.getlist('photos'):
                    if file and allowed_file(file.filename):
                        filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)

                        cursor.execute('''
                            INSERT INTO garage_photos (garage_id, image_url)
                            VALUES (%s, %s)
                        ''', (garage_id, filename))

            mysql.connection.commit()
            flash('Объявление гаража успешно создано!', 'success')
            return redirect(url_for('garage_detail', garage_id=garage_id))
        except ValueError as e:
            mysql.connection.rollback()
            logger.error(f"Value error in create garage: {str(e)}")
            flash('Некорректные данные в форме. Проверьте числовые значения.', 'danger')
            return redirect(url_for('create_garage'))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Create garage error: {str(e)}")
            flash('Ошибка при создании объявления. Пожалуйста, проверьте введенные данные.', 'danger')
            return redirect(url_for('create_garage'))
        finally:
            cursor.close()

    return render_template('create_garage.html')




@app.route('/garage/<int:garage_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_garage(garage_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Проверяем владельца гаража
        cursor.execute('SELECT * FROM garages WHERE id = %s', (garage_id,))
        garage = cursor.fetchone()

        if not garage or garage['owner_id'] != session['user_id']:
            flash('У вас нет прав для редактирования этого гаража', 'danger')
            return redirect(url_for('garage_detail', garage_id=garage_id))

        if request.method == 'POST':
            # Обновляем данные гаража
            update_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'price': int(request.form.get('price', 0)),
                'area': int(request.form.get('area', 0)),
                'address': request.form.get('address', '').strip(),
                'district': request.form.get('district', '').strip(),
                'height': float(request.form.get('height', 0)),
                'has_power': 1 if request.form.get('has_power') == 'on' else 0,
                'security': request.form.get('security', '').strip(),
                'vehicle_type': request.form.get('vehicle_type', 'car'),
                'id': garage_id
            }

            cursor.execute('''
                UPDATE garages 
                SET title = %s, description = %s, price = %s, area = %s, 
                    address = %s, district = %s, height = %s, 
                    has_power = %s, security = %s, vehicle_type = %s
                WHERE id = %s
            ''', tuple(update_data.values()))

            # Добавляем новые фото
            if 'photos' in request.files:
                for file in request.files.getlist('photos'):
                    if file and allowed_file(file.filename):
                        filename = f"{datetime.now().timestamp()}_{secure_filename(file.filename)}"
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)

                        cursor.execute('''
                            INSERT INTO garage_photos (garage_id, image_url)
                            VALUES (%s, %s)
                        ''', (garage_id, filename))

            mysql.connection.commit()
            flash('Гараж успешно обновлен!', 'success')
            return redirect(url_for('garage_detail', garage_id=garage_id))

        # Получаем фотографии гаража
        cursor.execute('SELECT * FROM garage_photos WHERE garage_id = %s', (garage_id,))
        photos = cursor.fetchall()

        return render_template('edit_garage.html', garage=garage, photos=photos)
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Edit garage error: {str(e)}")
        flash('Ошибка при редактировании гаража', 'danger')
        return redirect(url_for('garage_detail', garage_id=garage_id))
    finally:
        cursor.close()


@app.route('/garage/<int:garage_id>/delete', methods=['POST'])
@login_required
def delete_garage(garage_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Проверяем владельца
        cursor.execute('SELECT owner_id FROM garages WHERE id = %s', (garage_id,))
        garage = cursor.fetchone()

        if garage and garage['owner_id'] == session['user_id']:
            # Удаляем фотографии гаража
            cursor.execute('SELECT image_url FROM garage_photos WHERE garage_id = %s', (garage_id,))
            photos = cursor.fetchall()

            for photo in photos:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
                except OSError as e:
                    logger.error(f"Error deleting garage photo: {str(e)}")

            cursor.execute('DELETE FROM garage_photos WHERE garage_id = %s', (garage_id,))
            cursor.execute('DELETE FROM garages WHERE id = %s', (garage_id,))
            mysql.connection.commit()
            flash('Гараж успешно удален', 'success')

        return redirect(url_for('garages'))
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Delete garage error: {str(e)}")
        flash('Ошибка при удалении гаража', 'danger')
        return redirect(url_for('garages'))
    finally:
        cursor.close()


@app.route('/delete_garage_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_garage_photo(photo_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Проверяем права на удаление
        cursor.execute('''
            SELECT gp.* FROM garage_photos gp
            JOIN garages g ON gp.garage_id = g.id
            WHERE gp.id = %s AND g.owner_id = %s
        ''', (photo_id, session['user_id']))
        photo = cursor.fetchone()

        if photo:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
            except OSError as e:
                logger.error(f"Error deleting garage photo: {str(e)}")

            cursor.execute('DELETE FROM garage_photos WHERE id = %s', (photo_id,))
            mysql.connection.commit()
            flash('Фотография удалена', 'success')

        return redirect(url_for('edit_garage', garage_id=photo['garage_id']))
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Delete garage photo error: {str(e)}")
        flash('Ошибка при удалении фотографии', 'danger')
        return redirect(url_for('garages_detail'))
    finally:
        cursor.close()


# ======================
# УВЕДОМЛЕНИЯ И СООБЩЕНИЯ
# ======================
@app.route('/send_contact_request', methods=['POST'])
@login_required
def send_contact_request():
    try:
        property_type = request.form.get('property_type')
        property_id = int(request.form.get('property_id', 0))
        message = request.form.get('message', '').strip()
        phone = request.form.get('phone', '').strip()

        if not all([property_type, property_id, message, phone]):
            flash('Заполните все обязательные поля', 'danger')
            return redirect(url_for('index'))

        # Проверяем существование объекта
        if property_type == 'apartment':
            property_data = execute_query(
                'SELECT owner_id FROM apartments WHERE id = %s',
                (property_id,),
                fetch_one=True
            )
        else:
            property_data = execute_query(
                'SELECT owner_id FROM garages WHERE id = %s',
                (property_id,),
                fetch_one=True
            )

        if not property_data:
            flash('Объявление не найдено', 'danger')
            return redirect(url_for('index'))

        # Сохраняем сообщение
        execute_query('''
            INSERT INTO messages (property_type, property_id, sender_id, message, phone, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        ''', (property_type, property_id, session['user_id'], message, phone))

        # Создаем уведомление
        execute_query('''
            INSERT INTO notifications (user_id, property_type, property_id, type, created_at)
            VALUES (%s, %s, %s, 'message', NOW())
        ''', (property_data['owner_id'], property_type, property_id))

        mysql.connection.commit()
        flash('Ваше сообщение отправлено владельцу!', 'success')

        if property_type == 'apartment':
            return redirect(url_for('apartment_detail', apartment_id=property_id))
        else:
            return redirect(url_for('garage_detail', garage_id=property_id))
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Send contact error: {str(e)}")
        flash('Ошибка при отправке сообщения', 'danger')
        return redirect(url_for('index'))


@app.route('/notifications')
@login_required
def notifications():
    try:
        # Получаем уведомления с названиями объектов
        notifications_data = execute_query('''
            SELECT n.id, n.property_type, n.property_id, n.type, n.is_read, n.created_at,
                   CASE 
                       WHEN n.property_type = 'apartment' THEN a.title
                       WHEN n.property_type = 'garage' THEN g.title
                   END as property_title
            FROM notifications n
            LEFT JOIN apartments a ON n.property_type = 'apartment' AND n.property_id = a.id
            LEFT JOIN garages g ON n.property_type = 'garage' AND n.property_id = g.id
            WHERE n.user_id = %s
            ORDER BY n.is_read ASC, n.created_at DESC
        ''', (session['user_id'],))

        # Считаем непрочитанные
        unread_count = execute_query(
            'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
            (session['user_id'],),
            fetch_one=True
        )['count']

        return render_template(
            'notifications.html',
            notifications=notifications_data,
            unread_count=unread_count
        )

    except Exception as e:
        logger.error(f"Notifications error: {str(e)}")
        flash('Ошибка при загрузке уведомлений', 'danger')
        return redirect(url_for('index'))


@app.route('/notifications/view/<int:notification_id>')
@login_required
def view_notification(notification_id):
    try:
        # Помечаем уведомление как прочитанное
        execute_query('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = %s AND user_id = %s
        ''', (notification_id, session['user_id']))
        mysql.connection.commit()

        # Получаем данные уведомления
        notification = execute_query('''
            SELECT property_type, property_id 
            FROM notifications 
            WHERE id = %s AND user_id = %s
        ''', (notification_id, session['user_id']), fetch_one=True)

        if not notification:
            flash('Уведомление не найдено', 'danger')
            return redirect(url_for('notifications'))

        # Редирект на соответствующее объявление
        if notification['property_type'] == 'apartment':
            return redirect(url_for('apartment_detail', apartment_id=notification['property_id']))
        else:
            return redirect(url_for('garage_detail', garage_id=notification['property_id']))

    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"View notification error: {str(e)}")
        flash('Ошибка при обработке уведомления', 'danger')
        return redirect(url_for('notifications'))

@app.route('/notification/<int:notification_id>')
@login_required
def notification_detail(notification_id):
    try:
        # Получаем уведомление
        notification = execute_query('''
            SELECT n.*, 
                   CASE 
                       WHEN n.property_type = 'apartment' THEN a.title
                       WHEN n.property_type = 'garage' THEN g.title
                   END as property_title
            FROM notifications n
            LEFT JOIN apartments a ON n.property_type = 'apartment' AND n.property_id = a.id
            LEFT JOIN garages g ON n.property_type = 'garage' AND n.property_id = g.id
            WHERE n.id = %s AND n.user_id = %s
        ''', (notification_id, session['user_id']), fetch_one=True)

        if not notification:
            flash('Уведомление не найдено', 'danger')
            return redirect(url_for('notifications'))

        # Помечаем как прочитанное
        execute_query('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = %s
        ''', (notification_id,))
        mysql.connection.commit()

        # Перенаправляем на соответствующее объявление
        if notification['property_type'] == 'apartment':
            return redirect(url_for('apartment_detail', apartment_id=notification['property_id']))
        else:
            return redirect(url_for('garage_detail', garage_id=notification['property_id']))

    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Notification detail error: {str(e)}")
        flash('Ошибка при обработке уведомления', 'danger')
        return redirect(url_for('notifications'))


@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    try:
        execute_query('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE user_id = %s AND is_read = 0
        ''', (session['user_id'],))
        mysql.connection.commit()
        flash('Все уведомления помечены как прочитанные', 'success')
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Mark all read error: {str(e)}")
        flash('Ошибка при обновлении уведомлений', 'danger')

    return redirect(url_for('notifications'))


# ======================
# ОБРАБОТЧИКИ ОШИБОК
# ======================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# ======================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ======================
if __name__ == '__main__':
    if not os.path.exists('static/uploads'):
        os.makedirs('static/uploads')
    app.run(debug=True)