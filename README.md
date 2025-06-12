# Telegram Remove BG Bot

A powerful, feature-rich Telegram bot to remove image backgrounds for free. Includes referral rewards, premium upgrades, admin controls, multi-bot management, and stylish user experience. 

- 3 free uses per user per day (reset daily)
- Referral system (+1 use for both referrer and referee)
- Premium users: unlimited uses
- Admin broadcast, ban/unban, stats, and API key management
- Inline buttons: Download, Delete, Process Another, Share Bot, Help, My Stats, Create Your Own Bot
- SQLite user tracking
- Multi-bot management for admins
- Stylish user ID and name display

Deployable on Render, Railway, or any cloud platform. Powered by remove.bg or open-source background removal (rembg) for unlimited free use.

Admin: @in_yogeshwar (ID: 7176592290)

---

## Features
- Remove background from images sent as photos
- 3 free uses per user per day (reset daily)
- Referral system (+1 use for both referrer and referee)
- Premium users: unlimited uses
- Admin broadcast, ban/unban, stats, and API key management
- Inline buttons: Download, Delete, Process Another, Share Bot, Help, My Stats, Create Your Own Bot
- SQLite user tracking
- Multi-bot management for admins

---

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- [remove.bg](https://www.remove.bg/api) API key

### 2. Clone and Configure
```powershell
git clone <your-repo-url>
cd <your-repo-folder>
```

Create a `.env` file in the project folder:
```
BOT_TOKEN=your_telegram_bot_token
REMOVE_BG_API_KEY=your_removebg_api_key
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run Locally
```powershell
python bot.py
```

---

## Deploy on Render

1. Push your code to GitHub.
2. Go to [https://dashboard.render.com/](https://dashboard.render.com/)
3. Click **New +** → **Web Service**
4. Connect your GitHub and select your repo.
5. Set **Build Command**:  
   `pip install -r requirements.txt`
6. Set **Start Command**:  
   `python bot.py`
7. Add environment variables:
   - `BOT_TOKEN` (your Telegram bot token)
   - `REMOVE_BG_API_KEY` (your remove.bg API key)
8. Click **Create Web Service**.

---

## Admin Commands
- `/broadcast <msg>` — Send message to all users
- `/stats` — Show user stats
- `/ban <user_id>` — Ban user
- `/unban <user_id>` — Unban user
- `/setbgapi <api_key>` — Change Remove.bg API key
- `/grantpremium <user_id>` — Grant premium
- `/addbot <bot_username> <api_key>` — Register another bot
- `/setbotapi <bot_username> <api_key>` — Update API key for another bot
- `/listbots` — List all managed bots

## User Commands
- `/start` — Start the bot
- `/help` — Show help
- `/upgrade` — See premium info
- `/refer <referrer_id>` — Set your referrer
- `/rafer` — Show your stylish name and Telegram ID

---

## Credits
- Admin: @in_yogeshwar (ID: 7176592290)
- Powered by [remove.bg](https://www.remove.bg/api)

---

## License
MIT
