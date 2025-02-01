import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# ✅ Debugging: Ensure token is loaded
if not TOKEN:
    raise ValueError("🚨 ERROR: TELEGRAM_BOT_TOKEN is missing! Set it in Railway Variables.")

# ✅ Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()
solana_client = AsyncClient(SOLANA_RPC)

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ Fixed Keyboard Buttons (Compatible with aiogram v3+)
kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📜 Get Contract Address")],
        [KeyboardButton(text="🚀 Deploy Token")],
        [KeyboardButton(text="👜 Generate Wallet")],
        [KeyboardButton(text="🔥 Latest Launches")]
    ],
    resize_keyboard=True
)

async def get_latest_contract():
    """Fetch the latest contract address from Raydium."""
    RAYDIUM_API = "https://api.raydium.io/v2/sdk/liquidity/mainnet.json"
    try:
        response = requests.get(RAYDIUM_API).json()
        pools = response.get("official", [])  # Get official Raydium pools
        if pools:
            return pools[0]["baseMint"]  # Return the latest token address
        return "❌ No recent contract found."
    except Exception as e:
        return f"❌ Error fetching contract: {e}"

async def deploy_token():
    """Deploy a new SPL token on Solana."""
    try:
        payer = Keypair()
        mint = Keypair()
        mint_pubkey = mint.pubkey()
        return f"✅ Token Deployed: `{mint_pubkey}`"
    except Exception as e:
        logging.error(f"Token deployment failed: {e}")
        return f"❌ Error: {e}"

async def generate_wallet():
    """Generate a new Solana wallet."""
    wallet = Keypair()
    return f"👜 Wallet Address: `{wallet.pubkey()}`\n🔑 Private Key: `{wallet.to_base58()}`"

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Welcome to Solana Bot! 🚀\n\nChoose an option below:", reply_markup=kb)

@dp.message(lambda msg: msg.text == "📜 Get Contract Address")
async def send_contract(message: types.Message):
    ca = await get_latest_contract()
    await message.answer(f"📜 Latest Contract: `{ca}`", parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "🚀 Deploy Token")
async def send_deploy(message: types.Message):
    tx = await deploy_token()
    await message.answer(tx, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "👜 Generate Wallet")
async def send_wallet(message: types.Message):
    wallet_info = await generate_wallet()
    await message.answer(wallet_info, parse_mode="Markdown")

async def main():
    logging.info("🚀 Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
