# =============================================================================
# WORKERS
# =============================================================================
resource "null_resource" "worker_setup" {
  count = var.num_workers

  depends_on = [
    aws_instance.worker,
    aws_instance.nameserver,
    aws_instance.redis,
    aws_instance.rabbitmq,
  ]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.worker[count.index].public_ip
    timeout     = "20m"
  }

  # 1. Esperar a que cloud-init y las dependencias Python estén listas
  provisioner "remote-exec" {
    inline = [
      "echo '=== Esperando cloud-init ==='",
      "cloud-init status --wait 2>/dev/null || true",
      # Esperar deps Python (timeout 5 min)
      "timeout 300 bash -c 'until python3 -c \"import Pyro5, redis, pika\" 2>/dev/null; do echo Esperando deps...; sleep 5; done' || true",
      "echo '=== Deps OK ==='",
      # Esperar al NameServer via TCP (mas fiable que Pyro5 API)
      "timeout 300 bash -c 'until bash -c \"echo >/dev/tcp/${aws_instance.nameserver.private_ip}/9090\" 2>/dev/null; do echo Esperando NameServer...; sleep 5; done' || true",
      "echo '=== NameServer OK ==='",
      # Esperar a Redis
      "timeout 120 bash -c 'until redis-cli -h ${aws_instance.redis.private_ip} ping 2>/dev/null | grep -q PONG; do echo Esperando Redis...; sleep 5; done' || true",
      "echo '=== Redis OK ==='",
    ]
  }

  # 2. Subir el código
  provisioner "file" {
    source      = "${path.module}/../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    source      = "${path.module}/../indirect"
    destination = "/home/ec2-user/indirect"
  }

  # 3. Variables de entorno
  provisioner "file" {
    content     = <<-ENV
      export REDIS_HOST=${aws_instance.redis.private_ip}
      export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
      export RABBIT_HOST=${aws_instance.rabbitmq.private_ip}
      export WORKER_HOST=${aws_instance.worker[count.index].private_ip}
    ENV
    destination = "/home/ec2-user/sd_env.sh"
  }

  # 4. Servicio systemd para el worker DIRECTO
  provisioner "remote-exec" {
    inline = [
      "PYTHON=$(which python3)",
      "sudo tee /etc/systemd/system/sd-worker-direct.service > /dev/null <<EOF",
      "[Unit]",
      "Description=SD Direct Worker ${count.index + 1}",
      "After=network.target",
      "",
      "[Service]",
      "Environment=REDIS_HOST=${aws_instance.redis.private_ip}",
      "Environment=PYRO_NS_HOST=${aws_instance.nameserver.private_ip}",
      "Environment=WORKER_HOST=${aws_instance.worker[count.index].private_ip}",
      "ExecStart=$PYTHON /home/ec2-user/direct/worker.py --id ${count.index + 1} --host ${aws_instance.worker[count.index].private_ip}",
      "Restart=on-failure",
      "RestartSec=5",
      "User=ec2-user",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-worker-direct",
      "sudo systemctl start sd-worker-direct",
    ]
  }

  # 5. Script helper para INDIRECTO
  provisioner "file" {
    content     = <<-SCRIPT
      #!/bin/bash
      source ~/sd_env.sh
      echo "Arrancando worker indirecto..."
      cd ~/indirect
      python3 worker.py
    SCRIPT
    destination = "/home/ec2-user/start_indirect.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /home/ec2-user/start_indirect.sh",
      "echo '=== Worker ${count.index + 1} listo ==='",
    ]
  }
}

# =============================================================================
# LOAD BALANCER
# =============================================================================
resource "null_resource" "lb_setup" {
  depends_on = [null_resource.worker_setup]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.loadbalancer.public_ip
    timeout     = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5\" 2>/dev/null; do sleep 5; done' || true",
      # Esperar a que los workers estén registrados en el NS
      "timeout 300 bash -c 'until python3 -c \"import Pyro5.api; ns=Pyro5.api.locate_ns(host=\\'${aws_instance.nameserver.private_ip}\\', port=9090); ws=[k for k in ns.list() if k.startswith(\\'worker_\\')]; assert len(ws)>=${var.num_workers}\" 2>/dev/null; do echo Esperando workers en NS...; sleep 5; done' || true",
      "echo '=== Workers registrados ==='",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    content     = <<-ENV
      export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
      export LB_HOST=${aws_instance.loadbalancer.private_ip}
    ENV
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "PYTHON=$(which python3)",
      "sudo tee /etc/systemd/system/sd-lb.service > /dev/null <<EOF",
      "[Unit]",
      "Description=SD Load Balancer",
      "After=network.target",
      "",
      "[Service]",
      "Environment=PYRO_NS_HOST=${aws_instance.nameserver.private_ip}",
      "Environment=LB_HOST=${aws_instance.loadbalancer.private_ip}",
      "ExecStart=$PYTHON /home/ec2-user/direct/load_balancer.py",
      "Restart=on-failure",
      "RestartSec=5",
      "User=ec2-user",
      "",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-lb",
      "sudo systemctl start sd-lb",
      "echo '=== Load Balancer listo ==='",
    ]
  }
}

# =============================================================================
# CLIENT
# =============================================================================
resource "null_resource" "client_setup" {
  depends_on = [null_resource.lb_setup]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.client.public_ip
    timeout     = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5, redis, pika\" 2>/dev/null; do sleep 5; done' || true",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    source      = "${path.module}/../indirect"
    destination = "/home/ec2-user/indirect"
  }

  provisioner "file" {
    content = <<-ENV
      export REDIS_HOST=${aws_instance.redis.private_ip}
      export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
      export LB_HOST=${aws_instance.loadbalancer.private_ip}
      export RABBIT_HOST=${aws_instance.rabbitmq.private_ip}
      %{for i, w in aws_instance.worker~}
      export WORKER${i + 1}_HOST=${w.private_ip}
      export WORKER${i + 1}_PUB=${w.public_ip}
      %{endfor~}
    ENV
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "file" {
    content = <<-SCRIPT
      #!/bin/bash
      # Uso: bash ~/benchmark.sh <direct|indirect> <numbered|unnumbered>
      source ~/sd_env.sh
      ENFOQUE=$${1:-direct}
      MODO=$${2:-unnumbered}

      echo "======================================================"
      echo " Benchmark: $ENFOQUE / $MODO"
      echo "======================================================"

      echo ">> Reseteando Redis..."
      redis-cli -h $REDIS_HOST FLUSHDB
      redis-cli -h $REDIS_HOST SET total_sold 0
      echo ">> Redis limpio"

      if [ "$ENFOQUE" = "direct" ]; then
        cd ~/direct && python3 cliente.py --modo $MODO

      elif [ "$ENFOQUE" = "indirect" ]; then
        echo ""
        echo "Arranca los workers en cada instancia worker:"
        %{for i, w in aws_instance.worker~}
        echo "  ssh -i sd-key.pem ec2-user@${w.public_ip} 'bash ~/start_indirect.sh'"
        %{endfor~}
        echo ""
        read -p "Pulsa ENTER cuando los workers esten listos..."
        cd ~/indirect && python3 cliente.py --modo $MODO
      fi
    SCRIPT
    destination = "/home/ec2-user/benchmark.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /home/ec2-user/benchmark.sh",
      "echo '=== Cliente listo ==='",
    ]
  }
}
