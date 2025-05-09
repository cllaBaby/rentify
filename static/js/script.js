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