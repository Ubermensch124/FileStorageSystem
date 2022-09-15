# Вступительное задание в Школу Бэкенд Разработки 2022

url с интерактивной документацией - https://perform-2058.usr.yandex-academy.ru/docs

Задача: реализовать api для файловой системы

**Использованные технологии:** 
- Python
- FastApi
- MongoDB
- Docker

**Инструкция:**
1. Убедиться, что у вас установлены Git, Docker, Docker-compose с помощью команд в терминале:
   - "git --version"
   - "docker --version"
   - "docker-compose --version"
2. Клонировать данный репозиторий
3. Перейти в директорию с файлом docker-compose-ci.yaml
4. Ввести команду "docker-compose -f docker-compose-ci.yaml up -d"
5. Теперь можно посылать запросы на адрес http://localhost:80/
6. Интерактивная документация FastApi расположена по адресу http://localhost:80/docs

После запуска контейнеров через docker-compose можно запустить **файл тестирования**. <br>
Для этого введите в терминале "python tests/start_test.py", если вы находитесь в корневой директории. В ином случае путь до файла будет другим.
