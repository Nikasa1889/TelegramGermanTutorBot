import logging
import asyncio, nest_asyncio
import os
from datetime import datetime

from telegram import ReplyKeyboardRemove, Update, Poll
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (
  Application,
  CommandHandler,
  ContextTypes,
  ConversationHandler,
  MessageHandler,
  CallbackQueryHandler,
  PollAnswerHandler,
  filters,
)

from keyword_extractor import KeywordExtractor
from question_extractor import QuestionExtractor
from data_models import UserProfile, LearningSession, Keyword

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
KEYWORDS_PER_ROW = 3
KEYWORDS_PER_PAGE = 3 * KEYWORDS_PER_ROW


async def generate_translation(phrase: str) -> str:
  return "Sample translation for " + phrase


async def generate_definition(phrase: str) -> Keyword:
  # Replace this part with your actual definition generation logic.
  root = "SampleRoot_" + phrase
  definition = "Sample definition for " + phrase
  snippet = "Sample snippet for " + phrase

  keyword = Keyword(root=root,
                    word=phrase,
                    snippet=snippet,
                    definition=definition)
  return keyword


# Enable logging
logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level=logging.INFO)
logger = logging.getLogger(__name__)

LEARN_TEXT, ASK_QUESTION = range(2)
keyword_extractor = KeywordExtractor()
question_extractor = QuestionExtractor()


async def learn_handler(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering learn_handler")
  # Check if user sent /learn command with text
  if update.message.text.startswith("/learn"):
    # There is <text> argument.
    if len(update.message.text.split()) > 1:
      text = update.message.text[len("/learn"):].strip()
    else:
      await update.message.reply_text(
        "Please provide the text you want to learn about: ")
      return LEARN_TEXT
  else:
    # No /learn param, so must be in LEARN_TEXT state already
    text = update.message.text

  user_id = update.effective_user.id
  chat_id = update.effective_chat.id

  # Create or update UserProfile in user_data
  if 'profile' not in context.user_data:
    context.user_data['profile'] = UserProfile(user_id=user_id)

  user_profile = context.user_data['profile']
  # TODO: Check if text is too short (less than 5 sentences), then just translate and explain each sentence.
  # TODO: Check if the text too long (more than 1000 tokens).
  # Create a new LearningSession
  session_id = len(user_profile.sessions)
  session = LearningSession(session_id=session_id,
                            chat_id=chat_id,
                            text=text,
                            start_time=datetime.now())
  user_profile.sessions.append(session)
  await update.message.reply_text(
    "I'm extracting keywords and questions, please wait a few seconds...")
  # Run all requests in parallel.
  session.keywords, session.quiz = await asyncio.gather(
    keyword_extractor.extract_keywords(text),
    question_extractor.extract_questions(text))
  # Generate keywords for the session.
  await update.message.reply_text(
    "Click a keyword to learn more:",
    reply_markup=create_keywords_keyboard(context))

  # Generate quiz and start asking questions
  await ask_question_handler(update, context)

  return ASK_QUESTION


def create_keywords_keyboard(
    context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
  logging.info("Entering create_keywords")
  session = context.user_data['profile'].sessions[-1]
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
  session = context.user_data["profile"].sessions[-1]
  if session.next_question_idx >= len(session.quiz):
    await context.bot.send_message(session.chat_id,
                                   f'{session.summary_quiz()}')
    await context.bot.send_message(
      session.chat_id, "Select /continue, /stoplearn, or /learnnew to proceed")
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

  return ASK_QUESTION


async def ask_question_on_answer_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
  poll_answer = update.poll_answer
  session = context.user_data['profile'].sessions[-1]
  current_question = session.quiz[session.next_question_idx - 1]

  current_question.answer_time = datetime.now()
  current_question.answer_idx = poll_answer.option_ids[0]

  return await ask_question_handler(update, context)


async def continue_handler(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering continue_handler")
  user_profile = context.user_data['profile']
  session = user_profile.sessions[-1]

  # Generate a new set of questions and append them to the quiz
  new_questions = await question_extractor.extract_questions(session.text)
  session.quiz.extend(new_questions)

  return await ask_question_handler(update, context)


async def keywords_on_click_handler(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  user_profile = context.user_data['profile']
  session = user_profile.sessions[-1]
  data = query.data.split()

  if data[0] == "prev_page":
    if session.current_keyword_page <= 0: return
    session.current_keyword_page = max(0, session.current_keyword_page - 1)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(context))
  elif data[0] == "next_page":
    max_page = (len(session.keywords) - 1) // KEYWORDS_PER_PAGE
    if session.current_keyword_page >= max_page: return
    session.current_keyword_page = min(max_page,
                                       session.current_keyword_page + 1)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(context))
  else:
    selected_keyword = ' '.join(data[1:])
    keyword = next((k for k in session.keywords if k.word == selected_keyword),
                   None)

    if keyword:
      user_profile.vocabs.click_keyword(keyword, session.session_id)
      await query.edit_message_text(
        keyword.summary(), reply_markup=create_keywords_keyboard(context))
    else:
      await query.answer("Keyword not found.")

  return None


async def learn_text_handler(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering learn_text_handler")
  text = update.message.text.strip()
  if text:
    return await learn_handler(update, context)
  else:
    await update.message.reply_text("Please provide a non-empty text.")
    return LEARN_TEXT


async def stop_learn_handler(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering stop_learn_handler")
  user_profile = context.user_data['profile']
  session = user_profile.sessions[-1]
  session.end_time = datetime.now()

  await update.message.reply_text(session.summary())
  return ConversationHandler.END


async def ask_chatgpt_handler(update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> int:
  # Placeholder for the actual implementation
  await update.message.reply_text("ChatGPT is currently unavailable.")
  return None


async def define_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering define_handler")
  # Check if the user provided the word
  if len(context.args) == 0:
    await update.message.reply_text("No word to define. Send /define <word>")
    return

  phrase = " ".join(context.args)
  keyword = await generate_definition(phrase)
  context.user_data['profile'].vocabs.define_vocab(keyword, session_id=-1)
  # Reply to the user with the definition
  await update.message.reply_text(keyword.summary())


async def translate_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering translate_handler")

  # Check if the user provided the text
  if len(context.args) == 0:
    await update.message.reply_text(
      "No text to translate. Send /translate <text>")
    return

  text = " ".join(context.args)
  # Reply to the user with the translation
  await update.message.reply_text(await generate_translation(text))


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # Create UserProfile if not exist.
  if 'profile' not in context.user_data:
    user_id = update.effective_user.id
    context.user_data['profile'] = UserProfile(user_id=user_id)

  help_text = ("Welcome to GermanTutor Bot!\n\n"
               "Send /learn <text> to start learning session about the text.\n"
               "During the session, you can:\n"
               "- Learn keywords from the text\n"
               "- Answer quiz questions\n"
               "Send /define <word> to get short definition\n"
               "Send /translate <text> to get translation\n"
               "Send any text to ask ChatGPT directly\n"
               "Send /help to see this message.")

  await update.message.reply_text(help_text,
                                  reply_markup=ReplyKeyboardRemove())


def main():
  # Create the Application and pass it your bot's token.
  application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
  default_handlers = [
    CommandHandler("stoplearn", stop_learn_handler),
    CommandHandler('define', define_handler),
    CommandHandler('translate', translate_handler),
    CommandHandler('help', help_handler),
    MessageHandler(filters.TEXT & ~filters.COMMAND, ask_chatgpt_handler)
  ]
  learn_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("learn", learn_handler)],
    states={
      LEARN_TEXT:
      [MessageHandler(filters.TEXT & ~filters.COMMAND, learn_text_handler)],
      ASK_QUESTION: [
        CommandHandler("continue", continue_handler),
        CommandHandler("learnnew", learn_handler)
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

  # Trick to allow running Async in Colab
  loop = asyncio.new_event_loop()
  nest_asyncio.apply(loop)
  asyncio.set_event_loop(loop)

  # Run the bot until the user presses Ctrl-C
  application.run_polling()


if __name__ == '__main__':
  main()
