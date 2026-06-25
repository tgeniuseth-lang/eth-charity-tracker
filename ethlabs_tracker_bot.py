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
    def __init__(self, bot_token, channel_id):
        self.bot = Bot(token=bot_token)
        self.telegram_channel_id = channel_id
        self.ethlabs_wallet = "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79"
        self.token_contract = "0x345aD3dd40c5a544d4f5459f75efc475FE96C5e1"
        self.last_block = None
        self.total_donations = 0.0
        self.eth_price = 0.0
        self.image_url = "https://ibb.co/bRzrbJw3"
        self.rpc_urls = [
            "https://rpc.ankr.com/eth",
            "https://eth-mainnet.public.blastapi.io",
            "https://cloudflare-eth.com"
        ]
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
    
    def get_current_block(self):
        """Get current block number"""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        
        for rpc_url in self.rpc_urls:
            try:
                response = requests.post(rpc_url, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        return int(data["result"], 16)
            except:
                continue
        
        return None
    
    def get_token_events(self):
        """Get Transfer events from token contract"""
        current_block = self.get_current_block()
        if not current_block:
            print("Could not get current block")
            return []
        
        start_block = self.last_block or (current_block - 100)  # Look back 100 blocks
        
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getLogs",
            "params": [{
                "fromBlock": hex(start_block),
                "toBlock": hex(current_block),
                "address": self.token_contract,
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer event signature
                ]
            }],
            "id": 1
        }
        
        for rpc_url in self.rpc_urls:
            try:
                response = requests.post(rpc_url, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        self.last_block = current_block
                        return data["result"]
            except Exception as e:
                print(f"  RPC failed: {type(e).__name__}")
                continue
        
        return []
    
    def get_wallet_balance(self):
        """Get wallet balance"""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [self.ethlabs_wallet, "latest"],
            "id": 1
        }
        
        for rpc_url in self.rpc_urls:
            try:
                response = requests.post(rpc_url, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        balance_wei = int(data["result"], 16)
                        balance_eth = balance_wei / 1e18
                        return balance_eth
            except:
                continue
        
        return None
    
    async def send_telegram_message(self, message):
        try:
            await self.bot.send_photo(
                chat_id=self.telegram_channel_id,
                photo=self.image_url,
                caption=message,
                parse_mode="HTML"
            )
            print(f"✅ Telegram message with image sent")
        except TelegramError as e:
            print(f"Telegram error: {e}")
            try:
                await self.bot.send_message(
                    chat_id=self.telegram_channel_id,
                    text=message,
                    parse_mode="HTML"
                )
            except:
                pass
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
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking token contract events...")
        
        self.get_eth_price()
        print(f"ETH Price: ${self.eth_price:,.2f}")
        
        # Get token transfer events
        events = self.get_token_events()
        print(f"📊 Token events found: {len(events)}")
        
        # Get current wallet balance
        wallet_balance = self.get_wallet_balance()
        if wallet_balance is None:
            print("⚠️ Could not fetch wallet balance")
            return
        
        print(f"💰 Wallet balance: {wallet_balance:.4f} ETH")
        
        if wallet_balance > self.total_donations:
            new_donation = wallet_balance - self.total_donations
            print(f"🎉 New donation detected: {new_donation:.4f} ETH!")
            
            self.total_donations = wallet_balance
            self.save_state()
            
            message = self.format_donation_message(new_donation, wallet_balance)
            await self.send_telegram_message(message)
        else:
            print(f"No new donations (tracked: {self.total_donations:.4f} ETH)")
    
    async def run(self):
        print(f"🚀 Starting Ethlabs Donation Tracker")
        print(f"📍 Token: {self.token_contract}")
        print(f"📍 Wallet: {self.ethlabs_wallet}\n")
        
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
    
    tracker = EthlabsTracker(telegram_bot_token, telegram_channel_id)
    await tracker.run()

if __name__ == "__main__":
    asyncio.run(main())
