// Избранное
document.querySelectorAll('.btn-favorites').forEach(btn => {
    btn.addEventListener('click', function() {
        const icon = this.querySelector('i');
        this.classList.toggle('active');
        icon.classList.toggle('far');
        icon.classList.toggle('fas');
    });
});

// Табы
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.getAttribute('data-tab');
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(tabId).classList.add('active');
    });
});

// Карта
function initMap() {
    const map = L.map('map').setView([56.0184, 92.8672], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    // Примеры меток
    L.marker([56.0184, 92.8672])
        .addTo(map)
        .bindPopup("Квартира в центре, 35 000 ₽/мес");

    L.marker([56.0356, 92.8932])
        .addTo(map)
        .bindPopup("Коттедж, Сосновый бор, 120 000 ₽/мес");
}

document.addEventListener('DOMContentLoaded', initMap);

// Калькулятор
document.getElementById('calculate-btn').addEventListener('click', () => {
    const price = parseFloat(document.getElementById('price').value);
    const months = parseInt(document.getElementById('months').value);

    if (price && months) {
        const total = price * months;
        const discount = total * 0.1;
        document.getElementById('result').innerHTML = `
            <p>Итого: ${total.toLocaleString('ru-RU')} ₽</p>
            <p>Со скидкой 10%: ${(total - discount).toLocaleString('ru-RU')} ₽</p>
        `;
    } else {
        alert('Заполните все поля!');
    }
});

// FAQ
document.querySelectorAll('.faq-question').forEach(question => {
    question.addEventListener('click', () => {
        const answer = question.nextElementSibling;
        question.classList.toggle('active');
        answer.classList.toggle('active');
    });
});

document.addEventListener('DOMContentLoaded', function() {
    // Функция обновления счетчика
    function updateNotificationBadge() {
        fetch('/notifications/json')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const badge = document.querySelector('.notification-badge');
                if (badge) {
                    badge.textContent = data.unread_count > 0 ? data.unread_count : '';
                    badge.style.display = data.unread_count > 0 ? 'flex' : 'none';
                }
            })
            .catch(error => {
                console.error('Error fetching notifications:', error);
            });
    }

    // Клик по колокольчику
    const notificationBell = document.querySelector('.btn-notification');
    if (notificationBell) {
        notificationBell.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = '/notifications';
        });
    }

    // Обновление каждые 2 минуты
    setInterval(updateNotificationBadge, 120000);
    updateNotificationBadge(); // Первоначальная загрузка
});
// Обработка вкладок
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // Удаляем активный класс у всех кнопок и контента
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        // Добавляем активный класс текущей кнопке и соответствующему контенту
        btn.classList.add('active');
        const tabId = btn.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
    });
});
// Обработка вкладок
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        // Удаляем активный класс у всех кнопок и контента
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        // Добавляем активный класс текущей кнопке и контенту
        this.classList.add('active');
        const tabId = this.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
    });
});

// Сохранение состояния фильтра при возврате
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('district') || urlParams.has('min_price') || urlParams.has('max_price')) {
        document.querySelector('.search-filters').scrollIntoView({
            behavior: 'smooth'
        });
    }
});
