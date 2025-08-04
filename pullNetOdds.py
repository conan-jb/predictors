import requests
from bs4 import BeautifulSoup
import csv
import re
import sys


def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
    
def fetch_soup(url):
    html = fetch_html(url)
    return BeautifulSoup(html, 'html.parser') if html else None

def extract_covers(soup):
    results = []
    for card in soup.select('.picked-games .total'):
        game = card.select_one('.game-name').get_text(strip=True)
        total = card.select_one('.total-line').get_text(strip=True)
        pick = card.select_one('.pick').get_text(strip=True)
        confidence = card.select_one('.confidence').get_text(strip=True) if card.select_one('.confidence') else ''
        gid = card.get('data-gameid', '')
        results.append((gid, game, total, pick, confidence))
    return results

def extract_actionnetwork(soup):
    results = []
    for pick in soup.select('.mlb-pick'):
        tag = pick.select_one('.pick-tag').text.lower()
        if 'total' in tag or 'over/under' in tag:
            gid = pick.get('data-gameid', '')
            game = pick.select_one('.game-teams').get_text(" @ ", strip=True)
            total = pick.select_one('.total-line').text.strip()
            pick_text = pick.select_one('.pick-side').text.strip()
            confidence = pick.select_one('.confidence-text').text.strip() if pick.select_one('.confidence-text') else ''
            results.append((gid, game, total, pick_text, confidence))
    return results

def extract_bettingpros(soup):
    results = []
    for item in soup.select('.pick-card'):
        if 'Over/Under' in item.text:
            gid = item.get('data-gameid', '')
            game = item.select_one('.teams').text.strip()
            total = item.select_one('.total-line').text.strip()
            pick = item.select_one('.pick-side').text.strip()
            confidence = item.select_one('.confidence').text.strip() if item.select_one('.confidence') else ''
            results.append((gid, game, total, pick, confidence))
    return results

def extract_pickdawgz(soup):
    results = []
    paragraphs = soup.find_all("p")

    for i, p in enumerate(paragraphs):
        text = p.get_text().strip()
        if not text:
            continue

        # Look for lines like: "I like the Over 8.5", or "Take the Under 9"
        match = re.search(r"(Over|Under)\s?(\d+\.\d+|\d+)", text, re.IGNORECASE)
        if match:
            pick = match.group(1).capitalize()
            total = match.group(2)
            # Try to get the game name from a nearby heading or the paragraph itself
            game = "Unknown"
            if i > 0:
                prev = paragraphs[i - 1].get_text().strip()
                if " vs " in prev:
                    game = prev
            if game == "Unknown":
                game_match = re.search(r"([A-Za-z\s]+) vs ([A-Za-z\s]+)", text)
                if game_match:
                    game = f"{game_match.group(1).strip()} vs {game_match.group(2).strip()}"
            game_id = re.sub(r'\W+', '', game)
            results.append((
                f"PDZ-{game_id}",  # Game ID
                game,
                total,
                pick,
                ""  # No confidence info
            ))

    return results


def extract_oddsshark(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Look for the picks table
    rows = soup.select("table tbody tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 5:
            game = cols[0].text.strip()
            total_text = cols[2].text.strip()
            prediction = cols[3].text.strip()

            # Only include totals picks
            if "Over" in prediction or "Under" in prediction:
                total = total_text.replace("O/U", "").strip()
                confidence = cols[4].text.strip() if len(cols) > 4 else ""
                game_id = re.sub(r'\W+', '', game)  # crude GameID fallback
                results.append({
                    "Source": "OddsShark",
                    "GameID": f"ODS-{game_id}",
                    "Game": game,
                    "Total": total,
                    "Pick": prediction,
                    "Confidence": confidence
                })
    return results

extractors = {
    'Covers': extract_covers,
    'OddsShark': extract_oddsshark,
    'ActionNetwork': extract_actionnetwork,
    'BettingPros': extract_bettingpros,
    'PickDawgz': extract_pickdawgz
}
# Source URLs
sources = {
    'Covers': 'https://www.covers.com/picks/mlb',
    'OddsShark': 'https://www.oddsshark.com/mlb/computer-picks',
    'ActionNetwork': 'https://www.actionnetwork.com/mlb/picks',
    'BettingPros': 'https://www.bettingpros.com/mlb/',
    'PickDawgz': 'https://pickdawgz.com/mlb-picks/'
}



def main():
    print("Source,GameID,Game,Total,Pick,Confidence")
    for src, url in sources.items():
        if src == 'OddsShark':
            html = fetch_html(url)
            if html:
                results = extract_oddsshark(html)
                for row in results:
                    print(f"{row['Source']},{row['GameID']},{row['Game']},{row['Total']},{row['Pick']},{row['Confidence']}")
        else:
            soup = fetch_soup(url)
            if soup:
                rows = extractors[src](soup)
                for gid, game, total, pick, confidence in rows:
                    print(f"{src},{gid},{game},{total},{pick},{confidence}")

if __name__ == "__main__":
    main()