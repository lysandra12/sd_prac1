#!/bin/bash
# Instala y configura RabbitMQ en Amazon Linux 2
set -e

sudo yum update -y

# Instalar Erlang (dependencia de RabbitMQ)
sudo yum install -y https://github.com/rabbitmq/erlang-rpm/releases/download/v26.2.1/erlang-26.2.1-1.el7.x86_64.rpm

# Instalar RabbitMQ
sudo yum install -y https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.12.12/rabbitmq-server-3.12.12-1.el8.noarch.rpm

sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server

# Crear usuario 'user' con password 'user'
sudo rabbitmqctl add_user user user
sudo rabbitmqctl set_permissions -p / user ".*" ".*" ".*"
sudo rabbitmqctl set_user_tags user administrator

# Activar plugin de gestion (interfaz web en puerto 15672)
sudo rabbitmq-plugins enable rabbitmq_management

echo "RabbitMQ instalado. Usuario: user / Password: user"
echo "Interfaz web disponible en http://<IP>:15672"
