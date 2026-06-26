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
        self.contract_address = "0x345aD3dd40c5a544d4f5459f75efc475FE96C5e1"
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
                    self.total_donations = state.get("total_donations", 0.0)
            except Exception as e:
                print(f"Error loading state: {e}")
    
    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
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
    
    def get_contract_donations_from_logs(self):
        """Query recent blocks for ETH transfers FROM contract TO wallet"""
        try:
            # Get latest block number first
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
                            latest_block = int(data["result"], 16)
                            
                            # Query last 5000 blocks for transactions
                            start_block = max(0, latest_block - 5000)
                            
                            # Query all transactions in recent blocks
                            total_eth = 0.0
                            
                            for block_num in range(start_block, latest_block + 1, 100):
                                end_block = min(block_num + 100, latest_block + 1)
                                total_eth += self.query_block_range(rpc_url, block_num, end_block)
                            
                            return total_eth
                except:
                    continue
        except Exception as e:
            print(f"Error querying logs: {e}")
        
        return None
    
    def query_block_range(self, rpc_url, start_block, end_block):
        """Query transactions in a block range"""
        total = 0.0
        try:
            for block_num in range(start_block, end_block):
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [hex(block_num), True],
                    "id": 1
                }
                
                response = requests.post(rpc_url, json=payload, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and data["result"] and "transactions" in data["result"]:
                        for tx in data["result"]["transactions"]:
                            # Check if transaction is FROM contract TO wallet
                            if (tx.get("from", "").lower() == self.contract_address.lower() and 
                                tx.get("to", "").lower() == self.ethlabs_wallet.lower()):
                                eth_value = int(tx.get("value", "0"), 16) / 1e18
                                total += eth_value
        except Exception as e:
            print(f"Error in block range query: {e}")
        
        return total
    
    async def send_telegram_message(self, message):
        channel_id_1 = os.getenv("TELEGRAM_CHANNEL_ID")
        if channel_id_1:
            try:
                await self.bot.send_photo(
                    chat_id=channel_id_1,
                    photo=self.image_url,
                    caption=message,
                    parse_mode="HTML"
                )
                print(f"✅ Message sent to channel 1")
            except Exception as e:
                print(f"Error sending to channel 1: {e}")
        
        channel_id_2 = os.getenv("TELEGRAM_CHANNEL_ID_2")
        if channel_id_2:
            try:
                await self.bot.send_photo(
                    chat_id=channel_id_2,
                    photo=self.image_url,
                    caption=message,
                    parse_mode="HTML"
                )
                print(f"✅ Message sent to channel 2")
            except Exception as e:
                print(f"Error sending to channel 2: {e}")
    
    def format_donation_message(self, new_donation_eth, total_donations_eth):
        new_donation_usd = new_donation_eth * self.eth_price
        total_donations_usd = total_donations_eth * self.eth_price
        
        message = (
            "🧪 <b>ETHLABS - New Donation</b> 🧪\n\n"
            f"🎉 Added This Minute: {new_donation_eth:.4f} ETH ≈ ${new_donation_usd:,.2f}\n"
            f"📈 Total Donated: {total_donations_eth:.4f} ETH ≈ ${total_donations_usd:,.2f}\n\n"
            "🐦 Twitter: https://x.com/ethlabscommu?s=21&t=YiY-bEame32rtiQ832XeFg"
        )
        return message
    
    async def check_donations(self):
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking donations from contract...")
        
        self.get_eth_price()
        print(f"ETH Price: ${self.eth_price:,.2f}")
        
        current_total = self.get_contract_donations_from_logs()
        
        if current_total is None:
            print("⚠️ Could not fetch contract donations")
            return
        
        print(f"💰 Total from contract (all time): {current_total:.4f} ETH")
        print(f"📊 Last recorded: {self.total_donations:.4f} ETH")
        
        if current_total > self.total_donations:
            new_donation = current_total - self.total_donations
            print(f"🎉 New donation from contract: {new_donation:.4f} ETH!")
            
            self.total_donations = current_total
            self.save_state()
            
            message = self.format_donation_message(new_donation, self.total_donations)
            await self.send_telegram_message(message)
        else:
            print(f"No new donations from contract this minute")
    
    async def run(self):
        print(f"🚀 Starting Ethlabs Contract Tracker (RPC eth_getLogs)")
        print(f"📍 Monitoring FROM: {self.contract_address}")
        print(f"📍 TO: {self.ethlabs_wallet}\n")
        
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
