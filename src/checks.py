import json
import re
from threading import Event, Thread

from scratchattach import Session, Comment
from scratchattach import Project
from scratchattach import User

from datetime import datetime
import html

from ai import AIHandler
from utils import Utils
from scratch import Scratch

print_exc = Utils.print_exc
safe_post = Utils().safe_post


class Checks:
    def __init__(
            self,
            handler: AIHandler,
            MODE: str,
            blacklist: list,
            SPECIAL_TOOLS: list,
            session: Session,
            user: User,
            project: Project,
            scratch: Scratch,
            chats: dict,
            tavily=None
    ):
        self.handler = handler
        self.MODE = MODE
        self.tavily = tavily
        self.BLACKLIST = blacklist
        self.SPECIAL_TOOLS = SPECIAL_TOOLS
        self.session = session
        self.user = user
        self.project = project
        self.scratch = scratch
        self.CHATS = chats

    # Check for a tool that the AI used
    def check_tool(
            self,
            tool: str,
            session: Session,
            project: Project,
            information: str,
            user: User,
            original_message=None
    ):
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
                            {"comment": comment.content,
                             "replies": [reply.content for reply in comment.replies(limit=2)]})

                    response = self.handler.ask(
                        f"You were asked to read the past comments, this was the original comment: {original_message}, but now you have the information that was asked for: {comment_and_replies} so respond naturally to the original comment with the new information",
                        information
                    )

                    print(response)
                    return response

                case "time":
                    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    response = self.handler.ask(
                        f"You were asked to get the time and date, this was the original comment: {original_message}, but now you have the information that was asked for: {date_time} so respond naturally to the original comment with the new information",
                        information
                    )

                    print(response)
                    return response

                case "search":
                    query = ' '.join(tool.split()[1:])
                    search_result = self.tavily.search(query)

                    response = self.handler.ask(
                        f"You were asked/decided to search for information, this was the original comment: {original_message}, but now you have the information that was asked for: {search_result} so respond naturally to the original comment with the new information",
                        information
                    )

                    print(response)
                    return response

                case _:
                    print("[red]Invalid command[/]")
        except Exception as error:
            user.set_bio(
                f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
            print_exc(info="Error has occurred during tool call", error=error, MODE=self.MODE)

    # Check a scratch message for commands
    def check_message(
            self,
            content: str,
            comment: Comment,
            CHATS: list,
            information: str,
            user: User,
            project: Project,
            session: Session,
            HOLDER: str
    ):
        if content.startswith("!new"):
            if comment.author_name not in self.BLACKLIST:
                print("[cyan]Created new chat[/]")

                initiator_message = content.replace(
                    "!new",
                    "",
                    1
                ).strip()

                stop_event = Event()

                CHATS[comment.id] = {"stop_event": stop_event}

                Thread(
                    target=lambda: self.scratch.scan_thread(
                        comment.id,
                        initiator_message,
                        self.project,
                        self.CHATS,
                        information
                    ),
                    daemon=True
                ).start()
            else:
                print(f"[cyan]User {comment.author_name} is blacklisted[/]")

        elif content.startswith("?"):
            if comment.author_name in self.BLACKLIST:
                return
            print("[dim]User asked a question[/]")

            question = html.unescape(content.replace('?', '', 1).strip())
            filtered_question = re.sub(r"\[.*?]", '', question).strip()
            print(f"[cyan]{filtered_question}[/]")

            response = self.handler.ask(f"[{comment.author_name}]: {filtered_question}", information)

            response_dict = json.loads(response)
            print(response)

            if response_dict["tool"] is not None and any(tool in response_dict["tool"] for tool in self.SPECIAL_TOOLS):
                content = self.check_tool(response_dict["tool"], session, original_message=comment.content, information=information, user=user, project=project)

                safe_post(
                    json.loads(content)["message"],
                    comment.id,
                    session=self.session,
                    user=self.user,
                    project=self.project
                )

            else:
                self.check_tool(response_dict["tool"], session, information=information, user=user, project=project)

                safe_post(
                    response_dict["message"],
                    comment.id,
                    session=self.session,
                    user=self.user,
                    project=self.project
                )

        elif content.startswith("!blacklist"):
            if comment.author_name == HOLDER:
                return
            username = content.split()[1]
            self.BLACKLIST.append(username)
            safe_post(
                f"Successfully blacklisted {username}",
                comment.id,
                session=self.session,
                user=self.user,
                project=self.project
            )
            with open("blacklist.json", 'w') as file:
                json.dump(self.BLACKLIST, file)

        elif content.startswith("!switch_project"):
            url = content.split()[1]
            project_id = ''.join([num if num.isdigit() else '' for num in url])
            project = session.connect_project(int(project_id))
            print(f"[bold green]Switched project to \"{project.title}\"[/]")
