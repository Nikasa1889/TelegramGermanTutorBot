import re
from typing import List
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI
from data_models import Question


class QuestionExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)
    self.prompt_template = PromptTemplate(
      template=("Carefully generate 10 muti-choice German questions to test "
                "my understanding of a German text from top to bottom. "
                "Use only information in the text to generate question. "
                "One question has a single correct answer. "
                "A question has the following fields:\n"
                "- `text`: question text\n"
                "-  `a`, `b`,`c`,`d`:  4 options\n"
                "-  `ans`: correct answer, either a, b, c, or d\n"
                "-  `expl`: explains why ans is correct.\n\n"
                "{text}\n\n{format_instructions}"),
      input_variables=["text"],
      partial_variables={
        "format_instructions":
        ("The output contains one question per line. Example:\n"
         "text=Was kauft der Autor im Kiosk?;"
         "a=Eine Zeitung und eine Cola;b=Ein Getränk, ein Brötchen und Chips;"
         "c=Eine Tafel Schokolade;d=Eine Flasche Wasser und ein Sandwich;"
         "ans=b;expl=The text says \"Also kaufe ich mir ein Getränk und Chips\" "
         "which means \"So I buy a drink and chips\".")
      })
    self.llm_chain = LLMChain(prompt=self.prompt_template,
                              llm=self.model,
                              verbose=True)

  async def extract_questions(self, text: str) -> List[Question]:
    output = await self.llm_chain.apredict(text=text)
    print(output)
    question_re = re.compile(
      r"text=(.+);a=(.+);b=(.+);c=(.+);d=(.+);ans=(.+);expl=(.+)")
    questions = []
    for match in question_re.finditer(output):
      question_text, a, b, c, d, answer, explanation = match.groups()
      question = Question(question=question_text,
                          options=[a, b, c, d],
                          correct_idx="abcd".index(answer),
                          explanation=explanation.strip())
      if not question.validate_telegram_poll():
        continue
      questions.append(question)
    print(questions)
    return questions
