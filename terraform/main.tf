terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ─────────────────────────────────────────
# AMI: Amazon Linux 2 mas reciente
# ─────────────────────────────────────────
data "aws_ami" "amzn2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# ─────────────────────────────────────────
# Red
# ─────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "sd-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags = { Name = "sd-subnet-public" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "sd-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "sd-rt-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ─────────────────────────────────────────
# Grupo de seguridad
# ─────────────────────────────────────────
resource "aws_security_group" "sd" {
  name        = "sd-sg"
  description = "SSH desde cualquier IP + trafico libre interno"
  vpc_id      = aws_vpc.main.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Todo el trafico entre instancias del mismo SG
  ingress {
    description = "Trafico interno (mismo SG)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "sd-sg" }
}

# ─────────────────────────────────────────
# Par de claves SSH (generado automaticamente)
# ─────────────────────────────────────────
resource "tls_private_key" "sd" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "sd" {
  key_name   = "sd-key"
  public_key = tls_private_key.sd.public_key_openssh
}

# Guarda la clave privada en la raiz del proyecto
resource "local_sensitive_file" "pem" {
  filename        = "${path.module}/../sd-key.pem"
  content         = tls_private_key.sd.private_key_pem
  file_permission = "0400"
}
