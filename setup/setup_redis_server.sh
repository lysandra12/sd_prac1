#!/bin/bash
# Instala y configura Redis en Amazon Linux 2
set -e

sudo yum update -y
sudo amazon-linux-extras enable redis6
sudo yum install -y redis

# Permitir conexiones desde toda la VPC (no solo localhost)
sudo sed -i 's/^bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf

sudo systemctl enable redis
sudo systemctl start redis

echo "Redis instalado y arrancado"
redis-cli ping
