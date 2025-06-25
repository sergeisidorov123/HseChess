import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json
from collections import defaultdict
import TgBotChess

# Настройка таблицы
file = ""
url_Table = "https://docs.google.com/spreadsheets/d/1IirhmoGPCFm8cPO_mqShkGMnFKS211V0AIaIyvu2YLs/edit?gid=0#gid=0"

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
    header = worksheet.row_values(1)

    # СОздание таблицы
    if not header or header[0] != "Игрок":
        header = ["Игрок", "Призовые места"]
        worksheet.update('A1:B1', [header])

    # Добавление даты
    if tournament_date in header:
        date_col_index = header.index(tournament_date)
    else:
        date_col_index = len(header)
        worksheet.update_cell(1, date_col_index + 1, tournament_date)
        header.append(tournament_date)

    # Список игроков
    usernames = worksheet.col_values(1)[1:]
    name_to_row = {name: i + 2 for i, name in enumerate(usernames)}

    updates = []

    for player in results:
        username = player['username']
        rank = player['rank']
        played = player['played']  # 1 если >=5 игр, иначе 0

        if username not in name_to_row:
            # Добавление участников
            new_row = len(usernames) + 2
            name_to_row[username] = new_row
            usernames.append(username)

            # Обновление участников
            prize = 1 if rank <= 3 else 0
            updates.append({
                'range': f'A{new_row}:B{new_row}',
                'values': [[username, prize]]
            })
            # Участие в турнире
            updates.append({
                'range': gspread.utils.rowcol_to_a1(new_row, date_col_index + 1),
                'values': [[played]]
            })
        else:
            row = name_to_row[username]

            # Призовое место
            if rank <= 3:
                current_prize = worksheet.cell(row, 2).value
                try:
                    prize = int(current_prize) if current_prize else 0
                except:
                    prize = 0
                updates.append({
                    'range': f'B{row}',
                    'values': [[prize + 1]]
                })

            # Добавление в таблицу
            updates.append({
                'range': gspread.utils.rowcol_to_a1(row, date_col_index + 1),
                'values': [[played]]
            })

    # обновление таблицы
    if updates:
        worksheet.batch_update(updates)

# main
if __name__ == "__main__":
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IirhmoGPCFm8cPO_mqShkGMnFKS211V0AIaIyvu2YLs/edit"
    links = ["https://lichess.org/tournament/6BRXK21h"]

    for link in links:
        print(f"\nТурнир: {link}")
        try:
            results, date, top_players = process_tournament_link(link)
            update_sheet_with_results(results, date)

            # Телеграм
            TgBotChess.send_tournament_results(date, top_players, SPREADSHEET_URL)
            print(f"Турнир {link} обработан")
        except Exception as e:
            print({e})





# добавить тхт файл для турниров
# автоматическое добавление турниров
# добавить бота в беседу
# парсить турниры после их окончания
# добавить строчку с автоматом когда призовых более 10 или посещений более 30
