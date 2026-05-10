output "ips" {
  value = merge(
    {
      infra        = aws_instance.infra.public_ip
      loadbalancer = aws_instance.loadbalancer.public_ip
      client       = aws_instance.client.public_ip
    },
    { for i, w in aws_instance.worker : "worker${i + 1}" => w.public_ip }
  )
}

output "siguiente_paso" {
  value = <<-MSG

    ============================================================
     DIRECT listo — Infra (Redis+NS), Workers y LB arrancados
    ============================================================

     Entra al cliente y ejecuta el benchmark:

       ssh -i sd-direct-key.pem ec2-user@${aws_instance.client.public_ip}
       bash ~/benchmark.sh unnumbered
       bash ~/benchmark.sh numbered

    ============================================================
  MSG
}
