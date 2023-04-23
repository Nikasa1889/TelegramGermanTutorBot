import re
import nltk
from typing import List
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI
from data_models import Keyword

nltk.download('punkt')


class KeywordExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)

    self.list_keywords_template = PromptTemplate(
      template=(
        "Carefully list max 25 important vocabularies (noun, verb, adj, adv,...) "
        "sorted from most difficult to least. "
        "The vocabs must appear exactly in the text. \n\n"
        "{text}\n\n{format_instructions}"),
      input_variables=["text"],
      partial_variables={
        "format_instructions":
        "The output is a single line containing comma-separated list of vocabs"
      })

    self.define_template = PromptTemplate(
      template=(
        "Given a list of keywords, provide detailed info for each of them. "
        "Each keyword has: input=the requested keyword;"
        "root=root form of the keyword;"
        "art=the article (der/die/das) if the keyword is noun, otherwise empty;"
        "pos=noun, verb, adj, adv, prep, conj,...;def=its meaning\n\n"
        "Keywords: {keywords}\n\n{format_instructions}"),
      input_variables=["keywords"],
      partial_variables={
        "format_instructions":
        ("The output should present one Keyword per line. Example:\n"
         "input=Informationsschalter;root=Informationsschalter;"
         "pos=Noun;art=der;def=information desk\n"
         "input=sonniger;root=sonnig;pos=Adj;art=;def=sunny")
      })

    self.list_keywords_chain = LLMChain(prompt=self.list_keywords_template,
                                        llm=self.model,
                                        verbose=True)

    self.define_chain = LLMChain(prompt=self.define_template,
                                 llm=self.model,
                                 verbose=True)

  def _find_sentences(self, keywords: List[str], text: str) -> List[str]:
    sentences = nltk.sent_tokenize(text)
    found_sentences = []

    for keyword in keywords:
      lower_keyword = keyword.lower()
      pattern = re.compile(rf"\b{re.escape(lower_keyword)}\b", re.IGNORECASE)

      for sentence in sentences:
        if pattern.search(sentence):
          found_sentences.append(sentence)
          break
      else:
        found_sentences.append("")

    return found_sentences

  async def extract_keywords(self, text: str) -> List[Keyword]:
    # Step 1: List all keywords
    keywords_str = await self.list_keywords_chain.apredict(text=text)
    print(keywords_str)
    # Step 2: Define these keywords
    extracted_keywords = []
    defined_keywords_str = await self.define_chain.apredict(
      keywords=keywords_str)
    print(defined_keywords_str)
    # Step 3: Parse keywords
    pattern = r"input=(.+);\s?root=(.+);\s?pos=(.+);\s?art=(.*);\s?def=(.+)"
    for match in re.finditer(pattern, defined_keywords_str):
      word, root, pos, art, definition = match.groups()
      snippet = ""  # Set to empty string since it is not provided in the input
      if pos.lower() == "noun" and art:
        root = f'{art} {root}'
      keyword = Keyword(root=root,
                        word=word,
                        pos=pos,
                        snippet=snippet,
                        definition=definition)
      extracted_keywords.append(keyword)
    # Step 4: Find snippet.
    for i, sentence in enumerate(
        self._find_sentences([kw.word for kw in extracted_keywords], text)):
      extracted_keywords[i].snippet = sentence
    print(extracted_keywords)
    return extracted_keywords
