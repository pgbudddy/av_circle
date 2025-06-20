import requests
import json
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Load credentials from service account
credentials = service_account.Credentials.from_service_account_file(
    'service-account.json',
    scopes=['https://www.googleapis.com/auth/firebase.messaging']
)

# Apply scope and refresh token
scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/firebase.messaging'])
scoped_credentials.refresh(Request())

# Extract the access token
access_token = scoped_credentials.token

# Your FCM device token
DEVICE_TOKEN = 'dYL5i6NYTMCiyxQ5H0md01:APA91bHsR2n7IdxTnIyr7CAZ_yx8lcUB5dPo6yClgtojYCwxYl9D5iUP-1Vye-doZAw3sIxMdmeBO2l1Nv5tENnqt6_R4fvjHtsUYfdnriAIurjDcg7yAI4'

# Your Firebase project ID
PROJECT_ID = 'miniplex-66f40'

# Message payload
message = {
    "message": {
        "token": DEVICE_TOKEN,
        "notification": {
            "title": "Hello from Python v1 👋",
            "body": "This is sent using FCM HTTP v1 API"
        }
    }
}

# Endpoint URL
url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"

# Headers with the valid token
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json; UTF-8"
}

# Send the message
response = requests.post(url, headers=headers, data=json.dumps(message))

# Output
print("Status Code:", response.status_code)
try:
    print("Response:", response.json())
except Exception:
    print("Response Text:", response.text)
