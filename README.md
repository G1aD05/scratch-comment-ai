# Scratch Comment AI
> [!NOTE]
> **AI Usage:** \
> AI was used for making variables have better names and formatting code. \
> There is no AI generated code in this project

> [!CAUTION]
> Using this repeatedly can get your main account banned if you don't have a VPN on. \
> Free VPN suggestions: \
> [ProtonVPN](https://protonvpn.com/) \
> [1.1.1.1](https://1.1.1.1/)

## Requirements
1. `scratchattach`
2. `prompt_toolkit`
3. `ollama`
4. `rich`
5. `tavily` This is optional, it just enables web search

## How To Use
1. Go to [ollama](https://ollama.com) to get a free API key.
2. Run `export OLLAMA_API_KEY=your api key` in the terminal.
3. In `main.py` change `BOT` to the **bot's username**, `PASSWORD` to the **bot's password**, `ID` to the **target project's ID** and `HOLDER` to your **own username**.
4. Install the requirements with this command `uv add scratchattach prompt_toolkit ollama rich` or `python3 -m pip install scratchattach prompt_toolkit ollama rich`
5. Create a file named `blacklist.json` and set the contents to `[]`
6. Then run!

## Tools the Bot Can Use
1. Web search (if Tavily is enabled)
2. Favoriting a project
3. Liking a project
4. Getting the time
5. Reading past comments
6. Follow a user

> [!NOTE]
> The bot can only use one tool per comment
