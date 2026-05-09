# ── Workers ───────────────────────────────────────────────────────────────────
resource "null_resource" "worker_setup" {
  count      = var.num_workers
  depends_on = [aws_instance.worker, aws_instance.nameserver, aws_instance.redis]

  connection {
    type = "ssh"; user = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host    = aws_instance.worker[count.index].public_ip
    timeout = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5, redis\" 2>/dev/null; do sleep 5; done' || true",
      "timeout 300 bash -c 'until bash -c \"echo >/dev/tcp/${aws_instance.nameserver.private_ip}/9090\" 2>/dev/null; do echo Esperando NS...; sleep 5; done' || true",
      "timeout 120 bash -c 'until redis-cli -h ${aws_instance.redis.private_ip} ping 2>/dev/null | grep -q PONG; do sleep 5; done' || true",
      "echo '=== Entorno listo ==='",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    content     = "export REDIS_HOST=${aws_instance.redis.private_ip}\nexport PYRO_NS_HOST=${aws_instance.nameserver.private_ip}\nexport WORKER_HOST=${aws_instance.worker[count.index].private_ip}\n"
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "PYTHON=$(which python3)",
      "sudo tee /etc/systemd/system/sd-worker.service > /dev/null <<EOF",
      "[Unit]",
      "Description=SD Direct Worker ${count.index + 1}",
      "After=network.target",
      "[Service]",
      "Environment=REDIS_HOST=${aws_instance.redis.private_ip}",
      "Environment=PYRO_NS_HOST=${aws_instance.nameserver.private_ip}",
      "Environment=WORKER_HOST=${aws_instance.worker[count.index].private_ip}",
      "ExecStart=$PYTHON /home/ec2-user/direct/worker.py --id ${count.index + 1} --host ${aws_instance.worker[count.index].private_ip}",
      "Restart=on-failure",
      "RestartSec=5",
      "User=ec2-user",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-worker",
      "sudo systemctl start sd-worker",
      "echo '=== Worker ${count.index + 1} arrancado ==='",
    ]
  }
}

# ── Load Balancer ─────────────────────────────────────────────────────────────
resource "null_resource" "lb_setup" {
  depends_on = [null_resource.worker_setup]

  connection {
    type = "ssh"; user = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host    = aws_instance.loadbalancer.public_ip
    timeout = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5\" 2>/dev/null; do sleep 5; done' || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5.api; ns=Pyro5.api.locate_ns(host=\\'${aws_instance.nameserver.private_ip}\\',port=9090); ws=[k for k in ns.list() if k.startswith(\\'worker_\\')]; assert len(ws)>=${var.num_workers}\" 2>/dev/null; do echo Esperando workers...; sleep 5; done' || true",
      "echo '=== Workers registrados ==='",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "remote-exec" {
    inline = [
      "PYTHON=$(which python3)",
      "sudo tee /etc/systemd/system/sd-lb.service > /dev/null <<EOF",
      "[Unit]",
      "Description=SD Load Balancer",
      "After=network.target",
      "[Service]",
      "Environment=PYRO_NS_HOST=${aws_instance.nameserver.private_ip}",
      "Environment=LB_HOST=${aws_instance.loadbalancer.private_ip}",
      "ExecStart=$PYTHON /home/ec2-user/direct/load_balancer.py",
      "Restart=on-failure",
      "RestartSec=5",
      "User=ec2-user",
      "[Install]",
      "WantedBy=multi-user.target",
      "EOF",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-lb",
      "sudo systemctl start sd-lb",
      "echo '=== Load Balancer arrancado ==='",
    ]
  }
}

# ── Client ────────────────────────────────────────────────────────────────────
resource "null_resource" "client_setup" {
  depends_on = [null_resource.lb_setup]

  connection {
    type = "ssh"; user = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host    = aws_instance.client.public_ip
    timeout = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import Pyro5, redis\" 2>/dev/null; do sleep 5; done' || true",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    content     = "export REDIS_HOST=${aws_instance.redis.private_ip}\nexport PYRO_NS_HOST=${aws_instance.nameserver.private_ip}\n"
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "file" {
    content = <<-SCRIPT
      #!/bin/bash
      # Uso: bash ~/benchmark.sh <numbered|unnumbered>
      source ~/sd_env.sh
      MODO=$${1:-unnumbered}
      echo "====== Direct / $MODO ======"
      redis-cli -h $REDIS_HOST FLUSHDB
      redis-cli -h $REDIS_HOST SET total_sold 0
      echo "Redis reseteado"
      cd ~/direct && python3 cliente.py --modo $MODO
    SCRIPT
    destination = "/home/ec2-user/benchmark.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x ~/benchmark.sh",
      "echo '=== Cliente listo. Ejecuta: bash ~/benchmark.sh unnumbered ==='",
    ]
  }
}
