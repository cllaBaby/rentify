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

app = Flask(__name__)
csrf = CSRFProtect(app)

# Конфигурация приложения
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'your_secret_key_here'  # Замените на реальный секретный ключ

# Конфигурация MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '19710907'
app.config['MYSQL_DB'] = 'rentify'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)


# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('loggedin'):
            flash('Для доступа к этой странице необходимо войти в систему', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_new_apartment(created_at):
    return datetime.now() - created_at < timedelta(days=3)


@app.template_filter('time_ago')
def time_ago_filter(dt):
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    if days > 0:
        return f"{int(days)} д. назад"
    elif hours > 0:
        return f"{int(hours)} ч. назад"
    elif minutes > 0:
        return f"{int(minutes)} мин. назад"
    else:
        return "только что"


@app.route('/')
def index():
    if session.get('loggedin'):
        # Получаем количество непрочитанных уведомлений для отображения в шапке
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
                       (session['id'],))
        unread_count = cursor.fetchone()['count']
        return render_template('index.html', unread_count=unread_count)
    return render_template('index.html')


@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account and check_password_hash(account['password_hash'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['phone'] = account.get('phone', '')
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный email или пароль', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '')

        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Некорректный email адрес', 'danger')
        elif not re.match(r'^[A-Za-z0-9_]+$', username):
            flash('Имя пользователя должно содержать только буквы, цифры и подчеркивания', 'danger')
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            account = cursor.fetchone()

            if account:
                flash('Аккаунт с таким email уже существует', 'danger')
            else:
                hashed_password = generate_password_hash(password)
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, phone)
                    VALUES (%s, %s, %s, %s)
                ''', (username, email, hashed_password, phone))
                mysql.connection.commit()
                flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
                return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/apartments')
def apartments():
    page = request.args.get('page', 1, type=int)
    per_page = 6

    # Параметры фильтрации
    district = request.args.get('district')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    sort = request.args.get('sort', 'newest')

    query = '''
        SELECT a.*, u.username 
        FROM apartments a
        JOIN users u ON a.owner_id = u.id
        WHERE 1=1
    '''
    params = []

    if district:
        query += ' AND a.district = %s'
        params.append(district)
    if min_price is not None:
        query += ' AND a.price >= %s'
        params.append(min_price)
    if max_price is not None:
        query += ' AND a.price <= %s'
        params.append(max_price)

    if sort == 'price_asc':
        query += ' ORDER BY a.price ASC'
    elif sort == 'price_desc':
        query += ' ORDER BY a.price DESC'
    elif sort == 'area':
        query += ' ORDER BY a.area DESC'
    else:
        query += ' ORDER BY a.created_at DESC'

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    count_query = 'SELECT COUNT(*) as total FROM (' + query + ') as t'
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']

    query += ' LIMIT %s OFFSET %s'
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    apartments_data = cursor.fetchall()

    for apartment in apartments_data:
        apartment['is_new'] = is_new_apartment(apartment['created_at'])

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

    return render_template('apartments.html',
                           apartments=apartments_data,
                           pagination=pagination if pagination['pages'] > 1 else None)


@app.route('/apartment/<int:apartment_id>')
def apartment_detail(apartment_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute('''
        SELECT a.*, u.username, u.phone as owner_phone 
        FROM apartments a
        JOIN users u ON a.owner_id = u.id
        WHERE a.id = %s
    ''', (apartment_id,))
    apartment = cursor.fetchone()

    if not apartment:
        flash('Объявление не найдено', 'danger')
        return redirect(url_for('apartments'))

    cursor.execute('SELECT * FROM apartment_photos WHERE apartment_id = %s', (apartment_id,))
    photos = cursor.fetchall()

    # Проверяем, есть ли непрочитанные уведомления для этого объявления
    unread_count = 0
    if session.get('loggedin'):
        cursor.execute('''
            SELECT COUNT(*) as count FROM notifications 
            WHERE user_id = %s AND apartment_id = %s AND is_read = 0
        ''', (session['id'], apartment_id))
        unread_count = cursor.fetchone()['count']

    return render_template('apartment.html', apartment=apartment, photos=photos, unread_count=unread_count)


@app.route('/send_contact_request', methods=['POST'])
@login_required
def send_contact_request():
    apartment_id = request.form['apartment_id']
    message = request.form['message']
    phone = request.form['phone']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Получаем владельца объявления
    cursor.execute('SELECT owner_id FROM apartments WHERE id = %s', (apartment_id,))
    apartment = cursor.fetchone()

    if not apartment:
        flash('Объявление не найдено', 'danger')
        return redirect(url_for('index'))

    # Сохраняем сообщение
    cursor.execute('''
        INSERT INTO messages (apartment_id, sender_id, message, phone, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    ''', (apartment_id, session['id'], message, phone))

    # Создаем уведомление с типом 'message'
    cursor.execute('''
        INSERT INTO notifications (user_id, apartment_id, type, created_at)
        VALUES (%s, %s, 'message', NOW())
    ''', (apartment['owner_id'], apartment_id))

    mysql.connection.commit()

    flash('Ваше сообщение отправлено владельцу!', 'success')
    return redirect(url_for('apartment_detail', apartment_id=apartment_id))


@app.route('/notifications')
@login_required
def notifications():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Получаем только непрочитанные уведомления для выпадающего списка
    cursor.execute('''
        SELECT n.*, a.title as apartment_title
        FROM notifications n
        LEFT JOIN apartments a ON n.apartment_id = a.id
        WHERE n.user_id = %s AND n.is_read = 0
        ORDER BY n.created_at DESC
        LIMIT 10
    ''', (session['id'],))
    notifications = cursor.fetchall()

    # Получаем количество непрочитанных
    cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0', (session['id'],))
    unread_count = cursor.fetchone()['count']

    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count
    })


@app.route('/notification/<int:notification_id>')
@login_required
def view_notification(notification_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Получаем полную информацию об уведомлении
    cursor.execute('''
        SELECT n.*, a.*, u.username as sender_username, 
               m.message as client_message, m.phone as client_phone,
               m.created_at as message_date
        FROM notifications n
        LEFT JOIN apartments a ON n.apartment_id = a.id
        LEFT JOIN messages m ON n.apartment_id = m.apartment_id AND m.sender_id != %s
        LEFT JOIN users u ON m.sender_id = u.id
        WHERE n.id = %s AND n.user_id = %s
        LIMIT 1
    ''', (session['id'], notification_id, session['id']))

    notification = cursor.fetchone()

    if not notification:
        flash('Уведомление не найдено', 'danger')
        return redirect(url_for('all_notifications'))

    # Помечаем как прочитанное
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = %s', (notification_id,))
    mysql.connection.commit()

    return render_template('notification_detail.html',
                           notification=notification,
                           time_ago=time_ago_filter)


@app.route('/notifications/all')
@login_required
def all_notifications():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Получаем все уведомления с текстами сообщений
    cursor.execute('''
        SELECT n.id, n.is_read, n.created_at, 
               a.id as apartment_id, a.title as apartment_title,
               m.message as client_message, m.phone as client_phone,
               u.username as sender_name
        FROM notifications n
        JOIN apartments a ON n.apartment_id = a.id
        JOIN messages m ON n.apartment_id = m.apartment_id
        JOIN users u ON m.sender_id = u.id
        WHERE n.user_id = %s AND n.type = 'message'
        ORDER BY n.created_at DESC
    ''', (session['id'],))

    notifications = cursor.fetchall()

    return render_template('notifications.html',
                           notifications=notifications,
                           time_ago=time_ago_filter)


@app.route('/notification/<int:notification_id>/detail')
@login_required
def notification_detail(notification_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Получаем уведомление и помечаем как прочитанное
    cursor.execute('''
        UPDATE notifications SET is_read = 1 
        WHERE id = %s AND user_id = %s
    ''', (notification_id, session['id']))

    # Получаем полную информацию об уведомлении и сообщении
    cursor.execute('''
        SELECT n.*, a.*, u.username as sender_username, 
               m.message as client_message, m.phone as client_phone,
               m.created_at as message_date
        FROM notifications n
        LEFT JOIN apartments a ON n.apartment_id = a.id
        LEFT JOIN messages m ON n.apartment_id = m.apartment_id AND m.sender_id != %s
        LEFT JOIN users u ON m.sender_id = u.id
        WHERE n.id = %s AND n.user_id = %s
        ORDER BY m.created_at DESC
        LIMIT 1
    ''', (session['id'], notification_id, session['id']))

    notification = cursor.fetchone()

    if not notification:
        flash('Уведомление не найдено', 'danger')
        return redirect(url_for('all_notifications'))

    mysql.connection.commit()

    return render_template('notification_detail.html',
                           notification=notification,
                           time_ago=time_ago_filter)


@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        UPDATE notifications 
        SET is_read = 1 
        WHERE user_id = %s
    ''', (session['id'],))
    mysql.connection.commit()

    flash('Все уведомления помечены как прочитанные', 'success')
    return redirect(url_for('all_notifications'))


@app.route('/apartments/create', methods=['GET', 'POST'])
@login_required
def create_apartment():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = int(request.form['price'])
        rooms = int(request.form['rooms'])
        area = int(request.form['area'])
        floor = request.form['floor']
        address = request.form['address']
        district = request.form['district']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            INSERT INTO apartments 
            (title, description, price, rooms, area, floor, address, district, owner_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ''', (title, description, price, rooms, area, floor, address, district, session['id']))
        apartment_id = cursor.lastrowid

        # Обработка загрузки изображений
        if 'photos' in request.files:
            for file in request.files.getlist('photos'):
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    cursor.execute('''
                        INSERT INTO apartment_photos (apartment_id, image_url)
                        VALUES (%s, %s)
                    ''', (apartment_id, filename))

        mysql.connection.commit()
        flash('Объявление успешно опубликовано!', 'success')
        return redirect(url_for('apartment_detail', apartment_id=apartment_id))

    return render_template('create_apartment.html')


@app.route('/my-apartments')
@login_required
def my_apartments():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT a.*, COUNT(m.id) as messages_count 
        FROM apartments a
        LEFT JOIN messages m ON a.id = m.apartment_id
        WHERE a.owner_id = %s
        GROUP BY a.id
    ''', (session['id'],))
    apartments = cursor.fetchall()

    # Получаем количество непрочитанных уведомлений
    cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0', (session['id'],))
    unread_count = cursor.fetchone()['count']

    return render_template('my_apartments.html', apartments=apartments, unread_count=unread_count)


@app.route('/apartment/<int:apartment_id>/delete', methods=['POST'])
@login_required
def delete_apartment(apartment_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT owner_id FROM apartments WHERE id = %s', (apartment_id,))
    apartment = cursor.fetchone()

    if apartment and apartment['owner_id'] == session['id']:
        # Удаляем связанные фотографии
        cursor.execute('SELECT image_url FROM apartment_photos WHERE apartment_id = %s', (apartment_id,))
        photos = cursor.fetchall()
        for photo in photos:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
            except:
                pass

        cursor.execute('DELETE FROM apartment_photos WHERE apartment_id = %s', (apartment_id,))
        cursor.execute('DELETE FROM apartments WHERE id = %s', (apartment_id,))
        mysql.connection.commit()
        flash('Объявление успешно удалено', 'success')

    return redirect(url_for('my_apartments'))


@app.route('/apartment/<int:apartment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_apartment(apartment_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM apartments WHERE id = %s', (apartment_id,))
    apartment = cursor.fetchone()

    if not apartment or apartment['owner_id'] != session['id']:
        flash('У вас нет прав для редактирования этого объявления', 'danger')
        return redirect(url_for('my_apartments'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = int(request.form['price'])
        rooms = int(request.form['rooms'])
        area = int(request.form['area'])
        floor = request.form['floor']
        address = request.form['address']
        district = request.form['district']

        cursor.execute('''
            UPDATE apartments 
            SET title = %s, description = %s, price = %s, rooms = %s, 
                area = %s, floor = %s, address = %s, district = %s
            WHERE id = %s
        ''', (title, description, price, rooms, area, floor, address, district, apartment_id))

        # Обработка новых фотографий
        if 'photos' in request.files:
            for file in request.files.getlist('photos'):
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    cursor.execute('''
                        INSERT INTO apartment_photos (apartment_id, image_url)
                        VALUES (%s, %s)
                    ''', (apartment_id, filename))

        mysql.connection.commit()
        flash('Объявление успешно обновлено!', 'success')
        return redirect(url_for('apartment_detail', apartment_id=apartment_id))

    cursor.execute('SELECT * FROM apartment_photos WHERE apartment_id = %s', (apartment_id,))
    photos = cursor.fetchall()

    # Получаем количество непрочитанных уведомлений
    cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0', (session['id'],))
    unread_count = cursor.fetchone()['count']

    return render_template('edit_apartment.html', apartment=apartment, photos=photos, unread_count=unread_count)


@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT p.* FROM apartment_photos p
        JOIN apartments a ON p.apartment_id = a.id
        WHERE p.id = %s AND a.owner_id = %s
    ''', (photo_id, session['id']))
    photo = cursor.fetchone()

    if photo:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url']))
        except:
            pass

        cursor.execute('DELETE FROM apartment_photos WHERE id = %s', (photo_id,))
        mysql.connection.commit()
        flash('Фотография удалена', 'success')

    return redirect(url_for('edit_apartment', apartment_id=photo['apartment_id']))


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    # Создаем папку для загрузок, если ее нет
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)