#!/bin/bash
# Roda no servidor (Ubuntu 22.04+) como root
# Uso: bash setup.sh

set -e

echo "=== Instalando dependências ==="
apt-get update -q
apt-get install -y python3.12 python3.12-venv python3-pip

echo "=== Criando diretório do projeto ==="
mkdir -p /opt/bot-meet/data

echo "=== Copiando projeto ==="
# Execute este script após copiar o projeto para /opt/bot-meet
# scp -r ./* ubuntu@SEU_IP:/opt/bot-meet/

echo "=== Instalando dependências Python ==="
cd /opt/bot-meet
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -q

echo "=== Instalando serviços systemd ==="
cp deploy/bot.service /etc/systemd/system/bot-meet.service
cp deploy/dashboard.service /etc/systemd/system/bot-meet-dashboard.service

systemctl daemon-reload
systemctl enable bot-meet bot-meet-dashboard
systemctl start bot-meet bot-meet-dashboard

echo ""
echo "=== Pronto! ==="
echo "Dashboard: http://$(curl -s ifconfig.me):8765"
echo ""
echo "Comandos úteis:"
echo "  systemctl status bot-meet          # status do bot"
echo "  systemctl status bot-meet-dashboard # status do dashboard"
echo "  journalctl -u bot-meet -f           # logs do bot em tempo real"
echo "  journalctl -u bot-meet-dashboard -f # logs do dashboard"
echo "  systemctl restart bot-meet          # reiniciar o bot"
