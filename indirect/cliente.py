#!/usr/bin/env python3
import json
import time
import pika
import os

rabbit_host = os.getenv('RABBIT_HOST', 'localhost')

QUEUE_NUMBERED   = "ticket_numbered"
QUEUE_UNNUMBERED = "ticket_unnumbered"


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

    # Declarar ambas colas (idempotente si ya existen)
    channel.queue_declare(queue=QUEUE_NUMBERED,   durable=True)
    channel.queue_declare(queue=QUEUE_UNNUMBERED, durable=True)

    count  = 0
    inicio = time.time()

    if args.modo == 'numbered':
        queue = QUEUE_NUMBERED
        for client_id, seat_id in leer_benchmark_numbered("benchmark_numbered_60000.txt"):
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps({"seat_id": seat_id, "client_id": client_id}),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            count += 1
    else:
        queue = QUEUE_UNNUMBERED
        for client_id in leer_benchmark_unnumbered("benchmark_unnumbered_20000.txt"):
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps({"client_id": client_id}),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            count += 1

    fin        = time.time()
    elapsed    = fin - inicio
    throughput = count / elapsed if elapsed > 0 else 0

    print(f"\n{'='*50}")
    print(f"CLIENTE ({args.modo}) → cola '{queue}'")
    print(f"{'='*50}")
    print(f"  Peticiones enviadas : {count}")
    print(f"  Tiempo de envio     : {elapsed:.3f} s")
    print(f"  Throughput envio    : {throughput:.2f} msgs/s")
    print(f"  (El throughput real de procesado lo muestran los workers al terminar)")
    print(f"{'='*50}")

    connection.close()


if __name__ == "__main__":
    main()
