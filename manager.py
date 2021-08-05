from nonebot.log import logger
from nonebot.adapters.cqhttp.bot import Bot
from nonebot.adapters.cqhttp.event import Event
from nonebot.matcher import Matcher
from nonebot.permission import Permission
from nonebot.adapters.cqhttp.permission import GROUP_MEMBER, GROUP_OWNER, GROUP_ADMIN, PRIVATE_FRIEND
from nonebot.permission import SUPERUSER

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time

from typing import List

from . import core


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
        else:
            raise Exception
        return session_id + '_' + session_type

    async def add(self, paras: List[str]):
        url = paras[0]
        try:
            result = await core.fetch_feed(url)
            # Parse
            title = result['feed']['title']
            # Add it into db
            await core.add_feed(url, self.session, title, 60, self.self_id)
            # Add it into scheduler if not exist
            if self.scheduler.get_job(self.session) is None:
                self.scheduler.add_job(core.fetch_and_send,
                                       id=self.session, name=self.session,
                                       trigger='interval',
                                       seconds=60,
                                       args=(self.session, self.self_id))

            await self.matcher.send('RSS Feed Added!')

            logger.debug(f'RSS: {self.session} has added a feed.')
        except Exception as e:
            logger.error(f'RSS: {self.session} failed to add the feed {url}')
            logger.error(str(e))

            await self.matcher.send('RSS Feed Failed to Add!')

    async def delete(self, paras: List[str]):
        rows = await core.read_session_feeds(self.session)
        if 'all' in paras:
            await core.delete_session(self.session)
            self.scheduler.remove_job(self.session)
        else:
            for target in paras:
                if target.isdigit():
                    target = int(target)
                    url, name, _, _, _ = rows[target]
                    await core.delete_session_feed(self.session, url)
                    await self.matcher.send(f'Delete {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is not a num')
                    continue

            rows = await core.read_session_feeds(self.session)
            if len(rows) == 0:
                await self.delete(['all', ])

    async def info(self, paras=None):
        rows = await core.read_session_feeds(self.session)
        feeds = []
        marker = 0
        for row in rows:
            url, name, enable, tsp, failure = row
            enable = '✔' if enable == 1 else '✖'
            if tsp == 0.0:
                tsp_time = 'Never'
            else:
                tsp_time = time.ctime(tsp)
            feeds.append(f'[id]: {marker}\n[title]: {name}\n[status]: {enable}\n[url]: {url}\n[lastest feed got at]: {tsp_time}\n[failure]: {failure}')
            marker += 1
        msg = '\n\n'.join(feeds) if len(rows) > 0 else 'No feed found'
        await self.matcher.send(msg)

    async def set_interval(self, paras: List[str]):
        if paras[0].isdigit():
            interval = int(paras[0])
            await core.set_session_config(self.session, enable=True, interval=interval, self_id=self.self_id)

            self.scheduler.reschedule_job(self.session, trigger='interval', seconds=interval)
            logger.debug(f'RSS: Session job {self.session} changed the interval to {interval}s')
            await self.matcher.send('Interval changed!')
        else:
            await self.matcher.send('Interval is invalid')

    async def enable(self, paras: List[str]):
        rows = await core.read_session_feeds(self.session)
        if 'all' in paras:
            for row in rows:
                url, _, _, _, _ = row
                await core.set_feed_config(self.session, url, enable=True)
                await self.matcher.send(f'Enable ALL')
        else:
            for target in paras:
                if target.isdigit():
                    target = int(target)
                    url, name, _, _, _ = rows[target]
                    await core.set_feed_config(self.session, url=url, enable=True)
                    await self.matcher.send(f'Enable {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is not a num')
                    continue

    async def disable(self, paras: List[str]):
        rows = await core.read_session_feeds(self.session)
        if 'all' in paras:
            for row in rows:
                url, _, _, _, _ = row
                await core.set_feed_config(self.session, url, enable=False)
                await self.matcher.send(f'Disable ALL')
        else:
            for target in paras:
                if target.isdigit():
                    target = int(target)
                    url, name, _, _, _ = rows[target]
                    await core.set_feed_config(self.session, url, enable=False)
                    await self.matcher.send(f'Disable {name}')
                else:
                    await self.matcher.send(f'Skip for {target} for it is not a num')
                    continue
