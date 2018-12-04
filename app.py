# -*- coding: utf-8 -*-

# This is a simple Hello World Alexa Skill, built using
# the implementation of handler classes approach in skill builder.
import logging
import pymysql
import rds_config
import sys
import math
from datetime import datetime, timedelta

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model.ui import SimpleCard
from ask_sdk_model import Response
from ask_sdk_model.dialog import ElicitSlotDirective
from ask_sdk_model.slu.entityresolution import StatusCode

sb = SkillBuilder()
skillName = "News Chat"

rds_host  = "cs206.ci8sromxgv9w.us-west-2.rds.amazonaws.com"
name = rds_config.db_username
password = rds_config.db_password
db_name = rds_config.db_name

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
logger.addHandler(ch)

#conection
try:
    conn = pymysql.connect(rds_host, user=name, passwd=password, db=db_name, connect_timeout=5)
except:
    logger.error("ERROR: Unexpected error: Could not connect to MySql instance.")
    sys.exit()

#common strings
youCanAskFor = "You can ask me to read the top news from any source like The New York Times or CNN. I can also give you news by topic if you let me know what you want to hear about -- that can be politics, entertainment, music, or (almost) anything else you can think of."


#helper for getting slot of specified key, return false for success if fails to fetch

#TODO: Python map of users, in-memory.
def getUser(handler_input):
    userId = handler_input.request_envelope.context.System.user.user_id;
    #^ TODO test and make sure a valid userID is available
    return None


### reacts to invocation
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        #TODO: Collect relevant user information:
        # if cannot getUser(handler_input)
            #"Hi there! I can help you navigate news better. It looks like this is your first time using News Chat. What's your name?"
        #else
            #"Hi {user name}, let's chat about the news. "  + youCanAskFor

        speech_text = "Hi! let's chat about the news. " + youCanAskFor
        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard(skillName, speech_text)).set_should_end_session(
            False)
        return handler_input.response_builder.response

### Get three top articles from all sides (unbiased_balanced ones)
### Asks if like any one of the articles => Yes_Intent_Hanlder
class WhatsNewIntentHandler(AbstractRequestHandler):
    """Handler for Whats New Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("WhatsNewIntent")(handler_input)

    def read_choices(self, result, query):
        ids = {}
        speech_text = ""
        if query == "topic":
            speech_text = "We have no news about " + query + " at this time. " + youCanAskFor
        elif query == "source":
            speech_text = "We have no news from" + query + " at this time. " + youCanAskFor
        for index, row in enumerate(result):
            if index == 0:
                speech_text = "OK. Let me read you the most recent three headlines. "
                if query != " ":
                    speech_text += 'in %s' % query
            speech_text += " %s.  " %  row[2]
            ids[index] = row[0]
        speech_text += "Do you want more from any one of these stories? Let me know which one if you have a specific one in mind."
        return ids, speech_text

    def handle_topic(self, topic, handler_input):
        print("WhatsNewIntentHandler:handle_topic(_)")
        with conn.cursor() as cur:
            cur.execute('select * from articles where lower(topic) LIKE %s ORDER BY is_headline desc, created_at desc limit 3',  topic );
            result = cur.fetchall()
            self.session_attr['ids'], speech_text = self.read_choices(result, topic)

        self.session_attr['prevContext'] = "listArticles"
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle_source(self,source, handler_input):
        print("WhatsNewIntentHandler:handle_source(_)")
        with conn.cursor() as cur:
            print(source)
            cur.execute('select * from articles where lower(source) LIKE %s ORDER BY is_headline desc, created_at desc limit 3', source);
            result = cur.fetchall()
            self.session_attr['ids'], speech_text = self.read_choices(result, source)

        self.session_attr['prevContext'] = "listArticles"
        handler_input.response_builder.speak(speech_text).ask(speech_text)

        return handler_input.response_builder.response

    def handle_news(self, handler_input):
        print("WhatsNewIntentHandler:handle_news(_)")
        with conn.cursor() as cur:
            cur.execute('select * from articles where side = %s ORDER BY created_at DESC limit 3', 'unbiased_balanced');
            result = cur.fetchall()
            self.session_attr['ids'], speech_text = self.read_choices(result, "")

        self.session_attr['prevContext'] = "listArticles"
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response
        # return handler_input.response_builder.response

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attribute_manager = handler_input.attributes_manager
        self.session_attr = attribute_manager.session_attributes
        intent = handler_input.request_envelope.request.intent
        logger.info("WhatsNewIntentHandler:handle()")
        slots = intent.slots
        if 'Topic' in slots:
            topic_slot = slots['Topic']
            if topic_slot.resolutions:
                topic = topic_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                return self.handle_topic(topic, handler_input)
        if 'Source' in slots:
            source_slot = slots['Source']
            if source_slot.resolutions:
                source = source_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                return self.handle_source(source, handler_input)

        return self.handle_news(handler_input)


### User mentions order (first, second, third) -> Gives quick summary and lets user know how long the chosen article takes
### Asks user if wants to read the chosen articles
class ChooseArticleIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("ChooseArticleIntent")(handler_input) and "ids" in session_attr)

    def get_duration(self, wordcount):
        minutes = wordcount / 150
        logger.info(wordcount)
        logger.info(minutes)
        round_up = int(math.ceil(minutes))
        return round_up

    def read_headline_and_ask(self, handler_input, article_id, order):
        if order == "":
            speech_text = "Okay let's start with the first one then. "
        else:
            speech_text = "Let's take a look. "

        with conn.cursor() as cur:
            speech_text += " This is the headline of the story. "
            cur.execute('select * from articles where id = %s', article_id)
            results = cur.fetchall()
            logger.info(results)
            article = results[0]
            speech_text += article[3]
            duration = self.get_duration(article[8])
            if duration > 0:
                speech_text += " It takes around " + str(duration) + " minutes to read."
            else:
                speech_text += " It takes less than a minute to read."
            self.session_attr['article'] = article

        speech_text += " Shall I start reading?"
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle(self, handler_input):
        attribute_manager = handler_input.attributes_manager
        self.session_attr = attribute_manager.session_attributes
        intent = handler_input.request_envelope.request.intent
        logger.info("ChooseArticleIntentHandler:handle()")
        slots = intent.slots
        ids = self.session_attr['ids']

        speech_text = "Got it. "
        article_id = ids["0"]
        self.session_attr['prevContext'] = "chooseArticle"
        if is_intent_name("AMAZON.YesIntent")(handler_input): #ambiguously said "Yes" when asked interest in the list
            return self.read_headline_and_ask(handler_input, article_id, "")
        if 'Order' in slots:
            try:
                #slot is not filled (e.g. "just give me one")
                order = int(slots['Order'].value)
                article_id = ids[str(order-1)]
                print("artile_id %d" % article_id)
            except:
                return self.read_headline_and_ask(handler_input, article_id, "")

        return self.read_headline_and_ask(handler_input, article_id, order)


### Reading article if user says yes.
### Asks whether the users wants to know more about details of an article
### TODO: we have to make on for NOIntent to deal with no cases for each step
class YesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return is_intent_name("AMAZON.YesIntent")(handler_input)

    def read_article(self, handler_input, article):
        speech_text =  ("Okay! here we go!"
                           "{}" "...That's the end of the article."
                           " Anything you would want to know more about?"
                          .format(article[10][:1000]))
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("YesIntentHandler:handle()")
        attribute_manager = handler_input.attributes_manager
        self.session_attr = attribute_manager.session_attributes
        prev_context = self.session_attr["prevContext"]

        #CONTEXT: ChooseArticleIntent's "Shall I start reading?"
        if prev_context == "chooseArticle":
            article = self.session_attr["article"]
            self.session_attr["prevContext"] = "readArticle"
            return self.read_article(handler_input, article)

        #CONTEXT: WhatsNewIntent's "Do you want more from any one of these stories?"
        elif prev_context == "listArticles": # TODO:(minor) shall we ask the user which one they are interested in the most? currently it just choses the first one.
            return ChooseArticleIntentHandler().handle(handler_input)

        #CONTEXT: ChooseArticleIntent -> YesIntentHandler's read_article "Anything you would want to know more about?"
        elif prev_context == "readArticle":
            return AskDetailsIntentHandler().handle(handler_input)

        speech_text = "Sure! But sorry I just lost context of our conversation... Can we start over?" + youCanAskFor
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

### When asked "Anything you would want to know more about?" by YesIntentHandler, gets the detail the user wants to know and reply
class AskDetailsIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return ((is_intent_name("AskDetailsIntent")(handler_input) and
                "article" in session_attr) or is_intent_name("YesIntentHandler")(handler_input))

    def get_author_details(self, name):
        with conn.cursor() as cur:
            cur.execute('select job, beats from authors where lower(name) LIKE %s', "%" + name.lower() + "%")
            results = cur.fetchall()
            if len(results) > 0:
                author_details = results[0]
                job = author_details[0]
                beats = author_details[1]
                if len(job) == 0 and len(beats) == 0: #columns are nulls so we are not adding details
                    return "", False
                details = "The author %s is " % name
                if len(job) != 0:
                    details += job
                if len(beats) != 0:
                    details += " and usually writes about %s ." % beats
                return details, True
            return "", False

    def read_details(self, handler_input, article, indexes):
        speech_text = "Okay. "
        if len(indexes) == 0:
            name = article[12].split(',')[-1]
            #TODO: have to parse datetime in more readable format
            speech_text = "Here are some facts about the article. The article was written by %s in %s, and published on %s. " % (name, article[9] ,article[11])
            details, success = self.get_author_details(name)
            if success:
                speech_text += details

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle(self, handler_input):
        logger.info("In AskDetailsHandler")
        attribute_manager = handler_input.attributes_manager
        self.session_attr = attribute_manager.session_attributes
        article =  self.session_attr['article']
        if is_intent_name("AMAZON.YesIntent")(handler_input): #ambiguously said "Yes" when asked want to know more
            return self.read_details(handler_input, article, [])

        #TODO: check slots to see if the user is curious about particular detail (Add more slots other than author, and checks slots to deal with them here)
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "You can ask whats new to me!"

        handler_input.response_builder.speak(speech_text).ask(
            speech_text).set_card(SimpleCard(
                "Hello World", speech_text))
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "You’re welcome! As Walter Cronkite would say, 'And that’s the way it is' "

        handler_input.response_builder.speak(speech_text)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Okay bye for now! As Walter Cronkite would say, 'And that’s the way it is' "

        handler_input.response_builder.speak(speech_text)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speech = "Sorry, there was some problem. Please try again!!"
        handler_input.response_builder.speak(speech).ask(speech)

        return handler_input.response_builder.response


sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(WhatsNewIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(ChooseArticleIntentHandler())
sb.add_request_handler(YesIntentHandler())
sb.add_request_handler(AskDetailsIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

handler = sb.lambda_handler()
