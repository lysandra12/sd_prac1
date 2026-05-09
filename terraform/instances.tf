# ─────────────────────────────────────────────────────────────────────────────
# Scripts de user_data (se ejecutan en el primer arranque como root)
# ─────────────────────────────────────────────────────────────────────────────

locals {
  # Dependencias Python comunes a workers y cliente
  python_deps = <<-EOF
    #!/bin/bash
    set -e
    yum update -y
    yum install -y python3 python3-pip
    pip3 install --quiet Pyro5 serpent redis pika
    echo "Python deps OK" >> /var/log/sd-setup.log
  EOF

  # Redis server
  redis_setup = <<-EOF
    #!/bin/bash
    set -e
    yum update -y
    amazon-linux-extras enable redis6 -y
    yum install -y redis
    sed -i 's/^bind 127.0.0.1.*/bind 0.0.0.0/' /etc/redis/redis.conf
    sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
    systemctl enable redis
    systemctl start redis
    echo "Redis OK" >> /var/log/sd-setup.log
  EOF

  # Pyro5 Name Server con systemd
  nameserver_setup = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y python3 python3-pip
    pip3 install --quiet Pyro5 serpent

    PYTHON=$(which python3)

    printf '[Unit]\nDescription=Pyro5 Name Server\nAfter=network.target\n\n[Service]\nExecStart=%s -m Pyro5.nameserver --host 0.0.0.0 --port 9090\nRestart=always\nRestartSec=5\nUser=ec2-user\n\n[Install]\nWantedBy=multi-user.target\n' "$PYTHON" > /etc/systemd/system/pyro-ns.service

    systemctl daemon-reload
    systemctl enable pyro-ns
    systemctl start pyro-ns
    echo "Nameserver OK" >> /var/log/sd-setup.log
  EOF

  # RabbitMQ
  rabbitmq_setup = <<-EOF
    #!/bin/bash
    set -e
    yum update -y

    # Erlang
    yum install -y https://github.com/rabbitmq/erlang-rpm/releases/download/v26.2.1/erlang-26.2.1-1.el7.x86_64.rpm

    # RabbitMQ
    yum install -y https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.12.12/rabbitmq-server-3.12.12-1.el8.noarch.rpm

    systemctl enable rabbitmq-server
    systemctl start rabbitmq-server

    # Esperar a que arranque
    sleep 10

    rabbitmqctl add_user user user
    rabbitmqctl set_permissions -p / user ".*" ".*" ".*"
    rabbitmq-plugins enable rabbitmq_management
    systemctl restart rabbitmq-server
    echo "RabbitMQ OK" >> /var/log/sd-setup.log
  EOF
}

# ─────────────────────────────────────────────────────────────────────────────
# Instancias
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_instance" "redis" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_default
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.redis_setup

  tags = { Name = "redis" }
}

resource "aws_instance" "nameserver" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_default
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.nameserver_setup

  tags = { Name = "nameserver" }
}

resource "aws_instance" "loadbalancer" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_default
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps

  tags = { Name = "loadbalancer" }
}

resource "aws_instance" "rabbitmq" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_rabbitmq
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.rabbitmq_setup

  tags = { Name = "rabbitmq" }
}

resource "aws_instance" "worker" {
  count = var.num_workers

  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_default
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps

  tags = { Name = "worker${count.index + 1}" }
}

resource "aws_instance" "client" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type_default
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps

  tags = { Name = "client" }
}
