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


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })


send_telegram("✅ ETH charity token tracker is now online.")


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
                donor = event["args"]["from"]
                amount_raw = event["args"]["value"]
                amount = amount_raw / (10 ** decimals)
                tx_hash = event["transactionHash"].hex()

                message = f"""
🎉 <b>New Donation Received</b>

Amount: <b>{amount:,.4f} {symbol}</b>
From: <code>{donor}</code>

Tx:
https://etherscan.io/tx/{tx_hash}
"""
                send_telegram(message)

            last_block = current_block

        time.sleep(15)

    except Exception as e:
        print("Error:", e)
        time.sleep(30)
