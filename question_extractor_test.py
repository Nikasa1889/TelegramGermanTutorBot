import unittest
from question_extractor import QuestionExtractor


class TestQuestionExtractor(unittest.IsolatedAsyncioTestCase):

  async def test_story_extraction(self):
    text = """Heute ist ein sonniger Tag und ich möchte meine Großeltern in Hamburg besuchen. Im Bahnhof sind viele Menschen. Ich weiß nicht, wohin ich gehen soll. Ich suche mir Hilfe an dem Informationsschalter. Sie haben Informationen zu allen Zügen. Sie wissen, wie ich von Bremen nach Hamburg kommen kann. Die Mitarbeiter helfen mir den richtigen Zug, das richtige Gleis und die richtige Uhrzeit zu finden.

Hier ist dein Bahnticket. Gehe bitte zu Gleis Nummer 5. Dein Zug fährt um 15.45 Uhr von Bremen nach Hamburg."""
    question_extractor = QuestionExtractor()
    questions = await question_extractor.extract_questions(text)

    self.assertGreater(len(questions), 8, "Number of questions should be >= 8")

  async def test_dialog_extraction(self):
    text = """Lisa: Hallo, ich bin Lisa. Wie heißt du?
Max: Ich heiße Max. Schön, dich kennenzulernen.
Lisa: Woher kommst du?
Max: Ich komme aus Berlin. Und du?
Lisa: Ich komme aus München. Was machst du hier in der Stadt?
Max: Ich bin hier für eine Konferenz. Und du?
Lisa: Ich besuche meine Tante. Sie wohnt hier in der Nähe.
Max: Was machst du gerne in deiner Freizeit?
Lisa: Ich lese gerne Bücher und gehe gerne ins Kino. Und du?
Max: Ich spiele gerne Fußball und treffe mich mit Freunden.
Lisa: Das klingt gut. Vielleicht können wir ja mal zusammen ins Kino gehen?
Max: Ja, gerne. Das würde mir gefallen."""
    question_extractor = QuestionExtractor()
    questions = await question_extractor.extract_questions(text)

    self.assertGreater(len(questions), 8, "Number of questions should be >= 8")

if __name__ == '__main__':
  unittest.main()
