#!/bin/bash
# Instala todas las dependencias Python necesarias en Amazon Linux 2
set -e

sudo yum update -y
sudo yum install -y python3 python3-pip

pip3 install --upgrade pip
pip3 install Pyro5 serpent redis pika
