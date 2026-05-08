# ─────────────────────────────────────────────────────────────────────────────
# IPs de las instancias
# ─────────────────────────────────────────────────────────────────────────────

output "ips_publicas" {
  description = "IPs publicas para conectarte por SSH"
  value = merge(
    {
      redis        = aws_instance.redis.public_ip
      nameserver   = aws_instance.nameserver.public_ip
      loadbalancer = aws_instance.loadbalancer.public_ip
      rabbitmq     = aws_instance.rabbitmq.public_ip
      client       = aws_instance.client.public_ip
    },
    { for i, w in aws_instance.worker : "worker${i + 1}" => w.public_ip }
  )
}

output "siguiente_paso" {
  description = "Instrucciones post-deploy"
  value = <<-MSG

    ============================================================
     DESPLIEGUE COMPLETADO
    ============================================================

     Enfoque DIRECTO (Pyro5) — completamente automatico:
       Workers y Load Balancer ya estan corriendo.
       Solo entra al cliente y ejecuta:

         ssh -i sd-key.pem ec2-user@${aws_instance.client.public_ip}
         bash ~/benchmark.sh direct unnumbered
         bash ~/benchmark.sh direct numbered

     Enfoque INDIRECTO (RabbitMQ):
       1. Arranca workers en cada instancia:
    %{for i, w in aws_instance.worker~}
          ssh -i sd-key.pem ec2-user@${w.public_ip} 'bash ~/start_indirect.sh unnumbered 2'
    %{endfor~}
       2. Luego en el cliente:
         ssh -i sd-key.pem ec2-user@${aws_instance.client.public_ip}
         bash ~/benchmark.sh indirect unnumbered

     O deja que benchmark.sh te guie — te da las instrucciones al ejecutarlo.

    ============================================================
  MSG
}

output "ips_privadas" {
  description = "IPs privadas (usadas en las variables de entorno)"
  value = merge(
    {
      redis        = aws_instance.redis.private_ip
      nameserver   = aws_instance.nameserver.private_ip
      loadbalancer = aws_instance.loadbalancer.private_ip
      rabbitmq     = aws_instance.rabbitmq.private_ip
      client       = aws_instance.client.private_ip
    },
    { for i, w in aws_instance.worker : "worker${i + 1}" => w.private_ip }
  )
}

# ─────────────────────────────────────────────────────────────────────────────
# env.sh — exporta todas las variables de entorno listas para usar
# ─────────────────────────────────────────────────────────────────────────────
resource "local_file" "env_sh" {
  filename = "${path.module}/../env.sh"
  content  = <<-EOT
    #!/bin/bash
    # Auto-generado por Terraform. Ejecutar con: source env.sh
    export REDIS_HOST=${aws_instance.redis.private_ip}
    export PYRO_NS_HOST=${aws_instance.nameserver.private_ip}
    export LB_HOST=${aws_instance.loadbalancer.private_ip}
    export RABBIT_HOST=${aws_instance.rabbitmq.private_ip}
    %{for i, w in aws_instance.worker~}
    export WORKER${i + 1}_HOST=${w.private_ip}
    %{endfor~}

    echo "=== Variables de entorno cargadas ==="
    echo "  REDIS_HOST    = $REDIS_HOST"
    echo "  PYRO_NS_HOST  = $PYRO_NS_HOST"
    echo "  LB_HOST       = $LB_HOST"
    echo "  RABBIT_HOST   = $RABBIT_HOST"
    %{for i, w in aws_instance.worker~}
    echo "  WORKER${i + 1}_HOST   = $WORKER${i + 1}_HOST"
    %{endfor~}
  EOT
}

# ─────────────────────────────────────────────────────────────────────────────
# upload.sh — comandos scp para subir el codigo a cada instancia
# ─────────────────────────────────────────────────────────────────────────────
resource "local_file" "upload_sh" {
  filename = "${path.module}/../upload.sh"
  content  = <<-EOT
    #!/bin/bash
    # Auto-generado por Terraform.
    # Ejecutar desde la raiz del proyecto: bash upload.sh
    KEY="../sd-key.pem"

    echo "=== Subiendo codigo a las instancias ==="

    # Load Balancer
    scp -i $KEY -o StrictHostKeyChecking=no -r direct/ \
        ec2-user@${aws_instance.loadbalancer.public_ip}:~/

    # Workers
    %{for i, w in aws_instance.worker~}
    echo "Worker${i + 1}..."
    scp -i $KEY -o StrictHostKeyChecking=no -r direct/ indirect/ \
        ec2-user@${w.public_ip}:~/
    %{endfor~}

    # Cliente
    echo "Client..."
    scp -i $KEY -o StrictHostKeyChecking=no -r direct/ indirect/ \
        ec2-user@${aws_instance.client.public_ip}:~/

    echo "=== Listo ==="
    echo ""
    echo "Proximos pasos:"
    echo "  1. Arrancar workers (directo):"
    %{for i, w in aws_instance.worker~}
    echo "     ssh -i $KEY ec2-user@${w.public_ip}"
    echo "       cd direct && source ~/env_worker.sh && python3 worker.py --id ${i + 1} --host \$WORKER${i + 1}_HOST"
    %{endfor~}
    echo "  2. Arrancar LB (directo):"
    echo "     ssh -i $KEY ec2-user@${aws_instance.loadbalancer.public_ip}"
    echo "       cd direct && source ~/env_worker.sh && python3 load_balancer.py"
    echo "  3. Reset Redis y lanzar benchmark:"
    echo "     ssh -i $KEY ec2-user@${aws_instance.client.public_ip}"
    echo "       redis-cli -h \$REDIS_HOST FLUSHDB"
    echo "       cd direct && python3 cliente.py --modo unnumbered"
  EOT
}

# ─────────────────────────────────────────────────────────────────────────────
# ssh.sh — atajos para conectarte a cada instancia
# ─────────────────────────────────────────────────────────────────────────────
resource "local_file" "ssh_sh" {
  filename = "${path.module}/../ssh.sh"
  content  = <<-EOT
    #!/bin/bash
    # Uso: bash ssh.sh <nombre>
    # Nombres disponibles: redis, nameserver, loadbalancer, rabbitmq, client, worker1, worker2...
    KEY="../sd-key.pem"
    case "$1" in
      redis)       ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${aws_instance.redis.public_ip} ;;
      nameserver)  ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${aws_instance.nameserver.public_ip} ;;
      loadbalancer) ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${aws_instance.loadbalancer.public_ip} ;;
      rabbitmq)    ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${aws_instance.rabbitmq.public_ip} ;;
      client)      ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${aws_instance.client.public_ip} ;;
    %{for i, w in aws_instance.worker~}
      worker${i + 1})    ssh -i $KEY -o StrictHostKeyChecking=no ec2-user@${w.public_ip} ;;
    %{endfor~}
      *) echo "Uso: bash ssh.sh <redis|nameserver|loadbalancer|rabbitmq|client|worker1|worker2>" ;;
    esac
  EOT
}
