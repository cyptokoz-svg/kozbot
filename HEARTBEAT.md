# HEARTBEAT.md

# Monitor Polymarket Bot
- Check `systemctl status polymarket-bot` OR `ps aux | grep btc_15m`
- Read `bots/polymarket/paper_trades.jsonl` to track performance (NOT polymarket-bot/)
- If errors in `journalctl -u polymarket-bot` or `bots/polymarket/bot_run.log`, investigate and fix

# TODO: Install systemd service properly
- Service file: `bots/polymarket/polymarket-bot.service`
- Install: `sudo cp bots/polymarket/polymarket-bot.service /etc/systemd/system/`
- Enable: `sudo systemctl enable polymarket-bot`
- WorkingDir should be: `/home/ubuntu/clawd/bots/polymarket`
