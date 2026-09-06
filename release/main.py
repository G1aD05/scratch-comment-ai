import html
import json
import os
import re
import sys
import time
import traceback
import warnings
import inspect
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

import scratchattach as sa
from ollama import Client
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from scratchattach import Comment, LoginDataWarning, Session
from scratchattach.utils.exceptions import CommentPostFailure

from prompt import generate_system_prompt


# Custom exception for an invalid mode
class InvalidMode(Exception):
    pass


TAVILY_ENABLED = False
try:
    from tavily import TavilyClient

    tavily_client = TavilyClient(os.environ.get("TAVILY_API_KEY"))
    TAVILY_ENABLED = True
except ImportError:
    print("\x1b[31mTavily isn't enabled")

# Auto-complete for console
commands = WordCompleter([
    "list",
    "gen",
    "reply",
    "help",
    "switch_project",
    "mode",
    "stop"
])

# Ignore scratchattach login data warning
warnings.filterwarnings('ignore', category=LoginDataWarning)

# Config for comment AI
with open("config.json", 'r') as file:
    config = json.load(file)
    args = sys.argv
    # Account info
    HOLDER: str = config["holder"]

    # Project ID, either set with config or an argument in the command line
    ID: int = config["id"]
    if len(args) > 1:
        ID = int(args[1])

    # Model and host, what model it uses and what is the provider
    MODEL: str = config["model"]
    HOST: str = config["host"]
    THINKING: bool = config["thinking"]

    # Account rotation
    ROTATE: bool = config["rotate"]

    # Accounts
    ACCOUNTS = config["accounts"]

    # This is for testing, set to 'dev' if you only want the holder to use the bot and get more detailed errors
    if config["mode"] in ['dev', 'release']:
        MODE: str = config["mode"]
    else:
        raise InvalidMode("An invalid mode for the script was set, please choose 'dev' or 'release'")

# Users that aren't allowed to use the bot
with open("blacklist.json", 'r') as file:
    BLACKLIST: list = json.load(file)

# Stored chats from people using '!new'
CHATS: dict = {}

# List of tools that return a message to the model with information
SPECIAL_TOOLS: list = ["read", "time", "search"]
# Shutdown event, when the user presses ctrl+c this is set and the entire script stops
SHUTDOWN: Event = Event()

# How the index of which account should be used next
ACCOUNT_USE_INDEX = 0

# Rich's text output
console = Console(
    force_terminal=True,
    color_system="truecolor"
)

# Replace the built-in print function with rich's log function
print = console.log

print(f"[cyan]Bot is active on {ID}[/]")

# Ollama client
client = Client(
    host=HOST,
    headers={
        "Authorization": "Bearer " + os.environ.get("OLLAMA_API_KEY")
    }
)

# Scratch user session and project
session = sa.login(ACCOUNTS[0]["username"], ACCOUNTS[0]["password"])
project = session.connect_project(ID)

# Set the bot's "What I'm Working On" to "Is the script online?"
user = session.connect_user(ACCOUNTS[0]["username"])
user.set_wiwo("Is the script online?\nYes\n\nGitHub:\nhttps://github.com/G1aD05/scratch-comment-ai")


# Account rotation
def rotate() -> Session:
    global user, session, ACCOUNT_USE_INDEX

    # Check if account rotation is enabled
    if not ROTATE:
        return session

    username = session.username
    check_user: Session = session

    if len(ACCOUNTS) <= ACCOUNT_USE_INDEX:
        ACCOUNT_USE_INDEX = 0

    for i, account in enumerate(ACCOUNTS):
        if account["username"] == username:
            continue  # Skip account

        if i <= ACCOUNT_USE_INDEX:
            print(i)
            continue  # Skip account that has been used

        check_user = sa.login(account["username"], account["password"])

        if check_user.mute_status:
            continue  # Skip account with mute status

        break  # Break the loop once the requirements are met

    # If requirements are not met it will just return the original session
    ACCOUNT_USE_INDEX += 1
    user = check_user.connect_user(check_user.username)
    return check_user


# Information for the AI
information = {
    "loves": lambda: project.loves,
    "favorites": lambda: project.favorites,
    "title": lambda: project.title,
    "views": lambda: project.views,
    "instructions": lambda: project.instructions,
    "notes": lambda: project.notes,
    "url": lambda: project.url,
    "author": lambda: project.author_name,
}

project_information = '\n'.join(
    f"{key}: {value()}"
    for key, value in information.items()
)

# System message, change if you want but keep the tools and the json message format
system_message = generate_system_prompt(HOLDER, TAVILY_ENABLED)


# Print the entire exception if dev mode is enabled
def print_exc(error: Exception = '', info: str = ''):
    if MODE == 'dev':
        traceback.print_exc()
        with open(f"debug_dump_{datetime.now().strftime('%S-%M-%H')}", 'w') as file:
            template = f"""{" DEBUG DUMP ".center(50, '=')}


{" GLOBAL VARIABLES ".center(50, '=')}
{json.dumps(globals(), indent=2, default=str)}


{" EXCEPTION ".center(50, '=')}
{traceback.format_exc()}


{" CALL STACK ".center(50, '=')}
{''.join(traceback.format_stack())}
"""
            file.write(template)

            print(f"[bold]DUMPED DEBUG INFORMATION AT {Path(file.name).resolve()}[/]")
    elif MODE == 'release':
        print(f"[red]{info}: {error}[/]")


# Check for a tool that the AI used
def check_tool(tool: str, original_message=None):
    if not tool:
        return None

    command_name = tool.split()[0]

    try:
        match command_name:
            case "follow":
                username = tool.split()[1]

                session.connect_user(username).follow()

                print(f"[bold green]Followed: {username}[/]")

            case "love":
                project_url = tool.split()[1]
                project_id = ''.join([num if num.isdigit() else '' for num in project_url])

                session.connect_project(int(project_id)).love()
                print(f"[bold green]Loved: {project_id}[/]")

            case "favorite":
                project_url = tool.split()[1]
                project_id = ''.join([num if num.isdigit() else '' for num in project_url])

                session.connect_project(int(project_id)).favorite()
                print(f"[bold green]Favorited: {project_id}[/]")

            case "read":
                comments = project.comments(limit=15, offset=1)
                comment_and_replies = []

                for comment in comments:
                    comment_and_replies.append(
                        {"comment": comment.content, "replies": [reply.content for reply in comment.replies(limit=2)]})

                response = ask(
                    f"You were asked to read the past comments, this was the original comment: {original_message}, but now you have the information that was asked for: {comment_and_replies} so respond naturally to the original comment with the new information")

                print(response)
                return response

            case "time":
                date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                response = ask(
                    f"You were asked to get the time and date, this was the original comment: {original_message}, but now you have the information that was asked for: {date_time} so respond naturally to the original comment with the new information")

                print(response)
                return response

            case "search":
                query = ' '.join(tool.split()[1:])
                search_result = tavily_client.search(query)

                response = ask(
                    f"You were asked/decided to search for information, this was the original comment: {original_message}, but now you have the information that was asked for: {search_result} so respond naturally to the original comment with the new information")

                print(response)
                return response

            case _:
                print("[red]Invalid command[/]")
    except Exception as error:
        user.set_bio(
            f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
        print_exc(info="Error has occurred during tool call", error=error)


# Send a list of messages to the AI
def chat(history: list):
    messages = [
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "system",
            "content": "[ Project Information ]"
                       "The following information is context about the project. Do not associate the user with any of it unless they explicitly ask about it."
                       f"{project_information}"
        },
        *history
    ]

    response = client.chat(
        MODEL,
        messages=messages,
        think=THINKING
    )

    return response["message"]["content"]


# Ask the AI to generate content
def ask(prompt):
    system_prompt = (
        f"{system_message}\n\n"
        "[ Project Information ]\n"
        "The following information is context about the project. "
        "Do not associate the user with any of it unless they explicitly ask about it.\n\n"
        f"{project_information}"
    )

    response = client.generate(
        MODEL,
        prompt,
        system=system_prompt,
        think=THINKING
    )

    return response["response"]


# Safely post a comment to scratch
def safe_post(message, parent_id, *, commentee_id=''):
    global session, project, user

    session = rotate()
    project = session.connect_project(ID)
    user = session.connect_user(session.username)

    if session.mute_status is not None:
        print("[red]Failed to post comment: has mute[/]")
        return None

    try:
        posted_comment: Comment = project.reply_comment(
            message[:499],
            parent_id=parent_id,
            commentee_id=commentee_id
        )

        print("[bold green]Posted comment[/]")
        return posted_comment

    except CommentPostFailure as error:
        user.set_bio(
            f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
        print_exc(info="Failed to post comment", error=error)
        return None


def scan_thread(comment_id: int, initiator_message: str):
    """
    Scan a chain of replies from a base comment

    :param comment_id:
    :param initiator_message:
    :return:
    """

    # Stop event
    stop_event = CHATS[comment_id]["stop_event"]

    # List of comments not to scan again
    scanned_comment_ids: list[int] = []

    # Base comment
    comment: sa.Comment = project.comment_by_id(comment_id)

    # Initiator message
    message = initiator_message.strip()
    filtered_message = re.sub(r"\[.*?]", '', message).strip()

    # Attempt to use special tools
    try:
        # Append the message to chat history
        CHATS[comment_id]["messages"] = [
            {
                "role": "user",
                "content": f"[{comment.author_name}]: {html.unescape(filtered_message)}"
            }
        ]

        # Get a response from the model
        response = chat(CHATS[comment_id]["messages"])
        print(response)

        response_dict = json.loads(response)

        # Check for special tool usage
        if response_dict["tool"] is not None and any(tool in response_dict["tool"] for tool in SPECIAL_TOOLS):
            content = check_tool(response_dict["tool"], comment.content)

            response_dict = json.loads(content)

            comment_response = safe_post(
                response_dict["message"],
                comment_id
            )

        else:
            check_tool(response_dict["tool"])

            comment_response = safe_post(
                response_dict["message"],
                comment_id
            )

        # Append the model's response to chat history
        CHATS[comment_id]["messages"].append({
            "role": "assistant",
            "content": response_dict["message"]
        })

        # Append the model's comment to the comment check blacklist
        scanned_comment_ids.append(comment_response.id)

        # Continuously run until someone says "!stop"
        while not stop_event.is_set():
            stop_event.wait(1)

            # Refresh the base comment to get new replies
            comment = project.comment_by_id(comment_id)
            # Get the replies for checking
            replies: list[sa.Comment] = comment.replies()

            for reply in replies:
                if reply.id in scanned_comment_ids or reply.author_name in BLACKLIST:
                    continue

                print("[dim]New reply[/]")

                scanned_comment_ids.append(reply.id)

                print("[dim]Added comment ID to blacklist[/]")
                print(f"[dim]Reply: {reply.content}[/]")

                if reply.content.startswith("!stop"):
                    stop_event.set()
                    del CHATS[comment_id]
                    print("[green]Stopped scan[/]")
                    break

                question = reply.content.strip()
                filtered_question = re.sub(r"\[.*?]", '', question).strip()

                CHATS[comment_id]["messages"].append({
                    "role": "user",
                    "content": f"[{reply.author_name}]: {filtered_question}"
                })

                # Get a response from the model
                response = chat(CHATS[comment_id]["messages"])
                print(response)

                response_dict = json.loads(response)

                # Check for special tool usage
                if response_dict["tool"] is not None and any(tool in response_dict["tool"] for tool in SPECIAL_TOOLS):
                    content = check_tool(response_dict["tool"], question)

                    response_dict = json.loads(content)

                    comment_response = safe_post(
                        response_dict["message"],
                        comment_id,
                        commentee_id=reply.author_id
                    )

                else:
                    check_tool(response_dict["tool"])

                    comment_response = safe_post(
                        response_dict["message"],
                        comment_id,
                        commentee_id=reply.author_id
                    )

                # Append the model's response to chat history
                CHATS[comment_id]["messages"].append({
                    "role": "assistant",
                    "content": response_dict["message"]
                })

                if comment_response:
                    scanned_comment_ids.append(comment_response.id)
                    print(f"[dim]Bot's comment: {comment_response.id}[/]")

                stop_event.wait(30)

    except Exception as error:
        user.set_bio(
            f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
        print_exc(info="Chat encountered an error", error=error)


# Check a scratch message for commands
def check_message(content: str):
    if content.startswith("!new"):
        if latest_comment.author_name not in BLACKLIST:
            print("[cyan]Created new chat[/]")

            initiator_message = content.replace(
                "!new",
                "",
                1
            ).strip()

            stop_event = Event()

            CHATS[latest_comment.id] = {"stop_event": stop_event}

            Thread(
                target=lambda: scan_thread(
                    latest_comment.id,
                    initiator_message
                ),
                daemon=True
            ).start()
        else:
            print(f"[cyan]User {latest_comment.author_name} is blacklisted[/]")

    elif content.startswith("?"):
        if latest_comment.author_name in BLACKLIST:
            return
        print("[dim]User asked a question[/]")

        question = html.unescape(content.replace('?', '', 1).strip())
        filtered_question = re.sub(r"\[.*?]", '', question).strip()
        print(f"[cyan]{filtered_question}[/]")

        response = ask(f"[{latest_comment.author_name}]: {filtered_question}")

        response_dict = json.loads(response)
        print(response)

        if response_dict["tool"] is not None and any(tool in response_dict["tool"] for tool in SPECIAL_TOOLS):
            content = check_tool(response_dict["tool"], latest_comment.content)

            safe_post(
                json.loads(content)["message"],
                latest_comment.id
            )

        else:
            check_tool(response_dict["tool"])

            safe_post(
                response_dict["message"],
                latest_comment.id
            )

    elif content.startswith("!help"):
        safe_post(
            "Commands: !new -- creates a new chat, !stop -- stops the chat, Tools: follow, love, favorite",
            latest_comment.id
        )

    elif content.startswith("!blacklist"):
        if latest_comment.author_name == HOLDER:
            return
        username = content.split()[1]
        BLACKLIST.append(username)
        safe_post(
            f"Successfully blacklisted {username}",
            latest_comment.id
        )
        with open("blacklist.json", 'w') as file:
            json.dump(BLACKLIST, file)

    elif content.startswith("!switch_project"):
        global ID, project

        # Separate the id form the URL
        url = content.split()[1]
        project_id = ''.join([num if num.isdigit() else '' for num in url])

        # Set project to new project
        ID = int(project_id)
        project = session.connect_project(ID)

        print(f"[bold green]Switched project to \"{project.title}\"[/]")


# Check a message sent into the console
def check_prompt(response: str):
    global project

    try:
        match response.split()[0]:
            case "help":
                print("Commands:\nblacklist --- blacklist a user from using the bot\n")

            case "blacklist":
                if latest_comment.author_name == HOLDER:
                    return
                username = response.split()[1]
                BLACKLIST.append(username)
                safe_post(
                    f"Successfully blacklisted {username}",
                    latest_comment.id
                )
                with open("blacklist.json", 'w') as file:
                    json.dump(BLACKLIST, file)

            case "switch_project":
                global ID

                # Separate the ID from the URL
                url = response.split()[1]
                project_id = ''.join([num if num.isdigit() else '' for num in url])

                # Set ID to the new id and project to ID
                ID = int(project_id)
                project = session.connect_project(ID)

                print(f"[bold green]Switched project to \"{project.title}\"[/]")

            case "list":
                comments = project.comments(limit=10)
                for comment in comments:
                    print(f"{(comment.author_name + ' ').ljust(25, '━')} ID: {comment.id!s} Content: {comment.content}")

            case "reply":
                arguments = response.split()
                comment_id = arguments[1]
                content = ' '.join(arguments[2:])

                print(content)

                safe_post(
                    content,
                    comment_id
                )
            case "gen":
                arguments = response.split()
                comment_id = arguments[1]

                comment = project.comment_by_id(comment_id)

                response = ask(f"[{comment.author_name}]: {comment.content}")

                safe_post(
                    json.loads(response)["message"],
                    arguments[1]
                )

            case "mode":
                print(f"Mode: [bold]{MODE}[/]")

            case "stop":
                SHUTDOWN.set()

            case _:
                print("[red]Unknown command[/]")

    except Exception as error:
        user.set_bio(
            f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
        print_exc(info="Failed to run command, error", error=error)


# The console input loop
def input_loop():
    prompt = PromptSession("> ", completer=commands)
    try:
        with patch_stdout(raw=True):
            while not SHUTDOWN.is_set():
                message = prompt.prompt()
                check_prompt(message)
    except KeyboardInterrupt:
        SHUTDOWN.set()
        sys.exit()


if __name__ == "__main__":
    blacklist: set[int] = set()

    if MODE == 'dev':
        with open("comment_data.json", 'r') as file:
            comment_data: list[dict[str, str]] = json.load(file)

    Thread(target=input_loop, daemon=True).start()

    try:
        while not SHUTDOWN.is_set():
            latest_comment = project.comments(limit=1)[0]
            content = latest_comment.content

            if latest_comment.id not in blacklist:
                if MODE == 'dev':
                    comment_data.append({
                        "author": latest_comment.author_name,
                        "content": content,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "date": datetime.now().strftime("%m/%d/%Y"),
                        "id": latest_comment.id,
                        "project": ID
                    })

                    with open("comment_data.json", 'w') as file:
                        json.dump(comment_data, file, indent=2)

                print("[dim]New comment[/]")

                try:
                    if MODE == 'dev' and latest_comment.author_name == HOLDER:
                        check_message(content)
                    elif MODE == 'release':
                        check_message(content)
                except Exception as error:
                    print_exc(info="Unknown exception occurred", error=error)

            blacklist.add(latest_comment.id)

            time.sleep(1)

    finally:
        print("[bold green]Shutting down...[/]")
        user.set_wiwo(
            "Is the script online? No\nGitHub URL for this project:\nhttps://github.com/G1aD05/scratch-comment-ai"
        )
        sys.exit()
