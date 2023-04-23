from dataclasses import dataclass, field, asdict
from dacite import from_dict

from replit import db

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel, Field
import heapq
import os
import pickle
import random

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
  pos: str
  snippet: str
  definition: str
  time: datetime = field(default_factory=datetime.now)

  def summary(self) -> str:
    optional_snipet = f"\n\"{self.snippet}\"" if self.snippet else ""
    return f"{self.word} ({self.pos}): {self.definition}{optional_snipet}"


@dataclass
class Vocab:
  root: str
  encounters: List[VocabEncounter] = field(default_factory=list)
  ease_factor: float = 2.5
  last_review: Optional[date] = None
  next_review: Optional[date] = None
  interval: int = 0
  repetitions: int = 0
  quiz: List[Question] = field(default_factory=list)

  @classmethod
  def from_keyword(cls, keyword: Keyword, session_id: int):
    vocab = cls(root=keyword.root)
    vocab.encounter_keyword(keyword, session_id)
    return vocab

  def encounter_keyword(self, keyword: Keyword, session_id: int):
    self.encounters.append(VocabEncounter(session_id=session_id,
                                          word=keyword.word,
                                          pos=keyword.pos,
                                          snippet=keyword.snippet,
                                          definition=keyword.definition))

  def random_word(self):
    if self.encounters:
      return random.choice(self.encounters).word
    else:
      return self.root

  def correct_answer(self):
    self.update(quality=5)

  def wrong_answer(self):
    self.update(quality=2)

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

  def _encounter_keyword(self, keyword: Keyword, session_id: int, quality: int):
    root = keyword.root
    if root not in self.dictionary:
      vocab = Vocab.from_keyword(keyword, session_id) 
      self.dictionary[keyword.root] = vocab
    else:
      vocab = self.dictionary[root]
      vocab.encounter_keyword(keyword, session_id)

    vocab.update(quality)

  def define_vocab(self, keyword: Keyword, session_id: int):
    self._encounter_keyword(keyword, session_id, quality=1)

  def click_keyword(self, keyword: Keyword, session_id: int):
    self._encounter_keyword(keyword, session_id, quality=3)

  def due_vocabs(self, n: int):
    due_vocabs = [
      vocab for vocab in self.dictionary.values()
      if vocab.next_review <= date.today()
    ]

    due_vocabs.sort(key=lambda vocab: vocab.next_review)
    return due_vocabs[:n]


@dataclass
class LearningSession:
  session_id: int
  chat_id: str
  text: str   # If text = "VocabQuiz", it's a vocabulary quiz!
  start_time: datetime
  end_time: Optional[datetime] = None
  translation: Optional[str] = None
  quiz: List[Question] = field(default_factory=list)
  next_question_idx: int = 0
  keywords: List[Keyword] = field(default_factory=list)
  current_keyword_page: int = 0
  # Stores the vocab root corresponding to the quiz, when text="VocabQuiz".
  vocab_roots: List[str] = field(default_factory=list) 

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
  user_id: int
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


# class UserProfileDB:
#   # WARNING: assuming one request at a time from user_id, or race condition.
#   async def get_user_profile(self, user_id: int) -> UserProfile:
#     if str(user_id) in db:
#         return from_dict(UserProfile, db[str(user_id)])
#     else:
#         user_profile = UserProfile(user_id=user_id)
#         await self.set_user_profile(user_profile)
#         return user_profile
# 
#   async def set_user_profile(self, user_profile: UserProfile) -> None:
#     print(asdict(user_profile))
#     user_id = str(user_profile.user_id)
#     db[user_id] = asdict(user_profile)

class UserProfileDB:
    def __init__(self, directory: str = "user_profiles"):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def get_user_profile_file_path(self, user_id: str) -> str:
        return os.path.join(self.directory, f"{user_id}.pkl")

    async def get_user_profile(self, user_id: int) -> UserProfile:
        file_path = self.get_user_profile_file_path(str(user_id))

        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        else:
            user_profile = UserProfile(user_id=user_id)
            await self.set_user_profile(user_profile)
            return user_profile

    async def set_user_profile(self, user_profile: UserProfile) -> None:
        file_path = self.get_user_profile_file_path(str(user_profile.user_id))

        with open(file_path, 'wb') as f:
            pickle.dump(user_profile, f)

    async def remove_user_profile(self, user_id: int) -> None:
      file_path = self.get_user_profile_file_path(str(user_id))
      if os.path.exists(file_path):
        os.remove(file_path)

    async def get_all_user_profiles(self) -> List[UserProfile]:
        profiles = []
        for file_name in os.listdir(self.directory):
            if file_name.endswith(".pkl"):
                file_path = os.path.join(self.directory, file_name)
                with open(file_path, "rb") as f:
                    profiles.append(pickle.load(f))
        return profiles
