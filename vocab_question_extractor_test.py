import unittest
from data_models import Vocab
from vocab_question_extractor import VocabQuestionExtractor

class TestVocabQuestionExtractor(unittest.IsolatedAsyncioTestCase):

  async def test_extract_questions(self):
    # Create a sample list of Vocab objects
    sample_vocabs = [
        Vocab(root="vorsichtige"),
        Vocab(root="wandern"),
        Vocab(root="der Apfel"),
        Vocab(root="die verletzt")
    ]

    # Instantiate the VocabQuestionExtractor class
    question_extractor = VocabQuestionExtractor()
    # Call the extract_questions method with the sample vocabs
    questions = await question_extractor.extract_questions(sample_vocabs)

    # Check if the extracted questions match the number of input vocabs
    self.assertEqual(len(questions), len(sample_vocabs))
    # Check if the extracted questions have the correct roots
    for vocab in sample_vocabs:
      question = next((q for root, q in questions if vocab.root == root), None)
      self.assertIsNotNone(question)
      # Check if the extracted question object has the correct number of options
      self.assertEqual(len(question.options), 4)
      # Check if the correct_idx is within the range of the options
      self.assertTrue(0 <= question.correct_idx < len(question.options))

if __name__ == "__main__":
    unittest.main()
