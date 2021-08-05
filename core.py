import aiohttp
import feedparser
from loguru import logger
import nonebot
from time import mktime

from .sqlite import RSSDB

rss_db_path = nonebot.get_driver().config.rss_db
proxy = nonebot.get_driver().config.proxy
rss_header = nonebot.get_driver().config.header

rssdb = RSSDB(rss_db_path)


async def init_session_table():
    await rssdb.create_table('rss_all',
                             session='text primary key not null',
                             enable='int not null',
                             interval='int',
                             self_id='int not null')


async def read_sessions():
    rows = await rssdb.select('rss_all')
    return rows


async def read_session_feeds(session: str):
    rows = []
    try:
        rows = await rssdb.select(f'rss_{session}')
    except Exception:
        pass
    return rows


async def set_session_config(session: str, enable: bool, interval: int, self_id: int):
    await rssdb.add_entry('rss_all', session=session, enable=int(enable), interval=interval, self_id=self_id)


async def set_feed_config(session: str, url: str, **changes):
    rows = await rssdb.select(f'rss_{session}', url=url)

    # Supposing it has only one
    _, name, enable, tsp = rows[0]
    if changes.get('name'):
        name = changes['name']
    # Pay attention to the special value of key_enable and key_tsp
    if 'enable' in changes.keys():
        enable = int(changes['enable'])
    if 'tsp' in changes.keys():
        tsp = changes['tsp']

    await rssdb.add_entry(f'rss_{session}', url=url, name=name, enable=enable, tsp=tsp)


async def delete_session_feed(session: str, url: str):
    await rssdb.delete_entry(f'rss_{session}', url=url)


async def delete_session(session: str):
    await rssdb.delete_table(f'rss_{session}')
    await rssdb.delete_entry('rss_all', session=session)


async def add_feed(url: str, session: str, name: str, interval: int, self_id: int):
    await rssdb.add_entry('rss_all',
                          session=session,
                          enable=1,
                          interval=interval,
                          self_id=self_id)

    await rssdb.create_table(f'rss_{session}',
                             url='text primary key not null',
                             name='text',
                             enable='int not null',
                             tsp='float not null')

    await rssdb.add_entry(f'rss_{session}',
                          url=url,
                          name=name,
                          enable=1,
                          tsp=0.0)


async def fetch_feed(url: str):
    async with aiohttp.ClientSession() as client:
        async with client.get(url, proxy=proxy, headers=rss_header) as resp:
            if resp.status == 200:
                result = feedparser.parse(await resp.text(encoding='utf-8'))
                return result
            else:
                raise Exception(f'The feed({url}) to fetch returns status code {resp.status}')


async def get_newer_feed(url: str, last_tsp: float):
    latest_tsp = last_tsp
    unsent_entries = []

    result = await fetch_feed(url)
    entries = result.get('entries')
    for entry in entries:
        # Default to use updated_time
        if entry.get('updated_parsed'):
            time_parsed = entry['updated_parsed']
        else:
            time_parsed = entry['published_parsed']
        tsp = mktime(time_parsed)
        # Update latest tsp
        if tsp > latest_tsp:
            latest_tsp = tsp
        # Add this feed
        if tsp > last_tsp:
            unsent_entries.append(entry)

    return unsent_entries, latest_tsp


async def parse_and_send(entries: list, session: str, session_name: str, self_id: int):
    bot = nonebot.get_driver().bots[str(self_id)]

    session_id, session_type = session.split('_')
    session_id = int(session_id)
    for entry in entries:
        # Parse feed
        title = entry['title']
        link = entry['link']

        msg = f'{session_name}\n{title}\n( {link} )'
        if session_type == 'group':
            await bot.send_msg(group_id=session_id, message=msg, auto_escape=True)
        elif session_type == 'private':
            await bot.send_msg(user_id=session_id, message=msg, auto_escape=True)


async def fetch_and_send(session: str, self_id: int):
    rows = await rssdb.select(f'rss_{session}')
    logger.debug(f'RSS: Scheduled session {session} job running. Fetching the following feeds:')
    for row in rows:
        url, name, enable, tsp = row
        if enable:
            logger.debug('RSS: Fetching ' + url)
            try:
                unsent_entries, latest_tsp = await get_newer_feed(url, tsp)
                if len(unsent_entries) > 0:
                    await rssdb.add_entry(f'rss_{session}', url=url, name=name, enable=enable, tsp=latest_tsp)
                    await parse_and_send(unsent_entries, session, name, self_id)

                logger.debug('RSS: Done.')
            except Exception as e:
                logger.error('RSS: Fetching failed.')
                logger.error(str(e))
