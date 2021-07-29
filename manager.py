from nonebot.log import logger
from nonebot.adapters.cqhttp.bot import Bot
from nonebot.adapters.cqhttp.event import Event
from nonebot.matcher import Matcher
from nonebot.permission import Permission
from nonebot.adapters.cqhttp.permission import GROUP_MEMBER, GROUP_OWNER, GROUP_ADMIN, PRIVATE_FRIEND
from nonebot.permission import SUPERUSER

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time

from .core import *

def allowed_user():
    return Permission(GROUP_MEMBER, GROUP_OWNER, GROUP_ADMIN, PRIVATE_FRIEND, SUPERUSER)


class RSSManager(object):
    def __init__(self, matcher: Matcher, bot: Bot, event: Event, scheduler: AsyncIOScheduler) -> None:
        self.matcher = matcher
        self.bot = bot
        self.event = event
        self.scheduler = scheduler
        self.session = self.generate_session_string()
        self.self_id = event.self_id

    def generate_session_string(self):
        event_dict = self.event.dict()
        session_type = event_dict['message_type']
        if session_type == 'private':
            session_id = self.event.get_user_id()
        elif session_type == 'group':
            session_id = str(event_dict['group_id'])
        return session_id + '_' + session_type

    async def add(self, paras: list):
        url = paras[0]
        try:
            result = await fetch_feed(url)
            title = result['feed']['title']
            await add_feed(url, self.session, title, 60, self.self_id)
            await self.matcher.send('RSS Feed Added!')

            logger.debug(f'RSS: {self.session} has added a feed.')
        except Exception as e:
            logger.error(f'RSS: {self.session} failed to add the feed {url}')
            await self.matcher.send('RSS Feed Failed to Add!')


    async def delete(self, paras: list):
        rows = await read_session_feeds(self.session)
        if 'all' in paras:
            await delete_session(self.session)
            self.scheduler.remove_job(self.session)
        else:
            for target in paras:
                if isinstance(eval(target), int):
                    target = int(target)
                    url, name, _, _ = rows[target]
                    await delete_session_feed(self.session, url)
                    await self.matcher.send(f'Delete {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is invalid')
                    continue

            rows = await read_session_feeds(self.session)
            if len(rows) == 0:
                await self.delete(['all',])

    async def info(self, paras: list=None):
        rows = await read_session_feeds(self.session)
        feeds = []
        marker = 0
        for row in rows:
            url, name, enable, tsp = row
            enable = '✔' if enable == 1 else '✖'
            if tsp == 0.0:
                tsp_time = 'Never'
            else:
                tsp_time = time.ctime(tsp)
            feeds.append(f'[id]: {marker}\n[title]: {name}\n[status]: {enable}\n[url]: {url}\n[lastest feed got at]: {tsp_time}')
            marker += 1
        msg = '\n\n'.join(feeds) if len(rows) > 0 else 'No feed found'
        await self.matcher.send(msg)

    async def set_interval(self, paras: list):
        interval = int(paras[0])
        await set_session_config(self.session, enable=True, interval=interval, self_id=self.self_id)

        # Modify interval isn't allowed
        self.scheduler.remove_job(self.session)
        self.scheduler.add_job(fetch_and_send, trigger='interval', id=self.session, name=self.session, seconds=interval, args=(self.session, self.self_id))
        logger.debug(f'RSS: Session job {self.session} changed the interval to {interval}s')
        await self.matcher.send('Interval changed!')

    async def enable(self, paras: list):
        rows = await read_session_feeds(self.session)
        if 'all' in paras:
            for row in rows:
                url, _, _, _ =row
                await set_feed_config(self.session, url, enable=True)
                await self.matcher.send(f'Enable ALL')
        else:
            for target in paras:
                if isinstance(eval(target), int):
                        target = int(target)
                        url, name, _, _ = rows[target]
                        await set_feed_config(self.session, url=url, enable=True)
                        await self.matcher.send(f'Enable {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is invalid')
                    continue

    async def disable(self, paras: list):
        rows = await read_session_feeds(self.session)
        if 'all' in paras:
            for row in rows:
                url, _, _, _ =row
                await set_feed_config(self.session, url, enable=False)
                await self.matcher.send(f'Disable ALL')
        else:
            for target in paras:
                if isinstance(eval(target), int):
                        target = int(target)
                        url, name, _, _ = rows[target]
                        await set_feed_config(self.session, url, enable=False)
                        await self.matcher.send(f'Disable {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is invalid')
                    continue
