# api/auth.py - password login and the token check that guards every other route
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import config

# reads the "Authorization: Bearer <token>" header off the request, if there is one
bearer_scheme = HTTPBearer(auto_error=False)

# what this function does: say whether login is configured at all
def login_is_configured():
  return bool(config.JWT_SECRET and config.APP_USERNAME and config.APP_PASSWORD)

# what this function does: check the username and password, then hand back a signed token
def create_token(username, password):
  # an unconfigured .env means nobody can log in - safer than shipping a default password
  if not login_is_configured():
    return None
  if username != config.APP_USERNAME or password != config.APP_PASSWORD:
    return None
  expires_at = datetime.now(timezone.utc) + timedelta(hours=config.JWT_HOURS)
  return jwt.encode({"sub": username, "exp": expires_at},
                    config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

# what this function does: reject the request unless it carries a valid, unexpired token
def require_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
  if credentials is None:
    raise HTTPException(status_code=401, detail="Log in first, then send the token you get back.")
  try:
    payload = jwt.decode(credentials.credentials, config.JWT_SECRET,
                         algorithms=[config.JWT_ALGORITHM])
  except JWTError:
    raise HTTPException(status_code=401, detail="That token is invalid or has expired.")
  return payload["sub"]
