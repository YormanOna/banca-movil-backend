from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    firebase_uid = db.Column(db.String(255), unique=True, nullable=False)  # ID de Firebase
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    cards = db.relationship('Card', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)

class Card(db.Model):
    __tablename__ = 'cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_number = db.Column(db.String(16), nullable=False)
    is_frozen = db.Column(db.Boolean, default=False)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    card_number = db.Column(db.String(16), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    transaction = db.relationship('Transaction', uselist=False, backref='payment')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    details = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())