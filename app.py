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

class WhatsNewSpecificIntentHandler(AbstractRequestHandler):
    """Handler for Whats New Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("WhatsNewSpecificIntent")(handler_input)
    def handle(self, handler_input):
        logger.info("In WhatsNewSpecificIntentHandler")

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        speech_text = "I couldn't find anything about it"
        try:
            current_slot = handler_input.request_envelope.request.intent.slots["topic"]
            if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                topic = current_slot.resolutions.resolutions_per_authority[0].values[0].value.name
                speech_text = "Currently there is no news about " +topic
                with conn.cursor() as cur:
                    logger.info(topic)
                    cur.execute('select * from articles where lower(topic) = %s ORDER BY created_at desc limit 1', topic);
                    result = cur.fetchall()
                    for row in result:
                        speech_text = "Here is one headline in %s. Title is %s. Do you want to read this article?" % (row[1], row[2])
                        session_attr["article"] = row

        except Exception as e:
                 logger.info(e)

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

class WhatsNewIntentHandler(AbstractRequestHandler):
    """Handler for Whats New Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("WhatsNewIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In WhatsNewIntentHandler")


        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes


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
            session_attr["ids"] = ids
            speech_text += "Are you interested in any of these topics?"

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
        speech_text = "Got you! "
        id_selected = ids['0']
        try:
            current_slot = handler_input.request_envelope.request.intent.slots["Order"]
            order = int(current_slot.value)
            id_selected = ids[str(order-1)]
        except Exception as e:
            logger.info(e)
            speech_text += " Let's go with the first one then."

        with conn.cursor() as cur:
            cur.execute('select * from articles where id = %s', id_selected)
            results = cur.fetchall()
            logger.info(results)

            for row in results:
                session_attr['article'] = row
                # speech_text += row[3]
                # speech_text += "..."
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
                    session_attr['article'] = related_article
                # else:
                #     speech_text += ' This articles takes ' + str(duration) + ' minutes to read. Do you have time for this?'
                #     break

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
        speech_text =  ("<say-as interpret-as='interjection'> Okay! here we go! </say-as>"
                   "{}" "...That's the end of the article."
                   " Anything you would want to know more about?"
                  .format(article[10][:100]))
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
                speech_text = "The writer is specified as  %s. Do you want to know more about or from this writer?" % article[12]
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
        speech_text = "I'm sorry I could not find more related articles"
        try:
            current_slot = handler_input.request_envelope.request.intent.slots['Side']
            if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                logger.info("slot success")
                side = current_slot.resolutions.resolutions_per_authority[0].values[0].value.name
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
                            session_attr['article'] = row

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
sb.add_request_handler(WhatsNewSpecificIntentHandler())

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
