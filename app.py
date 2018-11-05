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

rds_host  = "cs206.ci8sromxgv9w.us-west-2.rds.amazonaws.com"
name = rds_config.db_username
password = rds_config.db_password
db_name = rds_config.db_name

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#fh = logging.FileHandler('spam.log')
ch = logging.StreamHandler()
logger.addHandler(ch)

try:
    conn = pymysql.connect(rds_host, user=name, passwd=password, db=db_name, connect_timeout=5)
except:
    logger.error("ERROR: Unexpected error: Could not connect to MySql instance.")
    sys.exit()
logger.info("connection worked")


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Hi there! I can help you navigate news better. Ask me anything!"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("Hello World", speech_text)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class WhatsNewIntentHandler(AbstractRequestHandler):
    """Handler for Whats New Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("WhatsNewIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In WhatsNewIntentHandler")

        last_hour_date_time = datetime.utcnow() - timedelta(hours = 1)
        side = None
        try:
            current_slot = handler_input.request_envelope.request.intent.slots["Side"]
            if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                if len(current_slot.resolutions.resolutions_per_authority[0].values) > 1:
                    prompt = "I see. Which would you like to hear more from"
                    values = " or ".join([e.value.name for e in current_slot.resolutions.resolutions_per_authority[0].values])
                    prompt += values + " ?"
                    return handler_input.response_builder.speak(prompt).ask(prompt).add_directive(ElicitSlotDirective(slot_to_elicit=current_slot.name)).response
                else:
                    side = current_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                    logger.info("side fetched")
                    logger.info(side)
                    with conn.cursor() as cur:
                        cur.execute('select * from articles where side = %s ORDER BY RAND() limit 1', side);
                        result = cur.fetchall()
                        for row in result:
                            speech_text = "Here is one headline from the %s side. %s. Are you interested in this one?" % (row[7], row[2])

        except Exception as e:
                 logger.info(e)

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes

        if side is None:
            with conn.cursor() as cur:
                cur.execute('select * from articles where side = %s ORDER BY created_at limit 3', 'unbiased_balanced');
                result = cur.fetchall()
                speech_text = "These are the top three headlines from all sides."
                countword = "First"
                ids = {}
                for index, row in enumerate(result):
                    speech_text += " %s, %s." % (countword, row[2])
                    ids[index] = row[0]
                    if index == 0:
                        countword = "Second"
                    elif index == 1:
                        countword = "Third"
                session_attr["ids"] = ids
                speech_text += "Are you interested in any of these?"

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


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
        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        # _ = attribute_manager.request_attributes["_"]
        ids = session_attr["ids"]
        logger.info(ids)
        speech_text = "Sure, here is the snippet of the story. "
        current_slot = handler_input.request_envelope.request.intent.slots["Order"]
        order = current_slot.value
        id_selected = ids[order]
        with conn.cursor() as cur:
            cur.execute('select * from articles where id = %s', id_selected)
            results = cur.fetchall()
            for row in results:
                session_attr['article'] = row
                speech_text += row[3]
                speech_text += "..."
                duration = self.get_duration(row[8])
                speech_text += ' This articles takes ' + str(duration) + ' minutes to read.'
                break
        speech_text += " Do you have time for this?"

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

class YesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.YesIntent")(handler_input) and
                "article" in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In YesIntentHandler")

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        article = session_attr['article']
        speech_text =  ("<say-as interpret-as='interjection'>okay here we go! </say-as>"
                   "{}" "<say-as interpret-as='interjection'> That's the end of the article.</say-as>"
                   "<amazon:effect name='whispered'> Anything you would want to know more? </amazon:effect>"
                  .format(article[10]))
        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


class AskDetailsHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AskDetailsIntent")(handler_input) and
                "article" in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In AskDetailsHandler")

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        article = session_attr['article']

        speech_text = "I unfortunately do not know much about that."
        try:
            current_slot = handler_input.request_envelope.request.intent.slots["details"]
            if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                author = current_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                logger.info("author fetched")
                speech_text = "it's written by %s. Do you want to know more about or from this journalist?" % article[12]
        except Exception as e:
            logger.info(e)

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response


class RelatedArticleHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("RelatedArticleIntent")(handler_input) and
                "article" in session_attr)
    def handle(self, handler_input):
        logger.info("In RelatedArticleHandler")
        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        article = session_attr['article']
        speech_text = "I'm sorry I don't see any related article on the site"
        try:
            current_slot = handler_input.request_envelope.request.intent.slots['Side']
            if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                logger.info("slot success")
                side = current_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                with conn.cursor() as cur:
                    cur.execute("select * from articles where topic = %s and lower(side) LIKE %s limit 1" ,(article[1], side))
                    result = cur.fetchall()
                    for row in result:
                        speech_text = "There is a related article from %s, as listed by AllSides.com as %s. Here is the headline. %s. " % (row[9], row[7] ,row[2])
                        speech_text += " Would you like to hear more?"

        except Exception as e:
            logger.info(e)

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
        speech_text = "Goodbye!"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("Hello World", speech_text))
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
        speech_text = (
            "I can't help you with that.  "
            "I only know about news... ")
        reprompt = "You can say what's new!"
        handler_input.response_builder.speak(speech_text).ask(reprompt)
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
