@echo off
REM ═══════════════════════════════════════════════════════════
REM  JARVIS Backend — быстрый запуск (Windows)
REM  Запускайте из папки backend\
REM ═══════════════════════════════════════════════════════════

echo.
echo  ================================================
echo   JARVIS Backend — запуск
echo  ================================================
echo.

REM Проверяем наличие .env
if not exist ".env" (
  echo  [!] Файл .env не найден.
  echo  [!] Скопируйте .env.example в .env и заполните данные MySQL.
  echo.
  copy .env.example .env
  echo  [!] Создан .env из шаблона — заполните и запустите снова.
  pause
  exit /b 1
)

REM Создаём venv если не существует
if not exist "venv" (
  echo  [1/3] Создаю виртуальное окружение...
  python -m venv venv
)

REM Активируем и ставим зависимости
echo  [2/3] Устанавливаю зависимости...
call venv\Scripts\activate
pip install -r requirements.txt --quiet

REM Запускаем
echo  [3/3] Запускаю сервер на http://localhost:8000
echo.
echo  API документация: http://localhost:8000/api/docs
echo.
uvicorn main:app --reload --host 0.0.0.0 --port 8000
