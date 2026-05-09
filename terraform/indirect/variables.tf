variable "aws_region" {
  default = "us-east-1"
}

variable "num_workers" {
  description = "Numero de instancias worker (cambia para el benchmark de escalabilidad)"
  type        = number
  default     = 2
}

variable "instance_type" {
  default = "t2.micro"
}
