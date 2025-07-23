import asyncio
import json
import os
import random
import re
import sys
import io
import traceback
import webbrowser
from datetime import datetime
from os import listdir, get_terminal_size
from os.path import isfile, join
from typing import Optional, Tuple, List, Dict, Any

import discord
import pytesseract
import requests
from colorama import Fore, init
from PIL import Image, ImageGrab, UnidentifiedImageError

# Initialize colorama
init(convert=True)

# ======================
# ERROR HANDLER CLASS
# ======================
class ErrorHandler:
    @staticmethod
    async def handle(error: Exception, context: str = "", critical: bool = False) -> None:
        """Centralized error handling with logging and optional webhook notification"""
        error_msg = f"{Fore.RED}ERROR [{context}]: {str(error)}{Fore.RESET}"
        print(error_msg)
        
        if debug:
            traceback.print_exc()
        
        if critical and webhook_url:
            await ErrorHandler._send_error_webhook(error, context)
    
    @staticmethod
    async def _send_error_webhook(error: Exception, context: str) -> None:
        """Send error notifications to webhook"""
        try:
            embed = {
                "title": "⚠️ Bot Error Occurred",
                "description": f"**Context**: {context}\n```{str(error)[:1000]}```",
                "color": 0xff0000,
                "timestamp": datetime.utcnow().isoformat()
            }
            requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        except Exception as e:
            print(f"{Fore.RED}Failed to send error webhook: {e}{Fore.RESET}")

# ======================
# CONFIGURATION LOADING
# ======================
def load_config() -> Dict[str, Any]:
    """Load and validate configuration with error handling"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to load config: {str(e)}")

    def get_config(key: str, default: Any = None, required: bool = False) -> Any:
        """Helper to safely get config values with validation"""
        try:
            value = config.get(key, default)
            if value is None and required:
                raise ValueError(f"Missing required config key: {key}")
            return value
        except KeyError:
            if required:
                raise ValueError(f"Missing required config key: {key}")
            return default

    # Validate and convert config values
    try:
        return {
            "token": get_config("token", required=True),
            "channels": get_config("channels", required=True),
            "guilds": get_config("servers", required=True),
            "accuracy": float(get_config("accuracy", "1.0")),
            "blaccuracy": float(get_config("blaccuracy", "0.7")),
            "log_hits": bool(get_config("log_hits", False)),
            "log_collection": bool(get_config("log_collection", False)),
            "timestamp": bool(get_config("timestamp", True)),
            "update_check": bool(get_config("update_check", True)),
            "autodrop": bool(get_config("autodrop", False)),
            "autodropchannel": get_config("autodropchannel") if get_config("autodrop", False) else None,
            "dropdelay": int(get_config("dropdelay", "1820")) if get_config("autodrop", False) else None,
            "randmin": int(get_config("randmin", "1")) if get_config("autodrop", False) else None,
            "randmax": int(get_config("randmax", "2")) if get_config("autodrop", False) else None,
            "debug": bool(get_config("debug", False)),
            "very_verbose": bool(get_config("very_verbose", False)),
            "check_print": bool(get_config("check_print", False)),
            "print_number": int(get_config("print_number", "1000")) if get_config("check_print", False) else None,
            "autofarm": bool(get_config("autofarm", False)),
            "resourcechannel": get_config("resourcechannel") if get_config("autofarm", False) else None,
            "webhook_url": get_config("webhook_url", "")
        }
    except ValueError as e:
        raise RuntimeError(f"Invalid config value: {str(e)}")

# ======================
# CONSTANTS & CONFIG
# ======================
try:
    # Constants
    MATCH_PATTERN = "(is dropping [3-4] cards!)|(I'm dropping [3-4] cards since this server is currently active!)"
    OCR_PATH = "temp"
    VERSION = "v2.3.2"
    UPDATE_URL = "https://raw.githubusercontent.com/TheGrog-sleepy/thegoatster/master/version.txt"
    REPO_URL = "https://github.com/TheGrog-sleepy/thegoatster"
    
    # Load configuration
    config = load_config()
    
    # Assign config values
    token = config["token"]
    channels = config["channels"]
    guilds = config["guilds"]
    accuracy = config["accuracy"]
    blaccuracy = config["blaccuracy"]
    loghits = config["log_hits"]
    logcollection = config["log_collection"]
    timestamp = config["timestamp"]
    update_check_enabled = config["update_check"]
    autodrop = config["autodrop"]
    debug = config["debug"]
    cprint = config["check_print"]
    autofarm = config["autofarm"]
    verbose = config["very_verbose"]
    webhook_url = config["webhook_url"]
    
    if autofarm:
        resourcechannel = config["resourcechannel"]
    if cprint:
        pn = config["print_number"]
    if autodrop:
        autodropchannel = config["autodropchannel"]
        dropdelay = config["dropdelay"]
        randmin = config["randmin"]
        randmax = config["randmax"]

except Exception as e:
    asyncio.run(ErrorHandler.handle(e, "Initialization", critical=True))
    sys.exit(1)

# ======================
# UTILITY FUNCTIONS
# ======================
def current_time() -> str:
    """Get current time in HH:MM:SS format"""
    return datetime.now().strftime("%H:%M:%S")

def isbutton(channel_id: int) -> bool:
    """Check if channel uses buttons instead of reactions"""
    return channel_id in [648044573536550922, 776520559621570621, 858004885809922078, 857978372688445481]

def tprint(message: str) -> None:
    """Print message with optional timestamp"""
    prefix = f"{Fore.LIGHTBLUE_EX}{current_time()} | {Fore.RESET}" if timestamp else ""
    print(f"{prefix}{message}")

def dprint(message: str) -> None:
    """Debug print (only when debug is enabled)"""
    if debug:
        tprint(f"{Fore.LIGHTRED_EX}Debug{Fore.BLUE} - {message}")

def vprint(message: str) -> None:
    """Verbose print (only when very_verbose is enabled)"""
    if verbose:
        tprint(f"{Fore.CYAN}{message}{Fore.WHITE}")

def filelength(filepath: str) -> int:
    """Get file size in bytes"""
    return os.path.getsize(filepath)

async def check_for_updates() -> bool:
    """Check for updates and open browser if available"""
    try:
        response = requests.get(UPDATE_URL, timeout=10)
        response.raise_for_status()
        latest_version = response.text.strip()
        
        if latest_version != VERSION:
            tprint(f"{Fore.RED}Update available! Current: {VERSION} | Latest: {latest_version}")
            tprint(f"{Fore.CYAN}Opening update page...{Fore.RESET}")
            webbrowser.open(REPO_URL)
            return True
        return False
    except Exception as e:
        await ErrorHandler.handle(e, "Update check")
        return False

# ======================
# IMAGE PROCESSING
# ======================
async def get_card(output_path: str, input_path: str, index: int) -> None:
    """Extract individual card from multi-card image"""
    try:
        with Image.open(input_path) as img:
            width, height = img.size
            card_height = height // (4 if filelength(input_path) > 836 else 3)
            top = index * card_height
            card = img.crop((0, top, width, top + card_height))
            card.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Failed to extract card {index}: {str(e)}")

async def get_top(output_path: str, input_path: str) -> None:
    """Extract top text (character name) from card"""
    try:
        with Image.open(input_path) as img:
            width, height = img.size
            # Crop top portion where character name appears
            top_text = img.crop((0, 0, width, height // 3))
            top_text.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Failed to extract top text: {str(e)}")

async def get_bottom(output_path: str, input_path: str) -> None:
    """Extract bottom text (anime name) from card"""
    try:
        with Image.open(input_path) as img:
            width, height = img.size
            # Crop bottom portion where anime name appears
            bottom_text = img.crop((0, height * 2 // 3, width, height))
            bottom_text.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Failed to extract bottom text: {str(e)}")

async def get_print(output_path: str, input_path: str) -> None:
    """Extract print number from card"""
    try:
        with Image.open(input_path) as img:
            width, height = img.size
            # Crop area where print number appears
            print_area = img.crop((width - 100, height - 50, width - 20, height - 20))
            print_area.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Failed to extract print number: {str(e)}")

async def capture_screenshot() -> Optional[bytes]:
    """Capture screenshot of the current screen"""
    try:
        screenshot = ImageGrab.grab()
        with io.BytesIO() as buffer:
            screenshot.save(buffer, format='PNG')
            return buffer.getvalue()
    except Exception as e:
        await ErrorHandler.handle(e, "Screenshot capture")
        return None

# ======================
# WEBHOOK FUNCTIONS
# ======================
async def send_webhook(card_name: str, quality: str, image_bytes: Optional[bytes] = None) -> bool:
    """Send card grab notification to Discord webhook"""
    if not webhook_url:
        return False
    
    try:
        embed = {
            "title": "🎴 Card Obtained!",
            "description": f"**{card_name}**\nQuality: {quality}",
            "color": 0x00ff00,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": f"Karuta Sniper {VERSION}"}
        }
        
        files = {}
        if image_bytes:
            files["file"] = ("card.png", image_bytes, "image/png")
        
        try:
            if files:
                response = requests.post(
                    webhook_url,
                    files=files,
                    data={"payload_json": json.dumps({"embeds": [embed]})},
                    timeout=10
                )
            else:
                response = requests.post(
                    webhook_url,
                    json={"embeds": [embed]},
                    timeout=10
                )
            
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            await ErrorHandler.handle(e, "Webhook request")
            return False
            
    except Exception as e:
        await ErrorHandler.handle(e, "Webhook preparation")
        return False

# ======================
# MAIN BOT CLASS
# ======================
class KarutaSniper(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.charblacklist: List[str] = []
        self.aniblacklist: List[str] = []
        self.animes: List[str] = []
        self.chars: List[str] = []
        self.ready: bool = False
        self.timer: int = 0
        self.url: Optional[str] = None
        self.missed: int = 0
        self.collected: int = 0
        self.cardnum: int = 0
        self.buttons: Optional[List[discord.Button]] = None
        
        if autofarm:
            self.button: Optional[discord.Button] = None

    async def on_ready(self) -> None:
        """Called when bot is logged in and ready"""
        try:
            # Clear console
            os.system("cls" if os.name == 'nt' else "clear")
            await asyncio.sleep(0.5)
            
            # Print banner
            banner = f"""{Fore.LIGHTMAGENTA_EX}
 ____  __.                    __             _________      .__                     
|    |/ _|____ _______ __ ___/  |______     /   _____/ ____ |__|_____   ___________ 
|      < \__  \\_  __ \  |  \   __\__  \    \_____  \ /    \|  \____ \_/ __ \_  __ \\
|    |  \ / __ \|  | \/  |  /|  |  / __ \_  /        \   |  \  |  |_> >  ___/|  | \/
|____|__ (____  /__|  |____/ |__| (____  / /_______  /___|  /__|   __/ \___  >__|   
        \/    \/                       \/          \/     \/   |__|        \/       
"""
            if sys.gettrace() is None:  # Only print banner if not debugging
                for line in banner.split("\n"):
                    print(line.center(get_terminal_size().columns))
                print(Fore.LIGHTMAGENTA_EX + "─" * get_terminal_size().columns)
            
            tprint(f"{Fore.BLUE}Logged in as {Fore.RED}{self.user.name}#{self.user.discriminator} {Fore.GREEN}({self.user.id}){Fore.RESET}")
            
            # Check for updates
            if update_check_enabled:
                try:
                    update_available = await check_for_updates()
                    if not update_available:
                        tprint(f"{Fore.GREEN}Running latest version ({VERSION}){Fore.RESET}")
                except Exception as e:
                    await ErrorHandler.handle(e, "Update check")
            
            # Debug info
            dprint(f"discord.py version {discord.__version__}")
            dprint(f"Tesseract version {pytesseract.get_tesseract_version()}")
            
            # Load keyword files
            await self.update_files()
            
            # Subscribe to guilds
            for guild_id in guilds:
                try:
                    guild = self.get_guild(guild_id)
                    if guild:
                        await guild.subscribe(
                            typing=True, 
                            activities=False, 
                            threads=False,
                            member_updates=False
                        )
                    else:
                        tprint(f"{Fore.YELLOW}Warning: Not in server {guild_id}{Fore.RESET}")
                except Exception as e:
                    await ErrorHandler.handle(e, f"Subscribing to guild {guild_id}")
            
            # Start background tasks
            asyncio.create_task(self.cooldown())
            asyncio.create_task(self.filewatch("keywords/animes.txt"))
            asyncio.create_task(self.filewatch("keywords/characters.txt"))
            asyncio.create_task(self.filewatch("keywords/aniblacklist.txt"))
            asyncio.create_task(self.filewatch("keywords/charblacklist.txt"))
            asyncio.create_task(self.configwatch("config.json"))
            
            if autodrop:
                asyncio.create_task(self.autodrop())
            
            self.ready = True
            tprint(f"{Fore.GREEN}Bot ready!{Fore.RESET}")
            
        except Exception as e:
            await ErrorHandler.handle(e, "Initialization", critical=True)

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages"""
        if not self.ready or message.author.id != 646937666251915264 or message.channel.id not in channels:
            return
        
        try:
            # Check for card drops
            if self.timer == 0 and re.search(MATCH_PATTERN, message.content):
                await self.process_card_drop(message)
            
            # Check for card grabs
            elif re.search(
                f"<@{str(self.user.id)}> took the \*\*.*\*\* card `.*`!|" +
                f"<@{str(self.user.id)}> fought off .* and took the \*\*.*\*\* card `.*`!",
                message.content
            ):
                await self.process_card_grab(message)
            
            # Check for cooldown resets
            elif message.content.startswith(f"<@{str(self.user.id)}>, your **Evasion"):
                dprint("Evasion blessing detected - resetting grab cooldown")
                self.timer = 0
            elif message.content.startswith(f"<@{str(self.user.id)}>, your **Generosity"):
                dprint("Generosity blessing detected - resetting drop cooldown")
        
        except Exception as e:
            await ErrorHandler.handle(e, "Message processing")

    async def process_card_drop(self, message: discord.Message) -> None:
        """Process a card drop message"""
        try:
            # Download card image
            try:
                with open("temp/card.webp", "wb") as f:
                    response = requests.get(message.attachments[0].url, timeout=10)
                    response.raise_for_status()
                    f.write(response.content)
            except (requests.RequestException, IOError) as e:
                await ErrorHandler.handle(e, "Downloading card image")
                return
            
            # Determine number of cards
            try:
                self.cardnum = 3 if filelength("temp/card.webp") == 836 else 4
            except OSError as e:
                await ErrorHandler.handle(e, "Checking card file size")
                return
            
            # Process each card
            for i in range(self.cardnum):
                try:
                    await get_card(f"{OCR_PATH}/card{i+1}.png", "temp/card.webp", i)
                    await get_top(f"{OCR_PATH}/card{i+1}.png", f"{OCR_PATH}/char/top{i+1}.png")
                    await get_bottom(f"{OCR_PATH}/card{i+1}.png", f"{OCR_PATH}/char/bottom{i+1}.png")
                    if cprint:
                        await get_print(f"{OCR_PATH}/card{i+1}.png", f"{OCR_PATH}/char/print{i+1}.png")
                except Exception as e:
                    await ErrorHandler.handle(e, f"Processing card {i+1}")
                    continue
            
            # Extract text from cards
            try:
                charlist, anilist, printlist = await self.extract_card_text()
            except Exception as e:
                await ErrorHandler.handle(e, "Extracting card text")
                return
            
            # Process matches
            try:
                await self.process_matches(message, charlist, anilist, printlist)
            except Exception as e:
                await ErrorHandler.handle(e, "Processing matches")
        
        except Exception as e:
            await ErrorHandler.handle(e, "Card drop processing")

    async def extract_card_text(self) -> Tuple[List[str], List[str], List[int]]:
        """Extract text from card images"""
        charlist = []
        anilist = []
        printlist = []
        
        char_config = r"--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@&0123456789/:- "
        print_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"
        
        for i in range(self.cardnum):
            try:
                # Extract character name
                char_img = f"{OCR_PATH}/char/top{i+1}.png"
                if not os.path.exists(char_img):
                    raise FileNotFoundError(f"Character image not found: {char_img}")
                
                char_text = pytesseract.image_to_string(
                    Image.open(char_img),
                    lang="eng",
                    config=char_config
                ).strip().replace("\n", " ")
                charlist.append(char_text)
                
                # Extract anime name
                anime_img = f"{OCR_PATH}/char/bottom{i+1}.png"
                if not os.path.exists(anime_img):
                    raise FileNotFoundError(f"Anime image not found: {anime_img}")
                
                anime_text = pytesseract.image_to_string(
                    Image.open(anime_img),
                    lang="eng",
                    config=char_config
                ).strip().replace("\n", " ")
                anilist.append(anime_text)
                
                # Extract print number if enabled
                if cprint:
                    print_img = f"{OCR_PATH}/char/print{i+1}.png"
                    if not os.path.exists(print_img):
                        raise FileNotFoundError(f"Print image not found: {print_img}")
                    
                    print_text = pytesseract.image_to_string(
                        Image.open(print_img),
                        lang="eng",
                        config=print_config
                    ).strip()
                    try:
                        printlist.append(int(re.sub(r" \d$| ", "", print_text)))
                    except ValueError:
                        printlist.append(9999999)
            
            except (UnidentifiedImageError, pytesseract.TesseractError) as e:
                await ErrorHandler.handle(e, f"OCR processing for card {i+1}")
                charlist.append("")
                anilist.append("")
                if cprint:
                    printlist.append(9999999)
                continue
            except Exception as e:
                await ErrorHandler.handle(e, f"Text extraction for card {i+1}")
                continue
        
        vprint(f"Anilist: {anilist}")
        vprint(f"Charlist: {charlist}")
        if cprint:
            vprint(f"Printlist: {printlist}")
        
        return charlist, anilist, printlist

    async def process_matches(self, message: discord.Message, 
                            charlist: List[str], anilist: List[str], 
                            printlist: List[int]) -> None:
        """Process all matches for the dropped cards"""
        self.url = message.attachments[0].url
        
        def emoji(index: int) -> str:
            """Get emoji for card position"""
            return ["1️⃣", "2️⃣", "3️⃣", "4️⃣"][index]
        
        # Check character matches
        for i, character in enumerate(charlist):
            if (api.isSomething(character, self.chars, accuracy) and
                not api.isSomething(character, self.charblacklist, accuracy) and
                not api.isSomething(anilist[i], self.aniblacklist, blaccuracy)):
                
                await self.handle_match(
                    message, 
                    f"Character: {character} from {anilist[i]}", 
                    i, 
                    emoji(i)
                )
        
        # Check anime matches
        for i, anime in enumerate(anilist):
            if (api.isSomething(anime, self.animes, accuracy) and
                not api.isSomething(charlist[i], self.charblacklist, accuracy) and
                not api.isSomething(anime, self.aniblacklist, blaccuracy)):
                
                await self.handle_match(
                    message, 
                    f"Anime: {anime} | {charlist[i]}", 
                    i, 
                    emoji(i)
                )
        
        # Check print matches if enabled
        if cprint:
            for i, prin in enumerate(printlist):
                if (prin <= pn and
                    anilist[i] not in self.aniblacklist and
                    charlist[i] not in self.charblacklist):
                    
                    await self.handle_match(
                        message, 
                        f"Print #{prin}", 
                        i, 
                        emoji(i)
                    )

    async def handle_match(self, message: discord.Message, 
                          match_text: str, index: int, emoji: str) -> None:
        """Handle a matched card"""
        tprint(f"{Fore.GREEN}[{message.channel.name}] Found {match_text}{Fore.RESET}")
        
        # Log the hit
        if loghits:
            try:
                with open("log.txt", "a", encoding='utf-8') as f:
                    log_entry = f"{current_time()} - {match_text} - {self.url}\n" if timestamp else f"{match_text} - {self.url}\n"
                    f.write(log_entry)
            except IOError as e:
                await ErrorHandler.handle(e, "Writing to hit log")
        
        # Handle interaction
        if isbutton(message.channel.id):
            await self.handle_button_click(message, index)
        else:
            await self.handle_reaction(message, emoji)

    async def handle_button_click(self, message: discord.Message, index: int) -> None:
        """Handle clicking a button on the card drop"""
        def edit_check(before: discord.Message, after: discord.Message) -> bool:
            return (before.id == message.id and 
                    not after.components[0].children[0].disabled)
        
        try:
            # Wait for message to become clickable
            edited = await self.wait_for(
                "message_edit",
                check=edit_check,
                timeout=10
            )
            await asyncio.sleep(random.uniform(0.55, 1.08))
            await edited[1].components[0].children[index].click()
            await self.after_click()
        except asyncio.TimeoutError:
            await ErrorHandler.handle(Exception("Timed out waiting for button"), "Button click")
        except Exception as e:
            await ErrorHandler.handle(e, "Button click")

    async def handle_reaction(self, message: discord.Message, emoji: str) -> None:
        """Handle adding a reaction to the card drop"""
        def reaction_check(reaction: discord.Reaction, user: discord.User) -> bool:
            return reaction.message.id == message.id
        
        try:
            reaction = await self.wait_for(
                "reaction_add",
                check=reaction_check,
                timeout=10
            )
            await self.react_add(reaction[0], emoji)
        except asyncio.TimeoutError:
            await ErrorHandler.handle(Exception("Timed out waiting for reaction"), "Reaction add")
        except Exception as e:
            await ErrorHandler.handle(e, "Reaction add")

    async def react_add(self, reaction: discord.Reaction, emoji: str) -> None:
        """Add a reaction to a message"""
        try:
            dprint(f"{Fore.BLUE}Attempting to react with {emoji}")
            await asyncio.sleep(random.uniform(0.55, 1.08))
            await reaction.message.add_reaction(emoji)
            self.timer += 60
            self.missed += 1
            dprint(f"{Fore.BLUE}Reacted successfully{Fore.RESET}")
        except discord.Forbidden:
            await ErrorHandler.handle(Exception("Missing reaction permissions"), "Reaction add", critical=True)
        except Exception as e:
            await ErrorHandler.handle(e, "Reaction add")

    async def process_card_grab(self, message: discord.Message) -> None:
        """Process a card grab message"""
        try:
            # Parse message
            match = re.search(
                f"<@{str(self.user.id)}>.*took the \*\*(.*)\*\* card `(.*)`!",
                message.content
            )
            if not match:
                raise ValueError("Failed to parse card grab message")
            
            # Update counters
            self.timer += 540
            self.missed -= 1
            self.collected += 1
            
            # Extract card info
            card_name = match.group(1)
            card_code = match.group(2)
            quality = self.extract_quality(message.content)
            
            # Log to console
            tprint(f"{Fore.BLUE}[{message.channel.name}] Obtained Card: {Fore.LIGHTMAGENTA_EX}{card_name} {Fore.RESET}(Quality: {quality})")
            
            # Log to file
            if logcollection:
                try:
                    with open("log.txt", "a", encoding='utf-8') as f:
                        log_entry = f"{current_time()} - Card: {card_name} - Quality: {quality} - {self.url}\n" if timestamp else f"Card: {card_name} - Quality: {quality} - {self.url}\n"
                        f.write(log_entry)
                except IOError as e:
                    await ErrorHandler.handle(e, "Writing to collection log")
            
            # Send webhook notification
            if webhook_url:
                try:
                    screenshot = await capture_screenshot()
                    await send_webhook(card_name, quality, screenshot)
                except Exception as e:
                    await ErrorHandler.handle(e, "Sending webhook notification")
        
        except Exception as e:
            await ErrorHandler.handle(e, "Processing card grab")

    def extract_quality(self, message_content: str) -> str:
        """Extract card quality from message content"""
        quality_map = {
            "poor": "Poor",
            "good": "Good",
            "great": "Great",
            "perfect": "Perfect",
            "special": "Special Edition",
            "mystic": "Mystic",
            "cosmic": "Cosmic"
        }
        
        for q in quality_map:
            if q in message_content.lower():
                return quality_map[q]
        return "Unknown"

    async def after_click(self) -> None:
        """Handle actions after clicking a button"""
        dprint("Button clicked successfully")
        self.timer += 60
        self.missed += 1

    async def cooldown(self) -> None:
        """Update cooldown timer and title"""
        while True:
            await asyncio.sleep(1)
            if self.timer > 0:
                self.timer -= 1
            
            # Update console title
            if os.name == 'nt':
                title = f"Karuta Sniper {VERSION} - Collected: {self.collected} | Missed: {self.missed}"
                if self.timer > 0:
                    title += f" | Cooldown: {self.timer}s"
                os.system(f"title {title}")

    async def update_files(self) -> None:
        """Update keyword lists from files"""
        try:
            with open("keywords/characters.txt", "r", encoding='utf-8') as f:
                self.chars = [line.strip() for line in f if line.strip()]
            
            with open("keywords/animes.txt", "r", encoding='utf-8') as f:
                self.animes = [line.strip() for line in f if line.strip()]
            
            with open("keywords/aniblacklist.txt", "r", encoding='utf-8') as f:
                self.aniblacklist = [line.strip() for line in f if line.strip()]
            
            with open("keywords/charblacklist.txt", "r", encoding='utf-8') as f:
                self.charblacklist = [line.strip() for line in f if line.strip()]
            
            tprint(
                f"{Fore.MAGENTA}Loaded {len(self.animes)} animes, {len(self.aniblacklist)} blacklisted animes, "
                f"{len(self.chars)} characters, {len(self.charblacklist)} blacklisted characters")
        
        except Exception as e:
            await ErrorHandler.handle(e, "Loading keyword files", critical=True)

    async def filewatch(self, path: str) -> None:
        """Watch for file changes and reload if modified"""
        watcher = api.FileWatch(path)
        dprint(f"Filewatch activated for {path}")
        while True:
            await asyncio.sleep(2)
            try:
                if watcher.watch():
                    await self.update_files()
            except Exception as e:
                await ErrorHandler.handle(e, "File watching")

    async def configwatch(self, path: str) -> None:
        """Watch for config changes and update variables"""
        watcher = api.FileWatch(path)
        while True:
            await asyncio.sleep(1)
            try:
                if watcher.watch():
                    with open(path, "r") as f:
                        new_config = json.load(f)
                    
                    # Update accuracy if changed
                    if "accuracy" in new_config and new_config["accuracy"] != str(accuracy):
                        global accuracy
                        accuracy = float(new_config["accuracy"])
                        dprint(f"Updated accuracy to {accuracy}")
            except Exception as e:
                await ErrorHandler.handle(e, "Config watching")

    async def autodrop(self) -> None:
        """Automatically drop cards in the specified channel"""
        channel = self.get_channel(autodropchannel)
        while True:
            try:
                # Calculate delay with jitter
                delay = dropdelay + random.randint(randmin, randmax)
                if self.timer > 0:
                    delay += self.timer
                
                await asyncio.sleep(delay)
                
                # Send drop command
                async with channel.typing():
                    await asyncio.sleep(random.uniform(0.2, 1))
                
                await channel.send("kd")
                tprint(f"{Fore.LIGHTWHITE_EX}Auto Dropped Cards")
            
            except Exception as e:
                await ErrorHandler.handle(e, "Auto drop")

# ======================
# MAIN EXECUTION
# ======================
if __name__ == "__main__":
    try:
        # Token handling
        if not token:
            inp = input(f"{Fore.RED}No token found, would you like to find tokens from your PC? (y/n): {Fore.RESET}")
            if inp.lower() == "y":
                try:
                    token = api.get_tokens(False)
                    input("Press any key to exit...")
                    sys.exit(0)
                except Exception as e:
                    asyncio.run(ErrorHandler.handle(e, "Token retrieval", critical=True))
                    sys.exit(1)
            else:
                sys.exit(0)
        
        # Create and run client
        intents = discord.Intents.default()
        intents.message_content = True
        
        client = KarutaSniper(intents=intents)
        tprint(f"{Fore.GREEN}Starting Bot{Fore.RESET}")
        
        try:
            client.run(token)
        except discord.LoginFailure as e:
            asyncio.run(ErrorHandler.handle(e, "Discord login", critical=True))
            sys.exit(1)
        except KeyboardInterrupt:
            tprint(f"{Fore.RED}Ctrl-C detected\nExiting...{Fore.RESET}")
            sys.exit(0)
        except Exception as e:
            asyncio.run(ErrorHandler.handle(e, "Bot runtime", critical=True))
            sys.exit(1)
    
    except Exception as e:
        asyncio.run(ErrorHandler.handle(e, "Main execution", critical=True))
        sys.exit(1)
