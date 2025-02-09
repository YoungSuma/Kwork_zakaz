import time
from threading import Thread
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Конфигурация
try:
    from config import token, id
except ModuleNotFoundError:
    if not os.path.exists('config.py'):
        with open('config.py', 'wt') as file:
            token = str(input('Введите токен от телеграм бота (Его можно получить у BotFather): '))
            id = str(input('Введите ID вашего аккаунта Telegram: '))
            file.write(f'token = "{token}"\nid = "{id}"')
        print('Файл config создан!')

def getSoupWithSelenium(url):
    """Получение объекта BeautifulSoup через Selenium."""
    options = Options()
    options.add_argument('--headless')  # Работа без графического интерфейса
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(5)  # Ждем загрузку контента
        soup = BeautifulSoup(driver.page_source, 'lxml')
        return soup
    except Exception as e:
        logging.error(f"Ошибка при использовании Selenium: {e}")
        return None
    finally:
        driver.quit()

def get_last_call():
    """Чтение последнего лога задач."""
    if not os.path.exists('lastOrder.log'):
        with open('lastOrder.log', 'wt', encoding='utf-8') as file:
            file.write('Start\n')
        logging.info("Файл lastOrder.log создан.")
    try:
        with open('lastOrder.log', 'rt', encoding='utf-8') as file:
            last_calls = set(file.read().splitlines())  # Используем set для уникальности
        logging.info(f"Загружены записи из lastOrder.log: {len(last_calls)} шт.")
        return last_calls
    except Exception as e:
        logging.error(f"Ошибка при чтении lastOrder.log: {e}")
        return set()

def save_last_call(orders):
    """Сохранение обработанных заказов в lastOrder.log."""
    with open('lastOrder.log', 'wt', encoding='utf-8') as file:
        file.write('\n'.join(orders))

def sendNotification(message):
    """Отправка уведомления в Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, data={
            "chat_id": int(id),
            "text": message,
            "parse_mode": "HTML"
        })
        if response.status_code == 200:
            logging.info("Уведомление успешно отправлено.")
        else:
            logging.error(f"Ошибка отправки сообщения: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")

def parsKwork():
    """Парсинг новых заказов с Kwork."""
    url = 'https://kwork.ru/projects?fc=41'  # Категория программирования

    logging.info("Использование Selenium для парсинга.")
    soup = getSoupWithSelenium(url)

    if not soup:
        logging.error("Не удалось получить данные с Kwork.")
        return

    # Находим все объявления
    orders = soup.find_all(class_='want-card want-card--list want-card--hover')  # Контейнер заказа
    logging.info(f"Найдено {len(orders)} заказов.")

    new_orders = []  # Список новых заказов для отправки
    processed_orders = set()  # Множество для хранения всех обработанных заказов

    for order in orders:
        try:
            # Извлекаем название заказа
            nameOrderElement = order.find(class_='wants-card__header-title breakwords pr250')  # Название заказа
            if not nameOrderElement:
                logging.warning("Не найден элемент с названием заказа. Пропускаем...")
                continue
            nameOrder = nameOrderElement.find('a').get_text(strip=True)
            urlOrder = 'https://kwork.ru' + nameOrderElement.find('a').get('href')

            # Извлекаем цену
            priceElement = order.find(class_='wants-card__price')  # Цена
            if not priceElement:
                logging.warning(f"Не найдена цена для заказа: {nameOrder}. Пропускаем...")
                continue
            priceText = priceElement.get_text(strip=True).replace('Желаемый бюджет: до', '').strip()
            priceNumber = int(''.join(filter(str.isdigit, priceText)))  # Извлекаем только цифры

            # Отладочный вывод
            logging.info(f"Обработка объявления: {nameOrder}, Цена: {priceNumber}")

            # Проверяем диапазон цены (от 500 до 100,000)
            min_price = 500
            max_price = 100000
            if min_price <= priceNumber <= max_price:
                processed_orders.add(nameOrder)  # Добавляем название в множество обработанных заказов

                # Проверяем, был ли проект уже обработан
                log = get_last_call()
                if nameOrder not in log:
                    # Формируем сообщение
                    text = f"""
На Kwork появилась новая задача!

Название: {nameOrder}
Цена: {priceText} ₽
Ссылка: {urlOrder}
                    """
                    new_orders.append(text)  # Добавляем новое объявление в список

        except (ValueError, AttributeError) as e:
            logging.error(f"Ошибка при обработке объявления: {e}. Детали: {order}")
            continue

    # Отправляем новые проекты в обратном порядке (последние приходят последними)
    for message in reversed(new_orders):
        sendNotification(message)

    # Сохраняем все обработанные проекты в файл
    save_last_call(processed_orders)

def startKwork():
    """Запуск бесконечного цикла парсинга Kwork."""
    print('Модуль парсинга Kwork запущен!')

    while True:
        try:
            parsKwork()
            time.sleep(600)  # Пауза между проверками
        except Exception as e:
            logging.error(f"Ошибка в основном цикле: {e}")
            time.sleep(120)  # Подождать перед повторной попыткой

def main():
    """Основная функция запуска программы."""
    print('Бот запускается...')
    threadKwork = Thread(target=startKwork)
    threadKwork.start()

if __name__ == "__main__":
    main()