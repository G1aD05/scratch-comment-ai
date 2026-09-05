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

To install all of these run `uv add -r requirements.txt` or `python3 -m pip install -r requirements.txt`

## How To Use
Clone the repository using `git clone https://github.com/G1aD05/scratch-comment-ai.git`. \
Then go to the `release` directory and change the config settings in `config.json`.

### Enabling Ollama cloud
Go to Ollama's [settings](https://ollama.com/settings/keys) and click `Add API Key` copy the key and run this command `export OLLAMA_API_KEY=ollama api key` \
Then in config change `host` to `https://ollama.com/` \
\
If you do not want to enable cloud usage then go to `config.json` and change `host` to `http://localhost:11434` or whatever server you want \
You can also use local IP addresses like `http://192.168.1.7:11434`

### Enabling Web Search
First you need to install the package so run `uv add tavily` or `python3 -m pip install tavily`

Go to [Tavily](https://app.tavily.com/home) and look for `API Keys`, once you have found it click the `+` button, name the key and click `Create` \
Copy the key and run this command `export TAVILY_API_KEY=tavily api key` \
\
Web search is completely optional, but without it the bot cannot search information. \
Tavily does have a free plan so you don't have to pay for this feature.

## Tools the Bot Can Use
1. Web search (if Tavily is enabled)
2. Favoriting a project
3. Liking a project
4. Getting the time
5. Reading past comments
6. Follow a user

> [!NOTE]
> The bot can only use one tool per comment

## Commands for the Console
1. `gen <comment id>` gets the AI to generate a response for that comment then posts it.
2. `reply <comment id> <content>` allows you to override the bot and reply to someone's comment as the bot.
3. `list` lists the last 15 comments.
4. `mode` prints the mode type, **dev** or **release**.
5. `switch_project <project id>` switches the project the bot monitors.
6. `stop` stops the bot.
7. `help` prints a list of commands.

## How to Use Account Rotation
Go to `config.json` and add as many accounts as you want to the `accounts` list \
Format it like this:
```json
accounts: [
  {
    "username": "bot username",
    "password": "bot password"
  }
]
```

Then find `rotate` and set it to `true`

