import os
import shutil
import sys
import termcolor

from commands import CLI, JsonDict

from secrets import GMAIL_SECRETS_FILE

from gmail import gmail_authenticate, list_emails, get_email, get_email_headers, archive_email, \
    add_label_to_email, get_email_attachments_metadata, get_labels, mark_as_spam

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

newline = "\n"

clean = "clean" in sys.argv or "-c" in sys.argv or "--clean" in sys.argv \
        or "clear" in sys.argv or "--clear" in sys.argv

if __name__ == '__main__':
    print("Getting emails...", end="\r")
    emails_by_sender = JsonDict("emails_by_sender.json")

    if len(emails_by_sender) == 0:
        clean = True

    if clean:
        emails_by_sender.clear()

    max_results = 500

    gmail_auth = gmail_authenticate(GMAIL_SECRETS_FILE, SCOPES)

    console_width = shutil.get_terminal_size().columns - 1

    if clean:
        messages = list_emails(gmail_auth, max_results=max_results)

        len_messages = len(messages)

        for cnt, msg in enumerate(messages):
            try:
                email_id = msg['id']

                cnt_str = f"[{str((cnt + 1)).zfill(len(str(len_messages)))} / {len_messages}]"

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

                try:
                    from_as_email = from_.split("<")[1].split(">")[0]
                except IndexError:
                    from_as_email = from_.split(">")[0]

                info_formatted = f"{from_formatted} {subject_formatted}"

                message = f"Getting info {cnt_str} {info_formatted}"
                message = message[:console_width - 1]
                print(" " * console_width, end="\r")
                print(message, end="\r")

                try:
                    emails_by_sender[from_as_email].append({"subject": subject,
                                                            "email_id": email_id,
                                                            "attachments": get_email_attachments_metadata(email)})
                except KeyError:
                    emails_by_sender[from_as_email] = [{"subject": subject,
                                                        "email_id": email_id,
                                                        "attachments": get_email_attachments_metadata(email)}]

            except:
                raise

        # remove emails with only one email
        emails_by_sender.string = {k: v for k, v in emails_by_sender.items() if len(v) > 1}
        emails_by_sender.save()

    # sort by number of emails
    emails_by_sender_sorted = {k: v for k, v in
                               sorted(emails_by_sender.items(), key=lambda item: len(item[1]), reverse=True)}

    len_str_emails_by_sender_sorted = len(str(len(emails_by_sender_sorted)))
    len_emails_by_sender_sorted = len(emails_by_sender_sorted)

    for cnt, emails in enumerate(emails_by_sender_sorted.items()):
        sender, emails = emails
        len_emails = len(emails)
        print(" " * console_width, end="\r")
        termcolor.cprint(
            f"Sender [{str(cnt+1).zfill(len_str_emails_by_sender_sorted)}/{len_emails_by_sender_sorted}]:"
            f" {len_emails} emails from"
            f" {sender}",
            "green")
        for email in emails:
            subject = email["subject"]
            email_id = email["email_id"]
            attachments = email["attachments"]
            if len(attachments) > 0:
                attachments = f"{newline}Attachments: {attachments}"
            else:
                attachments = ""
            print(f"{subject}{attachments}")
        print()
        while True:
            answer = CLI.get_int("What to do? \n"
                                 "1) Archive, \n"
                                 "2) Label, \n"
                                 "3) Mark as spam, \n"
                                 "4) Nothing:")
            if answer in [1, 2, 3, 4]:
                break
        if answer in [1, 2, 3]:
            labels = get_labels(gmail_auth, 'me')
            len_str_emails = len(str(len_emails))
            action = "Archiving" if answer == 1 else "Labeling" if answer == 2 else "Marking as spam"
            if answer == 2:
                enumerated_labels = list(enumerate(labels))
                for cnt_label, label in enumerated_labels:
                    print(f"{cnt_label} {label['id']}: {label['name']}")
                label_cnt = CLI.get_int("Label ID:")
                label = enumerated_labels[label_cnt]
                if not CLI.get_y_n(f"Label {label['name']}?"):
                    break
            for cnt_email, email in enumerate(emails):

                console_width = shutil.get_terminal_size().columns - 1
                message = f"{action} [{str(cnt_email).zfill(len_str_emails)}/{len_emails}] {email['subject']}"
                message = message[:console_width - 1]
                print(" " * console_width, end="\r")
                print(f"{message}", end="\r")

                email_id = email["email_id"]
                if answer == 2:
                    add_label_to_email(gmail_auth, 'me', email_id, label['id'])
                elif answer == 3:
                    mark_as_spam(gmail_auth, 'me', email_id)
                archive_email(gmail_auth, 'me', email_id)
        emails_by_sender.pop(sender)
        emails_by_sender.save()
