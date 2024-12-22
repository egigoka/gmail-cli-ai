import shutil
import sys
import termcolor

from commands import CLI, JsonDict

from secrets import GMAIL_SECRETS_FILE

from gmail import gmail_authenticate, list_emails, get_email, get_email_headers, archive_email, \
    add_label_to_email, get_email_attachments_metadata, get_labels, mark_as_spam

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

accounts = JsonDict("accounts.json")

auths = {}  # address: auth

newline = "\n"

clean = "clean" in sys.argv or "-c" in sys.argv or "--clean" in sys.argv \
        or "clear" in sys.argv or "--clear" in sys.argv

def print_accounts():
    for account_, _ in accounts.items():
        print(account_)
    

if __name__ == '__main__':

    while True:
        print("Available accounts:")
        print_accounts()

        print()

        print("Actions: ")
        print("1 - add account")
        print("2 - remove account")
        print("c - continue")
        
        print()

        action = input("Action: ")
        if action == "c":
            break
        elif action == "1":
            account_name = input("Account name: ")
            token_file = input("Token file: ")
            accounts[account_name] = token_file
            accounts.save()
        elif action == "2":
            account_name = input("Account name: ")
            try:
                accounts.pop(account_name)
            except KeyError:
                print("Incorrect account name.")
        else:
            print("Incorrect command")
        print()

    print("Getting emails...", end="\r")
    emails_by_sender = JsonDict("emails_by_sender.json")

    if len(emails_by_sender) == 0:
        clean = True

    if clean:
        emails_by_sender.clear()

    max_results = 500

    for account_name, token_file in accounts.items():
        print()
        print(f"Authenticating {account_name}...")
        auths[account_name] = gmail_authenticate(GMAIL_SECRETS_FILE, SCOPES, token_file)

    console_width = shutil.get_terminal_size().columns - 1

    for account, gmail_auth in auths.items():
        auths[account] = gmail_authenticate(GMAIL_SECRETS_FILE, SCOPES, account)

    if clean:
        accounts_len = len(auths)
        account_cnt = 0
        for account_name, gmail_auth in auths.items():
            account_cnt += 1
            messages = list_emails(gmail_auth, max_results=max_results)

            len_messages = len(messages)

            for cnt, msg in enumerate(messages):
                try:
                    email_id = msg['id']

                    cnt_str = f"[{account_cnt}/{accounts_len}] [{str((cnt + 1)).zfill(len(str(len_messages)))} / {len_messages}]"

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

                    info_formatted = f"{account_name} {from_formatted} {subject_formatted}"

                    message = f"Getting info {cnt_str} {info_formatted}"
                    message = message[:console_width - 1]
                    print(" " * console_width, end="\r")
                    print(message, end="\r")

                    try:
                        emails_by_sender[from_as_email].append({"subject": subject,
                                                                "email_id": email_id,
                                                                "attachments": get_email_attachments_metadata(email),
                                                                "account": account_name})
                    except KeyError:
                        emails_by_sender[from_as_email] = [{"subject": subject,
                                                            "email_id": email_id,
                                                            "attachments": get_email_attachments_metadata(email),
                                                            "account": account_name}]

                except Exception:
                    raise

        # remove emails with only one email
        # emails_by_sender.string = {k: v for k, v in emails_by_sender.items() if len(v) > 1}
        # emails_by_sender.save()

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
                                 "2) Mark as spam, \n"
                                 "3) Nothing:")
            if answer in [1, 2, 3]:
                break
        if answer in [1, 2]:
            len_str_emails = len(str(len_emails))
            action = "Archiving" if answer == 1 else "Marking as spam"
            label = None
            for cnt_email, email in enumerate(emails):
                gmail_auth = auths[email["account"]]

                console_width = shutil.get_terminal_size().columns - 1
                message = f"{action} [{str(cnt_email).zfill(len_str_emails)}/{len_emails}] {email['subject']}"
                message = message[:console_width - 1]
                print(" " * console_width, end="\r")
                print(f"{message}", end="\r")

                email_id = email["email_id"]
                if answer == 2:
                    mark_as_spam(gmail_auth, 'me', email_id)
                archive_email(gmail_auth, 'me', email_id)
        emails_by_sender.pop(sender)
        emails_by_sender.save()

    emails_by_sender.clear()
    emails_by_sender.save()
