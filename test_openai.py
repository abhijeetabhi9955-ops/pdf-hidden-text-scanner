from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    input="Say exactly: API connection successful"
)

print(response.output_text)
