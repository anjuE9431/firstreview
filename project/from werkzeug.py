from werkzeug.security import generate_password_hash

# Replace this with the real password you want
plain_password = "1234"

# Generate a secure hash
hashed_password = generate_password_hash(plain_password)

print(hashed_password)