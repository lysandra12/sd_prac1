class Cliente:
    def __init__(self, client_id, seat_id, request_id, operacion="BUY"):
        # Convertir a tipos apropiados si es necesario
        self.client_id = int(client_id) if client_id.isdigit() else client_id
        self.request_id = int(request_id) if request_id.isdigit() else request_id
        self.operacion = operacion
        self.seat_id = seat_id

    def __str__(self):
        return f"Cliente(id={self.client_id}, seat_id={self.seat_id}, request={self.request_id}, operacion={self.operacion})"
    
    def to_dict(self):
        """Convierte el objeto a diccionario"""
        return {
            'client_id': self.client_id,
            'seat_id': self.seat_id,
            'request_id': self.request_id,
            'operacion': self.operacion
        }
