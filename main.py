import os
import sys
import termcolor
import uuid

from openai import BadRequestError as openai_BadRequestError

from commands import JsonList

from secrets import OPENAI_API_KEY, GMAIL_SECRETS_FILE

from gpt import openai_authenticate, compose_gpt_message, get_messages_gpt
from gmail import gmail_authenticate, list_emails, get_email, get_email_headers, get_email_body, archive_email, \
    add_label_to_email, get_email_attachments_metadata, mark_email_as_useful, get_labels

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

useful_emails = JsonList("useful_emails.json")
newline = "\n"

if __name__ == '__main__':

    # args
    gpt3 = "gpt3" in sys.argv
    gpt4 = "gpt4" in sys.argv
    models = "models" in sys.argv

    max_results = 0
    for arg in sys.argv:
        if arg.startswith("max="):
            max_results = int(arg.split("=")[1])

    args_errors = []
    if not gpt3 and not gpt4 and not models:
        args_errors.append("Preffered model isn't chosen. "
                           "Add argument gpt3 or gpt4")
    if max_results == 0 and not models:
        args_errors.append("Count of mails to process isn't chosen."
                           "Add argument max=<count>")
    if args_errors:
        print(f"Usage: {sys.argv[0]} gpt3|gpt4|models max=<emails to process>")
        print(newline.join(args_errors))
        exit(1)

    # openai auth
    client = openai_authenticate(OPENAI_API_KEY)

    available_models = client.models

    if models:
        print(f"Available models:")
        
        for model in available_models.list():
            print(f"Model: {model}")
        exit(0)

    # gmail auth
    gmail_auth = gmail_authenticate(GMAIL_SECRETS_FILE, SCOPES)

    messages = list_emails(gmail_auth, max_results=max_results)

    len_messages = len(messages)

    if len_messages == 0 and max_results > 0:
        print("No messages to process")
        os.remove("useful_emails.json")
        exit(0)

    if gpt3:
        models_prioritized = [{"id": "gpt-3.5-turbo-16k", "tokens": 16385},
                              {"id": "gpt-3.5-turbo-instruct", "tokens": 4096},
                              {"id": "gpt-3.5-turbo", "tokens": 16385}]
        model_name = "GPT-3"
    elif gpt4:
        models_prioritized = [{"id": "gpt-4-1106-preview", "tokens": 128000},
                              {"id": "gpt-4", "tokens": 8192},
                              {"id": "gpt-4-vision-preview", "tokens": 128000}]
        model_name = "GPT-4"
    
    using_model = None
    tokens_count = None
    for prioritized_model in models_prioritized:
        found = False
        for model in available_models.list():
            if model.id == prioritized_model["id"]:
                print(f"Prioritizing model: {model}")
                using_model = model.id
                tokens_count = prioritized_model["tokens"]
                found = True
                break
        if found:
            break
        else:
            model_name = prioritized_model["id"]
            termcolor.cprint("CANNOT FIND MODEL {model_name}", "red")
    if using_model is None:
        print(f"Could not find prioritized model: {models_prioritized}")
        exit(1)

    labels = get_labels(gmail_auth, 'me')

    unsubscribe_from_emails = {}  # email_id, subject, from
    error_emails = {}  # email_id, subject, from, error

    for cnt, msg in enumerate(messages):
        try:
            email_id = msg['id']

            cnt_str = f"[{str((cnt + 1)).zfill(len(str(len_messages)))} / {len_messages}]"

            if email_id in useful_emails:
                print(f"{cnt_str} Skipping email {email_id} because it is marked as useful")
                continue

            email = get_email(gmail_auth, 'me', email_id)

            headers = get_email_headers(email)
            try:
                subject = headers['Subject']
            except KeyError:
                subject = headers['subject']
            subject_formatted = f"Subject: {subject}"

            try:
                from_ = headers['From']
            except KeyError:
                from_ = headers['from']

            from_formatted = f"From: {from_}"
            info_formatted = f"{from_formatted} {subject_formatted}"
            print(newline + f"{cnt_str} {info_formatted}")

            body = get_email_body(email)

            attachments = get_email_attachments_metadata(message=email)

            all_info = str(headers) + newline \
                + str(body) + newline \
                + str(attachments) + newline

            print(f"{len(all_info)=}")

            token_multiplier = 3.4

            messages = compose_gpt_message(tokens_count, token_multiplier, all_info)

            assessments = None
            retries = 10
            for i in range(retries + 1):
                try:
                    assessments = get_messages_gpt(openai_client=client,
                                                   model=using_model,
                                                   messages=messages,
                                                   max_tokens=100)
                    break
                except openai_BadRequestError:
                    if i == retries:
                        raise
                    token_multiplier -= 0.2
                    messages = compose_gpt_message(tokens_count, token_multiplier, all_info)

            assessment = assessments.choices[0].message.content.strip()

            if assessment.lower() == "useful":
                print(f"{model_name} Assessment of Email Usefulness:", assessment)
                termcolor.cprint("Marking email as useful", "green")
                mark_email_as_useful(useful_emails, email_id)
            elif assessment.lower() == "archive":
                print(f"{model_name} Assessment of Email Usefulness:", assessment)
                termcolor.cprint("Archiving email", "magenta")
                archive_email(gmail_auth, 'me', email_id)
            elif assessment.lower() == "unsubscribe":
                print(f"{model_name} Assessment of Email Usefulness:", assessment)
                unsubscribe_from_emails[email_id] = {"subject": subject_formatted,
                                                     "from": from_formatted}
            elif assessment.lower().startswith("assess label"):
                print(f"{model_name} Assessment of Email Usefulness:", assessment)
                label_name = " ".join(assessment.split(" ")[2:])
                if label_name.startswith("["):
                    label_name = label_name[1:]
                if label_name.endswith("]"):
                    label_name = label_name[:-1]
                try:
                    label_id = labels[label_name.lower()]
                    termcolor.cprint(f"Adding label {label_name} to email", "yellow")
                    add_label_to_email(gmail_auth, 'me', email_id, label_id)
                    archive_email(gmail_auth, 'me', email_id)
                except KeyError:
                    error = f"Label {label_name} is not recognized"
                    termcolor.cprint(error, "red")
                    error_emails[email_id] = {"subject": subject_formatted,
                                              "from": from_formatted,
                                              "error": error}
            else:
                print(f"{model_name} Assessment of Email Usefulness:", assessment)
                error = f"{model_name} Assessment of Email Usefulness is not recognized"
                termcolor.cprint(error, "red")
                error_emails[email_id] = {"subject": subject_formatted,
                                          "from": from_formatted,
                                          "error": error}
        except:
            error_emails[f"unknown {str(uuid.uuid4())}"] = {"subject": "unknown",
                                                            "from": "unknown",
                                                            "error": "Error processing email"}
            raise

    print()
    for email_id, email_info in unsubscribe_from_emails.items():
        from_ = email_info["from"]
        subject = email_info["subject"]
        termcolor.cprint(f"Unsubscribe from email {email_id} {newline}{from_}{newline}{subject}{newline}",
                         "red")
    print()
    for email_id, email_info in error_emails.items():
        from_ = email_info["from"]
        subject = email_info["subject"]
        error = email_info["error"]
        termcolor.cprint(f"Error in email {email_id} {newline}{from_}{newline}{subject}{newline}{error}{newline}",
                         "red")
