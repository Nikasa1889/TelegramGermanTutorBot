from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
from pydantic import BaseModel, Field
import heapq


class Keyword(BaseModel):
  root: str = Field(description="Definite form of the word")
  word: str = Field(description="Actual word found in the text")
  pos: str = Field(description="Part of speech of the word")
  snippet: str = Field(description="Text snippet containing the word")
  definition: str = Field(description="Definition of the word")

  def summary(self) -> str:
    optional_snipet = f"\n\"{self.snippet}\"" if self.snippet else ""
    return f"{self.root} ({self.pos}): {self.definition}{optional_snipet}"


@dataclass
class VocabEncounter:
  session_id: int
  word: str
  snippet: str
  definition: str
  time: datetime = field(default_factory=datetime.now)


@dataclass
class Vocab:
  root: str
  encounters: List[VocabEncounter] = field(default_factory=list)
  ease_factor: float = 2.5
  last_review: Optional[date] = None
  next_review: Optional[date] = None
  interval: int = 0
  repetitions: int = 0

  @classmethod
  def from_keyword(cls, keyword: Keyword, session_id: int):
    vocab = cls(root=keyword.root)
    encounter = VocabEncounter(session_id=session_id,
                               word=keyword.word,
                               snippet=keyword.snippet,
                               definition=keyword.definition)
    vocab.encounters.append(encounter)
    return vocab

  def update(self, quality: int):
    if quality < 0 or quality > 5:
      raise ValueError("Quality should be between 0 and 5.")

    self.ease_factor += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)

    if self.ease_factor < 1.3:
      self.ease_factor = 1.3

    self.repetitions += 1

    if quality < 3:
      self.repetitions = 0

    if self.repetitions == 1:
      self.interval = 1
    elif self.repetitions == 2:
      self.interval = 6
    else:
      self.interval = int(self.interval * self.ease_factor)

    self.last_review = date.today()
    self.next_review = date.today() + timedelta(days=self.interval)


@dataclass
class Vocabs:
  dictionary: Dict[str, Vocab] = field(default_factory=dict)

  def define_vocab(self, keyword: Keyword, session_id: int):
    root = keyword.root
    if root not in self.dictionary:
      self.dictionary[keyword.root] = Vocab.from_keyword(keyword, session_id)

    vocab = self.dictionary[root]
    vocab.update(quality=1)

  def click_keyword(self, keyword: Keyword, session_id: int):
    root = keyword.root
    if root not in self.dictionary:
      self.dictionary[keyword.root] = Vocab.from_keyword(keyword, session_id)

    vocab = self.dictionary[root]
    vocab.update(quality=3)

  def ignore_keyword(self, keyword: Keyword, session_id: int):
    root = keyword.root
    if root not in self.dictionary:
      self.dictionary[keyword.root] = Vocab.from_keyword(keyword, session_id)

    vocab = self.dictionary[root]
    vocab.update(quality=5)

  def due_vocabs(self, n: int):
    due_vocabs = [
      vocab for vocab in self.dictionary.values()
      if vocab.next_review <= date.today()
    ]

    due_vocabs.sort(key=lambda vocab: vocab.next_review)
    return due_vocabs[:n]


@dataclass
class Question:
  question: str
  options: List[str]
  correct_idx: int
  explanation: str
  ask_time: Optional[datetime] = None
  answer_time: Optional[datetime] = None
  answer_idx: Optional[int] = None

  def is_correct(self) -> bool:
    return self.answer_idx == self.correct_idx

  def validate_telegram_poll(self) -> bool:
    if len(self.question) > 255:
      return False

    if any(len(option) > 100 for option in self.options):
      return False

    if len(self.explanation) > 200:
      # Truncate if explanation is too long
      self.explanation = self.explanation[:200]

    if not (0 <= self.correct_idx < len(self.options)):
      return False

    return True


@dataclass
class LearningSession:
  session_id: int
  chat_id: str
  text: str
  start_time: datetime
  end_time: Optional[datetime] = None
  quiz: List[Question] = field(default_factory=list)
  next_question_idx: int = 0
  keywords: List[Keyword] = field(default_factory=list)
  current_keyword_page: int = 0

  def summary_quiz(self) -> str:
    duration = self.end_time - self.start_time if self.end_time else datetime.now(
    ) - self.start_time
    minutes_spent = round(duration.total_seconds() / 60, 2)

    num_correct_answers = sum(1 for q in self.quiz if q.is_correct())
    total_questions = len(self.quiz)

    return (f"Correct: {num_correct_answers} / {total_questions}; "
            f"Time: {minutes_spent} mins\n")

  def summary(self) -> str:
    keywords_str = ', '.join([keyword.root for keyword in self.keywords])
    return f"{self.summary_quiz()}\nKeywords: {keywords_str}"


@dataclass
class UserProfile:
  user_id: str
  sessions: List[LearningSession] = field(default_factory=list)
  vocabs: Vocabs = field(default_factory=Vocabs)

  def summary(self) -> str:
    total_sessions = len(self.sessions)

    total_time_spent = sum(
      (session.end_time - session.start_time).total_seconds() / 60
      for session in self.sessions if session.end_time is not None)

    num_vocabs = len(self.vocabs)

    # Select the 100 most recent vocab encounters
    recent_vocabs = heapq.nlargest(
      100,
      self.vocabs,
      key=lambda vocab: vocab.encounters[-1].session_id
      if vocab.encounters else 0)
    recent_vocabs_str = ', '.join([vocab.root for vocab in recent_vocabs])

    summary_str = (f"User Profile Summary:\n"
                   f"Total sessions: {total_sessions}\n"
                   f"Total time spent: {total_time_spent} minutes\n"
                   f"Number of learned vocabs: {num_vocabs}\n"
                   f"Recent vocabs: {recent_vocabs_str}")

    return summary_str
