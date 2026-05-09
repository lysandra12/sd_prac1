locals {
  python_deps = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y python3 python3-pip redis
    pip3 install --quiet redis pika
    echo "deps OK" >> /var/log/sd-setup.log
  EOF

  redis_setup = <<-EOF
    #!/bin/bash
    yum update -y
    amazon-linux-extras enable redis6 -y
    yum install -y redis
    sed -i 's/^bind 127.0.0.1.*/bind 0.0.0.0/' /etc/redis/redis.conf
    sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
    systemctl enable redis && systemctl start redis
    echo "Redis OK" >> /var/log/sd-setup.log
  EOF

  rabbitmq_setup = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y https://github.com/rabbitmq/erlang-rpm/releases/download/v26.2.1/erlang-26.2.1-1.el7.x86_64.rpm
    yum install -y https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.12.12/rabbitmq-server-3.12.12-1.el8.noarch.rpm
    systemctl enable rabbitmq-server && systemctl start rabbitmq-server
    sleep 15
    rabbitmqctl add_user user user
    rabbitmqctl set_permissions -p / user ".*" ".*" ".*"
    rabbitmq-plugins enable rabbitmq_management
    systemctl restart rabbitmq-server
    echo "RabbitMQ OK" >> /var/log/sd-setup.log
  EOF
}

resource "aws_instance" "redis" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.redis_setup
  tags = { Name = "indirect-redis" }
}

resource "aws_instance" "rabbitmq" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.rabbitmq_setup
  tags = { Name = "indirect-rabbitmq" }
}

resource "aws_instance" "worker" {
  count                  = var.num_workers
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps
  tags = { Name = "indirect-worker${count.index + 1}" }
}

resource "aws_instance" "client" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps
  tags = { Name = "indirect-client" }
}
