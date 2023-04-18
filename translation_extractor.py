import re
from typing import List
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI

class TranslationExtractor:

    def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
        self.model = ChatOpenAI(model_name=model_name, temperature=temperature)

        self.template = PromptTemplate(
            template=(
                "As a German tutor, carefully translate the following German "
                "text to English:\n\n"
                "{text}\n\n"
                "The output contains the original German text with each "
                "sentence followed by its translation put in parenthesis. "
                "For example:\n\n"
                "Ich wache auf und liege im Bett (I wake up and lay in bed). "
                "Ich bin müde, da ich gestern sehr spät eingeschlafen bin "
                "(I am tired because I fell asleep very late yesterday)."),
            input_variables=["text"])

        self.chain = LLMChain(prompt=self.template, llm=self.model, verbose=True)

    async def extract_translation(self, text: str) -> str:
        return await self.chain.apredict(text=text)
