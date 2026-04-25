import os
import sys
import json
import signal
import redis
import pika
import multiprocessing

TOTAL_SEATS = 20000
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', '6379'))
rabbit_host = os.getenv('RABBIT_HOST', '192.168.1.112')


def try_buy_seat(redis_client, seat_id, client_id):
    was_free = redis_client.setnx(seat_id, "OCCUPIED")
    if was_free:
        sold = redis_client.incr("total_sold")
        return True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold}/{TOTAL_SEATS})"
    owner = redis_client.get(seat_id)
    return False, f"Asiento {seat_id} ya ocupado por {owner}"


def run_worker(worker_id):
    redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    redis_client.flushdb()
    redis_client.set("total_sold", 0)
    try:
        redis_client.ping()
        print(f"✅ Worker {worker_id}: Conexión exitosa a Redis")
    except redis.exceptions.ConnectionError:
        print(f"❌ Worker {worker_id}: No se pudo conectar a Redis")
        sys.exit(1)

    credentials = pika.PlainCredentials('user', 'user')
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbit_host, port=5672, credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue="ticket_requests", durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        try:
            msg = json.loads(body)
            seat_id = msg["seat_id"]
            client_id = msg["client_id"]

            success, message = try_buy_seat(redis_client, seat_id, client_id)

            if success:
                print(f"[Worker {worker_id}] ✓ {message}")
            else:
                print(f"[Worker {worker_id}] ✗ {message}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError as e:
            print(f"[Worker {worker_id}] ✗ Error JSON: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except redis.ConnectionError as e:
            print(f"[Worker {worker_id}] ✗ Redis no disponible: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            print(f"[Worker {worker_id}] ✗ Error inesperado: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def signal_handler(sig, frame):
        print(f"\nWorker {worker_id} deteniéndose...")
        try:
            channel.stop_consuming()
        except Exception:
            pass

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 50)
    print(f"WORKER {worker_id} INICIADO")
    print("=" * 50)

    try:
        channel.basic_consume(queue="ticket_requests", on_message_callback=callback)
        channel.start_consuming()
    except KeyboardInterrupt:
        print(f"\nWorker {worker_id}: Ctrl+C recibido")
    finally:
        try:
            if channel.is_open:
                channel.close()
        except Exception:
            pass
        try:
            if connection.is_open:
                connection.close()
        except Exception:
            pass
        try:
            redis_client.close()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python worker.py <num_workers>")
        sys.exit(1)

    num_workers = int(sys.argv[1])
    processes = []

    try:
        for i in range(num_workers):
            p = multiprocessing.Process(target=run_worker, args=(i + 1,))
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("\nCtrl+C en el proceso principal. Cerrando workers...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join()