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
        "Carefully list max 40 important vocabularies (noun, verb, adj, adv,...) "
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
        "Each keyword requires `input`: the requested keyword; "
        "`root`: the root form with definite article for noun; "
        "`pos`: noun, verb, adj, adv, prep, conj,...; `def`: its meaning.\n\n"
        "Keywords: {keywords}\n\n{format_instructions}"),
      input_variables=["keywords"],
      partial_variables={
        "format_instructions":
        ("The output should present one Keyword per line. Example:\n"
         "input=Informationsschalter;root=der Informationsschalter;pos=Noun;def=information desk\n"
         "input=sonniger;root=sonnig;pos=Adj;def=sunny")
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
          match_start = pattern.search(sentence).start()
          start = max(0, match_start - 40)
          end = min(len(sentence), match_start + len(keyword) + 40)
          truncated_sentence = sentence[start:end]
          if start > 0:
            truncated_sentence = "..." + truncated_sentence
          if end < len(sentence):
            truncated_sentence = truncated_sentence + "..."
          found_sentences.append(truncated_sentence)
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
    pattern = r"input=(.+?);root=(.+?);pos=(.+?);def=(.+)"
    for match in re.finditer(pattern, defined_keywords_str):
      word, root, pos, definition = match.groups()
      snippet = ""  # Set to empty string since it is not provided in the input
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
