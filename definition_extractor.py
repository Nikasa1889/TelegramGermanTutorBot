import re
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI
from data_models import Keyword
from typing import List


class DefinitionExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)

    self.define_template = PromptTemplate(template=(
      "Return information about the German word `{word}` in English. "
      "Output contains one meaning per line, with following fields:\n"
      " - input: the word being asked;\n"
      " - root: root form of the word, with definite article if it's a noun;\n"
      " - pos: part of speech in abbr (Noun, Adj, Adv,...);\n"
      " - def: definition;\n"
      " - ex: a German example of the word being used.\n"
      "Example:\n"
      "input=fahren;root=fahren;pos=Verb;def=to drive/to ride/to travel;"
      "ex=Ich fahre morgen nach Berlin (I'm driving/going to Berlin tomorrow)."
      "input=fahren;root=das Fahren; pos=Noun; def=driving;"
      "ex=Das Fahren mit dem Fahrrad macht Spaß (Riding a bicycle is fun)."),
                                          input_variables=["word"])

    self.define_chain = LLMChain(prompt=self.define_template,
                                 llm=self.model,
                                 verbose=True)

  async def extract_definitions(self, word: str) -> List[Keyword]:
    extracted_keywords = []
    defined_word_str = await self.define_chain.apredict(word=word)
    print(defined_word_str)
    pattern = r"input=(.+?);root=(.+?);pos=(.+?);def=(.+?);ex=(.+)"
    for match in re.finditer(pattern, defined_word_str):
      word, root, pos, definition, example = match.groups()
      keyword = Keyword(root=root, word=word, pos=pos, snippet=example,
                        definition=definition)
      extracted_keywords.append(keyword)
    print(extracted_keywords)
    return extracted_keywords
