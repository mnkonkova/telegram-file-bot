# Telegram File Bot

Telegram-бот для управления файлами с AI-ассистентом на базе DeepSeek и векторным поиском.

## Возможности

- **Управление файлами** — загрузка, просмотр, скачивание, удаление через inline-кнопки
- **AI-агент** — отвечает на вопросы по содержимому файлов (DeepSeek + MCP filesystem)
- **Векторный поиск** — ChromaDB + DeepSeek embeddings для быстрого поиска по файлам
- **Авторизация** — админы управляют whitelist пользователей прямо через бота
- **Docker** — запуск одной командой

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню с кнопками |
| `/files` | Список файлов (кнопки: скачать / удалить) |
| `/cat <файл>` | Показать содержимое файла |
| `/delete <файл>` | Удалить файл |
| `/ask <вопрос>` | Задать вопрос AI по файлам |
| `/adduser @nick` | Добавить пользователя (админ) |
| `/removeuser @nick` | Удалить пользователя (админ) |
| `/users` | Список пользователей (админ) |

Также можно просто отправить текст — бот передаст его AI-агенту.
Отправка документа — сохраняет файл в хранилище.

## Запуск

```bash
cp .env.example .env
# заполнить токены в .env
docker compose up --build
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота из @BotFather |
| `DEEPSEEK_API_KEY` | API-ключ DeepSeek |
| `DEEPSEEK_BASE_URL` | URL API (по умолчанию `https://api.deepseek.com/v1`) |
| `DEEPSEEK_MODEL` | Модель (по умолчанию `deepseek-chat`) |
| `STORAGE_PATH` | Путь к хранилищу файлов |
| `DATA_PATH` | Путь к данным (индекс, ChromaDB, whitelist) |
| `MAX_AGENT_ITERATIONS` | Макс. итераций агента (по умолчанию 10) |

## Архитектура

```
Telegram <-> Bot (python-telegram-bot)
                  |
                  ├── File Manager (загрузка/удаление/просмотр)
                  |
                  ├── AI Agent (DeepSeek chat + function calling)
                  |     |
                  |     ├── Vector Search (ChromaDB + DeepSeek embeddings)
                  |     └── MCP Client (filesystem server через stdio)
                  |
                  └── Auth (admin whitelist в JSON)
```

## Стек

- Python 3.12, python-telegram-bot
- DeepSeek API (chat + embeddings)
- MCP filesystem server (Node.js)
- ChromaDB (векторная БД)
- Docker
