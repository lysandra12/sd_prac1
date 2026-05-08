#!/usr/bin/env python3
import os
import sys
import json
import signal
import time
import redis
import pika

TOTAL_TICKETS = 20000
TOTAL_SEATS   = 60000

redis_host  = os.getenv('REDIS_HOST',  'localhost')
redis_port  = int(os.getenv('REDIS_PORT', '6379'))
rabbit_host = os.getenv('RABBIT_HOST', 'localhost')

QUEUE_NUMBERED   = "ticket_numbered"
QUEUE_UNNUMBERED = "ticket_unnumbered"


# ─── Lógica de negocio ────────────────────────────────────────────────────────

def buy_numbered(redis_client, seat_id, client_id):
    """Reserva un asiento especifico de forma atomica."""
    was_free = redis_client.setnx(f"seat:{seat_id}", client_id)
    if was_free:
        sold = redis_client.incr("total_sold")
        return True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold}/{TOTAL_SEATS})"
    owner = redis_client.get(f"seat:{seat_id}")
    return False, f"Asiento {seat_id} ya ocupado por {owner}"


def buy_unnumbered(redis_client, client_id):
    """Asigna el siguiente ticket disponible de forma atomica."""
    sold = redis_client.incr("total_sold")
    if sold <= TOTAL_TICKETS:
        return True, f"Ticket #{sold} vendido a {client_id}"
    redis_client.decr("total_sold")
    return False, f"No quedan tickets (solicitado por {client_id})"


# ─── Worker ───────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self, name):
        self.name    = name
        self.success = 0
        self.fail    = 0
        self.t0      = None
        self.t1      = None

    def record(self, ok):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        self.t1 = now
        if ok:
            self.success += 1
        else:
            self.fail += 1

    def print(self):
        elapsed    = (self.t1 - self.t0) if self.t0 and self.t1 else 0.0
        total      = self.success + self.fail
        throughput = total / elapsed if elapsed > 0 else 0.0
        print(
            f"\n{'='*50}\n"
            f"RESUMEN WORKER — cola: {self.name}\n"
            f"{'='*50}\n"
            f"  Exitos    : {self.success}\n"
            f"  Fallos    : {self.fail}\n"
            f"  Total ops : {total}\n"
            f"  Tiempo    : {elapsed:.3f} s\n"
            f"  Throughput: {throughput:.2f} ops/s\n"
            f"{'='*50}"
        )


def main():
    rc = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        rc.ping()
        print(f"Worker: Redis OK ({redis_host}:{redis_port})")
    except redis.exceptions.ConnectionError:
        print(f"Worker: no se pudo conectar a Redis en {redis_host}:{redis_port}")
        sys.exit(1)

    credentials = pika.PlainCredentials('user', 'user')
    conn    = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbit_host, port=5672, credentials=credentials)
    )
    channel = conn.channel()

    channel.queue_declare(queue=QUEUE_NUMBERED,   durable=True)
    channel.queue_declare(queue=QUEUE_UNNUMBERED, durable=True)
    channel.basic_qos(prefetch_count=1)

    stats_n  = Stats(QUEUE_NUMBERED)
    stats_un = Stats(QUEUE_UNNUMBERED)

    # ── callback para cola numbered ──────────────────────────────────────────
    def on_numbered(ch, method, props, body):
        try:
            msg              = json.loads(body)
            ok, msg_text     = buy_numbered(rc, msg["seat_id"], msg["client_id"])
            stats_n.record(ok)
            print(f"[numbered] {'OK' if ok else 'KO'} {msg_text}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except redis.ConnectionError:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            print(f"[numbered] Error: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    # ── callback para cola unnumbered ────────────────────────────────────────
    def on_unnumbered(ch, method, props, body):
        try:
            msg              = json.loads(body)
            ok, msg_text     = buy_unnumbered(rc, msg["client_id"])
            stats_un.record(ok)
            print(f"[unnumbered] {'OK' if ok else 'KO'} {msg_text}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except redis.ConnectionError:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except Exception as e:
            print(f"[unnumbered] Error: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NUMBERED,   on_message_callback=on_numbered)
    channel.basic_consume(queue=QUEUE_UNNUMBERED, on_message_callback=on_unnumbered)

    def on_stop(sig, frame):
        print("\nDeteniendo worker...")
        try:
            channel.stop_consuming()
        except Exception:
            pass

    signal.signal(signal.SIGINT,  on_stop)
    signal.signal(signal.SIGTERM, on_stop)

    print(f"Worker listo | escuchando '{QUEUE_NUMBERED}' y '{QUEUE_UNNUMBERED}'")
    try:
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
            if conn.is_open:
                conn.close()
        except Exception:
            pass
        rc.close()
        stats_n.print()
        stats_un.print()


if __name__ == "__main__":
    main()
