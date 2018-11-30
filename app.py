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

#helpers for getting and posting attributes
def getAttribute(handler_input, key):
    attribute_manager = handler_input.attributes_manager
    session_attr = attribute_manager.session_attributes
    return session_attr[key]

def postAttribute(handler_input, key, value):
    attribute_manager = handler_input.attributes_manager
    if attribute_manager is None:
        logger.info("No attribute_manager is available")
        return #bye felicia
    session_attr = attribute_manager.session_attributes
    session_attr[key] = value

#helper for getting slot of specified key, return false for success if fails to fetch
def getSlot(handler_input, key):
    try:
        slot = handler_input.request_envelope.request.intent.slots[key]
        resolution = slot.resolutions.resolutions_per_authority[0]
        if resolution.status.code == StatusCode.ER_SUCCESS_MATCH:
            return resolution.values[0].value.name, True
    except Exception as e:
        logger.info(e)
        return None, False

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
### TODO: change to reflect new data pool, not just all-sides

class WhatsNewIntentHandler(AbstractRequestHandler):
    """Handler for Whats New Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("WhatsNewIntent")(handler_input)

    def handle_topic(topic, handler_input):
        print("WhatsNewIntentHandler:handle_topic(_)")
        speech_text = "We have no news about " + topic + " at this time. " + youCanAskFor
        with conn.cursor() as cur:
            cur.execute('select * from articles where lower(topic) LIKE %s ORDER BY created_at desc limit 1', "%" + topic + "%");
            result = cur.fetchall()
            for row in result:
                #TODO what exactly is returned here?
                speech_text = "Here is one headline in %s. Title is %s. Do you want to read this article?" % (row[1], row[2])
                #postAttribute(handler_input, "article", row)

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle_source(source, handler_input):
        print("WhatsNewIntentHandler:handle_source(_)")

        speech_text = "We have no news about " + source + " at this time. " + youCanAskFor
        with conn.cursor() as cur:
            cur.execute('select * from articles where lower(source) LIKE %s ORDER BY created_at desc limit 1', "%" + source + "%");
            result = cur.fetchall()
            #for row in result:
                #TODO what exactly is returned here?

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle_news(handler_input):

        with conn.cursor() as cur:
            cur.execute('select * from articles where side = %s ORDER BY created_at DESC limit 3', 'unbiased_balanced');
            result = cur.fetchall()
            speech_text = "These are the top three headlines."
            countword = "First"
            ids = {}
            for index, row in enumerate(result):
                speech_text += " %s, %s." % (countword, row[2])
                ids[index] = row[0]
                if index == 0:
                    countword = "Second"
                elif index == 1:
                    countword = "Third"
            postAttribute(handler_input, "ids", row)
            speech_text += "Are you interested in any of these topics?"

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attribute_manager = handler_input.attributes_manager
        logger.info("WhatsNewIntentHandler:handle()")
        topic, _ = getSlot(handler_input, "Topic")
        source, _ = getSlot(handler_input, "Source") #TODO: test
        if topic is not None:
            return self.handle_topic(topic, handler_input)
        elif source is not None:
            return self.handle_source(source, handler_input)

        return self.handle_news()


### User mentions order (first, second, third) -> Gives quick summary and lets user know how long the chosen article takes
### Asks user if wants to read the chosen articles
### TODO:  more accomodation of intent invocation, functionality to send email if says no for reading time.

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

    def handle(self, handler_input):
        logger.info("In ConfirmArticleHandler")
        ids = getAttribute(handler_input, "ids")
        logger.info(ids)
        speech_text = "Got you! "
        id_selected = ids[0]
        order, success = getSlot(handler_input, "Order")
        if success:
            id_selected = ids[str(order-1)]
        else:
            speech_text += " Let's go with the first one then."

        with conn.cursor() as cur:
            cur.execute('select * from articles where id = %s', id_selected)
            results = cur.fetchall()
            logger.info(results)

            for row in results:
                postAttribute(handler_input, "article", row)
                speech_text += 'Here is a quick summary of the issue. '
                speech_text += row[10]
                speech_text += 'Would you like to read an article about this? '
                cur.execute("select * from articles join article_relations on articles.id = article_relations.related_to_id where article_relations.article_id = %s and lower(article_relations.relation_type) = 'center' or lower(article_relations.relation_type) like 'lean' limit 1" ,row[0])
                related = cur.fetchall()
                for related_article in related:
                    related_duration = self.get_duration(related_article[8])
                    if related_duration > 0:
                        speech_text += 'It takes ' + str(self.get_duration(related_article[8])) + ' minutes to read.'
                    else:
                        speech_text += 'It takes less than a minute to read.'
                    postAttribute(handler_input, "article", related_article)

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


### Reading article if user says yes.
### Asks whether the users wants to know more about details of an article
### TODO: there are more contexts for user to say yes other than yes to reading an article - we have to differentiate invocation after"yes" according to contexts
###       no gracious fallback when said no
class YesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.YesIntent")(handler_input) and
                "article" in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In YesIntentHandler")
        article = getAttribute(handler_input, "article")
        speech_text =  ("<say-as interpret-as='interjection'> Okay! here we go! </say-as>"
                   "{}" "...That's the end of the article."
                   " Anything you would want to know more about?"
                  .format(article[10][:100]))
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

### When asked "Anything you would want to know more about?" by YesIntentHandler, gets the detail the user wants to know and reply
### Currently only supports author
### TODO: supports more details other than author, when said yes after this intent nothing really happens
class AskDetailsHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AskDetailsIntent")(handler_input) and
                "article" in session_attr)

    def handle(self, handler_input):
        logger.info("In AskDetailsHandler")
        article = getAttribute(handler_input, "article")
        speech_text = "I unfortunately do not know much about that."
        detail, success = getSlot(handler_input, "Details")
        if success:
            speech_text = "The writer is specified as  %s. Do you want to know more about or from this writer?" % article[12]
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


### When asked about what specific political side says
### TODO: remove this one since we are not dealing with side anymore
class RelatedArticleHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("RelatedArticleIntent")(handler_input) and
                "article" in session_attr)
    def handle(self, handler_input):
        logger.info("In RelatedArticleHandler")
        article = getAttribute(handler_input, "article")
        speech_text = "I'm sorry I could not find more related articles"
        side, success = getSlot(handler_input, "Side")
        if success:
            speech_text = "I'm sorry there is no more related articles from %s side" % side
            with conn.cursor() as cur:
                cur.execute("select article_id from article_relations where related_to_id = %s limit 1" ,article[0])
                origin_result = cur.fetchall()
                origin_article_id = ''
                for origin in origin_result:
                    logger.info(origin[0])
                    cur.execute("select * from articles join article_relations on articles.id = article_relations.related_to_id where article_relations.article_id = %s and lower(article_relations.relation_type) like %s and article_relations.related_to_id != %s  limit 1" ,(origin[0], side,article[0]))
                    result = cur.fetchall()
                    for row in result:
                        speech_text = "There is a related article from %s, categorized as %s by Allsides.com. Here is the title. %s. " % (row[9], row[7] ,row[2])
                        speech_text += " Would you like to hear more?"
                        postAttribute(handler_input, 'article', row)

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
sb.add_request_handler(AskDetailsHandler())
sb.add_request_handler(RelatedArticleHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

handler = sb.lambda_handler()
