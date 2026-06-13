from openai import OpenAI

client = OpenAI(
    api_key="sk-JCK3CWE6L2yx9ppcGZqCt9Ts5FxAnCEMRbBzxoOfHZzHrly4",
    base_url="https://api.chatanywhere.tech/v1"
)

for model in client.models.list():
    print(model.id)