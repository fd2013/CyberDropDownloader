from __future__ import annotations

import calendar
import datetime
import re
from typing import TYPE_CHECKING

from aiolimiter import AsyncLimiter
from yarl import URL

from cyberdrop_dl.clients.errors import NoExtensionFailure
from cyberdrop_dl.scraper.crawler import Crawler
from cyberdrop_dl.utils.dataclasses.url_objects import ScrapeItem
from cyberdrop_dl.utils.utilities import FILE_FORMATS, get_filename_and_ext, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.managers.manager import Manager


class BunkrrCrawler(Crawler):
    def __init__(self, manager: Manager):
        super().__init__(manager, "bunkrr", "Bunkrr")
        self.primary_base_domain = URL("https://bunkrr.su")
        self.ddos_guard_domain = URL("https://*.bunkrr.su")
        self.request_limiter = AsyncLimiter(10, 1)

        self.cookies_set = False

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        """Determines where to send the scrape item based on the url"""
        task_id = await self.scraping_progress.add_task(scrape_item.url)
        scrape_item.url = await self.get_stream_link(scrape_item.url)

        await self.set_cookies()

        if "a" in scrape_item.url.parts:
            await self.album(scrape_item)
        elif "v" in scrape_item.url.parts:
            await self.video(scrape_item)
        else:
            await self.other(scrape_item)

        await self.scraping_progress.remove_task(task_id)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem) -> None:
        """Scrapes an album"""
        async with self.request_limiter:
            soup = await self.client.get_BS4(self.domain, scrape_item.url)
        title = soup.select_one('h1[class="text-[24px] font-bold text-dark dark:text-white"]')
        for elem in title.find_all("span"):
            elem.decompose()

        title = await self.create_title(title.get_text().strip(), scrape_item.url.parts[2], None)
        await scrape_item.add_to_parent_title(title)

        card_listings = soup.select('div[class*="grid-images_box rounded-lg"]')
        for card_listing in card_listings:
            file = card_listing.select_one('a[class*="grid-images_box-link"]')
            date = await self.parse_datetime(card_listing.select_one('p[class*="date"]').text)
            link = file.get("href")
            if link.startswith("/"):
                link = URL("https://" + scrape_item.url.host + link)
            link = URL(link)
            link = await self.get_stream_link(link)
            await self.scraper_queue.put(ScrapeItem(link, scrape_item.parent_title, True, date))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        """Scrapes a video"""
        async with self.request_limiter:
            soup = await self.client.get_BS4(self.domain, scrape_item.url)
        link_container = soup.select("a[class*=bg-blue-500]")[-1]
        link = URL(link_container.get('href'))

        try:
            filename, ext = await get_filename_and_ext(link.name)
        except NoExtensionFailure:
            filename, ext = await get_filename_and_ext(scrape_item.url.name)

        await self.handle_file(link, scrape_item, filename, ext)

    @error_handling_wrapper
    async def other(self, scrape_item: ScrapeItem) -> None:
        """Scrapes an image/other file"""
        async with self.request_limiter:
            soup = await self.client.get_BS4(self.domain, scrape_item.url)
        link_container = soup.select('a[class*="text-white inline-flex"]')[-1]
        link = URL(link_container.get('href'))

        try:
            filename, ext = await get_filename_and_ext(link.name)
        except NoExtensionFailure:
            filename, ext = await get_filename_and_ext(scrape_item.url.name)

        await self.handle_file(link, scrape_item, filename, ext)

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def get_stream_link(self, url: URL) -> URL:
        """Gets the stream link for a given url"""
        cdn_possibilities = r"^(?:(?:(?:media-files|cdn|c|pizza|cdn-burger)[0-9]{0,2})|(?:(?:big-taco-|cdn-pizza|cdn-meatballs|cdn-milkshake)[0-9]{0,2}(?:redir)?))\.bunkr?\.[a-z]{2,3}$"

        if not re.match(cdn_possibilities, url.host):
            return url

        ext = url.suffix.lower()
        if ext == "":
            return url

        if ext in FILE_FORMATS['Images']:
            url = url.with_host(re.sub(r"^cdn(\d*)\.", r"i\1.", url.host))
        elif ext in FILE_FORMATS['Videos']:
            url = self.primary_base_domain / "v" / url.parts[-1]
        else:
            url = self.primary_base_domain / "d" / url.parts[-1]

        return url

    async def parse_datetime(self, date: str) -> int:
        """Parses a datetime string into a unix timestamp"""
        date = datetime.datetime.strptime(date, "%H:%M:%S %d/%m/%Y")
        return calendar.timegm(date.timetuple())

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def set_cookies(self):
        """Sets the cookies for the client"""
        if self.cookies_set:
            return

        if self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddg1']:
            self.client.client_manager.cookies.update_cookies({"__ddg1_": self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddg1']}, response_url=self.ddos_guard_domain)
        if self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddg2']:
            self.client.client_manager.cookies.update_cookies({"__ddg2_": self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddg2']}, response_url=self.ddos_guard_domain)
        if self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddgid']:
            self.client.client_manager.cookies.update_cookies({"__ddgid_": self.manager.config_manager.authentication_data['DDOS-Guard']['bunkrr_ddgid']}, response_url=self.ddos_guard_domain)

        self.cookies_set = True