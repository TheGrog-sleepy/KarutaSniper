import asyncio
import json
import os
import random
import re
import sys
from datetime import datetime
from os import listdir, get_terminal_size
from os.path import isfile, join

import discord
import pytesseract
import requests
from colorama import Fore, init
from PIL import Image

from lib import api
from lib.ocr import *

init(convert=True)

def first_run_setup():
    required_dirs = ["temp", "temp/char", "keywords"]
    for directory in required_dirs:
        os.makedirs(directory, exist_ok=True)
    
    if not os.path.exists("config.json"):
        default_config = {
            "token": "",
            "servers": [],
            "channels": [],
            "accuracy": 0.85,
            "blaccuracy": 0.7,
            "log_hits": True,
            "log_collection": True,
            "timestamp": True,
            "update_check": True,
            "autodrop": False,
            "autodropchannel": "",
            "dropdelay": 1820,
            "randmin": 1,
            "randmax": 2,
            "debug": False,
            "very_verbose": False,
            "check_print": True,
            "print_number": 1000,
            "event_settings": {
                "prioritize_watermelon": True
            },
            "blessing_settings": {
                "auto_drop_after_generosity": True,
                "evasion_cooldown_reset": True
            },
            "ocr_settings": {
                "tesseract_path": "",
                "custom_config": "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@&0123456789/:- ",
                "confidence_threshold": 70
            },
            "safety": {
                "max_actions_per_minute": 10,
                "random_delay_range": [0.5, 2.5],
                "typing_simulation": False
            }
        }
        with open("config.json", "w") as f:
            json.dump(default_config, f, indent=4)
        
        print(f"{Fore.GREEN}Created default config.json. Please fill in your details before running again.{Fore.RESET}")
        input("Press Enter to exit...")
        sys.exit(0)
    
    keyword_files = {
        "animes.txt": "# Add anime names here (one per line)\n# Example:\n# Attack on Titan\n# Jujutsu Kaisen",
        "characters.txt": "# Add character names here (one per line)\n# Example:\n# Eren Yeager\n# Gojo Satoru",
        "aniblacklist.txt": "# Add blacklisted anime here (one per line)",
        "charblacklist.txt": "# Add blacklisted characters here (one per line)"
    }
    
    for filename, content in keyword_files.items():
        path = os.path.join("keywords", filename)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

def check_requirements():
    try:
        import discord
        import pytesseract
        import PIL
    except ImportError as e:
        print(f"{Fore.RED}Missing required packages: {e}{Fore.RESET}")
        print(f"{Fore.CYAN}Please install requirements with: pip install -r requirements.txt{Fore.RESET}")
        input("Press Enter to exit...")
        sys.exit(1)

if not all(os.path.exists(f) for f in ["config.json", "keywords/animes.txt", "keywords/characters.txt"]):
    print(f"{Fore.YELLOW}Welcome to Karuta Sniper! Running first-time setup...{Fore.RESET}")
    first_run_setup()
check_requirements()

match = "(is dropping [3-4] cards!)|(I'm dropping [3-4] cards since this server is currently active!)|(special event drop!)"
path_to_ocr = "temp"
v = "v2.3.2"
if "v" in v:
    beta = False
    update_url = "https://raw.githubusercontent.com/NoMeansNowastaken/KarutaSniper/master/version.txt"
else:
    beta = True
    update_url = "https://raw.githubusercontent.com/NoMeansNowastaken/KarutaSniper/beta/version.txt"
with open("config.json") as f:
    config = json.load(f)

if os.name == 'nt':
    title = True
else:
    title = False

token = config["token"]
channels = config["channels"]
guilds = config["servers"]
accuracy = float(config["accuracy"])
blaccuracy = float(config["blaccuracy"])
loghits = config["log_hits"]
logcollection = config["log_collection"]
timestamp = config["timestamp"]
update = config["update_check"]
autodrop = config["autodrop"]
debug = config["debug"]
cprint = config["check_print"]
verbose = config["very_verbose"]
prioritize_watermelon = config.get("event_settings", {}).get("prioritize_watermelon", True)
if cprint:
    pn = int(config["print_number"])
if autodrop:
    autodropchannel = config["autodropchannel"]
    dropdelay = config["dropdelay"]
    randmin = int(config["randmin"])
    randmax = int(config["randmax"])

class Main(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.charblacklist = None
        self.aniblacklist = None
        self.animes = None
        self.chars = None
        self.messageid = None
        self.current_card = None
        self.ready = False
        self.timer = 0
        self.url = None
        self.missed = 0
        self.collected = 0
        self.cardnum = 0
        self.buttons = None
        self.watermelon_pos = None

    async def on_ready(self):
        if title:
            await asyncio.create_subprocess_shell("cls")
        else:
            await asyncio.create_subprocess_shell("clear")
        await asyncio.sleep(0.5)
        thing = f"""{Fore.LIGHTMAGENTA_EX}
 ____  __.                    __             _________      .__                     
|    |/ _|____ _______ __ ___/  |______     /   _____/ ____ |__|_____   ___________ 
|      < \__  \\_  __ \  |  \   __\__  \    \_____  \ /    \|  \____ \_/ __ \_  __ \\
|    |  \ / __ \|  | \/  |  /|  |  / __ \_  /        \   |  \  |  |_> >  ___/|  | \/
|____|__ (____  /__|  |____/ |__| (____  / /_______  /___|  /__|   __/ \___  >__|   
        \/    \/                       \/          \/     \/   |__|        \/       
"""
        if sys.gettrace() is None:
            for line in thing.split("\n"):
                print(line.center(get_terminal_size().columns))
            print(Fore.LIGHTMAGENTA_EX + "─" * get_terminal_size().columns)
        tprint(
            f"{Fore.BLUE}Logged in as {Fore.RED}{self.user.name}#{self.user.discriminator} {Fore.GREEN}({self.user.id}){Fore.RESET} "
        )
        latest_ver = update_check().strip()
        if latest_ver != v:
            tprint(
                f"{Fore.RED}You are on version {v}, while the latest version is {latest_ver}"
            )
        dprint(f"discord.py-self version {discord.__version__}")
        dprint(f"Tesseract version {pytesseract.get_tesseract_version()}")
        if beta:
            tprint(f"{Fore.RED}[!] You are on the beta branch, please report all actual issues to the github repo")
        await self.update_files()
        for guild in guilds:
            try:
                await self.get_guild(guild).subscribe(typing=True, activities=False, threads=False,
                                                      member_updates=False)
            except AttributeError:
                tprint(f"{Fore.RED}Error when subscribing to a server, maybe theres a server you aren't in")
        asyncio.get_event_loop().create_task(self.cooldown())
        asyncio.get_event_loop().create_task(self.filewatch("keywords\\animes.txt"))
        asyncio.get_event_loop().create_task(self.filewatch("keywords\\characters.txt"))
        asyncio.get_event_loop().create_task(
            self.filewatch("keywords\\aniblacklist.txt")
        )
        asyncio.get_event_loop().create_task(
            self.configwatch("config.json")
        )
        asyncio.get_event_loop().create_task(
            self.filewatch("keywords\\charblacklist.txt")
        )
        if autodrop:
            asyncio.get_event_loop().create_task(self.autodrop())
        self.ready = True

    async def on_message(self, message):
        cid = message.channel.id
        if (
                not self.ready
                or message.author.id != 646937666251915264
                or cid not in channels
        ):
            return

        if message.content.startswith(f"<@{str(self.user.id)}>, your ") and "blessing has activated!" in message.content:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            if "Evasion" in message.content:
                self.timer = 0
                dprint("Evasion blessing detected - resetting grab cooldown")
            elif "Generosity" in message.content and autodrop:
                self.timer = 0
                dprint("Generosity blessing detected - resetting drop cooldown")
                await self.get_channel(autodropchannel).send("kd")
                tprint(f"{Fore.LIGHTWHITE_EX}Auto Dropped Cards after blessing")
            return

        def mcheck(before, after):
            if before.id == message.id and not after.components[0].children[0].disabled:
                dprint("Message edit found")
                try:
                    self.buttons = after.components[0].children
                    return True
                except IndexError:
                    dprint(f"Fuck - {after.components}")
            else:
                return False

        def check(reaction0, user):
            return reaction0.message.id == message.id

        if re.search("A wishlisted card is dropping!", message.content):
            dprint("Whishlisted card detected")

        if self.timer == 0 and re.search(match, message.content):
            self.watermelon_pos = None
            with open("temp\\card.webp", "wb") as file:
                file.write(requests.get(message.attachments[0].url).content)
            
            is_watermelon_event = "special event drop" in message.content.lower()
            img = Image.open("temp\\card.webp")
            width, height = img.size
            
            if filelength("temp\\card.webp") == 836:
                self.cardnum = 3
                for a in range(3):
                    await get_card(
                        f"{path_to_ocr}\\card{a + 1}.png", "temp\\card.webp", a
                    )

                for a in range(3):
                    await get_top(
                        f"{path_to_ocr}\\card{a + 1}.png",
                        f"{path_to_ocr}\\char\\top{a + 1}.png"
                    )
                    await get_bottom(
                        f"{path_to_ocr}\\card{a + 1}.png",
                        f"{path_to_ocr}\\char\\bottom{a + 1}.png"
                    )
                    if cprint:
                        await get_print(
                            f"{path_to_ocr}\\card{a + 1}.png",
                            f"{path_to_ocr}\\char\\print{a + 1}.png"
                        )
            else:
                if width == 836 and height < 400:
                    self.cardnum = 4
                else:
                    self.cardnum = 5
                    self.watermelon_pos = 4
                    if height < 500:
                        self.watermelon_pos = 3

                for a in range(self.cardnum):
                    await get_card(
                        f"{path_to_ocr}\\card{a + 1}.png", "temp\\card.webp", a
                    )

                for a in range(self.cardnum):
                    await get_top(
                        f"{path_to_ocr}\\card{a + 1}.png",
                        f"{path_to_ocr}\\char\\top{a + 1}.png"
                    )
                    await get_bottom(
                        f"{path_to_ocr}\\card{a + 1}.png",
                        f"{path_to_ocr}\\char\\bottom{a + 1}.png"
                    )
                    if cprint:
                        await get_print(
                            f"{path_to_ocr}\\card{a + 1}.png",
                            f"{path_to_ocr}\\char\\print{a + 1}.png"
                        )

            onlyfiles = [
                ff for ff in listdir("temp\\char") if isfile(join("temp\\char", ff))
            ]
            charlist = []
            anilist = []
            printlist = []
            for img in onlyfiles:
                if "4" in img and self.cardnum < 4:
                    continue
                if "5" in img and self.cardnum < 5:
                    continue
                if "top" in img:
                    custom_config = r"--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@&0123456789/:- "
                    charlist.append(
                        pytesseract.image_to_string(
                            Image.open(
                                path_to_ocr
                                + "\\char\\top"
                                + re.sub(r"\D", "", img)
                                + ".png"
                            ),
                            lang="eng",
                            config=custom_config
                        )
                        .strip()
                        .replace("\n", " ")
                    )
                elif "bottom" in img:
                    custom_config = r"--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@&0123456789/:- "
                    anilist.append(
                        pytesseract.image_to_string(
                            Image.open(
                                path_to_ocr
                                + "\\char\\bottom"
                                + re.sub(r"\D", "", img)
                                + ".png"
                            ),
                            lang="eng",
                            config=custom_config
                        )
                        .strip()
                        .replace("\n", " ")
                    )
                elif cprint and "print" in img:
                    custom_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"
                    printlist.append(
                        pytesseract.image_to_string(
                            Image.open(path_to_ocr + f"\\char\\{img}"),
                            lang="eng",
                            config=custom_config
                        ).strip()
                    )
            vprint(f"Anilist: {anilist}")
            vprint(f"Charlist: {charlist}")
            for i, number in enumerate(printlist):
                try:
                    printlist[i] = int(re.sub(" \d$| ", "", number))
                except ValueError:
                    dprint(f"{Fore.RED}ValueError - current string: {number}")
                    printlist[i] = 9999999
            vprint(f"Printlist: {printlist}")

            def emoji(b):
                if self.watermelon_pos is not None and b == self.watermelon_pos:
                    return "🍉"
                match b:
                    case 0:
                        return "1️⃣"
                    case 1:
                        return "2️⃣"
                    case 2:
                        return "3️⃣"
                    case 3:
                        return "4️⃣"
                    case 4:
                        return "5️⃣"

            if self.watermelon_pos is not None and prioritize_watermelon:
                tprint(f"{Fore.GREEN}[{message.channel.name}] Found Watermelon Event - Prioritizing Grab{Fore.RESET}")
                self.url = message.attachments[0].url
                if loghits:
                    with open("log.txt", "a") as ff:
                        if timestamp:
                            ff.write(f"{current_time()} - Watermelon Event - {self.url}\n")
                        else:
                            ff.write(f"Watermelon Event - {self.url}\n")
                if isbutton(cid):
                    await self.wait_for("message_edit", check=mcheck)
                    await asyncio.sleep(random.uniform(0.55, 1.08))
                    await self.buttons[self.watermelon_pos].click()
                    await self.afterclick()
                else:
                    reaction = await self.wait_for("reaction_add", check=check)
                    await self.react_add(reaction, emoji(self.watermelon_pos))
                return
            elif self.watermelon_pos is not None:
                tprint(f"{Fore.YELLOW}[{message.channel.name}] Watermelon Event detected but skipping (disabled in config){Fore.RESET}")

            for i, character in enumerate(charlist):
                if (
                        api.isSomething(character, self.chars, accuracy)
                        and not api.isSomething(character, self.charblacklist, accuracy)
                        and not api.isSomething(anilist[i], self.aniblacklist, blaccuracy)
                ):
                    tprint(
                        f"{Fore.GREEN}[{message.channel.name}] Found Character: {Fore.MAGENTA}{character} {Fore.LIGHTMAGENTA_EX}from {Fore.LIGHTBLUE_EX}{anilist[i]}{Fore.RESET}"
                    )
                    self.url = message.attachments[0].url
                    if loghits:
                        with open("log.txt", "a") as ff:
                            if timestamp:
                                ff.write(f"{current_time()} - Character: {character} - {self.url}\n")
                            else:
                                ff.write(f"Character: {character} - {self.url}\n")
                    if isbutton(cid):
                        await self.wait_for("message_edit", check=mcheck)
                        await asyncio.sleep(random.uniform(0.55, 1.08))
                        await self.buttons[i].click()
                        await self.afterclick()
                    else:
                        reaction = await self.wait_for("reaction_add", check=check)
                        await self.react_add(reaction, emoji(i))
            for i, anime in enumerate(anilist):
                if (
                        api.isSomething(anime, self.animes, accuracy)
                        and not api.isSomething(charlist[i], self.charblacklist, accuracy)
                        and not api.isSomething(anime, self.aniblacklist, blaccuracy)
                ):
                    tprint(
                        f"{Fore.GREEN}[{message.channel.name}] Found Anime: {Fore.MAGENTA}{anime} {Fore.LIGHTMAGENTA_EX}| {Fore.LIGHTBLUE_EX}{charlist[i]}{Fore.RESET}"
                    )
                    self.url = message.attachments[0].url
                    if loghits:
                        with open("log.txt", "a") as ff:
                            if timestamp:
                                ff.write(f"{current_time()} - Anime: {anime} - {self.url}\n")
                            else:
                                ff.write(f"Anime: {anime} - {self.url}\n")
                    if isbutton(cid):
                        await self.wait_for("message_edit", check=mcheck)
                        await asyncio.sleep(random.uniform(0.55, 1.08))
                        await self.buttons[i].click()
                        await self.afterclick()
                    else:
                        reaction = await self.wait_for("reaction_add", check=check)
                        await self.react_add(reaction, emoji(i))
            if cprint:
                for i, prin in enumerate(printlist):
                    if (
                            prin <= pn
                            and anilist[i] not in self.aniblacklist
                            and charlist[i] not in self.charblacklist
                    ):
                        tprint(
                            f"{Fore.GREEN}[{message.channel.name}] Found Print # {Fore.MAGENTA}{prin}{Fore.RESET}"
                        )
                        self.url = re.sub(r"\?.*", "", message.attachments[0].url)
                        if loghits:
                            with open("log.txt", "a") as ff:
                                if timestamp:
                                    ff.write(f"{current_time()} - Print Number {prin} - {self.url}\n")
                                else:
                                    ff.write(f"Print Number {prin} - {self.url}\n")
                        if isbutton(cid):
                            await self.wait_for("message_edit", check=mcheck)
                            await asyncio.sleep(random.uniform(0.55, 1.08))
                            await self.buttons[i].click()
                            await self.afterclick()
                        else:
                            reaction = await self.wait_for("reaction_add", check=check)
                            await self.react_add(reaction, emoji(i))
        elif re.search(
                f"<@{str(self.user.id)}> took the \*\*.*\*\* card `.*`!|<@{str(self.user.id)}> fought off .* and took the \*\*.*\*\* card `.*`!",
                message.content
        ):
            a = re.search(
                f"<@{str(self.user.id)}>.*took the \*\*(.*)\*\* card `(.*)`!",
                message.content
            )
            self.timer += 540
            self.missed -= 1
            self.collected += 1
            tprint(
                f"{Fore.BLUE}[{message.channel.name}] Obtained Card: {Fore.LIGHTMAGENTA_EX}{a.group(1)}{Fore.RESET}"
            )
            if logcollection:
                with open("log.txt", "a") as ff:
                    if timestamp:
                        ff.write(f"{current_time()} - Card: {a.group(1)} - {self.url}\n")
                    else:
                        ff.write(f"Card: {a.group(1)} - {self.url}\n")

    async def react_add(self, reaction, emoji):
        reaction, _ = reaction
        try:
            dprint(f"{Fore.BLUE}Attempting to react")
            await asyncio.sleep(random.uniform(0.55, 1.08))
            await reaction.message.add_reaction(emoji)
        except discord.errors.Forbidden as oopsie:
            dprint(f"{Fore.RED}Fuck:\n{oopsie}")
            return
        self.timer += 60
        self.missed += 1
        dprint(f"{Fore.BLUE}Reacted with {emoji} successfully{Fore.RESET}")

    async def cooldown(self):
        while True:
            await asyncio.sleep(1)
            if self.timer > 0:
                self.timer -= 1
                if title:
                    await asyncio.create_subprocess_shell(
                        f"title Karuta Sniper {v} - Collected {self.collected} cards - Missed {self.missed} cards - On cooldown for {self.timer} seconds"
                    )
            elif title:
                await asyncio.create_subprocess_shell(
                    f"title Karuta Sniper {v} - Collected {self.collected} cards - Missed {self.missed} cards - Ready"
                )

    async def update_files(self):
        with open("keywords\\characters.txt") as ff:
            self.chars = ff.read().splitlines()

        with open("keywords\\animes.txt") as ff:
            self.animes = ff.read().splitlines()

        with open("keywords\\aniblacklist.txt") as ff:
            self.aniblacklist = ff.read().splitlines()

        with open("keywords\\charblacklist.txt") as ff:
            self.charblacklist = ff.read().splitlines()
        tprint(
            f"{Fore.MAGENTA}Loaded {len(self.animes)} animes, {len(self.aniblacklist)} blacklisted animes, {len(self.chars)} characters, {len(self.charblacklist)} blacklisted characters")

    async def filewatch(self, path):
        bruh = api.FileWatch(path)
        dprint(f"Filewatch activated for {path}")
        while True:
            await asyncio.sleep(2)
            if bruh.watch():
                await self.update_files()

    async def configwatch(self, path):
        bruh = api.FileWatch(path)
        while True:
            await asyncio.sleep(1)
            if bruh.watch():
                with open("config.json") as ff:
                    config = json.load(ff)
                    global accuracy, prioritize_watermelon
                    accuracy = float(config["accuracy"])
                    prioritize_watermelon = config.get("event_settings", {}).get("prioritize_watermelon", True)

    async def autodrop(self):
        channel = self.get_channel(autodropchannel)
        while True:
            await asyncio.sleep(dropdelay + random.randint(randmin, randmax))
            if self.timer != 0:
                await asyncio.sleep(self.timer)
            async with channel.typing():
                await asyncio.sleep(random.uniform(0.2, 1))
            await channel.send("kd")
            tprint(f"{Fore.LIGHTWHITE_EX}Auto Dropped Cards")

    async def afterclick(self):
        dprint(f"Clicked on Button")
        self.timer += 60
        self.missed += 1

def current_time():
    return datetime.now().strftime("%H:%M:%S")

def isbutton(data):
    if data in [648044573536550922, 776520559621570621, 858004885809922078, 857978372688445481]:
        return True
    else:
        return False

def tprint(message):
    if timestamp:
        print(f"{Fore.LIGHTBLUE_EX}{current_time()} | {Fore.RESET}{message}")
    else:
        print(message)

def dprint(message):
    if debug:
        tprint(f"{Fore.LIGHTRED_EX}Debug{Fore.BLUE} - {message}")

def vprint(message):
    if verbose:
        tprint(f"{Fore.CYAN}{message}{Fore.WHITE}")

def update_check():
    return requests.get(url=update_url).text

if token == "":
    inp = input(f"{Fore.RED}No token found, would you like to find tokens from your pc? (y/n): {Fore.RESET}")
    if inp == "y":
        token = api.get_tokens(False)
        input("Press any key to exit...")

client = Main(guild_subscriptions=False)
tprint(f"{Fore.GREEN}Starting Bot{Fore.RESET}")
try:
    client.run(token)
except KeyboardInterrupt:
    tprint(f"{Fore.RED}Ctrl-C detected\nExiting...{Fore.RESET}")
    client.close()
    exit()
