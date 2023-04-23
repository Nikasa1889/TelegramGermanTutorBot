import re
from typing import Dict, List, Tuple
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI
from data_models import Question, Vocab

class VocabQuestionExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)
    self.prompt_template = PromptTemplate(
        template=("Generate muti-choice questions to test my knowledge "
                  "of the following German keywords, "
                  "including their meaning, synonyms, antonyms, or "
                  "their various forms. One question per keyword. "
                  "Each question focuses on one keyword and contains "
                  "the following fields: "
                  "input=the keyword being asked, copied exactly from the list;"
                  "text=the question text;"
                  "a=1st option;b=2nd option;c=3rd option;d=4th option;"
                  "ans=correct answer, either a, b, c, or d;"
                  "expl=explains why ans is correct.\n\n"
                  "Keywords: {keywords}\n\n"
                  "The output contains one question per line. Example:\n"
              "input=...;text=...?;a=...;b=...;c=...;d=...;ans=d;expl=..."),
        input_variables=["keywords"],
        partial_variables={})
    self.llm_chain = LLMChain(prompt=self.prompt_template,
                              llm=self.model,
                              verbose=True)

  async def extract_questions(self, 
                              vocabs: List[Vocab]) -> List[Tuple[str, Question]]:
    formatted_keywords = ", ".join([vocab.root for vocab in vocabs])
    output = await self.llm_chain.apredict(keywords=formatted_keywords)
    print(output)
    question_re = re.compile(
        r"input=(.+);\s?text=(.+);\s?a=(.+);\s?b=(.+);\s?c=(.+);\s?d=(.+);\s?ans=(.+);\s?expl=(.+)")
    questions = []
    for match in question_re.finditer(output):
      root, question_text, a, b, c, d, answer, explanation = match.groups()
      question = Question(question=question_text,
                          options=[a, b, c, d],
                          correct_idx="abcd".index(answer),
                          explanation=explanation.strip())
      if not question.validate_telegram_poll():
        continue
      matched_vocab = next((vocab for vocab in vocabs 
                           if vocab.root.lower() == root.lower()), None)
      if matched_vocab:
        questions.append((matched_vocab.root, question))
    print(questions)
    return questions
