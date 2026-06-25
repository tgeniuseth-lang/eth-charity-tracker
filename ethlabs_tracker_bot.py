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
        self.ethlabs_wallet = "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79"
        self.last_known_balance = 0.0
        self.eth_price = 0.0
        # Public RPC endpoint (no key needed)
        self.rpc_url = "https://eth.public.blastapi.io"
        self.load_state()
        
    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.last_known_balance = state.get("last_known_balance", 0.0)
            except Exception as e:
                print(f"Error loading state: {e}")
    
    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "last_known_balance": self.last_known_balance
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
    
    def get_wallet_balance(self):
        """Get ETH balance using public RPC endpoint"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [self.ethlabs_wallet, "latest"],
                "id": 1
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "result" in data:
                    balance_wei = int(data["result"], 16)
                    balance_eth = balance_wei / 1e18
                    print(f"✅ Balance: {balance_eth:.4f} ETH (≈ ${balance_eth * self.eth_price:,.2f})")
                    return balance_eth
                else:
                    print(f"❌ RPC Error: {data}")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Exception: {type(e).__name__}: {e}")
            return None
    
    async def send_telegram_message(self, message):
        try:
            await self.bot.send_message(
                chat_id=self.telegram_channel_id,
                text=message,
                parse_mode="HTML"
            )
            print(f"✅ Telegram message sent")
        except TelegramError as e:
            print(f"Telegram error: {e}")
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def format_donation_message(self, donation_eth, total_eth):
        donation_usd = donation_eth * self.eth_price
        total_usd = total_eth * self.eth_price
        
        message = (
            "🧪 <b>ETHLABS - New Donation</b> 🧪\n\n"
            f"🎉 New Donation: {donation_eth:.4f} ETH ≈ ${donation_usd:,.2f}\n"
            f"📈 Total Donations: {total_eth:.4f} ETH ≈ ${total_usd:,.2f}\n\n"
            "🐦 Twitter: https://x.com/ethlabs_org?s=20"
        )
        return message
    
    async def check_donations(self):
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking wallet...")
        
        self.get_eth_price()
        print(f"ETH Price: ${self.eth_price:,.2f}")
        
        current_balance = self.get_wallet_balance()
        
        if current_balance is None:
            print("⚠️ Failed to fetch balance")
            return
        
        if current_balance > self.last_known_balance:
            new_donation = current_balance - self.last_known_balance
            print(f"🎉 New donation detected: {new_donation:.4f} ETH!")
            
            self.last_known_balance = current_balance
            self.save_state()
            
            message = self.format_donation_message(new_donation, current_balance)
            await self.send_telegram_message(message)
        else:
            print(f"No new donations (current: {current_balance:.4f} ETH)")
    
    async def run(self):
        print(f"🚀 Starting Ethlabs Donation Tracker")
        print(f"📍 Monitoring: {self.ethlabs_wallet}\n")
        
        while True:
            try:
                await self.check_donations()
            except Exception as e:
                print(f"Error: {e}")
            
            await asyncio.sleep(60)

async def main():
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    
    if not telegram_bot_token or not telegram_channel_id:
        print("❌ Missing TELEGRAM variables")
        return
    
    tracker = EthlabsTracker(telegram_bot_token, telegram_channel_id, None)
    await tracker.run()

if __name__ == "__main__":
    asyncio.run(main())
