import logging
import asyncio, nest_asyncio
import os
from datetime import datetime

import telegram
from telegram import ReplyKeyboardRemove, Update, Poll, Message
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

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
from definition_extractor import DefinitionExtractor
from translation_extractor import TranslationExtractor 
from data_models import UserProfile, LearningSession, Keyword

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

async def create_placeholder_message(chat_id: int,
                               context: ContextTypes.DEFAULT_TYPE) -> Message:
  await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING) 
  # Send the initial waiting message
  return await context.bot.send_message(chat_id=chat_id, text="I'm thinking, please wait...")

def get_user_profile(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> UserProfile:
  # Create or update UserProfile in user_data
  if 'profile' not in context.user_data:
    context.user_data['profile'] = UserProfile(user_id=user_id)
  return context.user_data['profile']
  
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
  user_profile = get_user_profile(user_id, context)
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
    "I'm extracting keywords and questions, please wait a few seconds...")
  # Run all requests in parallel.
  session.keywords, session.quiz = await asyncio.gather(
    keyword_extractor.extract_keywords(text),
    question_extractor.extract_questions(text))
  # Generate keywords for the session.
  await update.message.reply_text(
    "Click a keyword to learn more:",
    reply_markup=create_keywords_keyboard(update, context))

  # Generate quiz and start asking questions
  await ask_question_handler(update, context)

  return ASK_QUESTION


def create_keywords_keyboard(
    update: Update, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
  logging.info("Entering create_keywords")
  user_profile = get_user_profile(update.effective_user.id, context)
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
  user_profile = get_user_profile(update.effective_user.id, context)
  session = user_profile.sessions[-1]
  if session.next_question_idx >= len(session.quiz):
    await context.bot.send_message(session.chat_id,
                                   f'{session.summary_quiz()}')
    await context.bot.send_message(
      session.chat_id, "Select /morequestions, /translate, /stoplearn, or /learnnew to proceed")
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
  user_profile = get_user_profile(update.effective_user.id, context)
  session = user_profile.sessions[-1]
  current_question = session.quiz[session.next_question_idx - 1]

  current_question.answer_time = datetime.now()
  current_question.answer_idx = poll_answer.option_ids[0]

  return await ask_question_handler(update, context)


async def morequestions_handler(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> int:
  logging.info("Entering morequestions_handler")
  user_profile = get_user_profile(update.effective_user.id, context)
  session = user_profile.sessions[-1]
  message = await create_placeholder_message(update.effective_user.id, context)
  await message.edit_text("Generating new quiz...")
  # Generate a new set of questions and append them to the quiz
  new_questions = await question_extractor.extract_questions(session.text)
  session.quiz.extend(new_questions)

  return await ask_question_handler(update, context)


async def keywords_on_click_handler(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  user_profile = get_user_profile(update.effective_user.id, context)
  session = user_profile.sessions[-1]
  data = query.data.split()

  if data[0] == "prev_page":
    if session.current_keyword_page <= 0: return
    session.current_keyword_page = max(0, session.current_keyword_page - 1)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(update, context))
  elif data[0] == "next_page":
    max_page = (len(session.keywords) - 1) // KEYWORDS_PER_PAGE
    if session.current_keyword_page >= max_page: return
    session.current_keyword_page = min(max_page,
                                       session.current_keyword_page + 1)
    return await query.edit_message_reply_markup(
      create_keywords_keyboard(update, context))
  else:
    selected_keyword = ' '.join(data[1:])
    keyword = next((k for k in session.keywords if k.word == selected_keyword),
                   None)

    if keyword:
      user_profile.vocabs.click_keyword(keyword, session.session_id)
      await query.edit_message_text(
        keyword.summary(), reply_markup=create_keywords_keyboard(update, context))
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
  user_profile = get_user_profile(update.effective_user.id, context)
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
  keywords_future = definition_extractor.extract_definitions(phrase)
  message = await create_placeholder_message(update.message.chat_id, context)
  keywords = await keywords_future
  user_profile = get_user_profile(update.effective_user.id, context)
  for keyword in keywords:
    user_profile.vocabs.define_vocab(keyword, session_id=-1)
  # Reply to the user with the definition
  await message.edit_text("\n\n".join(kw.summary() for kw in keywords))

async def translate_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
  logging.info("Entering translate_handler")
  user_profile = get_user_profile(update.effective_user.id, context)
  # Check if the user provided the text
  
  if len(context.args) > 0:
    text = " ".join(context.args)
  elif user_profile.sessions and user_profile.sessions[-1].end_time is None:
    # If the user is in the middle of a session, use the last session's text. 
    text = user_profile.sessions[-1].text
  else:
    await update.message.reply_text("No text to translate. Send /translate <text>")
    return
  message = await create_placeholder_message(update.message.chat_id, context)
  # Reply to the user with the translation
  await message.edit_text(await translation_extractor.extract_translation(text))
  await update.message.reply_text("Select /morequestions, /translate, /stoplearn, or /learnnew to proceed")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # Create UserProfile if not exist.
  user_profile = get_user_profile(update.effective_user.id, context)

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
        CommandHandler("morequestions", morequestions_handler),
        CommandHandler("translate", translate_handler),
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
