from datetime import datetime

from openai import OpenAI

from gmail import get_equal_substrings_from_begging_center_end


def openai_authenticate(openai_api_key):
    return OpenAI(api_key=openai_api_key)


def get_messages_gpt(openai_client, model, messages, max_tokens):
    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens
    )

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
ONLY use labels that in list above.
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
