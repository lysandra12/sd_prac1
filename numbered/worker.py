import os

import pika
import json
import redis
import sys
import signal

# ========== CONFIGURACIÓN ==========
TOTAL_SEATS = 20000
# ========== CONEXIÓN A REDIS ==========

redis_host = os.getenv('REDIS_HOST', 10.0.1.190) 
redis_port = os.getenv('REDIS_PORT', 6379)
redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
try:
    redis_client.ping()
    print("✅ Conexión exitosa a Redis!")   
except redis.exceptions.ConnectionError:
    print("❌ No se pudo conectar a Redis. ¿Está el contenedor corriendo?")
    sys.exit(1)

# conexion a rabbitmq
credentials = pika.PlainCredentials('mi_usuario', 'mi_password')
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', port=5672, credentials=credentials))
channel = connection.channel()

# Declarar cola (durable = sobrevive reinicios de RabbitMQ)
channel.queue_declare(queue="ticket_requests", durable=True)

# Worker procesa 1 mensaje a la vez (prefetch=1 evita sobrecarga)
channel.basic_qos(prefetch_count=1)

# ========== FUNCIÓN ATÓMICA DE COMPRA ==========
def try_buy_seat(seat_id, client_id):
    """
    Intenta comprar un asiento usando SETNX atómico.
    Retorna (success, message)
    """    
    # SETNX: 1 si se puso, 0 si ya existía
    was_free = redis_client.setnx(seat_id, "OCCUPIED")
    
    if was_free:
        # Opcional: llevar contador de vendidos
        sold = redis_client.incr("total_sold")
        return True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold}/20000)"
    else:
        # El asiento ya está ocupado
        owner = redis_client.get(seat_id)
        return False, f"Asiento {seat_id} ya ocupado por {owner}"

# ========== CALLBACK DE PROCESAMIENTO ==========
def callback(ch, method, properties, body):
    """
    Procesa cada mensaje de RabbitMQ
    """
    try:
        msg = json.loads(body)
        
        seat_id = msg["seat_id"]
        client_id = msg["client_id"]
        
        print(f"\n[Worker] Procesando: Asiento {seat_id} para {client_id}")
        
        # PASO CRÍTICO: Verificar y comprar en Redis (ATÓMICO)
        success, message = try_buy_seat(seat_id, client_id)
        
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ A {message}")
        
        # Confirmar procesamiento (eliminar mensaje de cola)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        print(f"  ✗ Error JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)  # Descartar corrupto
    except redis.ConnectionError as e:
        print(f"  ✗ Redis no disponible: {e}")
        # NO hacer ack - mensaje se reencolará
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as e:
        print(f"  ✗ Error inesperado: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

# ========== INICIAR WORKER ==========
def signal_handler(sig, frame):
    print("\n\nDeteniendo worker...")
    channel.stop_consuming()
    connection.close()
    redis_client.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("=" * 50)
print(f"WORKER INICIADO")
print(f"Modo:     Asientos numerados (SETNX)")
print("=" * 50)

channel.basic_consume(queue="ticket_requests", on_message_callback=callback)
channel.start_consuming()