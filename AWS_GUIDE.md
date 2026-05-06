# Guía AWS EC2 — Sistema Distribuido de Tickets

## Arquitectura de instancias

| Nombre | Rol | Tipo |
|--------|-----|------|
| **redis** | Servidor Redis (compartido ambos enfoques) | t2.micro |
| **nameserver** | Pyro5 Name Server (solo directo) | t2.micro |
| **loadbalancer** | Load Balancer Pyro5 (solo directo) | t2.micro |
| **rabbitmq** | Broker RabbitMQ (solo indirecto) | t2.small* |
| **worker1** | Worker (directo e indirecto) | t2.micro |
| **worker2** | Worker (directo e indirecto) | t2.micro |
| **client** | Cliente que lanza los benchmarks | t2.micro |

> *RabbitMQ necesita algo más de RAM; t2.small tiene 2 GB. Los demás con t2.micro (1 GB) van bien.

---

## PARTE 1 — Configurar la VPC

### 1.1 Crear la VPC

1. Ve a **VPC → Your VPCs → Create VPC**
2. Rellena:
   - Name tag: `sd-vpc`
   - IPv4 CIDR: `10.0.0.0/16`
   - Tenancy: Default
3. Click **Create VPC**

### 1.2 Crear la subred

1. Ve a **VPC → Subnets → Create subnet**
2. Rellena:
   - VPC: `sd-vpc`
   - Subnet name: `sd-subnet-public`
   - Availability Zone: elige cualquiera (ej. `eu-west-1a`)
   - IPv4 CIDR: `10.0.1.0/24`
3. Click **Create subnet**
4. Selecciona la subred creada → **Actions → Edit subnet settings**
5. Activa **Enable auto-assign public IPv4 address** → Save

### 1.3 Crear y asociar el Internet Gateway

1. Ve a **VPC → Internet Gateways → Create internet gateway**
   - Name: `sd-igw`
2. Click **Create**, luego **Actions → Attach to VPC** → selecciona `sd-vpc`

### 1.4 Configurar la tabla de rutas

1. Ve a **VPC → Route Tables**
2. Selecciona la route table asociada a `sd-vpc` (la que aparece como "Main")
3. Pestaña **Routes → Edit routes → Add route**:
   - Destination: `0.0.0.0/0`
   - Target: `sd-igw`
4. Click **Save changes**
5. Pestaña **Subnet associations → Edit subnet associations**
   - Selecciona `sd-subnet-public` → Save

---

## PARTE 2 — Grupo de seguridad

1. Ve a **VPC → Security Groups → Create security group**
2. Rellena:
   - Name: `sd-sg`
   - VPC: `sd-vpc`
3. **Inbound rules** — añade estas reglas:

| Type | Protocol | Port range | Source | Descripción |
|------|----------|-----------|--------|-------------|
| SSH | TCP | 22 | 0.0.0.0/0 | Acceso SSH |
| All traffic | All | All | `sd-sg` (el propio SG) | Comunicación interna entre instancias |

> La segunda regla permite que todas las instancias del grupo hablen entre sí libremente (Redis, Pyro5, RabbitMQ, etc.) sin abrir puertos individuales.

4. **Outbound rules**: dejar el default (All traffic `0.0.0.0/0`)
5. Click **Create security group**

---

## PARTE 3 — Lanzar las instancias EC2

Para cada instancia sigue estos pasos comunes y cambia solo el Name y el tipo:

1. Ve a **EC2 → Instances → Launch instances**
2. **Name**: (ver tabla más abajo)
3. **AMI**: Amazon Linux 2 AMI (HVM) — 64-bit x86
4. **Instance type**: t2.micro (o t2.small para rabbitmq)
5. **Key pair**: crea uno nuevo o usa uno existente — guarda el `.pem`
6. **Network settings → Edit**:
   - VPC: `sd-vpc`
   - Subnet: `sd-subnet-public`
   - Auto-assign public IP: Enable
   - Security group: `sd-sg`
7. Click **Launch instance**

Repite para cada una:

| Name tag | Instance type |
|----------|--------------|
| `redis` | t2.micro |
| `nameserver` | t2.micro |
| `loadbalancer` | t2.micro |
| `rabbitmq` | t2.small |
| `worker1` | t2.micro |
| `worker2` | t2.micro |
| `client` | t2.micro |

Una vez lanzadas, anota las **IPs privadas** de cada instancia (columna "Private IPv4 address" en la consola EC2). Las necesitarás para configurar las variables de entorno.

---

## PARTE 4 — Configurar cada instancia

Conéctate por SSH a cada instancia:
```bash
ssh -i tu-clave.pem ec2-user@<IP_PUBLICA>
```

### 4.1 Instancia `redis`

```bash
sudo yum update -y
sudo amazon-linux-extras enable redis6
sudo yum install -y redis

# Permitir conexiones desde la VPC
sudo sed -i 's/^bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf

sudo systemctl enable redis
sudo systemctl start redis
redis-cli ping   # debe responder PONG
```

### 4.2 Instancia `nameserver`

```bash
sudo yum update -y
sudo yum install -y python3 python3-pip
pip3 install Pyro5 serpent
```

### 4.3 Instancia `loadbalancer`

```bash
sudo yum update -y
sudo yum install -y python3 python3-pip
pip3 install Pyro5 serpent
```

### 4.4 Instancia `rabbitmq`

```bash
sudo yum update -y

# Erlang
wget https://github.com/rabbitmq/erlang-rpm/releases/download/v26.2.1/erlang-26.2.1-1.el7.x86_64.rpm
sudo yum install -y erlang-26.2.1-1.el7.x86_64.rpm

# RabbitMQ
wget https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.12.12/rabbitmq-server-3.12.12-1.el8.noarch.rpm
sudo yum install -y rabbitmq-server-3.12.12-1.el8.noarch.rpm

sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server

# Usuario para los clientes/workers
sudo rabbitmqctl add_user user user
sudo rabbitmqctl set_permissions -p / user ".*" ".*" ".*"
sudo rabbitmq-plugins enable rabbitmq_management

sudo systemctl restart rabbitmq-server
echo "RabbitMQ listo"
```

### 4.5 Instancias `worker1`, `worker2` y `client`

```bash
sudo yum update -y
sudo yum install -y python3 python3-pip git
pip3 install Pyro5 serpent redis pika
```

Luego sube el código a cada instancia. Desde **tu máquina local**:

```bash
# Subir carpeta direct/ a worker1 y client
scp -i tu-clave.pem -r direct/ ec2-user@<IP_PUBLICA_WORKER1>:~/
scp -i tu-clave.pem -r direct/ ec2-user@<IP_PUBLICA_CLIENT>:~/

# Subir carpeta indirect/ a worker1, worker2 y client
scp -i tu-clave.pem -r indirect/ ec2-user@<IP_PUBLICA_WORKER1>:~/
scp -i tu-clave.pem -r indirect/ ec2-user@<IP_PUBLICA_WORKER2>:~/
scp -i tu-clave.pem -r indirect/ ec2-user@<IP_PUBLICA_CLIENT>:~/
```

---

## PARTE 5 — Ejecutar el enfoque DIRECTO (Pyro5)

Sustituye las IPs del ejemplo por las IPs privadas reales de tus instancias.

> Abre una terminal SSH por instancia. Respeta el orden de arranque.

### Paso 1 — Arrancar el Name Server (instancia `nameserver`)

```bash
python3 -m Pyro5.nameserver --host 0.0.0.0 --port 9090
```

### Paso 2 — Arrancar los Workers (instancias `worker1` y `worker2`)

En `worker1`:
```bash
export PYRO_NS_HOST=<IP_PRIVADA_NAMESERVER>
export REDIS_HOST=<IP_PRIVADA_REDIS>
export WORKER_HOST=<IP_PRIVADA_WORKER1>

cd ~/direct
python3 worker.py --id 1 --host $WORKER_HOST
```

En `worker2`:
```bash
export PYRO_NS_HOST=<IP_PRIVADA_NAMESERVER>
export REDIS_HOST=<IP_PRIVADA_REDIS>
export WORKER_HOST=<IP_PRIVADA_WORKER2>

cd ~/direct
python3 worker.py --id 2 --host $WORKER_HOST
```

### Paso 3 — Arrancar el Load Balancer (instancia `loadbalancer`)

```bash
export PYRO_NS_HOST=<IP_PRIVADA_NAMESERVER>
export LB_HOST=<IP_PRIVADA_LOADBALANCER>

cd ~/direct
python3 load_balancer.py
```

### Paso 4 — Resetear Redis antes del benchmark

En la instancia `redis` (o desde `client`):
```bash
redis-cli -h <IP_PRIVADA_REDIS> FLUSHDB
redis-cli -h <IP_PRIVADA_REDIS> SET total_sold 0
```

### Paso 5 — Ejecutar el benchmark (instancia `client`)

**Unnumbered** (20 000 tickets):
```bash
export PYRO_NS_HOST=<IP_PRIVADA_NAMESERVER>
cd ~/direct
python3 cliente.py --modo unnumbered
```

**Numbered** (60 000 asientos):
```bash
# Resetear Redis primero
redis-cli -h <IP_PRIVADA_REDIS> FLUSHDB

export PYRO_NS_HOST=<IP_PRIVADA_NAMESERVER>
cd ~/direct
python3 cliente.py --modo numbered
```

---

## PARTE 6 — Ejecutar el enfoque INDIRECTO (RabbitMQ)

### Paso 1 — Resetear Redis

```bash
redis-cli -h <IP_PRIVADA_REDIS> FLUSHDB
redis-cli -h <IP_PRIVADA_REDIS> SET total_sold 0
```

### Paso 2 — Arrancar los Workers (instancias `worker1` y `worker2`)

En `worker1` y `worker2` (cambia `--modo` según el benchmark):
```bash
export REDIS_HOST=<IP_PRIVADA_REDIS>
export RABBIT_HOST=<IP_PRIVADA_RABBITMQ>

cd ~/indirect
# Para unnumbered:
python3 worker.py --modo unnumbered --workers 2

# Para numbered:
python3 worker.py --modo numbered --workers 2
```

`--workers` controla cuántos procesos lanza esta instancia. Con 2 instancias y `--workers 2` tienes 4 workers en total.

### Paso 3 — Ejecutar el cliente (instancia `client`)

**Unnumbered**:
```bash
export RABBIT_HOST=<IP_PRIVADA_RABBITMQ>
cd ~/indirect
python3 cliente.py --modo unnumbered
```

**Numbered**:
```bash
# Resetear Redis primero
redis-cli -h <IP_PRIVADA_REDIS> FLUSHDB

export RABBIT_HOST=<IP_PRIVADA_RABBITMQ>
cd ~/indirect
python3 cliente.py --modo numbered
```

> El cliente envía todas las peticiones a la cola y termina. Los workers las procesan en paralelo. Al hacer Ctrl+C en los workers verás el resumen agregado de cada instancia.

---

## Resumen de puertos usados

| Puerto | Servicio |
|--------|---------|
| 22 | SSH |
| 6379 | Redis |
| 9090 | Pyro5 Name Server |
| 9099 | Pyro5 Load Balancer |
| 9001+ | Pyro5 Workers (automático) |
| 5672 | RabbitMQ AMQP |
| 15672 | RabbitMQ Management UI (opcional) |

Todos están cubiertos por la regla "All traffic dentro del Security Group".

---

## Consejos para el benchmark

- Mide el tiempo **total** que imprime el cliente (directo) o el tiempo hasta que el último worker termina de procesar (indirecto).
- Para el indirecto, el cliente mide solo el tiempo de *envío* a la cola. El tiempo real de procesamiento lo puedes medir con `time python3 worker.py 2` o añadiendo timestamps en los workers.
- Resetea siempre Redis entre pruebas para no contaminar los resultados.
- Para comparar directamente, usa el mismo número de workers en ambos enfoques.
