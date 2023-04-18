import unittest
from definition_extractor import DefinitionExtractor


class TesDefinitiontExtractors(unittest.IsolatedAsyncioTestCase):

  async def test_extract_keywords_sonniger(self):
    extractor = DefinitionExtractor()
    keywords = await extractor.extract_definitions("sonniger")
    print(keywords)
    self.assertEqual(len(keywords), 1)
    self.assertEqual(keywords[0].root, "sonnig")
    self.assertEqual(keywords[0].pos, "Adj")
    self.assertGreaterEqual(len(keywords[0].snippet), 20)

  async def test_extract_keywords_suchen(self):
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


if __name__ == '__main__':
  unittest.main()
