import unittest

from keyword_extractor import KeywordExtractor
from data_models import Keyword

text= """Heute ist ein sonniger Tag und ich möchte meine Großeltern in Hamburg besuchen. Im Bahnhof sind viele Menschen. Ich weiß nicht, wohin ich gehen soll. Ich suche mir Hilfe an dem Informationsschalter. Sie haben Informationen zu allen Zügen. Sie wissen, wie ich von Bremen nach Hamburg kommen kann. Die Mitarbeiter helfen mir den richtigen Zug, das richtige Gleis und die richtige Uhrzeit zu finden.

Hier ist dein Bahnticket. Gehe bitte zu Gleis Nummer 5. Dein Zug fährt um 15.45 Uhr von Bremen nach Hamburg.
"""

class TestKeywordExtractor(unittest.IsolatedAsyncioTestCase):

  async def test_keyword_extraction(self):

    keyword_extractor = KeywordExtractor()

    keywords = await keyword_extractor.extract_keywords(text)

    self.assertGreaterEqual(len(keywords), 20,
                            "Number of keywords should be at least 20")

    required_words = [
      Keyword(root='der Informationsschalter', word='informationsschalter', pos='Noun', snippet='Ich suche mir Hilfe an dem Informationsschalter.', definition='information desk'),
      Keyword(root='sonnig', word='sonniger', pos='Adj', snippet='Heute ist ein sonniger Tag und ich möchte meine Großeltern in Hamburg besuchen.', definition='sunny'),
      Keyword(root='besuchen', word='besuchen', pos='Verb', snippet='Heute ist ein sonniger Tag und ich möchte meine Großeltern in Hamburg besuchen.', definition='visit')]
    extracted_keywords = {kw.word.lower(): kw for kw in keywords}
    for word in required_words:
      self.assertIn(word.word, extracted_keywords,
                    f"{word.word} not found in extracted keyword")
      extracted_word = extracted_keywords[word.word]
      self.assertTrue(extracted_word.pos == word.pos and
                     extracted_word.snippet == word.snippet and 
                     extracted_word.root == word.root and
                      len(word.definition) >= 3,
                     f"{extracted_word} does not match expected {word}")
    
    unexpected_words =   ['sich']
    for word in unexpected_words:
      self.assertNotIn(word, extracted_keywords,
                       f"`{word}` found in extracted keyword")
    
      
if __name__ == '__main__':
  unittest.main()