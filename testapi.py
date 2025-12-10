import google.generativeai as genai

genai.configure(api_key="AIzaSyB7lJnDH2IIMmYXiGXy9vHzC12CcaWz-VU")

try:
    models = genai.list_models()
    print("可用模型：")
    for m in models:
        print("-", m.name)
except Exception as e:
    print("無法列出模型：", e)
