import os
import time
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

DONATION_WALLET = os.getenv(
    "DONATION_WALLET",
    "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79"
).lower()

DONATION_SENDER = os.getenv(
    "DONATION_SENDER",
    "0x77AF91F7FE24f97Cf18Ac7Cb5e7F4c858cf10ff5"
).lower()

IMAGE_URL = os.getenv("IMAGE_URL", "https://ibb.co/bRzrbJw3")

TOTAL_FILE = "total.json"
SEEN_FILE = "seen.json"


def load_json(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
    except Exception as e:
        print("Load JSON error:", e, flush=True)
    return default


def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("Save JSON error:", e, flush=True)


def get_eth_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "ethereum",
            "vs_currencies": "usd"
        }
        data = requests.get(url, params=params, timeout=15).json()
        return float(data["ethereum"]["usd"])
    except Exception as e:
        print("Price error:", e, flush=True)
        return 0


def send_text(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=20
        )
        print("Telegram text:", r.status_code, r.text, flush=True)
    except Exception as e:
        print("Telegram text error:", e, flush=True)


def send_photo(caption):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        r = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "photo": IMAGE_URL,
                "caption": caption,
                "parse_mode": "HTML"
            },
            timeout=20
        )

        print("Telegram photo:", r.status_code, r.text, flush=True)

        if r.status_code != 200:
            send_text(caption)

    except Exception as e:
        print("Telegram photo error:", e, flush=True)
        send_text(caption)


def get_internal_transactions():
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

    data = requests.get(url, params=params, timeout=25).json()
    result = data.get("result", [])

    if not isinstance(result, list):
        print("Etherscan error:", data, flush=True)
        return []

    return result


def main():
    send_text("✅ ETHLABS internal donation tracker is online.")

    total_data = load_json(TOTAL_FILE, {"total": 0.0})
    seen = load_json(SEEN_FILE, [])

    if not isinstance(seen, list):
        seen = []

    while True:
        try:
            txs = get_internal_transactions()

            for tx in reversed(txs[:30]):
                tx_hash = tx.get("hash", "")

                if not tx_hash or tx_hash in seen:
                    continue

                from_addr = tx.get("from", "").lower()
                to_addr = tx.get("to", "").lower()
                value_wei = int(tx.get("value", "0"))
                value_eth = value_wei / 10**18

                if (
                    from_addr == DONATION_SENDER
                    and to_addr == DONATION_WALLET
                    and value_eth > 0
                ):
                    total_data["total"] = float(total_data.get("total", 0)) + value_eth

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

                seen.append(tx_hash)

            seen = seen[-500:]
            save_json(SEEN_FILE, seen)
            save_json(TOTAL_FILE, total_data)

            time.sleep(60)

        except Exception as e:
            print("Main loop error:", e, flush=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
