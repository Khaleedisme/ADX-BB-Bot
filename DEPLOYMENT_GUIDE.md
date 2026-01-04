# GitHub 24/7 Deployment Guide
# ADX Volatility Waves Trading Bot

## 📋 Qısa Xülasə

Bu bot-u GitHub-a yükləyib aşağıdakı platformalarda pulsuz 24/7 çalışdıra bilərsiniz:
1. **Render.com** (Tövsiyə - Tam Pulsuz)
2. **Railway.app** (Pulsuz tier)
3. **Heroku** ($7/ay)
4. **VPS** (DigitalOcean, AWS və s.)

---

## 🚀 METHOD 1: Render.com (Tövsiyə Edilir)

### Addım 1: GitHub Repository Yarat

```bash
cd "C:\Users\ASUS\Desktop\bot\ADX BB Signals"

# Git başlat
git init
git add .
git commit -m "Initial commit: ADX Volatility Waves Bot"

# GitHub-da yeni repo yarat (github.com-da)
# Sonra:
git remote add origin https://github.com/Khaleedisme/ADX-BB-Bot.git
git branch -M main
git push -u origin main
```

### Addım 2: Render.com-a Qoşul

1. [https://render.com](https://render.com)-a daxil ol
2. GitHub ilə sign up et
3. "New +" düyməsinə bas
4. "Web Service" seç

### Addım 3: Repo Bağla

1. GitHub repo-nu seç: `adx-volatility-bot`
2. Service Name: `adx-volatility-bot`
3. Region: Frankfurt (ən yaxın)
4. Branch: `main`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `python adx_volatility_bot.py`

### Addım 4: Environment Variables

"Environment" bölməsinə keç və əlavə et:

```
TELEGRAM_BOT_TOKEN = 8597445147:AAGvZZLNigyCEpLol5CvHvQAxc9PVy6JrLM
TELEGRAM_USER_ID = 368629145
```

(BU DEĞİXDİRMƏYİN - artıq botda hardcoded-dir, amma deployment üçün yaxşıdır)

### Addım 5: Deploy Et

1. "Create Web Service" düyməsinə bas
2. Deploy başlayacaq (3-5 dəqiqə)
3. Logs-da "🚀 Starting ADX Volatility Waves Bot" görməlisiniz
4. Telegram-da startup mesajı alacaqsınız

### ✅ Bitdi!

Bot indi 24/7 işləyir. Render.com avtomatik yenidən başladır əgər problem olarsa.

### 🔄 Botu Yeniləmək (Update)

Kodda dəyişiklik etdikdən sonra Render-ə yeniləmək üçün sadəcə bu əmrləri terminalla yazın:

```bash
git add .
git commit -m "Update bot code"
git push origin main
```

Render avtomatik olaraq yeni kodu görəcək və botu yenidən deploy edəcək. Heç bir şey etməyə ehtiyac yoxdur.

---

## 🚄 METHOD 2: Railway.app

### Addım 1-2: GitHub Push (yuxarıdakı kimi)

### Addım 3: Railway Deploy

1. [https://railway.app](https://railway.app) - GitHub ilə login
2. "New Project" → "Deploy from GitHub repo"
3. Repo seç: `adx-volatility-bot`
4. Variables tab:
   - `TELEGRAM_BOT_TOKEN` = token
   - `TELEGRAM_USER_ID` = user_id
5. Deploy et

Railway avtomatik `requirements.txt` görüb Python project kimi tanıyacaq.

---

## 🟣 METHOD 3: Heroku ($7/ay)

### Addım 1: Heroku CLI Quraşdır

[https://devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)

```bash
# Windows PowerShell
winget install Heroku.HerokuCLI
```

### Addım 2: Login və Deploy

```bash
heroku login

cd "C:\Users\ASUS\Desktop\bot\ADX BB Signals"

# Heroku app yarat
heroku create adx-volatility-bot

# Environment variables
heroku config:set TELEGRAM_BOT_TOKEN=8597445147:AAGvZZLNigyCEpLol5CvHvQAxc9PVy6JrLM
heroku config:set TELEGRAM_USER_ID=368629145

# Git push
git push heroku main

# Worker başlat
heroku ps:scale web=1
```

### Logs Bax

```bash
heroku logs --tail
```

---

## 💻 METHOD 4: VPS Server

### Provider Seç

- DigitalOcean ($4/ay droplet) - tövsiyə edilir
- AWS Lightsail ($3.50/ay)
- Vultr ($2.50/ay)
- Hetzner (€3.29/ay)

### Server Quraşdırma

```bash
# SSH ilə bağlan
ssh root@YOUR_SERVER_IP

# Python quraşdır
apt update
apt install python3 python3-pip git -y

# Repo clone et
git clone https://github.com/YOUR_USERNAME/adx-volatility-bot.git
cd adx-volatility-bot

# Dependencies
pip3 install -r requirements.txt

# Screen istifadə edərək background-da işlət
screen -S trading-bot
python3 adx_volatility_bot.py

# Detach etmək üçün: Ctrl+A sonra D
```

### Screen-ə Qayıt

```bash
screen -r trading-bot
```

### Bot Başlatmaq Üçün Sistemdə Service Yarat

```bash
# Service file yarat
sudo nano /etc/systemd/system/trading-bot.service
```

Faylın içinə:

```ini
[Unit]
Description=ADX Volatility Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/adx-volatility-bot
ExecStart=/usr/bin/python3 /root/adx-volatility-bot/adx_volatility_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivləşdir:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Status yoxla
sudo systemctl status trading-bot

# Logs bax
journalctl -u trading-bot -f
```

---

## 🔧 TP/SL Dəyərlərini Dəyişmək

Bot-da indi 1m timeframe üçün optimal dəyərlər:

```python
TP_PERCENT = 0.1    # 0.1% = 1% with 10x leverage
SL_PERCENT = 0.08   # 0.08% = 0.8% with 10x leverage
```

**5m timeframe üçün:**
```python
TP_PERCENT = 0.2    # 0.2% = 2% with 10x leverage
SL_PERCENT = 0.15   # 0.15% = 1.5% with 10x leverage
```

Dəyişdirmək üçün:
1. `adx_volatility_bot.py` açın
2. Sətirlər 76-77-də dəyişdirin
3. GitHub-a push edin:
   ```bash
   git add .
   git commit -m "Updated TP/SL values"
   git push
   ```
4. Render/Railway avtomatik yenidən deploy edəcək

---

## 📊 Monitoring

### Telegram-da

- Bot `/status` əmri ilə statistika göstərəcək
- Hər tradedə avtomatik mesaj
- Başladıqda və dayandıqda məlumat

### Platformada

- **Render**: Dashboard → Logs
- **Railway**: Project → Deployments → View Logs
- **Heroku**: `heroku logs --tail`

---

## ⚡ Troubleshooting

### Bot başlamır

1. Logs yoxlayın
2. Environment variables düz olduğunu yoxlayın
3. Python version 3.10+ olduğundan əmin olun

### Bot dayandı

Avtomatik yenidən başlamalıdır. Əgər başlamazsa:
- Render: Deploy → "Clear build cache & deploy"
- Railway: Restart deployment
- Heroku: `heroku restart`

### Chart göndərmir

`matplotlib` dependency yoxdur:
```bash
pip install matplotlib
```

---

## 🎯 Tövsiyələr

1. **İlk deployment:** Render.com istifadə edin (ən asan və pulsuz)
2. **Monitor edin:** İlk 24 saat logs-ları izləyin
3. **Backup:** `trading_state.json` faylını vaxtaşırı yükləyin
4. **Updates:** GitHub-a push edəndə avtomatik deploy olur

---

## ✅ Deployment Checklist

- [ ] GitHub repo yaratdım
- [ ] Code push etdim
- [ ] Hosting platforması seçdim
- [ ] Environment variables əlavə etdim
- [ ] Deploy etdim
- [ ] Telegram-da startup mesajı gəldi
- [ ] Logs-da error yoxdur
- [ ] Bot işləyir 24/7

---

**Uğurlar! 🚀**

Suallar varsa README.md baxın və ya GitHub Issues açın.
