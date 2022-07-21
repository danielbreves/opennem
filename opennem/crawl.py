"""Primary OpenNEM crawler

"""
import logging
from typing import List, Optional

from pydantic import ValidationError

from opennem import settings
from opennem.controllers.nem import store_aemo_tableset
from opennem.controllers.schema import ControllerReturn
from opennem.core.crawlers.meta import CrawlStatTypes, crawler_get_all_meta, crawler_set_meta
from opennem.core.crawlers.schema import CrawlerDefinition, CrawlerSchedule, CrawlerSet
from opennem.core.parsers.aemo.mms import parse_aemo_url
from opennem.crawlers.aemo import AEMONEMDispatchActualGEN, AEMONEMNextDayDispatch
from opennem.crawlers.apvi import APVIRooftopLatestCrawler, APVIRooftopMonthCrawler, APVIRooftopTodayCrawler
from opennem.crawlers.bom import BOMCapitals
from opennem.crawlers.nemweb import (
    AEMONemwebDispatchIS,
    AEMONemwebDispatchISArchive,
    AEMONemwebRooftop,
    AEMONemwebRooftopForecast,
    AEMONemwebTradingIS,
    AEMONemwebTradingISArchive,
    AEMONNemwebDispatchScada,
    AEMONNemwebDispatchScadaArchive,
)
from opennem.crawlers.wem import WEMBalancing, WEMBalancingLive, WEMFacilityScada, WEMFacilityScadaLive
from opennem.utils.dates import get_today_opennem
from opennem.utils.modules import load_all_crawler_definitions

logger = logging.getLogger("opennem.crawler")


def load_crawlers() -> CrawlerSet:
    """Loads all the crawler definitions from a module and returns a CrawlSet"""
    crawlers = []
    crawler_definitions = []

    if settings.crawlers_module:
        # search_modules.append()
        crawler_definitions = load_all_crawler_definitions(settings.crawlers_module)
        crawler_definitions = [
            AEMONEMDispatchActualGEN,
            AEMONEMNextDayDispatch,
            AEMONemwebRooftop,
            AEMONemwebRooftopForecast,
            AEMONemwebTradingIS,
            AEMONemwebDispatchIS,
            AEMONNemwebDispatchScada,
            AEMONemwebTradingISArchive,
            AEMONemwebDispatchISArchive,
            AEMONNemwebDispatchScadaArchive,
            APVIRooftopTodayCrawler,
            APVIRooftopLatestCrawler,
            APVIRooftopMonthCrawler,
            BOMCapitals,
            WEMBalancing,
            WEMBalancingLive,
            WEMFacilityScada,
            WEMFacilityScadaLive,
        ]

    for crawler_inst in crawler_definitions:

        _meta = crawler_get_all_meta(crawler_inst.name)

        if not _meta:
            crawlers.append(crawler_inst)
            continue

        crawler_updated_with_meta: Optional[CrawlerDefinition] = None

        try:
            crawler_field_values = {
                **crawler_inst.dict(),
                **_meta,
                "version": "2",
            }
            crawler_updated_with_meta = CrawlerDefinition(
                **crawler_field_values,
            )
        except ValidationError as e:
            logger.error("Validation error for crawler {}: {}".format(crawler_inst.name, e))
            raise Exception("Crawler initiation error")

        if crawler_updated_with_meta:
            crawlers.append(crawler_updated_with_meta)

    cs = CrawlerSet(crawlers=crawlers)

    logger.debug("Loaded {} crawlers: {}".format(len(cs.crawlers), ", ".join([i.name for i in cs.crawlers])))

    return cs


def run_crawl(crawler: CrawlerDefinition, last_crawled: bool = True, limit: bool = False) -> None:
    """Runs a crawl from the crawl definition with ability to overwrite last crawled and obey the defined
    limit"""

    logger.info(
        "Crawling: {}. (Last Crawled: {}. Limit: {}. Server latest: {})".format(
            crawler.name, crawler.last_crawled, crawler.limit, crawler.server_latest
        )
    )

    # now in opennem time which is Australia/Sydney
    now_opennem_time = get_today_opennem()

    crawler_set_meta(crawler.name, CrawlStatTypes.version, crawler.version)
    crawler_set_meta(crawler.name, CrawlStatTypes.last_crawled, now_opennem_time)

    cr: Optional[ControllerReturn] = crawler.processor(crawler=crawler, last_crawled=last_crawled, limit=crawler.limit)

    if not cr:
        return None

    # run here
    has_errors = False

    logger.info("Inserted {} of {} records".format(cr.inserted_records, cr.total_records))

    if cr.errors > 0:
        has_errors = True
        logger.error("Crawl controller error for {}: {}".format(crawler.name, cr.error_detail))

    if not has_errors:
        if cr.server_latest:
            crawler_set_meta(crawler.name, CrawlStatTypes.latest_processed, cr.server_latest)
            crawler_set_meta(crawler.name, CrawlStatTypes.server_latest, cr.server_latest)
        else:
            logger.debug("{} has no server_latest return".format(crawler.name))

        logger.info("Set last_processed to {} and server_latest to {}".format(crawler.last_processed, cr.server_latest))


def run_crawl_urls(urls: list[str]) -> None:
    """Crawl a lsit of urls
    @TODO support directories
    """

    for url in urls:
        if url.lower().endswith(".zip") or url.lower().endswith(".csv"):
            try:
                ts = parse_aemo_url(url)
                store_aemo_tableset(ts)
            except Exception as e:
                logger.error(e)


_CRAWLER_SET = load_crawlers()


def run_crawls_all(last_crawled: bool = True) -> None:
    """Runs all the crawl definitions"""
    if not _CRAWLER_SET.crawlers:
        raise Exception("No crawlers found")

    for crawler in _CRAWLER_SET.crawlers:
        try:
            run_crawl(crawler, last_crawled=last_crawled)
        except Exception as e:
            logger.error("Error running crawl {}: {}".format(crawler.name, e))


def run_crawls_by_schedule(schedule: CrawlerSchedule, last_crawled: bool = True) -> None:
    """Gets the crawlers by schedule and runs them"""
    if not _CRAWLER_SET.crawlers:
        raise Exception("No crawlers found")

    for crawler in _CRAWLER_SET.get_crawlers_by_schedule(schedule):
        try:
            run_crawl(crawler, last_crawled=last_crawled)
        except Exception as e:
            logger.error("Error running crawl {}: {}".format(crawler.name, e))


def get_crawler_names() -> List[str]:
    """Get a list of crawler names"""
    crawler_names: List[str] = [i.name for i in _CRAWLER_SET.crawlers]

    return crawler_names


def get_crawl_set() -> CrawlerSet:
    """Access method for crawler set"""
    return _CRAWLER_SET


if __name__ == "__main__":
    urls = [
        "https://nemweb.com.au/Reports/Archive/Dispatch_Reports/PUBLIC_DISPATCH_20220612.zip",
        "https://nemweb.com.au/Reports/Archive/Dispatch_Reports/PUBLIC_DISPATCH_20220613.zip",
        "https://nemweb.com.au/Reports/Archive/Dispatch_Reports/PUBLIC_DISPATCH_20220614.zip",
        "https://nemweb.com.au/Reports/Archive/Dispatch_Reports/PUBLIC_DISPATCH_20220615.zip",
        "https://nemweb.com.au/Reports/Archive/Dispatch_Reports/PUBLIC_DISPATCH_20220616.zip",
        # dispatch is
        "https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/PUBLIC_DISPATCHIS_20220612.zip",
        "https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/PUBLIC_DISPATCHIS_20220613.zip",
        "https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/PUBLIC_DISPATCHIS_20220614.zip",
        "https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/PUBLIC_DISPATCHIS_20220615.zip",
        # trading is
        "https://nemweb.com.au/Reports/Archive/TradingIS_Reports/PUBLIC_TRADINGIS_20220605_20220611.zip",
        # test
        # "https://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_202207011120_0000000366159732.zip"
    ]

    # for url in urls:
    # parse_aemo_url_optimized(url)

    url = "https://nemweb.com.au/Reports/ARCHIVE/TradingIS_Reports/PUBLIC_TRADINGIS_20210620_20210626.zip"
    run_crawl_urls([url])
