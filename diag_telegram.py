import requests, os
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('TELEGRAM_TOKEN', '')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

print(f"Token: {token[:25]}...")
print(f"Chat ID configured: {chat_id}")

r = requests.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10)
info = r.json()
if info.get('ok'):
    print(f"Bot username: @{info['result']['username']}")
else:
    print(f"Bot error: {info}")

r2 = requests.get(f'https://api.telegram.org/bot{token}/getUpdates?limit=10', timeout=10)
updates = r2.json().get('result', [])
print(f"\nDerniers messages recus ({len(updates)}):")
seen_chats = set()
for u in updates:
    msg = u.get('message', {})
    chat = msg.get('chat', {})
    cid = chat.get('id')
    if cid and cid not in seen_chats:
        seen_chats.add(cid)
        print(f"  chat_id={cid}  type={chat.get('type')}  name={chat.get('first_name','')} {chat.get('last_name','')}")

# Try sending to configured chat_id
if chat_id:
    r3 = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat_id, 'text': 'Test BOTVINTED diagnostic'},
        timeout=10
    )
    print(f"\nTest envoi vers {chat_id}: {r3.json()}")
