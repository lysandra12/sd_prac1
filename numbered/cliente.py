import json
import time
import pika

from numbered.Clientes import Cliente 

class TicketClient:
    def __init__(self):

        self.credentials = pika.PlainCredentials('user', 'user')
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=10.0.1.8, port=5672, credentials=self.credentials)
        )
        self.channel = self.connection.channel()
        
        # Asegurar que la cola existe
        self.channel.queue_declare(queue="ticket_requests", durable=True)

    def send_buy_request(self, seat_id, client_id, request_id):
        """Envía una petición de compra a RabbitMQ"""
        # Crear mensaje
        message = {
            "seat_id": seat_id,
            "client_id": client_id
        }
        
        # Publicar mensaje persistente
        self.channel.basic_publish(
            exchange='',
            routing_key="ticket_requests",
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistente
            )
        )
        
        print(f"[Cliente] Enviado: Asiento {seat_id} para {client_id} (req: {request_id})")

# Ejemplo de uso
if __name__ == "__main__":
    client = TicketClient()
    inicio = time.time()

    with open("benchmark_numbered_60000.txt", 'r') as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            
            operacion, client_id, seat_id, request_id = linea.split()
            cliente = Cliente(client_id, seat_id, request_id, "BUY")
            client.send_buy_request(seat_id, client_id, request_id)

    fin = time.time()
    tiempo_total = fin - inicio
    print(f"[Cliente] Tiempo total: {tiempo_total} segundos")
    client.connection.close()
