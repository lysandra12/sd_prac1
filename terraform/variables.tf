variable "aws_region" {
  description = "Region de AWS donde desplegar"
  type        = string
  default     = "eu-west-1"
}

variable "num_workers" {
  description = "Numero de instancias worker a crear"
  type        = number
  default     = 2
}

variable "instance_type_default" {
  description = "Tipo de instancia para la mayoria de componentes"
  type        = string
  default     = "t2.micro"
}

variable "instance_type_rabbitmq" {
  description = "Tipo de instancia para RabbitMQ (necesita mas RAM)"
  type        = string
  default     = "t2.small"
}
