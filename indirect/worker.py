#!/usr/bin/env python3
import os
import sys
import json
import signal
import time
import redis
import pika
import multiprocessing

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


def run_worker(worker_id, modo, stats_queue):
    success_count = 0
    fail_count    = 0
    start_time    = None
    last_time     = None

    redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        redis_client.ping()
        print(f"Worker {worker_id}: Redis OK")
    except redis.exceptions.ConnectionError:
        print(f"Worker {worker_id}: No se pudo conectar a Redis en {redis_host}:{redis_port}")
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
                success, message = try_buy_seat(
                    redis_client, msg["seat_id"], msg["client_id"]
                )
            else:
                success, message = try_buy_ticket(
                    redis_client, msg["client_id"]
                )

            last_time = time.time()
            if success:
                success_count += 1
            else:
                fail_count += 1

            print(f"[Worker {worker_id}] {'OK' if success else 'KO'} {message}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError as e:
            print(f"[Worker {worker_id}] Error JSON: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except redis.ConnectionError as e:
            print(f"[Worker {worker_id}] Redis no disponible: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            print(f"[Worker {worker_id}] Error inesperado: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    signal.signal(signal.SIGINT, signal.SIG_IGN)

    print(f"Worker {worker_id} INICIADO ({modo})")
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

        elapsed    = (last_time - start_time) if start_time and last_time else 0.0
        total_ops  = success_count + fail_count
        throughput = total_ops / elapsed if elapsed > 0 else 0.0

        stats = {
            "worker_id":      worker_id,
            "success":        success_count,
            "fail":           fail_count,
            "total":          total_ops,
            "elapsed_s":      round(elapsed, 3),
            "throughput_ops": round(throughput, 2),
        }
        stats_queue.put(stats)
        print(
            f"\n=== Worker {worker_id} ===\n"
            f"  Exitos    : {success_count}\n"
            f"  Fallos    : {fail_count}\n"
            f"  Total ops : {total_ops}\n"
            f"  Tiempo    : {elapsed:.3f} s\n"
            f"  Throughput: {throughput:.2f} ops/s"
        )


def imprimir_resumen(modo, stats_list):
    if not stats_list:
        return
    total_ok   = sum(s["success"]   for s in stats_list)
    total_fail = sum(s["fail"]      for s in stats_list)
    total_ops  = sum(s["total"]     for s in stats_list)
    max_time   = max(s["elapsed_s"] for s in stats_list)
    throughput = total_ops / max_time if max_time > 0 else 0.0

    print(f"\n{'='*50}")
    print(f"RESUMEN AGREGADO — {modo} (indirecto)")
    print(f"{'='*50}")
    print(f"  Workers activos : {len(stats_list)}")
    print(f"  Total exitos    : {total_ok}")
    print(f"  Total fallos    : {total_fail}")
    print(f"  Total ops       : {total_ops}")
    print(f"  Tiempo (max w.) : {max_time:.3f} s")
    print(f"  Throughput real : {throughput:.2f} ops/s")
    print(f"{'='*50}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Worker RabbitMQ')
    parser.add_argument('--modo', choices=['numbered', 'unnumbered'], required=True)
    parser.add_argument('--workers', type=int, default=1,
                        help='Numero de procesos worker a lanzar')
    args = parser.parse_args()

    stats_queue = multiprocessing.Queue()
    processes   = []

    try:
        for i in range(args.workers):
            p = multiprocessing.Process(
                target=run_worker, args=(i + 1, args.modo, stats_queue)
            )
            p.start()
            processes.append(p)
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nCerrando workers...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join()

    stats_list = []
    while not stats_queue.empty():
        stats_list.append(stats_queue.get())
    imprimir_resumen(args.modo, stats_list)
