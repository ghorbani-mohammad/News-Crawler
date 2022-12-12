from __future__ import absolute_import, unicode_literals
import logging, datetime, redis, requests, json, requests
from dateutil import relativedelta

from celery.task.schedules import crontab

from crawler.celery import crawler
from .models import Agency, AgencyPageStructure, CrawlReport, Option
from .serializer import AgencyPageStructureSerializer
from .crawler_engine import CrawlerEngine
from reusable.other import only_one_concurrency


logger = logging.getLogger(__name__)
MINUTE = 60
TASKS_TIMEOUT = 10 * MINUTE


redis_news = redis.StrictRedis(host="news_crawler_redis", port=6379, db=0)
Exporter_API_URI = "http://172.22.0.1:8888/crawler/news"
Exporter_API_headers = {
    "Content-Type": "application/json",
    "User-Agent": "PostmanRuntime/7.17.1",
    "Accept": "*/*",
    "Cache-Control": "no-cache",
    "Postman-Token": "4b465a23-1b28-4b86-981d-67ccf94dda70,4beba7c1-fd77-4b44-bb14-2ea60fbfa590",
    "Host": "172.22.0.1:8888",
    "Accept-Encoding": "gzip, deflate",
    "Content-Length": "2796",
    "Connection": "keep-alive",
    "cache-control": "no-cache",
}


def check_must_crawl(page):
    now = datetime.datetime.now()
    try:
        status = Option.objects.filter(key="crawl_debug").first().value
    except:
        status = "False"
    x = CrawlReport.objects.filter(page=page.id, status="pending")
    if x.count() == 0:
        crawl(page)
    else:
        last_report = x.last()
        if (
            int((now - last_report.created_at).total_seconds() / (3600))
            >= page.crawl_interval
            or status == "True"
        ):
            last_report.status = "failed"
            last_report.save()
            crawl(page)


@crawler.task(name="check_agencies")
def check():
    logger.info("*** Check_agencies is started ***")
    agencies = Agency.objects.filter(status=True, deleted_at=None).values_list(
        "id", flat=True
    )
    pages = AgencyPageStructure.objects.filter(
        agency__in=agencies, deleted_at=None, lock=False
    )
    now = datetime.datetime.now()
    for page in pages:
        if page.last_crawl is None:
            check_must_crawl(page)
        else:
            diff_hour = int((now - page.last_crawl).total_seconds() / (3600))
            if diff_hour >= page.crawl_interval:
                check_must_crawl(page)


def crawl(page):
    logger.info("*** Page %s must be crawled", page.url)
    serializer = AgencyPageStructureSerializer(page)
    page_crawl.delay(serializer.data)


@crawler.task(name="page_crawl")
@only_one_concurrency(key="page_crawl", timeout=TASKS_TIMEOUT)
def page_crawl(page_structure):
    logger.info("---> Page crawling is started")
    crawler = CrawlerEngine(page_structure)
    crawler.run()


@crawler.task(name="redis_exporter")
@only_one_concurrency(key="redis_exporter", timeout=TASKS_TIMEOUT)
def redis_exporter():
    logger.info("---> Redis exporter is started")
    for key in redis_news.keys("*"):
        data = redis_news.get(key).decode("utf-8")
        try:
            data = json.loads(data)
        except:
            print(data)
            continue
        if not "date" in data:
            data["date"] = int(datetime.datetime.now().timestamp())
        if not "agency_id" in data:
            redis_news.delete(key)
            continue
        data["agency_id"] = int(data["agency_id"])
        try:
            response = requests.request(
                "GET",
                Exporter_API_URI,
                data=json.dumps(data),
                headers=Exporter_API_headers,
            )
        except Exception as e:
            logging.error(e)
            raise Exception(e)
        if response.status_code == 200 or response.status_code == 406:
            logging.error(response.status_code)
            redis_news.delete(key)
        elif response.status_code == 400:
            logging.error(response.status_code)
            redis_news.delete(key)
            logging.error(
                "Exporter error. code: %s || message: %s",
                str(response.status_code),
                str(response.text),
            )
            logging.error("Redis-key: %s", str(key))
        elif response.status_code == 500:
            logging.error(
                "Exporter error. code: %s || message: %s",
                str(response.status_code),
                str(response.text),
            )
            logging.error("Redis-key: %s", str(key))
            return
        else:
            logging.error(
                "Exporter error. code: %s || message: %s",
                str(response.status_code),
                str(response.text),
            )
            logging.error("Redis-key: %s", str(key))


@crawler.task(name="remove_obsolete_reports")
def remove_obsolete_reports():
    now = datetime.datetime.now()
    past_month = now - relativedelta.relativedelta(months=1)
    CrawlReport.objects.filter(created_at__lte=past_month).delete()


@crawler.task(
    run_every=(crontab(minute=0, hour=0)), name="reset_locks", ignore_result=True
)
def reset_locks():
    AgencyPageStructure.objects.update(lock=False)
