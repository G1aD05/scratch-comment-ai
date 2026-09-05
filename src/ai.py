from ollama import Client
import os


class AIHandler:
    def __init__(
            self,
            MODEL: str,
            THINKING: bool,
            HOST: str,
            SYS_MSG: str
    ):
        self.client = Client(
            HOST,
            headers={
                "Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"
            }
        )

        self.MODEL = MODEL
        self.THINKING = THINKING
        self.SYS_MSG = SYS_MSG

    # Send a list of messages to the AI
    def chat(
        self,
        history: list,
        information: str
    ):
        messages = [
            {
                "role": "system",
                "content": self.SYS_MSG
            },
            {
                "role": "system",
                "content": "[ Project Information ]"
                           "The following information is context about the project. Do not associate the user with any of it unless they explicitly ask about it."
                           f"{information}"
            },
            *history
        ]

        response = self.client.chat(
            self.MODEL,
            messages=messages,
            think=self.THINKING
        )

        return response["message"]["content"]

    # Ask the AI to generate content
    def ask(
        self,
        prompt: str,
        information: str
    ):
        SYS_PROMPT = (
            f"{self.SYS_MSG}\n\n"
            "[ Project Information ]\n"
            "The following information is context about the project. "
            "Do not associate the user with any of it unless they explicitly ask about it.\n\n"
            f"{information}"
        )

        response = self.client.generate(
            self.MODEL,
            prompt,
            system=SYS_PROMPT,
            think=self.THINKING
        )

        return response["response"]
