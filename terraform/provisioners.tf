# =============================================================================
# WORKERS
# Espera a que el NameServer y Redis estén listos, sube el código,
# crea servicio systemd para el modo directo y script helper para indirecto.
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
    timeout     = "10m"
  }

  # 1. Esperar a que cloud-init y las dependencias Python estén listas
  provisioner "remote-exec" {
    inline = [
      "echo '=== Esperando cloud-init ==='",
      "cloud-init status --wait 2>/dev/null || true",
      "until python3 -c 'import Pyro5, redis, pika' 2>/dev/null; do echo 'Esperando deps Python...'; sleep 5; done",
      "echo '=== Deps OK ==='",
      # Esperar al NameServer
      "until python3 -c \"import Pyro5.api; Pyro5.api.locate_ns('${aws_instance.nameserver.private_ip}', 9090)\" 2>/dev/null; do echo 'Esperando NameServer...'; sleep 5; done",
      "echo '=== NameServer OK ==='",
      # Esperar a Redis
      "until redis-cli -h ${aws_instance.redis.private_ip} ping 2>/dev/null | grep -q PONG; do echo 'Esperando Redis...'; sleep 5; done",
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

  # 3. Archivo de variables de entorno
  provisioner "file" {
    content = <<-ENV
      export REDIS_HOST=${aws_instance.redis.private_ip}
      export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
      export RABBIT_HOST=${aws_instance.rabbitmq.private_ip}
      export WORKER_HOST=${aws_instance.worker[count.index].private_ip}
    ENV
    destination = "/home/ec2-user/sd_env.sh"
  }

  # 4. Servicio systemd para el worker DIRECTO (arranca automáticamente)
  provisioner "file" {
    content = <<-UNIT
      [Unit]
      Description=SD Direct Worker ${count.index + 1}
      After=network.target

      [Service]
      Environment="REDIS_HOST=${aws_instance.redis.private_ip}"
      Environment="PYRO_NS_HOST=${aws_instance.nameserver.private_ip}"
      Environment="WORKER_HOST=${aws_instance.worker[count.index].private_ip}"
      ExecStart=/usr/local/bin/python3 /home/ec2-user/direct/worker.py \
        --id ${count.index + 1} \
        --host ${aws_instance.worker[count.index].private_ip}
      Restart=on-failure
      RestartSec=5
      User=ec2-user

      [Install]
      WantedBy=multi-user.target
    UNIT
    destination = "/tmp/sd-worker-direct.service"
  }

  # 5. Script helper para el modo INDIRECTO (el usuario solo corre este script)
  provisioner "file" {
    content = <<-SCRIPT
      #!/bin/bash
      # Uso: bash ~/start_indirect.sh <numbered|unnumbered>
      # Ejemplo: bash ~/start_indirect.sh unnumbered
      source ~/sd_env.sh
      MODO=$${1:-unnumbered}
      echo "Arrancando worker en modo $MODO..."
      cd ~/indirect
      python3 worker.py --modo $MODO
    SCRIPT
    destination = "/home/ec2-user/start_indirect.sh"
  }

  # 6. Instalar y arrancar el servicio directo
  provisioner "remote-exec" {
    inline = [
      "sudo mv /tmp/sd-worker-direct.service /etc/systemd/system/",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-worker-direct",
      "sudo systemctl start sd-worker-direct",
      "chmod +x /home/ec2-user/start_indirect.sh",
      "echo '=== Worker ${count.index + 1} listo ==='",
    ]
  }
}

# =============================================================================
# LOAD BALANCER
# Espera a que todos los workers estén registrados en el NameServer,
# luego arranca el LB como servicio systemd.
# =============================================================================
resource "null_resource" "lb_setup" {
  depends_on = [null_resource.worker_setup]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.loadbalancer.public_ip
    timeout     = "10m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "until python3 -c 'import Pyro5' 2>/dev/null; do sleep 5; done",
      # Esperar a que todos los workers estén registrados
      "until python3 -c \"\nimport Pyro5.api\nns = Pyro5.api.locate_ns('${aws_instance.nameserver.private_ip}', 9090)\nregistros = [k for k in ns.list() if k.startswith('worker_')]\nassert len(registros) >= ${var.num_workers}, f'Solo {len(registros)} workers'\nprint(f'Workers registrados: {registros}')\n\" 2>/dev/null; do echo 'Esperando workers en NS...'; sleep 5; done",
      "echo '=== Workers registrados, arrancando LB ==='",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../direct"
    destination = "/home/ec2-user/direct"
  }

  provisioner "file" {
    content = <<-ENV
      export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
      export LB_HOST=${aws_instance.loadbalancer.private_ip}
    ENV
    destination = "/home/ec2-user/sd_env.sh"
  }

  provisioner "file" {
    content = <<-UNIT
      [Unit]
      Description=SD Load Balancer
      After=network.target

      [Service]
      Environment="PYRO_NS_HOST=${aws_instance.nameserver.private_ip}"
      Environment="LB_HOST=${aws_instance.loadbalancer.private_ip}"
      ExecStart=/usr/local/bin/python3 /home/ec2-user/direct/load_balancer.py
      Restart=on-failure
      RestartSec=5
      User=ec2-user

      [Install]
      WantedBy=multi-user.target
    UNIT
    destination = "/tmp/sd-lb.service"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /tmp/sd-lb.service /etc/systemd/system/",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable sd-lb",
      "sudo systemctl start sd-lb",
      "echo '=== Load Balancer listo ==='",
    ]
  }
}

# =============================================================================
# CLIENT
# Sube el código y genera scripts listos para ejecutar benchmarks.
# =============================================================================
resource "null_resource" "client_setup" {
  depends_on = [null_resource.lb_setup]

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = tls_private_key.sd.private_key_pem
    host        = aws_instance.client.public_ip
    timeout     = "10m"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait 2>/dev/null || true",
      "until python3 -c 'import Pyro5, redis, pika' 2>/dev/null; do sleep 5; done",
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

  # Variables de entorno con todas las IPs
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

  # Script principal de benchmark — un solo comando lo hace todo
  provisioner "file" {
    content = <<-SCRIPT
      #!/bin/bash
      # =====================================================
      # Uso: bash ~/benchmark.sh <enfoque> <modo>
      #
      #   bash ~/benchmark.sh direct   unnumbered
      #   bash ~/benchmark.sh direct   numbered
      #   bash ~/benchmark.sh indirect unnumbered
      #   bash ~/benchmark.sh indirect numbered
      # =====================================================
      set -e
      source ~/sd_env.sh

      ENFOQUE=$${1:-direct}
      MODO=$${2:-unnumbered}

      echo ""
      echo "======================================================"
      echo " Benchmark: $ENFOQUE / $MODO"
      echo "======================================================"

      # Resetear Redis antes de cada prueba
      echo ">> Reseteando Redis..."
      redis-cli -h $REDIS_HOST FLUSHDB
      redis-cli -h $REDIS_HOST SET total_sold 0
      echo ">> Redis limpio"

      if [ "$ENFOQUE" = "direct" ]; then
        cd ~/direct
        python3 cliente.py --modo $MODO

      elif [ "$ENFOQUE" = "indirect" ]; then
        echo ""
        echo "INDIRECTO: los workers deben estar corriendo en las instancias worker."
        echo "Si no los has arrancado, abre otra terminal y en cada worker ejecuta:"
        %{for i, w in aws_instance.worker~}
        echo "  ssh -i sd-key.pem ec2-user@${w.public_ip} 'bash ~/start_indirect.sh $MODO'"
        %{endfor~}
        echo ""
        read -p "Pulsa ENTER cuando los workers esten listos..."
        cd ~/indirect
        python3 cliente.py --modo $MODO
      fi
    SCRIPT
    destination = "/home/ec2-user/benchmark.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /home/ec2-user/benchmark.sh",
      "echo '=== Cliente listo ==='",
      "echo ''",
      "echo '  Para ejecutar un benchmark:'",
      "echo '    bash ~/benchmark.sh direct   unnumbered'",
      "echo '    bash ~/benchmark.sh direct   numbered'",
      "echo '    bash ~/benchmark.sh indirect unnumbered'",
      "echo '    bash ~/benchmark.sh indirect numbered'",
    ]
  }
}
