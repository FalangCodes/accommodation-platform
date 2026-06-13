from cryptography.fernet import Fernet
from app.core.config import settings

def encrypt_value(value: str) -> str:
    f = Fernet(settings.ENCRYPTION_KEY.encode())
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted: str) -> str:
    f = Fernet(settings.ENCRYPTION_KEY.encode()).decode()
    return f.decrypt(encrypted.encode()).decode()