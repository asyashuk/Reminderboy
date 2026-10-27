import os
import threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from apscheduler.schedulers.background import BackgroundScheduler

# Отримуємо токен з змінних середовища Render
TOKEN = os.environ.get("8727485507:AAEV2YL1giD4La9Jwc3PtvXocuDCjsK9dN0")
bot = telebot.TeleBot(TOKEN)

# Словник для відстеження стану діалогу (наприклад, чи чекаємо ми на текст нагадування після "так")
user_states = {}

# Запускаємо фоновий планувальник для нагадувань
scheduler = BackgroundScheduler()
scheduler.start()


# Функція, яка відправляє нагадування в потрібний час
def send_reminder(chat_id, topic):
  bot.send_message(chat_id, f"⏰ Нагадую! Тобі потрібно: {topic}")


# --- ОБРОБНИК ПОВІДОМЛЕНЬ ---


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
  text = message.text.strip()
  text_lower = text.lower()
  chat_id = message.chat.id
  user_id = message.from_user.id

  # 1. Привіт / Так
  if text_lower in ["привіт", "hello", "hi"]:
    user_states[user_id] = "waiting_for_yes"
    bot.reply_to(message, "Привіт, хочеш зробити нагадування?")
    return

  if user_states.get(user_id) == "waiting_for_yes" and text_lower in [
      "так",
      "ага",
      "да",
  ]:
    user_states[user_id] = "waiting_for_reminder_params"
    bot.reply_to(message, "Очікую, забувашка 🤭")
    return

  # 2. Дякую
  if text_lower in ["дякую", "спасибі", "дякую тобі"]:
    bot.reply_to(message, "🥰")
    return

  # 3. "Я знову забула" (важливо перевіряти ДО загальної перевірки на "забула")
  if "я знову забула" in text_lower:
    bot.reply_to(
        message,
        "Сьогодні вам заборонено заходити в діс. Якщо не послухаєтесь, я"
        " перестану вам про все нагадувати.",
    )
    return

  # 4. "Я забула" (будь-який текст, що містить "забула")
  if "забула" in text_lower:
    bot.reply_to(message, "Ще раз забудеш - я почну тобі погрожувати.")
    return

  # 5. Обробка нагадувань: "Нагадай, щоб ... через ... хв/год" або "в HH:MM"
  # Приклад формату: "Нагадай, щоб купити хліб через 5 хв" або "Нагадай, щоб вимкнути праску в 23:50"
  if text_lower.startswith("нагадай"):
    try:
      # Простий парсинг формату: "Нагадай, щоб [тема] через [X] [хвилин/годин]"
      # Або на конкретний час в кінці
      if "через" in text_lower:
        parts = text.split("через")
        topic_part = parts[0].replace("Нагадай, щоб", "").replace("нагадай", "")
        time_part = parts[1].strip()   наприклад "5 хв" або "1 година"

        # Витягуємо число і одиницю виміру
        time_nums = "".join(filter(str.isdigit, time_part))
        if not time_nums:
          bot.reply_to(
              message,
              "Не зрозумів час. Напиши, наприклад: 'через 10 хв' або 'через 1"
              " год'",
          )
          return

        amount = int(time_nums)

        # Рахуємо час спрацювання
        if "год" in time_part or "годин" in time_part:
          run_time = datetime.now() + timedelta(hours=amount)
        else:  # за замовчуванням хвилини
          run_time = datetime.now() + timedelta(minutes=amount)

        scheduler.add_job(
            send_reminder,
            "date",
            run_date=run_time,
            args=[chat_id, topic_part.strip()],
        )
        bot.reply_to(
            message,
            f"Зрозуміло! Нагадаю про '{topic_part.strip()}' о"
            f" {run_time.strftime('%H:%M')}.",
        )
        return

      elif " в " in text_lower or " о " in text_lower:
        # Приклад: "Нагадай випити води в 23:50"
        separator = " в " if " в " in text_lower else " о "
        parts = text.split(separator)
        topic_part = parts[0].replace("Нагадай, щоб", "").replace("нагадай", "")
        time_str = parts[1].strip()  # наприклад "23:50"

        # Додаємо задачу на конкретний час сьогодні
        now = datetime.now()
        target_time = datetime.strptime(time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )

        if target_time < now:  # Якщо час вже минув сьогодні, ставимо на завтра
          target_time += timedelta(days=1)

        scheduler.add_job(
            send_reminder,
            "date",
            run_date=target_time,
            args=[chat_id, topic_part.strip()],
        )
        bot.reply_to(
            message,
            f"Зрозуміло! Нагадаю о {time_str}: '{topic_part.strip()}'",
        )
        return
      else:
        bot.reply_to(
            message,
            "Будь ласка, вкажіть час через 'через X хв' або 'в HH:MM'.",
        )
        return
    except Exception as e:
      bot.reply_to(
          message,
          "Ой, щось пішло не так при налаштуванні нагадування. Перевірте"
          " формат запису!",
      )
      return

  # Якщо бот не впізнав команду
  # (Можете залишити тут пусте місце або додати стандартну відповідь, якщо хочете)


# --- FLASK СЕРВЕР ДЛЯ RENDER (щоб бот не засинав) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is active!"


def run_flask():
  app.run(host="0.0.0.0", port=10000)


if __name__ == "__main__":
  # Запускаємо Flask у фоновому потоці
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.start()

  # Запускаємо самого Telegram бота
  bot.infinity_polling()
