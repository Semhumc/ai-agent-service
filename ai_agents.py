from json import tool
import re
import markdownify
import requests
from smolagents import CodeAgent, WebSearchTool, OpenAIServerModel
from openai import OpenAI

class ai_agent:
    def __init__(self):
        try:
            with open("system_prompt.txt", "r",encoding="utf-8") as file:
                systemPrompt = file.read()
        except FileNotFoundError:
            print("System prompt file not found. Using default prompt.")
            systemPrompt = "You are a helpful AI assistant."

        self.agent = CodeAgent(
            instructions=systemPrompt,
            tools=[WebSearchTool(), self.visit_webpage],
            model=model,
            stream_outputs=True
        )
        model=OpenAIServerModel(
                model_id="google/gemini-2.5-flash",
                api_base="https://openrouter.ai/api/v1",  # Leave this blank to query OpenAI servers.
                api_key="",
                max_tokens=16000,  # Limit the number of tokens to 16000
            ),
    


    @tool
    def visit_webpage(url: str) -> str:
        try:
        # Send a GET request to the URL
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes

        # Convert the HTML content to Markdown
            markdown_content = markdownify(response.text).strip()

        # Remove multiple line breaks
            markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

            return markdown_content

        except requests.RequestException as e:
            return f"Error fetching the webpage: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"



    def generate_trip_plan(self, prompt_data: dict) -> str:
        """
        Verilen bilgilere dayanarak bir seyahat planı oluşturur ve JSON string'i olarak döndürür.
        """
        user_prompt = f"""
        Lütfen aşağıdaki bilgilere göre bir seyahat planı oluştur ve sadece belirtilen JSON formatında yanıt ver:
        - Kullanıcı ID: {prompt_data['user_id']}
        - Plan Adı: {prompt_data['name']}
        - Açıklama: {prompt_data['description']}
        - Başlangıç Noktası: {prompt_data['start_position']}
        - Bitiş Noktası: {prompt_data['end_position']}
        - Başlangıç Tarihi: {prompt_data['start_date']}
        - Bitiş Tarihi: {prompt_data['end_date']}
        """
        
        result_str = self.agent.run(user_prompt)
        print(f"🧠 AI'dan gelen ham sonuç:\n{result_str}")
        
        # JSON formatında olup olmadığını kontrol et
        if not result_str.strip().startswith("{") or not result_str.strip().endswith("}"):
            print("AI'dan gelen sonuç JSON formatında değil. Düzeltmeye çalışıyorum...")
            # JSON formatına dönüştürmeye çalış
            result_str = re.sub(r'(\w+):', r'"\1":', result_str)       

        if result_str.strip().startswith("```json"):
            result_str = result_str.strip()[7:-3].strip()

        return result_str
