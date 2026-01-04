# ADX Volatility Waves Trading Bot

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

## 🚀 24/7 Deployment on Render/Heroku

Bu bot GitHub-da hostlanıb 7/24 çalışdırıla bilər.

### Option 1: Render.com (Tövsiyə edilir - Pulsuz)

1. **GitHub-a upload et:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

2. **Render.com-a daxil ol:**
   - [render.com](https://render.com) - qeydiyyatdan keç
   - "New +" → "Web Service" seç
   - GitHub repo-nu bağla
   - Settings:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python adx_volatility_bot.py`
     - **Environment**: Python 3

3. **Environment Variables əlavə et:**
   - `TELEGRAM_BOT_TOKEN` = sizin bot token
   - `TELEGRAM_USER_ID` = sizin user ID
   - Digər parametrlər .env.example-dan

4. **Deploy et** - avtomatik başlayacaq

### Option 2: Heroku

1. **Heroku CLI quraşdır:**
   ```bash
   heroku login
   heroku create your-bot-name
   ```

2. **Environment variables set et:**
   ```bash
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set TELEGRAM_USER_ID=your_id
   ```

3. **Deploy et:**
   ```bash
   git push heroku main
   heroku ps:scale worker=1
   ```

### Option 3: Railway.app

1. [railway.app](https://railway.app)-a daxil ol
2. "New Project" → "Deploy from GitHub repo"
3. Repo seç və environment variables əlavə et
4. Avtomatik deploy olacaq

### Option 4: VPS Server (DigitalOcean, AWS, etc.)

```bash
# Server-də
git clone YOUR_REPO_URL
cd ADX-BB-Signals
pip install -r requirements.txt

# Environment variables
cp .env.example .env
nano .env  # Edit with your values

# Run with screen/tmux
screen -S trading-bot
python adx_volatility_bot.py
# Press Ctrl+A+D to detach
```

## 📊 Lokal İstifadə

```bash
pip install -r requirements.txt
python adx_volatility_bot.py
```

## ⚙️ Konfiqurasiya

`.env` faylında:
- `TELEGRAM_BOT_TOKEN` - BotFather-dən alın
- `TELEGRAM_USER_ID` - @userinfobot-dan alın
- `TIMEFRAME` - 1m, 5m, 15m və s.
- `TP_PERCENT` - 0.1 (10x leverage ilə 1%)
- `SL_PERCENT` - 0.08 (10x leverage ilə 0.8%)

## 📈 Features

- ✅ ADX-adjusted Bollinger Bands
- ✅ Gradient zone visualization
- ✅ Paper trading with realistic fees
- ✅ 10x leverage support
- ✅ Telegram notifications
- ✅ Partial TP system
- ✅ Trailing stop
- ✅ 20 cryptocurrency pairs

## 🔧 TP/SL Settings

**1 dəqiqəlik timeframe üçün:**
- TP1: 0.1% (10x leverage = 1% PnL)
- TP2: 0.15% (10x leverage = 1.5% PnL)
- SL: 0.08% (10x leverage = 0.8% loss)

**5 dəqiqəlik timeframe üçün:**
- TP1: 0.2% (10x leverage = 2% PnL)
- TP2: 0.3% (10x leverage = 3% PnL)
- SL: 0.15% (10x leverage = 1.5% loss)

## 📁 Files

- `adx_volatility_bot.py` - Əsas bot
- `requirements.txt` - Dependencies
- `.env.example` - Environment template
- `Procfile` - Heroku config
- `render.yaml` - Render config
- `start_bot.bat` - Windows başlatma

## ⚠️ Diqqət

Bu paper trading bot-dur. Real pul işlətmir, yalnız simulyasiya edir.

## 📞 Support

Issues və ya suallar üçün GitHub Issues-dan istifadə edin.
