import os
import time
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

DONATION_WALLET = "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79".lower()
DONATION_SENDER = "0x77AF91F7FE24f97Cf18Ac7Cb5e7F4c858cf10ff5".lower()

IMAGE_URL = "https://ibb.co/bRzrbJw3"
TOTAL_FILE = "total.json"
SEEN_FILE = "seen.json"


def get_eth_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        return requests.get(url, timeout=10).json()["ethereum"]["usd"]
    except:
        return 0


def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)


def send_photo(caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    r = requests.post(url, data={
        "chat_id": CHAT_ID,
        "photo": IMAGE_URL,
        "caption": caption,
        "parse_mode": "HTML"
    })
    print("Telegram:", r.status_code, r.text, flush=True)


def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })
    print("Telegram:", r.status_code, r.text, flush=True)


send_text("✅ ETHLABS internal donation tracker is online.")

total_data = load_json(TOTAL_FILE, {"total": 0})
seen = load_json(SEEN_FILE, [])

while True:
    try:
        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": DONATION_WALLET,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }

data = requests.get(url, params=params, timeout=20).json()

result = data.get("result", [])

if not isinstance(result, list):
    print("Etherscan error:", data, flush=True)
    time.sleep(60)
    continue

txs = result

        for tx in reversed(txs[:20]):
            tx_hash = tx.get("hash")

            if tx_hash in seen:
                continue

            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value_eth = int(tx.get("value", 0)) / 10**18

            if (
                from_addr == DONATION_SENDER
                and to_addr == DONATION_WALLET
                and value_eth > 0
            ):
                seen.append(tx_hash)
                total_data["total"] += value_eth

                eth_price = get_eth_price()
                donation_usd = value_eth * eth_price
                total_usd = total_data["total"] * eth_price

                caption = f"""
🧪 <b>ETHLABS - New Donation</b> 🧪

🎉 New Donation: <b>{value_eth:,.4f} ETH</b> ≈ <b>${donation_usd:,.2f}</b>
📈 Total Donations: <b>{total_data["total"]:,.4f} ETH</b> ≈ <b>${total_usd:,.2f}</b>

🐦 Twitter: https://x.com/ethlabs_org?s=20
"""

                send_photo(caption)

            if tx_hash not in seen:
                seen.append(tx_hash)

        seen = seen[-500:]
        save_json(SEEN_FILE, seen)
        save_json(TOTAL_FILE, total_data)

        time.sleep(60)

    except Exception as e:
        print("Error:", e, flush=True)
        time.sleep(60)
