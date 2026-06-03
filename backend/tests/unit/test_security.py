from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from jose import jwt

def test_password_hashing():
    plain_pass = "SecureStudent123!" # Keep this under 72 characters!
    
    hashed = get_password_hash(plain_pass)
    
    assert hashed != plain_pass
    assert verify_password(plain_pass, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_create_access_token():
    dummy_student_id = "99"
    token = create_access_token(dummy_student_id)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert decoded["sub"] == dummy_student_id
    assert decoded["type"] == "access"
    assert "exp" in decoded