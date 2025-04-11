import telebot
import requests
import os

token = os.getenv('TOKEN')

if token == 'None':
    print(token)
    quit()

API_URL = "http://localhost:5000/api"

bot = telebot.TeleBot(token)

@bot.message_handler(commands=['help'])
def handle_start(message):
    text = (
        '/articles \n'
        '/article' '[id] \n'
        '/users \n'
        '/tags \n'
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['articles'])
def handle_articles(message):
    response = requests.get(f"{API_URL}/articles")
    if response.status_code == 200:
        articles = response.json()['articles']
        text = "\n".join([f"{article['title']}" for article in articles])
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, response.status_code)

@bot.message_handler(commands=['article'])
def handle_article(message):
    try:
        article_id = int(message.text.split()[1])
        response = requests.get(f"{API_URL}/articles/{article_id}")
        if response.status_code == 200:
            article = response.json()
            text = (
                f"{article['title']}\n"
                f"Автор: {article['author']}\n"
                f"Тег: {article['tag']}\n"
                f"Просмотры: {article['views']}\n"
                f"Лайки: {article['likes']}\n"
                f"Комментарии: {article['comments_count']}"
            )
        else:
            text = "Cтатья не найдена"
        
        bot.send_message(message.chat.id, text)
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "Укажите ID статьи: article [id]")

@bot.message_handler(commands=['users'])
def handle_users(message):
    response = requests.get(f"{API_URL}/users")
    if response.status_code == 200:
        users = response.json()['users']
        text = "\n".join([f"{user['username']}" for user in users])
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, response.status_code)

@bot.message_handler(commands=['tags'])
def handle_tags(message):
    response = requests.get(f"{API_URL}/tags")
    if response.status_code == 200:
        tags = response.json()
        text = "\n".join([f"{tag['name']}" for tag in tags])
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, response.status_code)

if __name__ == "__main__":
    bot.polling(none_stop=True)
    print('бот запущен')
