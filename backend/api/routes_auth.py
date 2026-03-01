from fastapi import APIRouter, HTTPException
from schemas.models import OTPSendRequest, OTPVerifyRequest, TokenResponse, LoginRequest, RegisterRequest
from services.dynamodb_service import create_or_update_user

router = APIRouter()

# In-memory OTP store + name cache for development.
_otp_store: dict = {}
_name_store: dict = {}  # phone -> name, so verify-otp can upsert with name

@router.post("/send-otp", summary="Send an OTP to the user's phone")
async def send_otp(request: OTPSendRequest):
    mock_otp = "123456"
    _otp_store[request.phone_number] = mock_otp
    if request.name:
        _name_store[request.phone_number] = request.name
    # Save email if provided
    if request.email:
        _name_store[f"{request.phone_number}_email"] = request.email
    print(f"[MOCK] Sending OTP {mock_otp} to {request.phone_number}")
    return {"message": "OTP sent successfully."}

@router.post("/verify-otp", response_model=TokenResponse, summary="Verify OTP and return auth token")
async def verify_otp(request: OTPVerifyRequest):
    stored_otp = _otp_store.get(request.phone_number)

    if not stored_otp or stored_otp != request.otp:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP.")

    del _otp_store[request.phone_number]

    # Upsert user in DynamoDB with name captured from send-otp step
    name = request.name or _name_store.pop(request.phone_number, request.phone_number)
    
    # Normally handle email from _name_store or request
    # email = request.email or _name_store.pop(f"{request.phone_number}_email", None)

    try:
        create_or_update_user(user_id=request.phone_number, name=name)
    except Exception as e:
        print(f"[WARN] DynamoDB upsert failed (non-fatal): {e}")

    mock_token = f"mock_jwt_for_{request.phone_number}"
    return TokenResponse(
        access_token=mock_token,
        user_id=request.phone_number,
        name=name,
    )

# --- Password-Based Auth ---

@router.post("/register", response_model=TokenResponse, summary="Register a user with password")
async def register_user(request: RegisterRequest):
    # In a real app: Hash the password using bcrypt, store in DB.
    # For now, we mock success and just upsert the user to dynamo.
    try:
        create_or_update_user(user_id=request.phone_number, name=request.name)
    except Exception as e:
        print(f"[WARN] DynamoDB upsert failed (non-fatal): {e}")

    mock_token = f"mock_jwt_for_{request.phone_number}"
    return TokenResponse(
        access_token=mock_token,
        user_id=request.phone_number,
        name=request.name,
    )

@router.post("/login", response_model=TokenResponse, summary="Login a user with email/phone and password")
async def login_user(request: LoginRequest):
    # In a real app: Find user by identifier (email/phone), verify bcrypt hash.
    # Mocking success for demo.
    
    # We do a fake lookup. 
    user_id = request.identifier
    name = "Demo User" # Normally fetch from DB
    
    # Always succeed in dev mode:
    mock_token = f"mock_jwt_for_{user_id}"
    return TokenResponse(
        access_token=mock_token,
        user_id=user_id,
        name=name,
    )
