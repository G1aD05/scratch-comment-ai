import re
import html
import json

import scratchattach as sa
from scratchattach import Project, Session, User

from src.ai import AIHandler
from src.checks import Checks
from utils import Utils

print_exc = Utils.print_exc
safe_post = Utils().safe_post


class Scratch:
    def __init__(
            self,
            handler: AIHandler,
            checks: Checks,
            session: Session,
            project: Project,
            user: User,
            special_tools: list,
            blacklist: list,
            mode: str
    ):
        self.handler = handler
        self.checks = checks
        self.session = session
        self.project = project
        self.user = user
        self.SPECIAL_TOOLS = special_tools
        self.BLACKLIST = blacklist
        self.mode = mode

    def check_tool(self, tool, information: str, original_message=None):
        return self.checks.check_tool(
            tool,
            self.session,
            self.project,
            information,
            self.user,
            original_message=original_message
        )

    def scan_thread(self, comment_id: int, initiator_message: str, project: Project, CHATS: list, information: str):
        """
        Scan a chain of replies from a base comment

        :param information:
        :param CHATS:
        :param project:
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
            response = self.handler.chat(CHATS[comment_id]["messages"], information)
            print(response)

            response_dict = json.loads(response)

            # Check for special tool usage
            if response_dict["tool"] is not None and any(tool in response_dict["tool"] for tool in self.SPECIAL_TOOLS):
                content = self.check_tool(response_dict["tool"], information, original_message=comment.content)

                response_dict = json.loads(content)

                comment_response = safe_post(
                    response_dict["message"],
                    comment_id
                )

            else:
                self.check_tool(response_dict["tool"], information)

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
                    if reply.id in scanned_comment_ids or reply.author_name in self.BLACKLIST:
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
                    response = self.handler.chat(CHATS[comment_id]["messages"], information)
                    print(response)

                    response_dict = json.loads(response)

                    # Check for special tool usage
                    if response_dict["tool"] is not None and any(
                            tool in response_dict["tool"] for tool in self.SPECIAL_TOOLS):
                        content = self.check_tool(response_dict["tool"], information, original_message=question)

                        response_dict = json.loads(content)

                        comment_response = safe_post(
                            response_dict["message"],
                            comment_id,
                            commentee_id=reply.author_id,
                            session=self.session,
                            user=self.user,
                            project=self.project
                        )

                    else:
                        self.check_tool(response_dict["tool"], information)

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
            self.user.set_bio(
                f"This is the most recent error, you can use this to find out why the bot didn't respond:\n{error}")
            print_exc(info="Chat encountered an error", error=error, MODE=self.mode)
