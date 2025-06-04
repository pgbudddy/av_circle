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
	"x-rapidapi-key": "61d6e1e530msh362ab2cba9dd614p1c18fcjsnec1702960611",
	"x-rapidapi-host": "grok-3-0-ai.p.rapidapi.com",
	"Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print(data['choices'][0]['message']['content'])