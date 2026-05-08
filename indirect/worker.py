#!/usr/bin/env python3
import os
import sys
import json
import signal
import time
import redis
import pika

TOTAL_TICKETS = 20000   # limite unnumbered
TOTAL_SEATS   = 60000   # limite numbered

redis_host  = os.getenv('REDIS_HOST',  'localhost')
redis_port  = int(os.getenv('REDIS_PORT', '6379'))
rabbit_host = os.getenv('RABBIT_HOST', 'localhost')


def try_buy_seat(redis_client, seat_id, client_id):
    """Numbered: reserva un asiento especifico de forma atomica."""
    was_free = redis_client.setnx(f"seat:{seat_id}", client_id)
    if was_free:
        sold = redis_client.incr("total_sold")
        return True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold}/{TOTAL_SEATS})"
    owner = redis_client.get(f"seat:{seat_id}")
    return False, f"Asiento {seat_id} ya ocupado por {owner}"


def try_buy_ticket(redis_client, client_id):
    """Unnumbered: asigna el siguiente ticket disponible de forma atomica."""
    sold = redis_client.incr("total_sold")
    if sold <= TOTAL_TICKETS:
        return True, f"Ticket #{sold} vendido a {client_id}"
    redis_client.decr("total_sold")
    return False, f"No quedan tickets (solicitado por {client_id})"


def run(modo):
    import argparse
    success_count = 0
    fail_count    = 0
    start_time    = None
    last_time     = None

    redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        redis_client.ping()
        print(f"Worker: Redis OK ({redis_host}:{redis_port})")
    except redis.exceptions.ConnectionError:
        print(f"Worker: No se pudo conectar a Redis en {redis_host}:{redis_port}")
        sys.exit(1)

    credentials = pika.PlainCredentials('user', 'user')
    connection  = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbit_host, port=5672, credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue="ticket_requests", durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        nonlocal success_count, fail_count, start_time, last_time
        try:
            msg = json.loads(body)
            now = time.time()
            if start_time is None:
                start_time = now

            if modo == 'numbered':
                success, message = try_buy_seat(redis_client, msg["seat_id"], msg["client_id"])
            else:
                success, message = try_buy_ticket(redis_client, msg["client_id"])

            last_time = time.time()
            if success:
                success_count += 1
            else:
                fail_count += 1

            print(f"[Worker] {'OK' if success else 'KO'} {message}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError as e:
            print(f"[Worker] Error JSON: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except redis.ConnectionError as e:
            print(f"[Worker] Redis no disponible: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            print(f"[Worker] Error inesperado: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def print_stats():
        elapsed    = (last_time - start_time) if start_time and last_time else 0.0
        total_ops  = success_count + fail_count
        throughput = total_ops / elapsed if elapsed > 0 else 0.0
        print(
            f"\n{'='*50}\n"
            f"RESUMEN WORKER ({modo})\n"
            f"{'='*50}\n"
            f"  Exitos    : {success_count}\n"
            f"  Fallos    : {fail_count}\n"
            f"  Total ops : {total_ops}\n"
            f"  Tiempo    : {elapsed:.3f} s\n"
            f"  Throughput: {throughput:.2f} ops/s\n"
            f"{'='*50}"
        )

    def signal_handler(sig, frame):
        print("\nDeteniendo worker...")
        try:
            channel.stop_consuming()
        except Exception:
            pass

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Worker INICIADO | modo={modo} | RabbitMQ={rabbit_host}")
    try:
        channel.basic_consume(queue="ticket_requests", on_message_callback=callback)
        channel.start_consuming()
    except Exception:
        pass
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
        redis_client.close()
        print_stats()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Worker RabbitMQ')
    parser.add_argument('--modo', choices=['numbered', 'unnumbered'], required=True,
                        help='Tipo de benchmark')
    args = parser.parse_args()
    run(args.modo)
