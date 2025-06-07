import requests

url = "https://grok-3-0-ai.p.rapidapi.com/"

payload = {
	"model": "grok-3",
	"messages": [
		{
			"role": "user",
			"content": "find best B&W speaker"
		}
	]
}
headers = {
	"x-rapidapi-key": "8b31ed4e64mshdcb2f841718d838p121b29jsn3a3a5510eb63",
	"x-rapidapi-host": "grok-3-0-ai.p.rapidapi.com",
	"Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print(data['choices'][0]['message']['content'])