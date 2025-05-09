from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename



app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Конфигурация MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '********'
app.config['MYSQL_DB'] = 'rentify'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Секретный ключ для сессий
app.secret_key = 'your_secret_key_here'
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
mysql = MySQL(app)

@app.route('/')
def index():
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
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный email или пароль', 'danger')
    print(session)
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '')

        # Валидация
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
    # Здесь будет логика получения данных из БД
    # Пока используем статические данные для примера
    apartments_data = [
        {
            "id": 1,
            "title": "2-комн. квартира, 45 м²",
            "location": "Центральный район, ул. Ленина, 15",
            "price": 35000,
            "rooms": 2,
            "floor": "5/9",
            "area": 45,
            "image": "apartment1.jpg",
            "is_new": True
        },
        {
            "id": 2,
            "title": "1-комн. квартира, 32 м²",
            "location": "Свердловский район, ЖК 'Солнечный'",
            "price": 28000,
            "rooms": 1,
            "floor": "3/10",
            "area": 32,
            "image": "apartment2.jpg",
            "is_new": False
        }
        # Добавьте больше квартир по аналогии
    ]
    return render_template('apartments.html', apartments=apartments_data)

@app.route('/apartment/<int:apartment_id>')
def apartment_detail(apartment_id):
    # Здесь будет логика получения данных о конкретной квартире из БД
    # Пока используем статические данные для примера
    apartment = {
        "id": apartment_id,
        "title": "2-комн. квартира, 45 м²",
        "location": "Центральный район, ул. Ленина, 15",
        "price": 35000,
        "rooms": 2,
        "floor": "5/9",
        "area": 45,
        "image": "apartment1.jpg"
    }
    return render_template('apartment.html', apartment=apartment)


# Маршрут для страницы создания объявления
@app.route('/apartments/create', methods=['GET', 'POST'])
def create_apartment():
    if not session.get('loggedin'):
        flash('Для публикации объявления необходимо войти в систему', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = int(request.form['price'])
        rooms = int(request.form['rooms'])
        area = int(request.form['area'])
        floor = request.form['floor']
        address = request.form['address']
        district = request.form['district']

        # Обработка загрузки изображения
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                filename = secure_filename(image.filename)
                image_path = os.path.join('static', 'uploads', filename)
                image.save(image_path)
                image_url = f'uploads/{filename}'
            else:
                image_url = 'default-apartment.jpg'
        else:
            image_url = 'default-apartment.jpg'

        # Сохранение в БД
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            INSERT INTO apartments 
            (title, description, price, rooms, area, floor, address, district, image_url, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (title, description, price, rooms, area, floor, address, district, image_url, session['id']))
        mysql.connection.commit()

        flash('Объявление успешно опубликовано!', 'success')
        return redirect(url_for('apartments'))

    return render_template('create_apartment.html')


# Маршрут для просмотра своих объявлений
@app.route('/my-apartments')
def my_apartments():
    if not session.get('loggedin'):
        flash('Для просмотра ваших объявлений необходимо войти в систему', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM apartments WHERE owner_id = %s', (session['id'],))
    apartments = cursor.fetchall()

    return render_template('my_apartments.html', apartments=apartments)


@app.route('/apartment/<int:apartment_id>/edit', methods=['GET', 'POST'])
def edit_apartment(apartment_id):
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM apartments WHERE id = %s', (apartment_id,))
    apartment = cursor.fetchone()

    if not apartment or apartment['owner_id'] != session['id']:
        flash('У вас нет прав для редактирования этого объявления', 'danger')
        return redirect(url_for('my_apartments'))

    if request.method == 'POST':
        # Логика обновления данных
        pass

    return render_template('edit_apartment.html', apartment=apartment)


@app.route('/apartment/<int:apartment_id>/delete', methods=['POST'])
def delete_apartment(apartment_id):
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT owner_id FROM apartments WHERE id = %s', (apartment_id,))
    apartment = cursor.fetchone()

    if apartment and apartment['owner_id'] == session['id']:
        cursor.execute('DELETE FROM apartments WHERE id = %s', (apartment_id,))
        mysql.connection.commit()
        flash('Объявление успешно удалено', 'success')

    return redirect(url_for('my_apartments'))

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)