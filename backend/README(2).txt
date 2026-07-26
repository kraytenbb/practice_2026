BookHub

BookHub — веб-приложение для поиска, хранения и чтения электронных книг.

Возможности

-   Регистрация и авторизация пользователей
-   Просмотр каталога книг
-   Поиск книг по названию и автору
-   Просмотр карточки книги
-   Чтение полного текста произведений
-   Личная библиотека пользователя
-   История чтения
-   Автоматическая загрузка книг через Gutendex API

Используемые технологии

Backend: - Python 3 - FastAPI - SQLAlchemy - Uvicorn

База данных: - PostgreSQL

Frontend: - HTML - CSS - JavaScript

Внешний сервис: - Gutendex API

Структура проекта

BookHub ├── backend │ ├── static │ ├── legacy │ ├── auth.py │ ├──
config.py │ ├── database.py │ ├── home_page.py │ ├──
load_gutendex_books.py │ ├── main.py │ ├── migrate_auth.py │ ├──
models.py │ ├── routes.py │ └── requirements.txt ├── frontend │ ├──
index.html │ ├── style.css │ └── script.js

Запуск проекта

1.  Создать виртуальное окружение.
2.  Установить зависимости: pip install -r requirements.txt
3.  Создать базу данных PostgreSQL и указать параметры подключения в
    config.py.
4.  Выполнить миграцию: python migrate_auth.py
5.  При необходимости загрузить книги: python load_gutendex_books.py
6.  Запустить сервер: uvicorn main:app –reload
7.  Открыть в браузере: http://127.0.0.1:8000

Автор

Проект разработан в учебных целях в рамках практики.

Лицензия

Книги импортируются из Project Gutenberg через Gutendex API и относятся
к общественному достоянию.
