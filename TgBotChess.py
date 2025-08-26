import telebot
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)


def send_tournament_results(link_next, tournament_date, top_players, spreadsheet_url):
    try:
        if not link_next:
            pass
        else:
            message = f"Ссылка на следующий турнир : {link_next}\n"
            message += f"\nРезультаты доступны по ссылке: \nhttps://docs.google.com/spreadsheets/d/1IirhmoGPCFm8cPO_mqShkGMnFKS211V0AIaIyvu2YLs"

            bot.send_message(CHAT_ID, message, timeout=10)
            return True
    except:
        raise Exception("")

