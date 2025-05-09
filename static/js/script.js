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

// Обработка вкладок в разделе "Популярные варианты"
document.addEventListener('DOMContentLoaded', function() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Удаляем активный класс у всех кнопок и контента
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Добавляем активный класс к выбранной кнопке и соответствующему контенту
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const notificationsBtn = document.getElementById('notificationsBtn');
    const notificationsMenu = document.getElementById('notificationsMenu');

    if (notificationsBtn && notificationsMenu) {
        // Загрузка уведомлений при открытии меню
        notificationsBtn.addEventListener('click', function(e) {
            e.stopPropagation();

            fetch('/notifications')
                .then(response => response.json())
                .then(data => {
                    const list = document.querySelector('.notifications-list');
                    list.innerHTML = '';

                    if (data.notifications.length > 0) {
                        data.notifications.forEach(notification => {
                            const item = document.createElement('a');
                            item.href = `/notification/${notification.id}`;
                            item.className = 'notification-item unread';
                            item.innerHTML = `
                                <div class="notification-icon">
                                    <i class="fas fa-envelope"></i>
                                </div>
                                <div class="notification-content">
                                    <p>${notification.message}</p>
                                    <small>${new Date(notification.created_at).toLocaleString()}</small>
                                </div>
                            `;
                            list.appendChild(item);
                        });
                    } else {
                        list.innerHTML = '<div class="notification-empty"><p>Нет новых уведомлений</p></div>';
                    }

                    notificationsMenu.classList.toggle('show');
                });
        });

        // Закрытие при клике вне меню
        document.addEventListener('click', function() {
            notificationsMenu.classList.remove('show');
        });

        // Предотвращаем закрытие при клике внутри меню
        notificationsMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
});
// Обновление счетчика уведомлений каждые 30 секунд
function updateNotificationCount() {
    if (document.getElementById('notificationsBtn')) {
        fetch('/notifications')
            .then(response => response.json())
            .then(data => {
                const badge = document.querySelector('.btn-notifications .badge');
                if (data.unread_count > 0) {
                    if (!badge) {
                        const newBadge = document.createElement('span');
                        newBadge.className = 'badge bg-danger';
                        newBadge.textContent = data.unread_count;
                        document.querySelector('.btn-notifications').appendChild(newBadge);
                    } else {
                        badge.textContent = data.unread_count;
                    }
                } else if (badge) {
                    badge.remove();
                }
            });
    }
}

// Первое обновление при загрузке страницы
updateNotificationCount();

// Периодическое обновление
setInterval(updateNotificationCount, 30000);