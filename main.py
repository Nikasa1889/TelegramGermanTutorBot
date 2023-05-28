import logging
import asyncio
import random
import os
from datetime import datetime, time
from typing import Optional, List

from telegram import ReplyKeyboardRemove, Update, Poll, Message
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

from telegram.ext import (Application, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler,
                          CallbackQueryHandler, PollAnswerHandler, filters,
                          JobQueue)

from keyword_extractor import KeywordExtractor
from question_extractor import QuestionExtractor
from definition_extractor import DefinitionExtractor
from translation_extractor import TranslationExtractor
from ask_anything_extractor import AskAnythingExtractor
from vocab_question_extractor import VocabQuestionExtractor
from data_models import UserProfile, LearningSession, UserProfileDB

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
KEYWORDS_PER_ROW = 3
KEYWORDS_PER_PAGE = 3 * KEYWORDS_PER_ROW

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO)
logger = logging.getLogger(__name__)

LEARN_TEXT, ASK_QUESTION = range(2)
keyword_extractor = KeywordExtractor()
question_extractor = QuestionExtractor()
definition_extractor = DefinitionExtractor()
translation_extractor = TranslationExtractor()
ask_anything_extractor = AskAnythingExtractor()
vocab_question_extractor = VocabQuestionExtractor()
db = UserProfileDB()


async def create_placeholder_message(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> Message:
  await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
  # Send the initial waiting message
  return await context.bot.send_message(chat_id=chat_id,
                                        text="I'm thinking, please wait...")


def retrieve_text_to_learn(text: Optional[str],
                           update: Update) -> Optional[str]:
  if text:
    return text
  if update.message.text.startswith("/learn"):
    # There is <text> argument.
    if len(update.message.text.split()) > 1:
      return update.message.text[len("/learn"):].strip()
    else:
      return None
  else:
    # No /learn param, so must be in LEARN_TEXT state already
    return update.message.text


async def learn_handler(update: Update,
                        context: ContextTypes.DEFAULT_TYPE,
                        text: Optional[str] = None) -> int:
  logging.info("Entering learn_handler")
  text = retrieve_text_to_learn(text, update)
  if not text:
    await update.message.reply_text(
      "Please send a German text you want to learn, "
      "or /randomA1, /randomA2, or /randomB1 to learn a random German text: ")
    return LEARN_TEXT

  user_id = update.effective_user.id
  chat_id = update.effective_chat.id

  # Create or update UserProfile in user_data
  user_profile = await db.get_user_profile(user_id)
  # TODO: Check if text is too short (less than 5 sentences), then just translate and explain each sentence.

  # Truncate text to max 1500 tokens.
  text = text[:1500]
  # Create a new LearningSession
  session_id = len(user_profile.sessions)
  session = LearningSession(session_id=session_id,
                            chat_id=chat_id,
                            text=text,
                            start_time=datetime.now())
  user_profile.sessions.append(session)
  await update.message.reply_text(
    "I'm extracting keywords and questions, please wait ~30 seconds...")
  # Run all requests in parallel.
  keywords_task = asyncio.create_task(keyword_extractor.extract_keywords(text))
  questions_task = asyncio.create_task(
    question_extractor.extract_questions(text))

  # Generate keywords for the session.
  session.keywords = await keywords_task
  await update.message.reply_text(
    "Click a keyword to learn more:",
    reply_markup=create_keywords_keyboard(user_profile))
  await db.set_user_profile(user_profile)

  # Generate quiz and start asking questions
  session.quiz = await questions_task
  # Make sure saving the use_profile before calling another handler.
  await db.set_user_profile(user_profile)
  await ask_question_handler(update, context)

  return ASK_QUESTION


def create_keywords_keyboard(
    user_profile: UserProfile) -> InlineKeyboardMarkup:
  logging.info("Entering create_keywords")
  session = user_profile.sessions[-1]
  keywords = [keyword.word for keyword in session.keywords]

  current_page = session.current_keyword_page
  start_index = current_page * KEYWORDS_PER_PAGE
  end_index = start_index + KEYWORDS_PER_PAGE
  page_keywords = keywords[start_index:end_index]

  keyboard = [[
    InlineKeyboardButton(text=word, callback_data=f'keyword {word}')
    for word in page_keywords[i:i + KEYWORDS_PER_ROW]
  ] for i in range(0, len(page_keywords), KEYWORDS_PER_ROW)]

  # Add << and >> buttons at the end to allow user to increase or decrease the current page.
  navigation_buttons = [
    InlineKeyboardButton("<<", callback_data="prev_page"),
    InlineKeyboardButton(">>", callback_data="next_page")
  ]
  keyboard.append(navigation_buttons)

  return InlineKeyboardMarkup(keyboard)


async def ask_question_handler(update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering ask_question_handler")
  user_profile = await db.get_user_profile(update.effective_user.id)
  session = user_profile.sessions[-1]
  if session.next_question_idx >= len(session.quiz):
    await context.bot.send_message(session.chat_id,
                                   f'{session.summary_quiz()}')
    if (session.text != "VocabQuiz"):
      await context.bot.send_message(
        session.chat_id,
        "Send /morequestions, /translate, /stoplearn, or /learnnew to proceed"
      )
    else:
      await context.bot.send_message(
        session.chat_id,
        "Send /vocabs to practice more")
  else:
    question = session.quiz[session.next_question_idx]
    logger.info(f'ask_question: {question}')
    await context.bot.send_poll(session.chat_id,
                                question.question,
                                question.options,
                                is_anonymous=False,
                                allows_multiple_answers=False,
                                type=Poll.QUIZ,
                                correct_option_id=question.correct_idx,
                                explanation=question.explanation)
    # Update asking_question_idx in the LearningSession
    session.next_question_idx += 1
    await db.set_user_profile(user_profile)

  return ASK_QUESTION


async def ask_question_on_answer_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  poll_answer = update.poll_answer
  user_profile = await db.get_user_profile(update.effective_user.id)
  session = user_profile.sessions[-1]
  current_question = session.quiz[session.next_question_idx - 1]

  current_question.answer_time = datetime.now()
  current_question.answer_idx = poll_answer.option_ids[0]

  # Update vocab progress if it's a VocabQuiz
  if session.text == "VocabQuiz":
    vocab_root = session.vocab_roots[session.next_question_idx - 1]
    if vocab_root in user_profile.vocabs.dictionary:
      vocab = user_profile.vocabs.dictionary[vocab_root]
      if current_question.is_correct():
        vocab.correct_answer()
      else:
        vocab.wrong_answer()

  await db.set_user_profile(user_profile)

  return await ask_question_handler(update, context)


async def morequestions_handler(update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering morequestions_handler")
  user_profile = await db.get_user_profile(update.effective_user.id)
  session = user_profile.sessions[-1]
  message = await create_placeholder_message(update.effective_user.id, context)
  await message.edit_text("Generating new quiz...")
  # Generate a new set of questions and append them to the quiz
  new_questions = await question_extractor.extract_questions(session.text)
  session.quiz.extend(new_questions)
  await db.set_user_profile(user_profile)

  return await ask_question_handler(update, context)


async def keywords_on_click_handler(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  user_profile = await db.get_user_profile(update.effective_user.id)
  session = user_profile.sessions[-1]
  data = query.data.split()

  if data[0] == "prev_page":
    if session.current_keyword_page <= 0: return
    session.current_keyword_page = max(0, session.current_keyword_page - 1)
    await db.set_user_profile(user_profile)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(user_profile))
  elif data[0] == "next_page":
    max_page = (len(session.keywords) - 1) // KEYWORDS_PER_PAGE
    if session.current_keyword_page >= max_page: return
    session.current_keyword_page = min(max_page,
                                       session.current_keyword_page + 1)
    await db.set_user_profile(user_profile)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(user_profile))
  else:
    selected_keyword = ' '.join(data[1:])
    keyword = next((k for k in session.keywords if k.word == selected_keyword),
                   None)

    if keyword:
      user_profile.vocabs.click_keyword(keyword, session.session_id)
      await db.set_user_profile(user_profile)
      if keyword.summary() == query.message.text:
        # Users click on the same keyword, skip.
        return None
      await query.edit_message_text(
        keyword.summary(), reply_markup=create_keywords_keyboard(user_profile))
    else:
      await query.answer("Keyword not found.")

  return None


async def learn_text_handler(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering learn_text_handler")
  text = update.message.text.strip()
  if text:
    return await learn_handler(update, context, text)
  else:
    await update.message.reply_text(
      "Please send a non-empty text or /randomA1, /randomA2 or /randomB1")
    return LEARN_TEXT


def remove_introducing_paragraph(string: str) -> str:
  paragraphs = string.split('\n\n')
  if paragraphs[0].endswith(':'):
    del paragraphs[0]
  return '\n\n'.join(paragraphs)


async def random_text_handler(update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering random_text_handler")
  message = await create_placeholder_message(update.effective_user.id, context)
  random_type = random.choice(["story"])
  level = random.choice(["A1", "A2", "B1", "B2"])
  level_map = {
    "/randomA1": "A1",
    "/randomA2": "A2",
    "/randomB1": "B1",
    "/randomB2": "B2"
  }
  if update.message.text in level_map:
    level = level_map[update.message.text]
  await message.edit_text(
    f"Generating a German {random_type} at {level} level for you to learn...")
  text = await ask_anything_extractor.extract_response(
    f"Give me an interesting {random_type} that usually appears in German {level} reading test. Only include German text!"
  )
  text = remove_introducing_paragraph(text)
  text = text.replace("\n\n", "\n")
  await message.edit_text(text)
  return await learn_handler(update, context, text)


async def stop_learn_handler(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering stop_learn_handler")
  user_profile = await db.get_user_profile(update.effective_user.id)
  session = user_profile.sessions[-1]
  session.end_time = datetime.now()
  await db.set_user_profile(user_profile)

  await update.message.reply_text(session.summary())
  return ConversationHandler.END


async def ask_anything_handler(update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering ask_anything_handler")
  # Placeholder for the actual implementation
  response_future = ask_anything_extractor.extract_response(
    update.message.text)
  message = await create_placeholder_message(update.effective_user.id, context)
  await message.edit_text(await response_future)
  return None


async def define_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering define_handler")
  # Check if the user provided the word
  if len(context.args) == 0:
    await update.message.reply_text("No word to define. Send /define <word>")
    return

  phrase = " ".join(context.args)
  keywords_future = definition_extractor.extract_definitions(phrase)
  message = await create_placeholder_message(update.message.chat_id, context)
  keywords = await keywords_future
  user_profile = await db.get_user_profile(update.effective_user.id)
  for keyword in keywords:
    user_profile.vocabs.define_vocab(keyword, session_id=-1)
  # Reply to the user with the definition
  if keywords:
    await db.set_user_profile(user_profile)
    await message.edit_text("\n\n".join(kw.summary() for kw in keywords))
  else:
    generic_def = await ask_anything_extractor.extract_response(
      f'What does ` {phrase}` mean?')
    await message.edit_text(generic_def)


async def translate_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering translate_handler")
  user_profile = await db.get_user_profile(update.effective_user.id)
  # Check if the user provided the text
  translation = None
  message = await create_placeholder_message(update.message.chat_id, context)
  if len(context.args) > 0:
    text = " ".join(context.args)
    translation = await translation_extractor.extract_translation(text)
  elif user_profile.sessions and user_profile.sessions[-1].end_time is None:
    # If the user is in the middle of a session, use the last session's text.
    session = user_profile.sessions[-1]
    if session.translation:
      # Reuses existing translation if there is.
      translation = session.translation
    else:
      translation = await translation_extractor.extract_translation(
        session.text)
      session.translation = translation
      await db.set_user_profile(user_profile)
  else:
    await message.edit_text("No text to translate. Send /translate <text>")
    return
  # Reply to the user with the translation
  await message.edit_text(translation)


async def refresh_vocab_quiz():
  all_user_profiles = await db.get_all_user_profiles()

  for user_profile in all_user_profiles:
    due_vocabs = user_profile.vocabs.due_vocabs(n=30)
    if not due_vocabs:
      continue

    quiz_vocabs = []
    for vocab in due_vocabs:
      n = len(vocab.quiz)
      if n == 0 or random.random() < 1 / n:
        quiz_vocabs.append(vocab)
      # Do not refresh more than 10 vocabs at a time
      if len(quiz_vocabs) >= 10:
        break

    if len(quiz_vocabs) == 0:
      continue

    new_questions = await vocab_question_extractor.extract_questions(
      vocabs=quiz_vocabs)

    for root, question in new_questions:
      matched_vocab = next(vocab for vocab in quiz_vocabs
                           if vocab.root == root)
      if not matched_vocab:
        continue
      matched_vocab.quiz.append(question)

    await db.set_user_profile(user_profile)


async def remind_vocabs(user_profiles: List[UserProfile],
                        context: ContextTypes.DEFAULT_TYPE):
  for user_profile in user_profiles:
    if not user_profile.sessions:
      continue
    latest_session = user_profile.sessions[-1]

    due_vocabs = user_profile.vocabs.due_vocabs(n=10)
    if not due_vocabs:
      await context.bot.send_message(
        chat_id=latest_session.chat_id,
        text=f'No more vocabs due today, great job!')
      continue

    message = "Here are your due vocabs for today:\n\n"
    for i, vocab in enumerate(due_vocabs):
      message += f"{i+1}. {vocab.root}\n"
      for encounter in vocab.encounters:
        message += f"  - {encounter.summary()}\n"
      message += "\n"

    await context.bot.send_message(chat_id=latest_session.chat_id,
                                   text=message)
    await refresh_vocab_quiz()
    await context.bot.send_message(
      chat_id=latest_session.chat_id,
      text="Send /vocabquiz to show how well you remember these words.")


async def remind_vocabs_handler(context: ContextTypes.DEFAULT_TYPE):
  all_user_profiles = await db.get_all_user_profiles()
  await remind_vocabs(all_user_profiles, context)


async def vocabs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_profile = await db.get_user_profile(update.effective_user.id)
  await remind_vocabs([user_profile], context)


async def vocabquiz_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering vocabquiz_handler")

  user_profile = await db.get_user_profile(update.effective_user.id)
  due_vocabs = user_profile.vocabs.due_vocabs(n=20)
  for v in due_vocabs:
    print(v)
  quiz = [random.choice(vocab.quiz) for vocab in due_vocabs if vocab.quiz][:10]
  vocab_roots = [vocab.root for vocab in due_vocabs if vocab.quiz][:10]
  session_id = len(user_profile.sessions)
  session = LearningSession(session_id=session_id,
                            text="VocabQuiz",
                            chat_id=update.effective_chat.id,
                            vocab_roots=vocab_roots,
                            quiz=quiz,
                            start_time=datetime.now())
  user_profile.sessions.append(session)
  await db.set_user_profile(user_profile)

  return await ask_question_handler(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  help_text = (
    "Welcome to GermanTutor Bot!\n\n"
    "Send /learn: start learning a German Text. I'll help you: \n"
    "- Learn keywords from the text\n"
    "- Practice with quiz questions\n"
    "- Translate the text\n"
    "Send /vocabs: list vocabs to learn today, extracted from your activity\n"
    "Send /define Danke: short definition of the word 'Danke'\n"
    "Send /translate Es war einmal: to translate the phrase 'Es war einmal'\n"
    "Send any question, like 'Why \"Ich weiß, dass ich Deutsch lernen kann\" and not \"dass ich kann lernen Deutsch\"?'\n"
    "Send /help to see this message.")

  await update.message.reply_text(help_text,
                                  reply_markup=ReplyKeyboardRemove())


def main():
  # Create the Application and pass it your bot's token.
  application = Application.builder().token(
    TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()
  default_handlers = [
    CommandHandler("stoplearn", stop_learn_handler),
    CommandHandler('define', define_handler),
    CommandHandler('def', define_handler),
    CommandHandler('translate', translate_handler),
    CommandHandler('trans', translate_handler),
    CommandHandler('help', help_handler),
    CommandHandler('vocabs', vocabs_handler),
    CommandHandler('vocabquiz', vocabquiz_handler),
    MessageHandler(filters.TEXT & ~filters.COMMAND, ask_anything_handler)
  ]
  learn_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("learn", learn_handler)],
    states={
      LEARN_TEXT: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, learn_text_handler),
        CommandHandler("random", random_text_handler),
        CommandHandler("randomA1", random_text_handler),
        CommandHandler("randomA2", random_text_handler),
        CommandHandler("randomB1", random_text_handler),
        CommandHandler("randomB2", random_text_handler),
      ],
      ASK_QUESTION: [
        CommandHandler("morequestions", morequestions_handler),
        CommandHandler("translate", translate_handler),
        CommandHandler("trans", translate_handler),
        CommandHandler("learnnew", learn_handler),
        CommandHandler("learn", learn_handler)
      ]
    },
    fallbacks=default_handlers,
    map_to_parent={
      ConversationHandler.END: -1,
    })

  application.add_handler(learn_conv_handler)

  # Register the callback query handler
  application.add_handler(
    CallbackQueryHandler(keywords_on_click_handler,
                         pattern='^[keyword|prev_page|next_page]'))
  application.add_handler(PollAnswerHandler(ask_question_on_answer_handler))

  # Register stateless commands
  for handler in default_handlers:
    application.add_handler(handler)
  application.add_handler(CommandHandler('start', help_handler))

  # Schedule the handler to run every day at 10:00am
  job_queue = application.job_queue
  job_queue.run_daily(remind_vocabs_handler, time(hour=10, minute=0, second=0))
  # Run the bot until the user presses Ctrl-C
  application.run_polling()


if __name__ == '__main__':
  main()
