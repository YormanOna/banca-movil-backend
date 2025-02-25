from flask import Flask, request, jsonify
from models import db, User, Card, Payment, Transaction
from config import Config
import pyrebase
import requests

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Inicializar Firebase
firebase = pyrebase.initialize_app(app.config['FIREBASE_CONFIG'])
auth = firebase.auth()

# Crear tablas en la base de datos
with app.app_context():
    db.create_all()

# Registro de usuario con Firebase Auth
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name, email, password = data.get('name'), data.get('email'), data.get('password')
    if not all([name, email, password]):
        return jsonify({'error': 'Faltan datos'}), 400
    
    try:
        user = auth.create_user_with_email_and_password(email, password)  # Sin encriptar, como pediste
        new_user = User(firebase_uid=user['localId'], name=name, email=email)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Usuario registrado', 'id': new_user.id}), 201
    except:
        return jsonify({'error': 'Error al registrar, email puede estar en uso'}), 409

# Inicio de sesión con Firebase Auth
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email, password = data.get('email'), data.get('password')
    
    try:
        # Intentar iniciar sesión con Firebase Auth
        user = auth.sign_in_with_email_and_password(email, password)
        
        # Buscar al usuario en la base de datos local por su firebase_uid
        db_user = User.query.filter_by(firebase_uid=user['localId']).first()
        
        if not db_user:
            return jsonify({'error': 'Usuario no encontrado en la base de datos'}), 404
        
        # Retornar solo los datos del usuario sin el balance ni las tarjetas
        return jsonify({
            'message': 'Inicio de sesión exitoso',
            'user': {
                'id': db_user.id,  # ID del usuario en la base de datos
                'name': db_user.name,
                'email': db_user.email
            }
        })
    except Exception as e:
        print(e)  # Imprimir el error para diagnosticar
        return jsonify({'error': 'Credenciales inválidas'}), 401


# Agregar tarjeta
@app.route('/cards', methods=['POST'])
def add_card():
    data = request.get_json()
    user_id, card_number, balance = data.get('user_id'), data.get('card_number'), data.get('balance', 0.0)

    if not all([user_id, card_number]) or len(card_number) != 16 or not card_number.isdigit():
        return jsonify({'error': 'Datos inválidos'}), 400

    card = Card(user_id=user_id, card_number=card_number, balance=balance)
    db.session.add(card)
    db.session.commit()
    return jsonify({'message': 'Tarjeta agregada', 'id': card.id, 'balance': card.balance}), 201

# Congelar tarjeta
@app.route('/cards/<int:card_id>/freeze', methods=['PUT'])
def freeze_card(card_id):
    card = Card.query.get_or_404(card_id)
    card.is_frozen = True
    db.session.commit()
    return jsonify({'message': 'Tarjeta congelada', 'is_frozen': card.is_frozen})

# Procesar pago y enviar notificación con FCM
@app.route('/payments', methods=['POST'])
def process_payment():
    data = request.get_json()
    user_id, amount, card_number = data.get('user_id'), data.get('amount'), data.get('card_number')

    if not all([user_id, amount, card_number]) or amount <= 0:
        return jsonify({'error': 'Datos inválidos'}), 400

    card = Card.query.filter_by(card_number=card_number, user_id=user_id).first()
    if not card or card.is_frozen:
        return jsonify({'error': 'Tarjeta no válida o congelada'}), 400

    if card.balance < amount:
        return jsonify({'error': 'Saldo insuficiente'}), 400

    # Crear pago y transacción
    payment = Payment(user_id=user_id, amount=amount, card_number=card_number)
    transaction = Transaction(payment=payment, details=f'Pago de {amount} con tarjeta {card_number[-4:]}')

    # Restar saldo a la tarjeta
    card.balance -= amount
    db.session.add_all([payment, transaction])
    db.session.commit()

    # Enviar notificación con FCM
    fcm_url = 'https://fcm.googleapis.com/fcm/send'
    headers = {
        'Authorization': f'key={app.config["FIREBASE_SERVER_KEY"]}',
        'Content-Type': 'application/json'
    }
    payload = {
        'to': '/topics/user_' + str(user_id),
        'notification': {
            'title': 'Pago Realizado',
            'body': f'Has realizado un pago de ${amount} con éxito.'
        }
    }
    requests.post(fcm_url, json=payload, headers=headers)

    return jsonify({'message': 'Pago procesado', 'payment_id': payment.id})

# Historial de transacciones
@app.route('/transactions/<int:user_id>', methods=['GET'])
def get_transactions(user_id):
    date_filter = request.args.get('date')
    query = Transaction.query.join(Payment).filter(Payment.user_id == user_id)
    
    if date_filter:
        query = query.filter(db.func.date(Transaction.timestamp) == date_filter)
    transactions = [{
        'id': t.id,
        'amount': t.payment.amount,
        'details': t.details,
        'timestamp': t.timestamp.isoformat()
    } for t in query.all()]
    return jsonify({'transactions': transactions})

@app.route('/cards/<int:user_id>', methods=['GET'])
def get_cards(user_id):
    cards = Card.query.filter_by(user_id=user_id).all()
    return jsonify([{'id': c.id, 'card_number': c.card_number, 'is_frozen': c.is_frozen, 'balance': c.balance} for c in cards])

if __name__ == '__main__':
    app.run(debug=True)