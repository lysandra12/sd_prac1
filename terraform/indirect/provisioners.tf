resource "null_resource" "worker_setup" {
  count      = var.num_workers
  depends_on = [aws_instance.worker, aws_instance.infra]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.worker[count.index].public_ip
    timeout     = "20m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "timeout 300 bash -c 'until python3 -c \"import redis, pika\" 2>/dev/null; do sleep 5; done' || true",
      "timeout 120 bash -c 'until redis-cli -h ${aws_instance.infra.private_ip} ping 2>/dev/null | grep -q PONG; do sleep 5; done' || true",
      "timeout 300 bash -c 'until bash -c \"echo >/dev/tcp/${aws_instance.infra.private_ip}/5672\" 2>/dev/null; do echo Esperando RabbitMQ...; sleep 5; done' || true",
      "echo '=== Entorno listo ==='",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../../indirect"
    destination = "/home/ec2-user/indirect"
  }

  provisioner "file" {
    content     = "export REDIS_HOST=${aws_instance.infra.private_ip}\nexport RABBIT_HOST=${aws_instance.infra.private_ip}\n"
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "PYTHON=$(which python3)",
      "sudo tee /etc/systemd/system/sd-worker.service > /dev/null <<EOF",
      "[Unit]",
      "Description=SD Indirect Worker ${count.index + 1}",
      "After=network.target",
      "[Service]",
      "Environment=REDIS_HOST=${aws_instance.infra.private_ip}",
      "Environment=RABBIT_HOST=${aws_instance.infra.private_ip}",
      "ExecStart=$PYTHON /home/ec2-user/indirect/worker.py",
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

resource "null_resource" "client_setup" {
  depends_on = [null_resource.worker_setup]

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
      "timeout 300 bash -c 'until python3 -c \"import redis, pika\" 2>/dev/null; do sleep 5; done' || true",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../../indirect"
    destination = "/home/ec2-user/indirect"
  }

  provisioner "file" {
    content     = "export REDIS_HOST=${aws_instance.infra.private_ip}\nexport RABBIT_HOST=${aws_instance.infra.private_ip}\n"
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "file" {
    content = <<-SCRIPT
      #!/bin/bash
      # Uso: bash ~/benchmark.sh <numbered|unnumbered>
      source ~/sd_env.sh
      MODO=$${1:-unnumbered}
      echo "====== Indirect / $MODO ======"
      python3 -c "import redis; r=redis.Redis(host='$REDIS_HOST'); r.flushdb(); r.set('total_sold',0); print('Redis reseteado')"
      cd ~/indirect && python3 cliente.py --modo $MODO
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
