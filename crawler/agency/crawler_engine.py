import re  # Don't remove this package, this package used dynamically in code
import logging, redis, json, time, datetime, validators
from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from agency.models import AgencyPageStructure, CrawlReport

logger = logging.getLogger("django")


class CrawlerEngine:
    def __init__(self, page, header=None):
        # TODO: ip and port of webdriver must be dynamic
        # Initialize Chrome browser (connect to chrome container)

        self.log_messages = ""

        # Increase speed by some tunning
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--enable-automation")
        options.add_argument("--no-sandbox")

        # connect to chrome container
        self.driver = webdriver.Remote(
            "http://news_crawler_chrome:4444/wd/hub",
            desired_capabilities=DesiredCapabilities.CHROME,
            options=options,
        )

        # set headers to looks like a common user
        self.driver.header_overrides = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.11 (KHTML, like Gecko) "
            "Chrome/23.0.1271.64 Safari/537.11",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
            "Accept-Encoding": "none",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }

        # TODO: ip and port of redis must be dynamic
        # initialize redis_news memory for storing news
        # initialize redis_duplicate_checker for checking duplicate links
        self.redis_news = redis.StrictRedis(host="news_crawler_redis", port=6379, db=0)
        self.redis_duplicate_checker = redis.StrictRedis(
            host="news_crawler_redis", port=6379, db=1
        )

        # locking webpage, so laters tasks can not crawl the page simultaneously
        self.page = page
        AgencyPageStructure.objects.filter(id=self.page["id"]).update(lock=True)

        # create report for this crawl
        self.page_structure = AgencyPageStructure.objects.get(id=self.page["id"])
        self.report = CrawlReport.objects.create(
            page_id=self.page["id"], status="pending"
        )
        self.header = header

    def fetch_links(self):
        # fetch links from a webpage by structure that had specified by operator
        links = []
        self.driver.get(self.page["url"])
        doc = BeautifulSoup(self.driver.page_source, "html.parser")
        attribute = self.page["news_links_structure"]
        attribute = json.dumps(attribute)
        attribute = json.loads(attribute)
        self.custom_logging(f"\n\nstructure for fetching links are: \n{attribute}\n\n")
        tag = attribute["tag"]
        del attribute["tag"]
        code = ""
        if "code" in attribute.keys():
            code = attribute["code"]
            del attribute["code"]
        elements = doc.findAll(tag, attribute)
        if code != "":
            temp_code = """
{0}
            """
            temp_code = temp_code.format(code)
            self.custom_logging(f"Executing code: \n{temp_code}")
            exec(temp_code)
            self.custom_logging("executed code")
        else:
            for element in elements:
                links.append(element["href"])
        links = list(set([link for link in links if validators.url(link)]))
        self.fetched_links = links
        self.fetched_links_count = len(links)

    # TODO: Make crawl_news_page as task function
    def crawl_one_page(self, link):
        # crawl a link and get data that specified by the structure of the page
        meta = self.page["news_meta_structure"]
        article = {}
        article["link"] = link
        self.custom_logging(f"getting content of news: {link}")
        self.driver.get(link)
        # TODO: sleep to page load must be dynamic
        # do some sleep to all elements of page loaded completely
        time.sleep(4)
        doc = BeautifulSoup(self.driver.page_source, "html.parser")
        for key in meta.keys():
            attribute = meta[key].copy()
            tag = attribute["tag"]
            del attribute["tag"]
            if tag == "value":
                article[key] = attribute["value"]
                self.custom_logging(
                    f"\tspecified tag get's value directly and it's value is: \n {attribute['value']}"
                )
                continue
            if tag == "code":
                code = attribute["code"]
                temp_code = """
{0}
                """
                temp_code = temp_code.format(code)
                try:
                    exec(temp_code)
                except Exception as e:
                    self.custom_logging(f"Getting attr {key} got error")
                    self.custom_logging(f"The code was:\n {temp_code} ")
                    self.custom_logging(f"Error was:\n {str(e)}")
                continue
            code = ""
            if "code" in attribute.keys():
                code = attribute["code"]
                del attribute["code"]
            self.custom_logging(f"key: {key} tag: {tag} attr: {attribute}")
            element = doc.find(tag, attribute)
            if element is None:
                self.custom_logging(f"element is null, attribute: {attribute}")
                break
            if code != "":
                temp_code = """
{0}
                """
                temp_code = temp_code.format(code)
                try:
                    exec(temp_code)
                except Exception as e:
                    self.custom_logging(f"Getting attr {key} got error")
                    self.custom_logging(f"The code was:\n {temp_code} ")
                    self.custom_logging(f"Error was:\n {str(e)}")
            else:
                article[key] = element.text
        logger.info(article)
        self.save_to_redis(article)

    def save_to_redis(self, article):
        article["agency_id"] = self.page_structure.agency.id
        article["source"] = self.page_structure.agency.name

        # TODO: expiration must be dynamic
        self.redis_duplicate_checker.set(article["link"], "", ex=86400 * 30)
        if "title" in article.keys() and "body" in article.keys():
            self.redis_news.set(article["link"], json.dumps(article))

    def check_links(self):
        counter = self.fetched_links_count
        print(len(self.fetched_links))
        for link in self.fetched_links:
            if self.redis_duplicate_checker.exists(link) or not validators.url(link):
                counter -= 1
                continue
            else:
                self.crawl_one_page(link)

        self.page_structure.last_crawl = datetime.datetime.now()
        self.page_structure.save()
        AgencyPageStructure.objects.filter(id=self.page["id"]).update(lock=False)
        self.report.fetched_links = self.fetched_links_count
        self.report.new_links = counter
        self.report.status = "complete"
        self.report.log = self.log_messages
        self.report.save()
        self.driver.quit()

    def custom_logging(self, message):
        logger.info(message)
        self.log_messages += f"{message} \n"

    def run(self):
        self.custom_logging(f"------> Fetching links from {self.page['url']} started")
        self.fetch_links()
        self.custom_logging(
            f"------> We found {self.fetched_links_count} number of links"
        )
        self.check_links()


# Crawler version 2
class CrawlerEngineV2:
    def __init__(self, header=None):
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--enable-automation")
        options.add_argument("--no-sandbox")
        self.driver = webdriver.Remote(
            "http://news_crawler_chrome_browser:4444/wd/hub",
            desired_capabilities=DesiredCapabilities.CHROME,
            options=options,
        )
        self.driver.header_overrides = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.11 (KHTML, like Gecko) "
            "Chrome/23.0.1271.64 Safari/537.11",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
            "Accept-Encoding": "none",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }

    def get_links(self, structure, url):
        links = []
        self.driver.get(url)
        doc = BeautifulSoup(self.driver.page_source, "html.parser")
        attribute = json.dumps(structure)
        attribute = json.loads(attribute)
        tag = attribute["tag"]
        del attribute["tag"]
        code = ""
        if "code" in attribute.keys():
            code = attribute["code"]
            del attribute["code"]
        elements = doc.findAll(tag, attribute)
        if code != "":
            temp_code = """
{0}
            """
            temp_code = temp_code.format(code)
            exec(temp_code)
        else:
            for element in elements:
                links.append(element["href"])
        links = set([link for link in links if validators.url(link)])
        return links

    def get_content(self, structure, url):
        article = {}
        article["link"] = url
        self.driver.get(url)
        # TODO: sleep to page load must be dynamic
        doc = BeautifulSoup(self.driver.page_source, "html.parser")
        for key in structure.keys():
            attribute = structure[key].copy()
            tag = attribute["tag"]
            del attribute["tag"]
            if tag == "value":
                article[key] = attribute["value"]
                print(
                    "\tspecified tag get's value directly and it's value is: \n {}".format(
                        attribute["value"]
                    )
                )
                continue
            if tag == "code":
                code = attribute["code"]
                temp_code = """
{0}
                """
                temp_code = temp_code.format(code)
                try:
                    exec(temp_code)
                except Exception as e:
                    print("Getting attr {} got error".format(key))
                    print("The code was:\n {} ".format(temp_code))
                    print("Error was:\n {}".format(str(e)))
                continue
            code = ""
            if "code" in attribute.keys():
                code = attribute["code"]
                del attribute["code"]
            print("key: {} tag: {} attr: {}".format(key, tag, attribute))
            element = doc.find(tag, attribute)
            if element is None:
                print("element is null, attribute: {}".format(attribute))
                break
            if code != "":
                temp_code = """
{0}
                """
                temp_code = temp_code.format(code)
                try:
                    exec(temp_code)
                except Exception as e:
                    print("Getting attr {} got error".format(key))
                    print("The code was:\n {} ".format(temp_code))
                    print("Error was:\n {}".format(str(e)))
            else:
                article[key] = element.text
        return article
