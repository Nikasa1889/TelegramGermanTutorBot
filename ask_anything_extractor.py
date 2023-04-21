from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI


class AskAnythingExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)

    self.ask_anything_template = PromptTemplate(template=(
      "You are a friendly and helpful German Tutor bot, who helps me "
      "learn high German while having fun. Be concise and don't add motivation speech at the end. My request:\n\n{request}"),
                                                input_variables=["request"])

    self.ask_anything_chain = LLMChain(prompt=self.ask_anything_template,
                                       llm=self.model,
                                       verbose=True)

  async def extract_response(self, request: str) -> str:
    response = await self.ask_anything_chain.apredict(request=request)
    return response.strip()
