import unittest
from definition_extractor import DefinitionExtractor


class TesDefinitiontExtractor(unittest.IsolatedAsyncioTestCase):

  async def test_sonniger(self):
    extractor = DefinitionExtractor()
    keywords = await extractor.extract_definitions("sonniger")
    print(keywords)
    self.assertGreaterEqual(len(keywords), 1)
    
    sonnig_word = next(kw for kw in keywords if kw.pos == "Adj")
    self.assertIsNotNone(sonnig_word)
    self.assertEqual(sonnig_word.root, "sonnig")
    self.assertGreaterEqual(len(sonnig_word.snippet), 20)

  async def test_multiple_meanings(self):
    extractor = DefinitionExtractor()
    keywords = await extractor.extract_definitions("suchen")
    print(keywords)
    found_verbs = []
    found_nouns = []
    for kw in keywords:
      if kw.pos == "Verb":
        found_verbs.append(kw)
      elif kw.pos == "Noun":
        found_nouns.append(kw)
    self.assertGreaterEqual(len(found_verbs), 1,
                            "At least 1 verbs should be found")
    self.assertGreaterEqual(len(found_nouns), 1,
                            "At least 1 noun should be found")

  async def test_extract_various_words(self):
    extractor = DefinitionExtractor()
    testing_words = ["kümmern", "der Autor"]
    for word in testing_words:
      keywords = await extractor.extract_definitions(word)
      print(keywords)
      self.assertGreaterEqual(len(keywords), 1)


if __name__ == '__main__':
  unittest.main()
