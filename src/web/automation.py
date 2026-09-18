"""Web Automation - Browser interaction with CTF platforms"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from ..core.models import Challenge, ChallengeCategory, ChallengeType
from ..core.db import get_session_factory
from ..observability import get_logger


@dataclass
class CTFPlatform:
    """CTF platform configuration."""
    name: str
    base_url: str
    login_url: str
    challenges_url: str
    selectors: Dict[str, str]  # CSS selectors for elements
    auth_type: str = "form"  # form, oauth, basic


@dataclass
class CTFCredentials:
    """Credentials for CTF platform."""
    platform: str
    username: str
    password: str
    api_key: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class DiscoveredChallenge:
    """Challenge discovered on platform."""
    platform: str
    name: str
    url: str
    category: Optional[ChallengeCategory] = None
    description: str = ""
    points: int = 0
    solves: int = 0
    difficulty: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)


class WebAutomation:
    """Browser automation for CTF platform interaction."""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.logger = get_logger("web_automation")
    
    async def initialize(self):
        """Initialize browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout)
    
    async def close(self):
        """Close browser."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def login(self, platform: CTFPlatform, credentials: CTFCredentials) -> bool:
        """Login to CTF platform."""
        try:
            self.logger.info(f"Logging into {platform.name}")
            await self._page.goto(platform.login_url, wait_until="networkidle")
            
            if platform.auth_type == "form":
                # Fill login form
                username_sel = platform.selectors.get("username", "input[name='username'], input[name='email'], input[type='email']")
                password_sel = platform.selectors.get("password", "input[name='password'], input[type='password']")
                submit_sel = platform.selectors.get("submit", "button[type='submit'], input[type='submit']")
                
                await self._page.fill(username_sel, credentials.username)
                await self._page.fill(password_sel, credentials.password)
                await self._page.click(submit_sel)
                await self._page.wait_for_load_state("networkidle")
            
            # Check if login succeeded
            if await self._is_logged_in(platform):
                self.logger.info(f"Login successful for {platform.name}")
                return True
            
            self.logger.error(f"Login failed for {platform.name}")
            return False
            
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
    
    async def _is_logged_in(self, platform: CTFPlatform) -> bool:
        """Check if login was successful."""
        try:
            # Check for logout button or user menu
            logged_in_selectors = [
                platform.selectors.get("logout", "a:has-text('Logout'), button:has-text('Logout')"),
                platform.selectors.get("user_menu", ".user-menu, .dropdown-toggle, [data-user]"),
                "text=Logout", "text=Sign out", "text=Disconnect"
            ]
            
            for sel in logged_in_selectors:
                if await self._page.locator(sel).count() > 0:
                    return True
            
            # Check URL - should not be on login page
            if "login" not in self._page.url.lower():
                return True
                
            return False
        except:
            return False
    
    async def discover_challenges(self, platform: CTFPlatform) -> List[DiscoveredChallenge]:
        """Discover all challenges on platform."""
        challenges = []
        
        try:
            self.logger.info(f"Discovering challenges on {platform.name}")
            await self._page.goto(platform.challenges_url, wait_until="networkidle")
            
            # Wait for challenge list to load
            challenge_list_sel = platform.selectors.get("challenge_list", ".challenge-list, .challenges, table.challenges, [data-challenges]")
            await self._page.wait_for_selector(challenge_list_sel, timeout=10000)
            
            # Get challenge elements
            challenge_item_sel = platform.selectors.get("challenge_item", ".challenge, .challenge-row, tr.challenge, [data-challenge]")
            items = await self._page.locator(challenge_item_sel).all()
            
            for item in items:
                challenge = await self._parse_challenge_item(item, platform)
                if challenge:
                    challenges.append(challenge)
            
            # Handle pagination
            while await self._has_next_page(platform):
                await self._click_next_page(platform)
                await self._page.wait_for_load_state("networkidle")
                items = await self._page.locator(challenge_item_sel).all()
                for item in items:
                    challenge = await self._parse_challenge_item(item, platform)
                    if challenge:
                        challenges.append(challenge)
            
            self.logger.info(f"Discovered {len(challenges)} challenges on {platform.name}")
            
        except Exception as e:
            self.logger.error(f"Challenge discovery error: {e}")
        
        return challenges
    
    async def _parse_challenge_item(self, item, platform: CTFPlatform) -> Optional[DiscoveredChallenge]:
        """Parse a single challenge element."""
        try:
            selectors = platform.selectors
            
            name = await item.locator(selectors.get("name", ".name, .title, h3, h4, [data-name]")).first.text_content()
            name = name.strip() if name else ""
            
            if not name:
                return None
            
            # Get challenge URL
            link = await item.locator("a").first.get_attribute("href")
            url = urljoin(platform.base_url, link) if link else ""
            
            # Get category
            cat_text = await item.locator(selectors.get("category", ".category, .tag, [data-category]")).first.text_content()
            category = self._parse_category(cat_text) if cat_text else None
            
            # Get points
            points_text = await item.locator(selectors.get("points", ".points, .score, [data-points]")).first.text_content()
            points = self._parse_int(points_text) if points_text else 0
            
            # Get solves
            solves_text = await item.locator(selectors.get("solves", ".solves, .solvers, [data-solves]")).first.text_content()
            solves = self._parse_int(solves_text) if solves_text else 0
            
            # Get difficulty
            diff_text = await item.locator(selectors.get("difficulty", ".difficulty, .level, [data-difficulty]")).first.text_content()
            difficulty = diff_text.strip() if diff_text else ""
            
            return DiscoveredChallenge(
                platform=platform.name,
                name=name,
                url=url,
                category=category,
                points=points,
                solves=solves,
                difficulty=difficulty,
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse challenge: {e}")
            return None
    
    def _parse_category(self, text: str) -> Optional[ChallengeCategory]:
        """Parse category from text."""
        text = text.lower().strip()
        cat_map = {
            "web": ChallengeCategory.WEB,
            "crypto": ChallengeCategory.CRYPTO,
            "pwn": ChallengeCategory.PWN,
            "reverse": ChallengeCategory.REVERSE,
            "reversing": ChallengeCategory.REVERSE,
            "forensics": ChallengeCategory.FORENSICS,
            "forensic": ChallengeCategory.FORENSICS,
            "osint": ChallengeCategory.OSINT,
            "stego": ChallengeCategory.STEGO,
            "steganography": ChallengeCategory.STEGO,
            "mobile": ChallengeCategory.MOBILE,
            "malware": ChallengeCategory.MALWARE,
            "cloud": ChallengeCategory.CLOUD,
            "network": ChallengeCategory.NETWORK,
            "supply chain": ChallengeCategory.SUPPLY_CHAIN,
            "ad": ChallengeCategory.AD,
            "active directory": ChallengeCategory.AD,
            "web3": ChallengeCategory.WEB3,
            "blockchain": ChallengeCategory.WEB3,
            "ai": ChallengeCategory.AI_SECURITY,
            "ml": ChallengeCategory.AI_SECURITY,
            "sidechannel": ChallengeCategory.SIDECHANNEL,
            "firmware": ChallengeCategory.FIRMWARE,
            "social": ChallengeCategory.SOCIAL,
            "social engineering": ChallengeCategory.SOCIAL,
            "programming": ChallengeCategory.PROGRAMMING,
            "coding": ChallengeCategory.PROGRAMMING,
        }
        
        for key, cat in cat_map.items():
            if key in text:
                return cat
        return None
    
    def _parse_int(self, text: str) -> int:
        """Parse integer from text."""
        match = re.search(r'\d+', text)
        return int(match.group()) if match else 0
    
    async def _has_next_page(self, platform: CTFPlatform) -> bool:
        """Check if there's a next page."""
        next_sel = platform.selectors.get("next_page", "a:has-text('Next'), button:has-text('Next'), .pagination .next, [rel='next']")
        return await self._page.locator(next_sel).count() > 0
    
    async def _click_next_page(self, platform: CTFPlatform):
        """Click next page button."""
        next_sel = platform.selectors.get("next_page", "a:has-text('Next'), button:has-text('Next'), .pagination .next, [rel='next']")
        await self._page.click(next_sel)
    
    async def get_challenge_details(self, challenge: DiscoveredChallenge) -> Dict[str, Any]:
        """Get detailed challenge information."""
        details = {"url": challenge.url, "name": challenge.name}
        
        try:
            await self._page.goto(challenge.url, wait_until="networkidle")
            
            # Extract description
            desc_selectors = [
                ".description, .challenge-description, .markdown-body, [data-description]",
                ".challenge-content, .content, main"
            ]
            
            for sel in desc_selectors:
                elements = await self._page.locator(sel).all()
                if elements:
                    details["description"] = await elements[0].text_content()
                    break
            
            # Extract files/attachments
            file_links = await self._page.locator("a[href*='download'], a[href*='attachment'], a[href*='file']").all()
            files = []
            for link in file_links:
                href = await link.get_attribute("href")
                text = await link.text_content()
                if href:
                    files.append({"url": urljoin(challenge.url, href), "name": text.strip()})
            details["files"] = files
            
            # Extract hints
            hint_elements = await self._page.locator(".hint, .hints, [data-hint]").all()
            hints = [await el.text_content() for el in hint_elements]
            details["hints"] = [h.strip() for h in hints if h.strip()]
            
        except Exception as e:
            self.logger.warning(f"Failed to get challenge details: {e}")
        
        return details
    
    async def submit_flag(self, platform: CTFPlatform, challenge: DiscoveredChallenge, flag: str) -> Dict[str, Any]:
        """Submit flag for challenge."""
        result = {"success": False, "message": "", "correct": False}
        
        try:
            await self._page.goto(challenge.url, wait_until="networkidle")
            
            # Find flag input
            flag_input_sel = platform.selectors.get("flag_input", "input[name='flag'], input[name='answer'], input[placeholder*='flag'], input[placeholder*='answer']")
            submit_sel = platform.selectors.get("flag_submit", "button:has-text('Submit'), input[type='submit'], button[type='submit']")
            
            await self._page.fill(flag_input_sel, flag)
            await self._page.click(submit_sel)
            await self._page.wait_for_load_state("networkidle")
            
            # Check result
            success_indicators = [
                "text=Correct", "text=Success", "text=Accepted", "text=Flag accepted",
                ".success, .correct, .accepted, [data-correct]"
            ]
            
            for indicator in success_indicators:
                if await self._page.locator(indicator).count() > 0:
                    result["success"] = True
                    result["correct"] = True
                    result["message"] = "Flag accepted!"
                    break
            
            if not result["correct"]:
                error_indicators = [
                    "text=Incorrect", "text=Wrong", "text=Invalid", "text=Try again",
                    ".error, .incorrect, .wrong, [data-error]"
                ]
                for indicator in error_indicators:
                    if await self._page.locator(indicator).count() > 0:
                        result["message"] = "Flag rejected"
                        break
            
        except Exception as e:
            result["message"] = str(e)
            self.logger.error(f"Flag submission error: {e}")
        
        return result
    
    async def download_files(self, challenge: DiscoveredChallenge, dest_dir: Path) -> List[Path]:
        """Download challenge files."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        
        try:
            details = await self.get_challenge_details(challenge)
            
            for file_info in details.get("files", []):
                url = file_info["url"]
                name = file_info["name"] or url.split("/")[-1]
                dest_path = dest_dir / name
                
                # Download via browser context
                response = await self._context.request.get(url)
                if response.ok:
                    content = await response.body()
                    dest_path.write_bytes(content)
                    downloaded.append(dest_path)
                    self.logger.info(f"Downloaded: {name}")
                    
        except Exception as e:
            self.logger.error(f"File download error: {e}")
        
        return downloaded


# Predefined platform configurations
PLATFORMS = {
    "ctfd": CTFPlatform(
        name="CTFd",
        base_url="",
        login_url="/login",
        challenges_url="/challenges",
        selectors={
            "username": "input[name='name']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
            "logout": "a:has-text('Logout')",
            "challenge_list": ".challenges-container, .challenge-list",
            "challenge_item": ".challenge, .challenge-row",
            "name": ".challenge-name, .name",
            "category": ".category, .tag",
            "points": ".value, .points",
            "solves": ".solves",
            "difficulty": ".difficulty",
            "next_page": ".pagination .next a",
            "flag_input": "input[name='key'], input[name='flag']",
            "flag_submit": "button[type='submit']",
        }
    ),
    "rctf": CTFPlatform(
        name="RCTF",
        base_url="",
        login_url="/login",
        challenges_url="/challenges",
        selectors={
            "username": "input[name='username']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
            "logout": ".logout",
            "challenge_list": ".challenge-list",
            "challenge_item": ".challenge-item",
            "name": ".challenge-title",
            "category": ".challenge-category",
            "points": ".challenge-score",
            "solves": ".challenge-solves",
        }
    ),
    "ctfhub": CTFPlatform(
        name="CTFHub",
        base_url="",
        login_url="/user/login",
        challenges_url="/challenges",
        selectors={
            "username": "input[name='username']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
            "logout": "a:has-text('登出')",
            "challenge_list": ".challenge-list",
            "challenge_item": ".challenge-card",
            "name": ".challenge-name",
            "category": ".challenge-tag",
            "points": ".challenge-score",
            "solves": ".challenge-solves",
        }
    ),
}


class CTFAutonomousAgent:
    """Fully autonomous CTF agent that can discover and solve challenges."""
    
    def __init__(
        self,
        platform_name: str,
        base_url: str,
        credentials: CTFCredentials,
        orchestrator,  # Local Orchestrator instance
        headless: bool = True,
    ):
        self.platform_name = platform_name
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.orchestrator = orchestrator
        self.headless = headless
        
        # Setup platform config
        self.platform = PLATFORMS.get(platform_name.lower())
        if not self.platform:
            raise ValueError(f"Unknown platform: {platform_name}. Supported: {list(PLATFORMS.keys())}")
        
        self.platform.base_url = self.base_url
        self.platform.login_url = urljoin(self.base_url, self.platform.login_url)
        self.platform.challenges_url = urljoin(self.base_url, self.platform.challenges_url)
        
        self.web = WebAutomation(headless=headless)
        self.logger = get_logger("ctf_autonomous")
        self._running = False
    
    async def start(self):
        """Start autonomous solving."""
        self._running = True
        await self.web.initialize()
        
        try:
            # Login
            if not await self.web.login(self.platform, self.credentials):
                raise RuntimeError("Login failed")
            
            # Main solving loop
            while self._running:
                await self._solve_cycle()
                await asyncio.sleep(60)  # Check for new challenges periodically
                
        finally:
            await self.web.close()
    
    async def stop(self):
        """Stop autonomous solving."""
        self._running = False
    
    async def _solve_cycle(self):
        """One cycle of challenge discovery and solving."""
        self.logger.info("Starting solve cycle")
        
        # Discover challenges
        challenges = await self.web.discover_challenges(self.platform)
        
        for challenge in challenges:
            if not self._running:
                break
            
            # Check if already solved in local DB
            existing = self.orchestrator.get_challenge(challenge.name)
            if existing and existing.solve_result and existing.solve_result.success:
                self.logger.info(f"Already solved: {challenge.name}")
                continue
            
            # Download files
            with tempfile.TemporaryDirectory() as tmpdir:
                files = await self.web.download_files(challenge, Path(tmpdir))
                
                # Get full details
                details = await self.web.get_challenge_details(challenge)
                
                # Add to local orchestrator
                local_challenge = await self.orchestrator.add_challenge(
                    name=f"{self.platform.name}-{challenge.name}",
                    description=details.get("description", challenge.description),
                    target_info={"url": challenge.url, "platform": self.platform.name},
                    challenge_type=ChallengeType.JEOPARDY,
                )
                
                # Store downloaded files as artifacts
                for f in files:
                    artifact_id = await self.orchestrator.artifacts.store_file(
                        f, source=f"{self.platform.name}/{challenge.name}"
                    )
                    await self.orchestrator.challenges.add_file(local_challenge.id, artifact_id)
                
                # Solve
                self.logger.info(f"Solving: {challenge.name}")
                result = await self.orchestrator.solve(local_challenge.id)
                
                if result.success and result.flag:
                    # Submit flag
                    submit_result = await self.web.submit_flag(self.platform, challenge, result.flag)
                    if submit_result.get("correct"):
                        self.logger.info(f"✅ Flag submitted and accepted for {challenge.name}")
                    else:
                        self.logger.warning(f"⚠️ Flag submission failed: {submit_result.get('message')}")
                else:
                    self.logger.info(f"❌ Could not solve: {challenge.name}")
        
        self.logger.info("Solve cycle complete")


# Add missing imports
import tempfile
from pathlib import Path