# Práctica 1 — Sistemas Distribuidos
## Venta de Entradas con Comunicación Directa e Indirecta

**Asignatura:** Sistemas Distribuidos  
**Universidad:** Universitat Rovira i Virgili  

---

## 9.1 Descripción del Sistema

### Visión general

Se ha implementado un sistema de venta de entradas para conciertos con dos arquitecturas distribuidas independientes:

- **Arquitectura Directa**: los clientes se comunican con los workers a través de un Load Balancer mediante llamadas RPC síncronas (Pyro5).
- **Arquitectura Indirecta**: los clientes publican peticiones en colas de mensajes (RabbitMQ) que los workers consumen de forma asíncrona.

Ambas arquitecturas soportan dos modos de venta:
- **Numbered**: asientos numerados con identificador único. Se garantiza que cada asiento solo se vende una vez.
- **Unnumbered**: entradas sin asiento asignado. Se venden hasta agotar el aforo total.

### Middleware utilizado

| Componente | Tecnología | Propósito |
|---|---|---|
| Comunicación directa | Pyro5 (Python Remote Objects) | RPC sobre TCP entre cliente, LB y workers |
| Comunicación indirecta | RabbitMQ + pika | Cola de mensajes duradera entre cliente y workers |
| Estado compartido | Redis | Almacenamiento atómico del estado de ventas |
| Registro de servicios | Pyro5 NameServer | Descubrimiento de workers en la arquitectura directa |

### Despliegue en AWS Academy

La infraestructura se despliega automáticamente con **Terraform** sobre instancias EC2 de Amazon Linux 2 en la región `us-east-1`. Cada arquitectura tiene su propia configuración independiente.

**Arquitectura Directa** — instancias EC2:

| Instancia | Tipo | Función |
|---|---|---|
| `direct-infra` | t2.micro | Redis + Pyro5 NameServer |
| `direct-loadbalancer` | t2.micro | Load Balancer (Pyro5) |
| `direct-workerN` | t2.micro | Worker RPC (N instancias) |
| `direct-client` | t2.micro | Cliente benchmark |

**Arquitectura Indirecta** — instancias EC2:

| Instancia | Tipo | Función |
|---|---|---|
| `indirect-infra` | t2.small | Redis + RabbitMQ |
| `indirect-workerN` | t2.micro | Worker consumidor (N instancias) |
| `indirect-client` | t2.micro | Cliente benchmark |

Todos los servicios se configuran como unidades **systemd** y arrancan automáticamente tras el despliegue. El despliegue completo se realiza con un único comando:

```bash
terraform apply -var="num_workers=N"
```

---

## 9.2 Comparación Arquitectónica

### Comunicación directa vs. indirecta

| Aspecto | Directa (Pyro5) | Indirecta (RabbitMQ) |
|---|---|---|
| Tipo | Síncrona (request-reply) | Asíncrona (fire-and-forget) |
| Acoplamiento | Fuerte (cliente espera respuesta) | Débil (cliente no espera) |
| Latencia por petición | Alta (2 saltos de red: cliente→LB→worker) | Baja para el cliente (solo publica) |
| Throughput | Limitado por el LB | Escala con el número de workers |
| Tolerancia a fallos | Si el LB cae, el sistema falla | Si un worker cae, otro toma sus mensajes |

### Estrategia de balanceo de carga

**Directa**: el Load Balancer implementa un algoritmo **round-robin** sobre la lista de workers registrados en el Pyro5 NameServer. El LB es un único punto de entrada y, por tanto, un posible cuello de botella. La lista de workers se carga al arrancar el LB; añadir workers requiere reiniciar el LB.

**Indirecta**: el balanceo es **implícito**. Los workers compiten por los mensajes de las colas `ticket_numbered` y `ticket_unnumbered` con `prefetch_count=1`, lo que garantiza una distribución equitativa de la carga sin ningún componente central adicional.

### Mecanismos de consistencia

Ambas arquitecturas utilizan **Redis** como fuente de verdad compartida:

- **Numbered**: operación atómica `SETNX seat:<id> <client_id>`. Solo el primer cliente que ejecuta la operación obtiene el asiento; los demás reciben un fallo.
- **Unnumbered**: operación atómica `INCR total_sold`. Si el valor resultante supera el aforo, se revierte con `DECR`. Garantiza que nunca se venden más entradas de las disponibles.

Estas operaciones son atómicas en Redis por diseño, lo que elimina condiciones de carrera sin necesidad de bloqueos a nivel de aplicación.

### Cuellos de botella y limitaciones

**Arquitectura Directa:**
- El Load Balancer centralizado es el principal cuello de botella: todas las peticiones pasan por él.
- Cada petición requiere dos conexiones Pyro5 (cliente→LB y LB→worker), lo que duplica la latencia de red.
- Los experimentos muestran que el throughput se estanca e incluso decrece al añadir más de 2 workers, confirmando la saturación del LB.

**Arquitectura Indirecta:**
- RabbitMQ puede convertirse en cuello de botella con un número muy elevado de workers.
- Al ser asíncrona, el cliente no recibe confirmación de éxito o fallo por petición.
- La instancia que aloja Redis y RabbitMQ conjuntamente puede limitar el rendimiento bajo alta carga (se usó t2.small para mitigar esto).

---

## 9.3 Resultados Experimentales

Los benchmarks se han ejecutado con 1, 2, 3 y 6 workers para ambas arquitecturas y modos, sobre instancias EC2 t2.micro en AWS Academy.

### Datos de rendimiento

**Arquitectura Directa — Throughput total (ops/s):**

| Workers | Unnumbered | Numbered |
|---------|-----------|---------|
| 1 | 328,72 | 269,09 |
| 2 | 287,97 | 251,14 |
| 3 | 286,10 | 238,08 |
| 6 | 279,56 | 248,61 |

**Arquitectura Indirecta — Throughput total (ops/s):**

| Workers | Unnumbered | Numbered |
|---------|-----------|---------|
| 1 | 681,14 | 517,40 |
| 2 | 1327,51 | 1074,17 |
| 3 | 1867,35 | 1492,70 |
| 6 | 2584,90 | 2226,34 |

### Gráficas

**Figura 1 — Throughput comparativo por arquitectura y modo**

```
[ PEGAR AQUÍ: grafica_throughput.png ]
```

---

**Figura 2 — Éxitos vs. Fallos por configuración**

```
[ PEGAR AQUÍ: grafica_exitos_fallos.png ]
```

---

**Figura 3 — Escalabilidad: throughput vs. número de workers**

```
[ PEGAR AQUÍ: grafica_escalabilidad.png ]
```

---

**Figura 4 — Distribución de carga entre workers**

```
[ PEGAR AQUÍ: grafica_carga_workers.png ]
```

---

### Análisis de escalabilidad

La arquitectura **indirecta escala de forma casi lineal** con el número de workers:
- De 1 a 6 workers (×6), el throughput unnumbered pasa de 681 a 2585 ops/s (×3,8).
- El factor de escalado no es perfecto porque RabbitMQ introduce cierta latencia adicional al aumentar la concurrencia.

La arquitectura **directa no escala** más allá de 2 workers:
- El throughput máximo se alcanza con 2 workers (~346 ops/s unnumbered).
- Con 3 y 6 workers el rendimiento cae, confirmando que el LB está saturado.

### Comportamiento observado

- En modo **numbered**, ambas arquitecturas presentan más fallos que éxitos cuando hay múltiples workers, ya que los mismos asientos son solicitados por varios clientes concurrentemente. Esto es el comportamiento esperado y correcto.
- En modo **unnumbered**, los fallos son prácticamente nulos porque Redis gestiona el contador de forma atómica y los workers retroceden inmediatamente si el aforo se supera.
- La distribución de carga entre workers es muy equitativa en ambas arquitecturas (desviación < 5% entre workers).

---

## 9.4 Discusión Conceptual

### Tradeoffs entre throughput y consistencia

Ambas arquitecturas priorizan la consistencia sobre el throughput al usar operaciones atómicas de Redis. Esto garantiza la corrección (ningún asiento se vende dos veces) a costa de que Redis sea un punto de contención compartido.

En la arquitectura indirecta, el throughput es mucho mayor porque los workers procesan mensajes de forma completamente independiente; la consistencia se delega a Redis sin que haya ningún componente intermediario (LB) que frene el flujo.

### Impacto de la contención en el rendimiento

La contención es más evidente en el modo **numbered**: múltiples workers intentan reservar los mismos asientos, generando una tasa de fallos de aproximadamente el 23% (5997 fallos sobre 25997 intentos). Esta contención es inherente al problema y no puede eliminarse sin sacrificar consistencia.

En modo **unnumbered** la contención es mínima porque el contador Redis es muy rápido de incrementar y la probabilidad de colisión es baja con los volúmenes de prueba.

### Idoneidad de cada enfoque para sistemas reales

**Comunicación Directa (Pyro5 + LB)** es adecuada cuando:
- Se requiere respuesta inmediata al cliente (el usuario sabe si obtuvo el asiento al instante).
- El número de workers es bajo y estable.
- La simplicidad del sistema es prioritaria.

**Comunicación Indirecta (RabbitMQ)** es adecuada cuando:
- El throughput y la escalabilidad son prioritarios.
- Se puede tolerar que el cliente no reciba confirmación inmediata.
- Se espera un número elevado y variable de workers (auto-scaling).
- Se requiere tolerancia a fallos: si un worker cae, los mensajes no se pierden (colas durables).

En un sistema de venta de entradas real, la arquitectura indirecta sería preferible para la venta masiva (p.ej., conciertos con alta demanda), mientras que la directa podría usarse para consultas de disponibilidad donde la latencia baja es crítica.

---

## Instrucciones de despliegue

### Requisitos previos

- Terraform >= 1.0
- AWS CLI configurado con credenciales de AWS Academy (`~/.aws/credentials`)
- Python 3 con `matplotlib` (para las gráficas)

### Despliegue de la arquitectura directa

```bash
cd terraform/direct
terraform init
terraform apply -var="num_workers=2"
# Seguir las instrucciones del output
```

### Despliegue de la arquitectura indirecta

```bash
cd terraform/indirect
terraform init
terraform apply -var="num_workers=2"
# Seguir las instrucciones del output
```

### Ejecución del benchmark

```bash
# En el cliente EC2 (SSH)
bash ~/benchmark.sh unnumbered
bash ~/benchmark.sh numbered
```

### Destruir la infraestructura

```bash
terraform destroy
```

---

## Código fuente

```
prac1_sd/
├── direct/
│   ├── worker.py          # Worker Pyro5
│   ├── load_balancer.py   # Load Balancer round-robin
│   └── cliente.py         # Cliente benchmark
├── indirect/
│   ├── worker.py          # Worker RabbitMQ
│   └── cliente.py         # Cliente benchmark
├── terraform/
│   ├── direct/            # Infraestructura AWS arquitectura directa
│   └── indirect/          # Infraestructura AWS arquitectura indirecta
└── graficas.py            # Generación de gráficas
```
