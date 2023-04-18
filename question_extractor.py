import re
from typing import List
from langchain import PromptTemplate, LLMChain
from langchain.chat_models import ChatOpenAI
from data_models import Question


class QuestionExtractor:

  def __init__(self, model_name='gpt-3.5-turbo', temperature=0.7):
    self.model = ChatOpenAI(model_name=model_name, temperature=temperature)
    self.prompt_template = PromptTemplate(
      template=("Generate 10 mutiple-choice German questions to test "
                "my understanding of a German text. A question has the "
                "following fields:\n"
                "- `text`: question text\n"
                "-  `a`, `b`,`c`,`d`:  4 options\n"
                "-  `ans`: correct answer, either a, b, c, or d\n"
                "-  `expl`: explains why ans is correct.\n"
                "The question uses only information in the text.\n"
                "There is one single correct answer.\n"
                "Text: {text}\n\n"
                "{format_instructions}"),
      input_variables=["text"],
      partial_variables={
        "format_instructions":
        ("The output contains one question per line. Example:\n"
         "text=Was macht der Autor, als der Zug nicht pünktlich kommt?;"
         "a=Er geht zum Kiosk zurück;b=Er ruft seine Großeltern an;"
         "c=Er wartet am Gleis;d=Er geht nach Hause;ans=c;"
         "expl=The author waits at the platform when the train is not punctual."
         "text=Was kauft der Autor im Kiosk?;"
         "a=Eine Zeitung und eine Cola;b=Ein Getränk, ein Brötchen und Chips;"
         "c=Eine Tafel Schokolade;d=Eine Flasche Wasser und ein Sandwich;"
         "ans=b;expl=The text says \"Also kaufe ich mir im Kiosk ein Getränk, "
         "ein Brötchen und Chips\" which means \"So I buy a drink "
         "and chips in the kiosk\".")
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
