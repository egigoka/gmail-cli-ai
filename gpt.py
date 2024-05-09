from datetime import datetime
import time

from openai import OpenAI, RateLimitError

from gmail import get_equal_substrings_from_begging_center_end

from commands import dirify, Str


class TooManyTokensError(Exception):
    def __init__(self, tokens_count_new, requested_tokens):
        self.tokens_count_new = tokens_count_new
        self.requested_tokens = requested_tokens


def openai_authenticate(openai_api_key):
    return OpenAI(api_key=openai_api_key)


def get_messages_gpt(openai_client, model, messages, max_tokens, max_retries=10, retry=1):
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens
        )
    except RateLimitError as e:
        if retry > max_retries:
            raise
        response_json = e.response.json()
        if response_json['error']['type'] == 'tokens':
            tokens_count_new = Str.substring(response_json['error']['message'], ' on tokens per min (TPM): Limit ')
            tokens_count_new = Str.get_integers(tokens_count_new)[0]
            requested_tokens = Str.substring(response_json['error']['message'], 'Requested ')
            requested_tokens = Str.get_integers(requested_tokens)[0]
            raise TooManyTokensError(tokens_count_new=tokens_count_new, requested_tokens=requested_tokens)
        time.sleep(pow(2, retry))
        response = get_messages_gpt(openai_client=openai_client,
                                    model=model,
                                    messages=messages,
                                    max_tokens=max_tokens,
                                    max_retries=max_retries,
                                    retry=retry + 1)

    return response


def compose_gpt_message(tokens_count, token_multiplier, all_info):
    today_date = datetime.today().strftime('%Y-%m-%d')
    today_time = datetime.today().strftime('%H:%M:%S')
    prompt = f"""I am an AI assisting with email management. 
For each email, I will categorize it as either 'useful', 'archive', 'unsubscribe', 
or suggest a label like 'real people', 'sales', 'purchases', 'immediate'. 
Based on the content above, should this email be marked as 'useful', archived, unsubscribed, 
or assigned a specific label? Provide the appropriate action.

Useful emails should be DEFINITELY WORTHY of reading.
Unsubscribed emails should be useless.
Labeled emails should represent label.

IF EMAIL IS DEFINED BY A LABEL, YOU MUST USE THAT LABEL.

You can only answer:
'useful',
'archive',
'unsubscribe',
'assess label [real people, sales, purchased, immediate, software version updates]'

DO NOT use synonyms like "purchases" instead of "purchased".
ONLY use answers from list above.
DO NOT add ANY text like "This email should be..."
ONLY use answers from list above.
DO NOT start with "The email should be..."
ONLY use answers from list above.
DO NOT add brackets around the label name.
DO NOT add square brackets around the label name!
ONLY use labels that in list above.
When you're using a label, START MESSAGE WITH "assess label".
DO NOT use multiple labels.
ONLY use single label from list above.
DO NOT summarize the email.
ONLY answer with predetermined answers.

DO NOT archive or unsubscribe emails from Have I Been Pwned <noreply@haveibeenpwned.com>.


Keep in mind that today is {today_date} and the time is {today_time}: 
Emails that are time sensitive and old are NOT useful.
Example: news, new posts from Patreon, Boosty or similar sites, sales, limited offers, checks, security alerts, etc."""

    messages = [
        {"role": "system",
         "content": prompt},
        {"role": "user",
         "content": "Assess the usefulness of the following email:{0}"}
    ]

    cut_to_total = tokens_count * token_multiplier

    cut_to = cut_to_total - len(str(messages))

    all_info_cut = get_equal_substrings_from_begging_center_end(all_info, cut_to)

    for message in messages:
        if "{0}" in message["content"]:
            message["content"] = message["content"].replace("{0}", all_info_cut)
            break
    return messages
