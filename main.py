import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json
from collections import defaultdict
import TgBotChess
import pytz
import schedule


# Настройка таблицы
file = os.getenv('SERVICE_ACCOUNT_FILE')
url_Table = os.getenv('SPREADSHEET_URL')

# ПОдключение к таблице
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(file, scope)
gc = gspread.authorize(credentials)
sh = gc.open_by_url(url_Table)
worksheet = sh.get_worksheet(0)


# Получение кол-ва игр
def get_games_count_per_player(tournament_id):
    url = f"https://lichess.org/api/tournament/{tournament_id}/games"
    headers = {"Accept": "application/x-ndjson"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception({response.status_code})

    games_count = defaultdict(int)
    for line in response.text.strip().splitlines():
        game = json.loads(line)
        for color in ["white", "black"]:
            player_info = game.get("players", {}).get(color, {})
            username = player_info.get("user", {}).get("name")
            if username:
                username = username.lower()
                games_count[username] += 1

    return games_count


# Получение данных турнира
def fetch_tournament_data(tournament_id):
    base_url = f"https://lichess.org/api/tournament/{tournament_id}"

    # Запрос
    response = requests.get(base_url)
    if response.status_code != 200:
        raise Exception({response.status_code})

    try:
        first_page = response.json()
    except:
        raise Exception("")

    # Прогрузка всех страниц
    total_players = first_page.get("nbPlayers", 0)
    print(f"Общее количество игроков в турнире: {total_players}")

    all_players = first_page["standing"]["players"]
    total_pages = (total_players + 9) // 10

    for page_num in range(2, total_pages + 1):
        url = f"{base_url}?page={page_num}"
        response = requests.get(url)

        if response.status_code != 200:
            print({response.status_code})
            continue

        try:
            data = response.json()
            players = data.get("standing", {}).get("players", [])
            all_players.extend(players)
        except:
            raise Exception("")

        time.sleep(0.5)


    # Дата турнира
    starts_at_raw = first_page.get("startsAt")
    if isinstance(starts_at_raw, (int, float)):
        tournament_date = datetime.utcfromtimestamp(int(starts_at_raw) // 1000).strftime("%Y-%m-%d")
    elif isinstance(starts_at_raw, str):
        tournament_date = datetime.strptime(starts_at_raw, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    else:
        raise Exception("Неизвестный формат даты начала турнира")

    # Получение игр
    games_count_dict = get_games_count_per_player(tournament_id)

    # Обработка игроков
    results = []
    for player in all_players:
        username = player.get("username", player.get("name", "Unknown")).lower()
        rank = player.get("rank", 0)
        nb_games = games_count_dict.get(username, 0)
        played = 1 if nb_games >= 5 else 0

        results.append({
            "username": username,
            "rank": rank,
            "nb_games": nb_games,
            "played": played
        })

    return results, tournament_date


# Парс турнира
def process_tournament_link(link):
    tournament_id = link.split("/")[-1]
    players_raw, tournament_date = fetch_tournament_data(tournament_id)

    # Топ игроков
    top_players = sorted(players_raw, key=lambda x: x['rank'])[:3]

    # Добавление в массив
    results = []
    for player in players_raw:
        username = player['username']
        rank = player['rank']
        nb_games = player['nb_games']
        played = player['played']
        results.append({
            "username": username,
            "rank": rank,
            "nb_games": nb_games,
            "played": played
        })

    return results, tournament_date, top_players


def update_sheet_with_results(results, tournament_date):
    # Заголовки
    header = worksheet.row_values(1)

    # Базовые заголовки
    if not header or len(header) < 4:
        header = ["", "", "Игрок", "Призовые"]  # A, B, C, D
        worksheet.update(values='A1:D1', range_name=[header])
        header = worksheet.row_values(1)

    # Создаем заголовок для призовых если его нет
    if len(header) < 4 or header[3] != "Призовые":
        worksheet.update_cell(1, 4, "Призовые")  # Столбец D
        header = worksheet.row_values(1)

    # Добавление турнира со столбца Е(после фи и рейтинга)
    if tournament_date in header:
        date_col_index = header.index(tournament_date) + 1
    else:
        date_col_index = 5

        # Пустая колонка
        while date_col_index <= len(header) and header[date_col_index - 1]:
            date_col_index += 1

        worksheet.update_cell(1, date_col_index, tournament_date)
        header = worksheet.row_values(1)

    # Игроки
    usernames = worksheet.col_values(3)[1:]  # Колонка C
    name_to_row = {name.lower(): i + 2 for i, name in enumerate(usernames) if name}

    updates = []

    for player in results:
        username = player['username'].lower()
        rank = player['rank']
        played = player['played']

        if username not in name_to_row:
            # Добавляем нового игрока
            new_row = len(usernames) + 2
            name_to_row[username] = new_row
            usernames.append(username)

            # Добавляем ник в столбец C и призовые в столбец D
            prize = 1 if rank <= 3 else 0
            updates.append({
                'range': f'C{new_row}:D{new_row}',  # C - ник, D - призовые
                'values': [[username, prize]]
            })

            # Добавляем участие в турнире (начиная с E)
            updates.append({
                'range': f'{gspread.utils.rowcol_to_a1(new_row, date_col_index)}',
                'values': [[played]]
            })
        else:
            row = name_to_row[username]

            # Обновляем призовые места в столбце D
            if rank <= 3:
                current_prize = worksheet.cell(row, 4).value  # Столбец D
                try:
                    prize = int(current_prize) if current_prize else 0
                except:
                    prize = 0
                updates.append({
                    'range': f'D{row}',  # Столбец D
                    'values': [[prize + 1]]
                })

            # Добавляем участие в турнире (начиная с E)
            updates.append({
                'range': f'{gspread.utils.rowcol_to_a1(row, date_col_index)}',
                'values': [[played]]
            })

    # Обновляем таблицу
    if updates:
        worksheet.batch_update(updates)

# main
def main_func():
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IirhmoGPCFm8cPO_mqShkGMnFKS211V0AIaIyvu2YLs/edit"
    with open('tournaments.txt', 'r', encoding='utf-8') as file:
        link = file.readline().strip()

    with open('tournaments.txt', 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open('tournaments.txt', 'w', encoding='utf-8') as file:
        file.writelines(lines[1:])

    with open('tournaments.txt', 'r', encoding='utf-8') as file:
        link_next = file.readline().strip()


    try:
        results, date, top_players = process_tournament_link(link)
        update_sheet_with_results(results, date)

        # Телеграм
        TgBotChess.send_tournament_results(link_next, date, top_players, SPREADSHEET_URL)
        print(f"Турнир {link} обработан")
    except Exception as e:
        print({e})

if __name__ == "__main__":
    timezone = pytz.timezone('Asia/Yekaterinburg')
    schedule.every().day.at("20:00").do(main_func)


    print(f"Текущее время: {datetime.now(timezone)}")


    while True:
        schedule.run_pending()
        time.sleep(60)
        print(f"Текущее время: {datetime.now(timezone)}")



