output "ips" {
  value = merge(
    {
      redis    = aws_instance.redis.public_ip
      rabbitmq = aws_instance.rabbitmq.public_ip
      client   = aws_instance.client.public_ip
    },
    { for i, w in aws_instance.worker : "worker${i + 1}" => w.public_ip }
  )
}

output "siguiente_paso" {
  value = <<-MSG

    ============================================================
     INDIRECT listo — Redis, RabbitMQ y Workers arrancados
    ============================================================

     Entra al cliente y ejecuta el benchmark:

       ssh -i sd-indirect-key.pem ec2-user@${aws_instance.client.public_ip}
       bash ~/benchmark.sh unnumbered
       bash ~/benchmark.sh numbered

    ============================================================
  MSG
}
