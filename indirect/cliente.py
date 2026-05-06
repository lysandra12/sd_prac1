#!/usr/bin/env python3
import json
import time
import pika
import os

rabbit_host = os.getenv('RABBIT_HOST', 'localhost')


def leer_benchmark_numbered(archivo):
    with open(archivo, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            partes = linea.split()
            # formato: BUY client_id seat_id request_id
            yield partes[1], partes[2]   # client_id, seat_id


def leer_benchmark_unnumbered(archivo):
    with open(archivo, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            partes = linea.split()
            # formato: BUY client_id request_id
            yield partes[1]              # client_id


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Cliente RabbitMQ')
    parser.add_argument('--modo', choices=['numbered', 'unnumbered'], required=True)
    args = parser.parse_args()

    credentials = pika.PlainCredentials('user', 'user')
    connection  = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbit_host, port=5672, credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue="ticket_requests", durable=True)

    count  = 0
    inicio = time.time()

    if args.modo == 'numbered':
        for client_id, seat_id in leer_benchmark_numbered("benchmark_numbered_60000.txt"):
            message = {"seat_id": seat_id, "client_id": client_id}
            channel.basic_publish(
                exchange='',
                routing_key="ticket_requests",
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            count += 1
    else:
        for client_id in leer_benchmark_unnumbered("benchmark_unnumbered_20000.txt"):
            message = {"client_id": client_id}
            channel.basic_publish(
                exchange='',
                routing_key="ticket_requests",
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            count += 1

    fin = time.time()
    elapsed    = fin - inicio
    throughput = count / elapsed if elapsed > 0 else 0

    print(f"\n=== Cliente ({args.modo}) ===")
    print(f"  Peticiones enviadas : {count}")
    print(f"  Tiempo de envio     : {elapsed:.3f} s")
    print(f"  Throughput envio    : {throughput:.2f} msgs/s")
    print(f"  (El throughput real de procesado lo muestra el worker al terminar)")

    connection.close()


if __name__ == "__main__":
    main()
