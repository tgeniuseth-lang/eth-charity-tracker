import os
import time
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

IMAGE_PATH = "banner.png"
TOTAL_FILE = "total.json"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]

token = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI)

decimals = token.functions.decimals().call()
symbol = token.functions.symbol().call()

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

    with open(IMAGE_PATH, "rb") as photo:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML"
            },
            files={"photo": photo}
        )

    print("Telegram status:", response.status_code, flush=True)
    print("Telegram response:", response.text, flush=True)


def send_telegram_text(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })


send_telegram_text("✅ ETHLABS donation tracker is now online.")

total_donations = load_total()

while True:
    try:
        current_block = w3.eth.block_number

        if current_block > last_block:
            events = token.events.Transfer.get_logs(
                from_block=last_block + 1,
                to_block=current_block,
                argument_filters={"to": DONATION_WALLET}
            )

            for event in events:
                amount_raw = event["args"]["value"]
                amount = amount_raw / (10 ** decimals)

                total_donations += amount
                save_total(total_donations)

                eth_price = get_eth_price()

                donation_usd = amount * eth_price
                total_usd = total_donations * eth_price

                caption = f"""
🧪 <b>ETHLABS - New Donation</b> 🧪

🎉 New Donation: <b>{amount:,.4f} {symbol}</b> ≈ <b>${donation_usd:,.2f}</b>
📈 Total Donations: <b>{total_donations:,.4f} {symbol}</b> ≈ <b>${total_usd:,.2f}</b>

🐦 Twitter: https://x.com/ethlabs_org?s=20
"""

                send_telegram_photo(caption)

            last_block = current_block

        time.sleep(60)

    except Exception as e:
        print("Error:", e, flush=True)
        time.sleep(60)
