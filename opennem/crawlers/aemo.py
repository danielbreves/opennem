"""AEMO Crawlers


"""
import logging
from typing import List, Optional

from opennem.controllers.nem import ControllerReturn, store_aemo_tableset
from opennem.core.crawlers.schema import CrawlerDefinition
from opennem.core.parsers.aemo.mms import parse_aemo_urls
from opennem.core.parsers.dirlisting import DirlistingEntry, get_dirlisting

logger = logging.getLogger("opennem.crawler.aemo")


def run_aemo_mms_crawl(
    crawler: CrawlerDefinition, last_crawled: bool = True, limit: bool = False
) -> Optional[ControllerReturn]:
    """Runs the AEMO MMS crawlers"""
    if not crawler.url:
        raise Exception("Require a URL to run AEMO MMS crawlers")

    dirlisting = get_dirlisting(crawler.url, timezone="Australia/Brisbane")

    if crawler.filename_filter:
        dirlisting.apply_filter(crawler.filename_filter)

    logger.debug(
        "Got {} entries, {} files and {} directories".format(
            dirlisting.count, dirlisting.file_count, dirlisting.directory_count
        )
    )

    entries_to_fetch: List[DirlistingEntry] = []

    if crawler.latest and crawler.server_latest:
        entries_to_fetch = dirlisting.get_files_modified_since(crawler.server_latest)
        logger.debug("Getting last crawled since {}".format(crawler.server_latest))

    elif crawler.limit:
        entries_to_fetch = dirlisting.get_most_recent_files(limit=crawler.limit)
        logger.debug("Getting limit {}".format(crawler.limit))

    else:
        entries_to_fetch = dirlisting.get_files()

    if not entries_to_fetch:
        logger.info("Nothing to do")
        return None

    logger.info("Fetching {} entries".format(len(entries_to_fetch)))

    ts = parse_aemo_urls([i.link for i in entries_to_fetch])

    controller_returns = store_aemo_tableset(ts)
    controller_returns.last_modified = max([i.modified_date for i in entries_to_fetch])  # type: ignore

    return controller_returns
