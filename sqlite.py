import aiosqlite


class RSSDB(object):
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        self.conn = await aiosqlite.connect(self.db_path)
        return self.conn
    
    async def add_entry(self, table_name: str, **values):
        keys = ','.join(values.keys())
        placeholder = ','.join('?'*len(values.keys()))
        values = tuple(values.values())

        query = f'INSERT OR REPLACE INTO {table_name} ( {keys} ) VALUES ( {placeholder} )'
        await self.conn.execute(query, values)
        await self.conn.commit()

    async def update_entry(self, table_name: str, update_tuple: tuple, conditions: dict):
        cons = ' AND '.join([key+'= ?' for key in conditions.keys()])
        update = f'{update_tuple[0]} = ?'
        values = (update_tuple[1], *conditions.values())

        query = f'UPDATE {table_name} SET {update} WHERE {cons}'

        await self.conn.execute(query, values)
        await self.conn.commit()

    async def create_table(self, table_name: str, **kwargs):
        props = ','.join([key+' '+value for key, value in kwargs.items()])

        query = f'CREATE TABLE IF NOT EXISTS {table_name} ( {props} )'

        await self.conn.execute(query)
        await self.conn.commit()

    async def select(self, table_name: str, **conditions):
        if len(conditions.keys()) == 0:
            query = f'SELECT * FROM {table_name}'
            cursor = await self.conn.execute(query)
        else:
            cons = ' AND '.join([key+'= ?' for key in conditions.keys()])
            query = f'SELECT * FROM {table_name} WHERE {cons}'
            values = tuple(conditions.values())
            cursor = await self.conn.execute(query, values)

        rows = await cursor.fetchall()
        return rows

    async def delete_entry(self, table_name: str, **conditions):
        cons = ' AND '.join([key+'= ?' for key in conditions.keys()])
        query = f'DELETE FROM {table_name} WHERE {cons}'

        values = tuple(conditions.values())

        await self.conn.execute(query, values)
        await self.conn.commit()
    
    async def delete_table(self, table_name: str):
        query = f'DROP TABLE {table_name}'

        await self.conn.execute(query)

    async def close(self):
        await self.conn.close()
