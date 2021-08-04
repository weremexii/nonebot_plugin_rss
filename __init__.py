import os
import nonebot
from nonebot import on_command
from nonebot.log import logger
from nonebot.adapters.cqhttp.bot import Bot
from nonebot.adapters.cqhttp.event import Event

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core import *
from .manager import RSSManager, allowed_user

if not os.path.exists('data'):
    os.mkdir('data')

rss = on_command('rss', permission=allowed_user())
rss_db_path = nonebot.get_driver().config.rss_db
scheduler = AsyncIOScheduler()

@nonebot.get_driver().on_startup
async def start():
    await rssdb.init()
    await init_session_table()
    rows = await read_sessions()
    for row in rows:
        session, enable, interval, self_id = row
        if enable:
            scheduler.add_job(fetch_and_send, id=session, name=session, trigger='interval', seconds=interval, args=(session, self_id))

    scheduler.start()
    logger.info('RSS: APScheduler start.')
    logger.debug('RSS: APScheduler-loaded session jobs are as below:')
    for job in scheduler.get_jobs():
        logger.debug(str(job))

@nonebot.get_driver().on_shutdown
async def close():
    await rssdb.close()

@rss.handle()
async def _(bot: Bot, event: Event):
    cmds = event.get_plaintext().strip().split()
    cmd, paras = cmds[0], cmds[1:]
    manager = RSSManager(rss, bot, event, scheduler)
    cmd_dict = {
        'add': manager.add,
        'info': manager.info,
        'del': manager.delete,
        'interval': manager.set_interval,
        'enable': manager.enable,
        'disable': manager.disable
    }
    if cmd_dict.get(cmd):
        await cmd_dict[cmd](paras)
    else:
        await rss.send('Command is invalid')
