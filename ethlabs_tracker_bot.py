import os
import json
import requests
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "ethlabs_state.json"

class EthlabsTracker:
    def __init__(self, bot_token, channel_id, api_key):
        self.bot = Bot(token=bot_token)
        self.telegram_channel_id = channel_id
        self.etherscan_api_key = api_key
        self.ethlabs_wallet = "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79"
        self.token_contract = "0x345aD3dd40c5a544d4f5459f75efc475FE96C5e1"
        self.last_block = None
        self.total_donations = 0.0
        self.eth_price = 0.0
        self.load_state()
        
    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.last_block = state.get("last_block")
                    self.total_donations = state.get("total_donations", 0.0)
            except Exception as e:
                print(f"Error loading state: {e}")
    
    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "last_block": self.last_block,
                    "total_donations": self.total_donations
                }, f)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def get_eth_price(self):
        try:
            response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5)
            if response.status_code == 200:
                self.eth_price = response.json()["ethereum"]["usd"]
                return self.eth_price
        except Exception as e:
            print(f"Error fetching ETH price: {e}")
        return self.eth_price
    
    def check_wallet_balance(self):
        """Check current ETH balance in wallet"""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "balance",
                "address": self.ethlabs_wallet,
                "tag": "latest",
                "apikey": self.etherscan_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "1":
                    balance_wei = int(data["result"])
                    balance_eth = balance_wei / 1e18
                    return balance_eth
        except Exception as e:
            print(f"Error checking balance: {e}")
        return None
    
    def get_all_incoming_transactions(self):
        """Get ALL ETH transfers to wallet (not just internal)"""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": self.ethlabs_wallet,
                "startblock": self.last_block or 0,
                "endblock": 99999999,
                "sort": "asc",
                "apikey": self.etherscan_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "1":
                    transactions = data["result"]
                    if transactions:
                        self.last_block = int(transactions[-1]["blockNumber"])
                        return transactions
        except Exception as e:
            print(f"Error fetching transactions: {e}")
        return []
    
    async def send_telegram_message(self, message):
        try:
            await self.bot.send_message(
                chat_id=self.telegram_channel_id,
                text=message,
                parse_mode="HTML"
            )
            print(f"✅ Message sent to Telegram")
        except TelegramError as e:
            print(f"Telegram error: {e}")
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def format_donation_message(self, donation_eth):
        donation_usd = donation_eth * self.eth_price
        total_usd = self.total_donations * self.eth_price
        
        message = (
            "🧪 <b>ETHLABS - New Donation</b> 🧪\n\n"
            f"🎉 New Donation: {donation_eth:.4f} ETH ≈ ${donation_usd:,.2f}\n"
            f"📈 Total Donations: {self.total_donations:.4f} ETH ≈ ${total_usd:,.2f}\n\n"
            "🐦 Twitter: https://x.com/ethlabs_org?s=20"
        )
        return message
    
    async def check_donations(self):
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking wallet: {self.ethlabs_wallet}")
        
        # Get ETH price
        self.get_eth_price()
        print(f"ETH Price: ${self.eth_price:,.2f}")
        
        # Check wallet balance
        balance = self.check_wallet_balance()
        if balance is not None:
            print(f"💰 Wallet Balance: {balance:.4f} ETH (≈ ${balance * self.eth_price:,.2f})")
        else:
            print(f"⚠️ Could not fetch wallet balance")
        
        # Get all transactions
        transactions = self.get_all_incoming_transactions()
        print(f"📊 Total transactions found: {len(transactions)}")
        
        if transactions:
            print("\n📋 Last 5 transactions:")
            for tx in transactions[-5:]:
                from_addr = tx.get("from", "N/A")[:10]
                value_wei = int(tx.get("value", 0))
                value_eth = value_wei / 1e18
                tx_hash = tx.get("hash", "N/A")[:10]
                print(f"  - From: {from_addr}... | Value: {value_eth:.4f} ETH | Hash: {tx_hash}...")
        else:
            print("⚠️ No transactions found. The wallet may not have received ETH yet.")
            print(f"   Make sure trades are happening on the token!")
    
    async def run(self):
        print(f"🚀 Starting Ethlabs Donation Tracker")
        print(f"📍 Monitoring wallet: {self.ethlabs_wallet}")
        print(f"📍 Token contract: {self.token_contract}")
        print(f"⏱️  Check interval: 60 seconds\n")
        
        while True:
            try:
                await self.check_donations()
            except Exception as e:
                print(f"Error in main loop: {e}")
            
            await asyncio.sleep(60)

async def main():
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    etherscan_api_key = os.getenv("ETHERSCAN_API_KEY")
    
    if not telegram_bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return
    if not telegram_channel_id:
        print("❌ TELEGRAM_CHANNEL_ID not set")
        return
    if not etherscan_api_key:
        print("❌ ETHERSCAN_API_KEY not set")
        return
    
    tracker = EthlabsTracker(telegram_bot_token, telegram_channel_id, etherscan_api_key)
    await tracker.run()

if __name__ == "__main__":
    asyncio.run(main())
