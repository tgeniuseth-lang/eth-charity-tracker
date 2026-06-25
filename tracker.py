import os
import time
import json
import requests
from web3 import Web3

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RPC_URL = os.getenv("RPC_URL")

TOKEN_ADDRESS = Web3.to_checksum_address(
    os.getenv("TOKEN_ADDRESS", "0x345aD3dd40c5a544d4f5459f75efc475FE96C5e1")
)
DONATION_WALLET = Web3.to_checksum_address(
    os.getenv("DONATION_WALLET", "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79")
)

TOTAL_FILE = "total.json"
IMAGE_URL = "https://ibb.co/bRzrbJw3"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
last_block = w3.eth.block_number


def get_eth_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        data = requests.get(url, timeout=10).json()
        return float(data["ethereum"]["usd"])
    except Exception:
        return 0


def load_total():
    if os.path.exists(TOTAL_FILE):
        with open(TOTAL_FILE, "r") as f:
            return json.load(f).get("total", 0)
    return 0


def save_total(total):
    with open(TOTAL_FILE, "w") as f:
        json.dump({"total": total}, f)


def send_telegram_photo(caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "photo": IMAGE_URL,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )

    print("Telegram status:", response.status_code, flush=True)
    print("Telegram response:", response.text, flush=True)


def send_telegram_text(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })

    print("Telegram status:", response.status_code, flush=True)
    print("Telegram response:", response.text, flush=True)


send_telegram_text("✅ ETHLABS ETH donation tracker is now online.")

total_donations = load_total()

while True:
    try:
        current_block = w3.eth.block_number

        if current_block > last_block:
            for block_number in range(last_block + 1, current_block + 1):
                block = w3.eth.get_block(block_number, full_transactions=True)
                print("Checking block:", block_number, flush=True)

                for tx in block.transactions:
                    if (
                        tx.to
                        and Web3.to_checksum_address(tx.to) == DONATION_WALLET
                        and tx["from"]
                        and Web3.to_checksum_address(tx["from"]) == TOKEN_ADDRESS
                    ):
                        amount_eth = w3.from_wei(tx.value, "ether")
                        if amount_eth > 0:
                            amount_eth = float(amount_eth)
                            total_donations += amount_eth
                            save_total(total_donations)

                            eth_price = get_eth_price()
                            donation_usd = amount_eth * eth_price
                            total_usd = total_donations * eth_price

                            caption = f"""
🧪 <b>ETHLABS - New Donation</b> 🧪

🎉 New Donation: <b>{amount_eth:,.4f} ETH</b> ≈ <b>${donation_usd:,.2f}</b>
📈 Total Donations: <b>{total_donations:,.4f} ETH</b> ≈ <b>${total_usd:,.2f}</b>

🐦 Twitter: https://x.com/ethlabs_org?s=20
"""

                            send_telegram_photo(caption)

            last_block = current_block

        time.sleep(60)

    except Exception as e:
        print("Error:", e, flush=True)
        time.sleep(60)
