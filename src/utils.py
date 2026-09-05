import traceback

from scratchattach import Comment
from scratchattach.utils.exceptions import CommentPostFailure


class Utils:
    # Print the entire exception if dev mode is enabled
    @staticmethod
    def print_exc(MODE: str, error: Exception = '', info: str = ''):
        if MODE == 'dev':
            traceback.print_exc()
        elif MODE == 'release':
            print(f"[red]{info}: {error}[/]")

    # Safely post a comment to scratch
    def safe_post(self, message, parent_id, *, commentee_id='', session, project, user):
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
            self.print_exc(info="Failed to post comment", error=error)
            return None
