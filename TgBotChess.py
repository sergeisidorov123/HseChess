import telebot
import os


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

bot = telebot.TeleBot(TELEGRAM_TOKEN)


def send_tournament_results(tournament_date, top_players, spreadsheet_url):
    try:
        message = f"Призеры турнира ({tournament_date}):\n"
        for i, player in enumerate(top_players, 1):
            message += f"{i}. {player['username']}\n"

        message += f"\nРезультаты доступны по ссылке: \nhttps://docs.google.com/spreadsheets/d/1IirhmoGPCFm8cPO_mqShkGMnFKS211V0AIaIyvu2YLs/edit?gid=0#gid=0 "

        bot.send_message(CHAT_ID, message, timeout=10)
        return True
    except:
        raise Exception("")


if __name__ == "__main__":
    test_data = {
        "tournament_date": "2023-11-15",
        "top_players": [
            {"username": "Player1", "nb_games": 10},
            {"username": "Player2", "nb_games": 9},
            {"username": "Player3", "nb_games": 8}
        ],
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/test"
    }

    send_tournament_results(**test_data)