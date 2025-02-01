import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# ✅ Ensure all required environment variables are set
if not TOKEN or not SOLANA_PRIVATE_KEY:
    raise ValueError("🚨 ERROR: Missing TELEGRAM_BOT_TOKEN or SOLANA_PRIVATE_KEY in environment variables.")

# ✅ Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()
solana_client = AsyncClient(SOLANA_RPC)

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ Trading settings
STOP_LOSS_PERCENT = 20  # Sell if price drops by 20%
TAKE_PROFIT_PERCENT = 100  # Sell if price increases by 100% (2x)
MIN_VOLUME = 500  # Minimum 500 SOL trading volume to snipe
tracked_tokens = {}  # Stores tokens and buy prices

# ✅ Keyboard Buttons (Telegram Control)
kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎯 Start Sniping")],
        [KeyboardButton(text="📜 View Recent Tokens")],
        [KeyboardButton(text="💰 Sell Tokens")],
    ],
    resize_keyboard=True
)

async def get_high_volume_tokens():
    """Fetch newly launched tokens with high volume from Pump.fun"""
    PUMPFUN_API = "https://pump.fun/api/latest_tokens"

    try:
        response = requests.get(PUMPFUN_API).json()
        tokens = response.get("tokens", [])
        
        # Filter tokens with trading volume > MIN_VOLUME
        high_volume_tokens = [
            token["mint_address"] for token in tokens if token["volume"] >= MIN_VOLUME
        ]

        return high_volume_tokens[:5]  # Return top 5 tokens
    except Exception as e:
        logging.error(f"Error fetching tokens: {e}")
        return []

async def get_sol_balance():
    """Check the bot's SOL balance."""
    async with AsyncClient(SOLANA_RPC) as client:
        balance = await client.get_balance(Keypair.from_base58_string(SOLANA_PRIVATE_KEY).pubkey())
        return balance['result']['value'] / 10**9  # Convert from lamports to SOL

async def buy_token(token_address, amount_in_sol):
    """Automatically buy a token on Pump.fun"""
    balance = await get_sol_balance()
    if balance < amount_in_sol:
        return f"❌ Insufficient SOL! Available: {balance} SOL, Required: {amount_in_sol} SOL"

    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        driver.get(f"https://pump.fun/token/{token_address}")
        await asyncio.sleep(2)

        buy_button = driver.find_element(By.XPATH, "//button[contains(text(),'Buy')]")
        buy_button.click()
        await asyncio.sleep(2)

        input_field = driver.find_element(By.NAME, "amount")
        input_field.send_keys(str(amount_in_sol))

        confirm_button = driver.find_element(By.XPATH, "//button[contains(text(),'Confirm')]")
        confirm_button.click()
        await asyncio.sleep(5)  # Wait for transaction to process

        driver.quit()

        # ✅ Store token and buy price for stop-loss tracking
        buy_price = await get_token_price(token_address)
        if buy_price:
            tracked_tokens[token_address] = buy_price

        return f"✅ Bought {amount_in_sol} SOL worth of {token_address}\n💰 Buy Price: {buy_price} SOL"
    except Exception as e:
        logging.error(f"Buy failed: {e}")
        return f"❌ Buy failed: {e}"

async def get_token_price(token_address):
    """Fetch current token price from Pump.fun API"""
    PUMPFUN_PRICE_URL = f"https://pump.fun/api/price/{token_address}"

    try:
        response = requests.get(PUMPFUN_PRICE_URL).json()
        return response.get("price", None)  # Return token price
    except Exception as e:
        logging.error(f"Error fetching price: {e}")
        return None

async def sell_token(token_address, amount):
    """Automatically sell a token on Pump.fun"""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        driver.get(f"https://pump.fun/token/{token_address}")
        await asyncio.sleep(2)

        sell_button = driver.find_element(By.XPATH, "//button[contains(text(),'Sell')]")
        sell_button.click()
        await asyncio.sleep(2)

        input_field = driver.find_element(By.NAME, "amount")
        input_field.send_keys(str(amount))

        confirm_button = driver.find_element(By.XPATH, "//button[contains(text(),'Confirm')]")
        confirm_button.click()
        await asyncio.sleep(5)  # Wait for transaction to process

        driver.quit()
        return f"✅ Sold {amount} of {token_address}"
    except Exception as e:
        logging.error(f"Sell failed: {e}")
        return f"❌ Sell failed: {e}"

async def check_take_profit():
    """Monitor token prices and auto-sell when price increases by 100% (2x)."""
    while True:
        for token, buy_price in tracked_tokens.items():
            current_price = await get_token_price(token)
            if current_price and current_price >= buy_price * (1 + TAKE_PROFIT_PERCENT / 100):
                logging.info(f"🚀 Take-profit triggered for {token} at {current_price} SOL")
                await sell_token(token, 100)  # Sell all tokens
                del tracked_tokens[token]  # Remove from tracking
        await asyncio.sleep(30)  # Check every 30 seconds

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Welcome to Pump.fun Sniper Bot! 🚀\n\nChoose an option below:", reply_markup=kb)

@dp.message(lambda msg: msg.text == "🎯 Start Sniping")
async def start_sniping(message: types.Message):
    """Start sniping for new high-volume tokens"""
    await message.answer("🔍 Searching for high-volume tokens...")
    tokens = await get_high_volume_tokens()

    if tokens:
        await message.answer(f"🎯 Found high-volume tokens: {tokens}")
        tx = await buy_token(tokens[0], 0.1)  # Buy first high-volume token
        await message.answer(tx)
    else:
        await message.answer("❌ No high-volume tokens found.")

@dp.message(lambda msg: msg.text == "📜 View Recent Tokens")
async def view_recent_tokens(message: types.Message):
    """Show recent tokens without buying"""
    tokens = await get_high_volume_tokens()
    if tokens:
        await message.answer(f"📜 High-Volume Tokens:\n" + "\n".join(tokens))
    else:
        await message.answer("❌ No high-volume tokens found.")

async def main():
    logging.info("🚀 Bot is starting...")
    asyncio.create_task(check_take_profit())  # Auto-sell at 2x price
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

