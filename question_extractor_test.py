import unittest
from question_extractor import QuestionExtractor

text = """Heute ist ein sonniger Tag und ich möchte meine Großeltern in Hamburg besuchen. Im Bahnhof sind viele Menschen. Ich weiß nicht, wohin ich gehen soll. Ich suche mir Hilfe an dem Informationsschalter. Sie haben Informationen zu allen Zügen. Sie wissen, wie ich von Bremen nach Hamburg kommen kann. Die Mitarbeiter helfen mir den richtigen Zug, das richtige Gleis und die richtige Uhrzeit zu finden.

Hier ist dein Bahnticket. Gehe bitte zu Gleis Nummer 5. Dein Zug fährt um 15.45 Uhr von Bremen nach Hamburg."""


class TestQuestionExtractor(unittest.IsolatedAsyncioTestCase):

  async def test_question_extraction(self):
    question_extractor = QuestionExtractor()
    questions = await question_extractor.extract_questions(text)

    self.assertGreater(len(questions), 8, "Number of questions should be >= 8")


if __name__ == '__main__':
  unittest.main()
