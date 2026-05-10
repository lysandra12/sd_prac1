locals {
  python_deps = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y python3 python3-pip redis
    pip3 install --quiet Pyro5 serpent redis
    echo "deps OK" >> /var/log/sd-setup.log
  EOF

  # Redis + Pyro5 NameServer en la misma instancia
  infra_setup = <<-EOF
    #!/bin/bash
    yum update -y
    # Redis
    amazon-linux-extras enable redis6 -y
    yum install -y redis
    sed -i 's/^bind 127.0.0.1.*/bind 0.0.0.0/' /etc/redis/redis.conf
    sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
    systemctl enable redis && systemctl start redis
    # Pyro5 NameServer
    yum install -y python3 python3-pip
    pip3 install --quiet Pyro5 serpent
    PYTHON=$(which python3)
    printf '[Unit]\nDescription=Pyro5 NameServer\nAfter=network.target\n\n[Service]\nExecStart=%s -m Pyro5.nameserver --host 0.0.0.0 --port 9090\nRestart=always\nRestartSec=5\nUser=ec2-user\n\n[Install]\nWantedBy=multi-user.target\n' "$PYTHON" \
      > /etc/systemd/system/pyro-ns.service
    systemctl daemon-reload
    systemctl enable pyro-ns && systemctl start pyro-ns
    echo "Infra OK" >> /var/log/sd-setup.log
  EOF
}

# Una sola instancia para Redis + NameServer
resource "aws_instance" "infra" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.infra_setup
  tags = { Name = "direct-infra" }
}

resource "aws_instance" "loadbalancer" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps
  tags = { Name = "direct-loadbalancer" }
}

resource "aws_instance" "worker" {
  count                  = var.num_workers
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps
  tags = { Name = "direct-worker${count.index + 1}" }
}

resource "aws_instance" "client" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.sd.id]
  key_name               = aws_key_pair.sd.key_name
  user_data              = local.python_deps
  tags = { Name = "direct-client" }
}
