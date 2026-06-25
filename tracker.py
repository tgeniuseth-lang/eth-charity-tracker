import os
import json
import requests
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # Your channel ID or chat ID
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHLABS_WALLET = "0xEa985CDf2616ccDf88e037c5b2d91134278d7d79"
CHECK_INTERVAL = 60  # 1 minute in seconds

# Storage for tracking donations
STATE_FILE = "ethlabs_state.json"

class EthlabsTracker:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.ethlabs_wallet = ETHLABS_WALLET.lower()
        self.last_block = None
        self.total_donations = 0.0
        self.eth_price = 0.0
        self.load_state()
        
    def load_state(self):
        """Load saved state from file"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.last_block = state.get("last_block")
                    self.total_donations = state.get("total_donations", 0.0)
            except Exception as e:
                print(f"Error loading state: {e}")
    
    def save_state(self):
        """Save current state to file"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "last_block": self.last_block,
                    "total_donations": self.total_donations
                }, f)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def get_eth_price(self):
        """Fetch current ETH price in USD from CoinGecko"""
        try:
            response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5)
            if response.status_code == 200:
                self.eth_price = response.json()["ethereum"]["usd"]
                return self.eth_price
        except Exception as e:
            print(f"Error fetching ETH price: {e}")
        return self.eth_price
    
    def get_wallet_balance(self):
        """Get current ETH balance of wallet via Etherscan"""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "balance",
                "address": self.ethlabs_wallet,
                "tag": "latest",
                "apikey": ETHERSCAN_API_KEY
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "1":
                    balance_wei = int(data["result"])
                    balance_eth = balance_wei / 1e18
                    return balance_eth
        except Exception as e:
            print(f"Error fetching wallet balance: {e}")
        return None
    
    def get_recent_transactions(self):
        """Fetch recent incoming transactions to wallet"""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": self.ethlabs_wallet,
                "startblock": self.last_block or 0,
                "endblock": 99999999,
                "sort": "asc",
                "apikey": ETHERSCAN_API_KEY
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
        """Send formatted message to Telegram"""
        try:
            await self.bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=message,
                parse_mode="HTML"
            )
            print(f"Message sent: {message}")
        except TelegramError as e:
            print(f"Telegram error: {e}")
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def format_donation_message(self, donation_eth):
        """Format a donation message"""
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
        """Main function to check for new donations"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for donations...")
        
        # Update ETH price
        self.get_eth_price()
        print(f"ETH Price: ${self.eth_price:,.2f}")
        
        # Get current wallet balance
        current_balance = self.get_wallet_balance()
        if current_balance is None:
            print("Failed to fetch wallet balance")
            return
        
        print(f"Wallet Balance: {current_balance:.4f} ETH")
        
        # Check if there's a new donation
        if current_balance > self.total_donations:
            new_donation = current_balance - self.total_donations
            print(f"✅ New donation detected: {new_donation:.4f} ETH")
            
            self.total_donations = current_balance
            self.save_state()
            
            # Send Telegram message
            message = self.format_donation_message(new_donation)
            await self.send_telegram_message(message)
        else:
            print("No new donations")
    
    async def run(self):
        """Run the tracker continuously"""
        print(f"Starting Ethlabs Donation Tracker")
        print(f"Monitoring wallet: {self.ethlabs_wallet}")
        print(f"Check interval: {CHECK_INTERVAL} seconds")
        
        while True:
            try:
                await self.check_donations()
            except Exception as e:
                print(f"Error in main loop: {e}")
            
            # Wait for next check
            await asyncio.sleep(CHECK_INTERVAL)

async def main():
    """Main entry point"""
    # Validate environment variables
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env file")
        return
    if not TELEGRAM_CHANNEL_ID:
        print("❌ TELEGRAM_CHANNEL_ID not set in .env file")
        return
    if not ETHERSCAN_API_KEY:
        print("❌ ETHERSCAN_API_KEY not set in .env file")
        return
    
    tracker = EthlabsTracker()
    await tracker.run()

if __name__ == "__main__":
    asyncio.run(main())
