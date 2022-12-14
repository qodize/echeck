import psycopg2
import dataclasses
import datetime as dt
from typing import List

pg_database = 'hakaton'
pg_username = 'postgres'
pg_password = 'postgres'
pg_host = '127.0.0.1'


def postgres_wrapper(func):
    def wrap(*args, **kwargs):
        with psycopg2.connect(dbname=pg_database,
                              user=pg_username,
                              password=pg_password,
                              host=pg_host) as conn:
            with conn.cursor() as cursor:
                return func(cursor, *args, **kwargs)

    return wrap


@dataclasses.dataclass
class User:
    id: int
    phone: str
    username: str


@dataclasses.dataclass
class Emotion:
    id: int
    value: int
    description: str
    user_id: int
    title: str
    ts: dt.datetime


@dataclasses.dataclass
class Group:
    id: int
    owner_id: int


@postgres_wrapper
def ping(cursor):
    try:
        cursor.execute("SELECT * FROM users")
        cursor.fetchall()
        return True
    except Exception as e:
        return False


class AlreadyExists(Exception):
    pass


class Users:

    @staticmethod
    @postgres_wrapper
    def get_emotions_values(cursor, user_id):
        cursor.execute(f"""SELECT e.value FROM emotions as e WHERE user_id = {user_id} ORDER BY e.ts ASC""")
        res = cursor.fetchall()
        return [r[0] for r in res]

    @staticmethod
    @postgres_wrapper
    def get(cursor, phone: str) -> User or None:
        cursor.execute(f"SELECT pk_id, phone, username FROM users WHERE phone = '{phone}'")
        res = cursor.fetchall()
        if res:
            user = User(*res[0])
            cursor.execute(f"SELECT e.value FROM emotions as e WHERE user_id = {user.id} ORDER BY e.ts ASC")
            user.all_emotions = [e[0] for e in cursor.fetchall()]
            return user
        else:
            None

    @staticmethod
    @postgres_wrapper
    def create(cursor, phone: str, username: str) -> User:
        try:
            cursor.execute(f"INSERT INTO users VALUES (DEFAULT, '{phone}', '{username}') RETURNING id")
        except psycopg2.Error:
            raise AlreadyExists()
        id_ = cursor.fetchall()[0][0]
        return User(id_, phone, username)

    @staticmethod
    @postgres_wrapper
    def get_user_groups(cursor, phone: str) -> List[Group]:
        cursor.execute(f"""
        SELECT pk_id FROM users WHERE phone like '{phone}'
        """)
        res = cursor.fetchall()
        if not res:
            cursor.execute(f"""INSERT INTO users VALUES (DEFAULT, {phone}, 'unknown') RETURNING pk_id""")
            res = cursor.fetchall()
        user_id = res[0][0]
        cursor.execute(f"""
        SELECT groups.pk_id, owner_id
        FROM user_to_group JOIN groups ON group_id = groups.pk_id
        WHERE user_id = {user_id}
        """)
        return [Group(*group_args) for group_args in cursor.fetchall()]


class Groups:
    @staticmethod
    @postgres_wrapper
    def get_group_users(cursor, group_id: int) -> List[User]:
        cursor.execute(f"""
        SELECT users.pk_id, users.phone, users.username
        FROM user_to_group JOIN users ON user_id = users.pk_id
        WHERE group_id = {group_id}
        """)
        return [User(*user_args) for user_args in cursor.fetchall()]

    @staticmethod
    @postgres_wrapper
    def create(cursor, owner_id: int) -> Group:
        cursor.execute(f"""
        INSERT INTO groups
        VALUES (DEFAULT, {owner_id})
        RETURNING pk_id, owner_id
        """)
        group_args = cursor.fetchall()[0]
        cursor.execute(f"""
        INSERT INTO user_to_group VALUES ({group_args[1]}, {group_args[0]})
        """)
        return Group(*group_args)

    @staticmethod
    @postgres_wrapper
    def get_group_emotions(cursor, group_id) -> List[Emotion]:
        cursor.execute(f"""
        SELECT e.pk_id, e.user_id, e.value, e.title, e.description, e.ts
        FROM emotions as e
        JOIN user_to_group as utg ON e.user_id = utg.user_id
        WHERE utg.group_id = {group_id}
        ORDER BY e.ts DESC
        """)
        res = cursor.fetchall()
        return [Emotion(*e_args) for e_args in res]


class Emotions:
    @staticmethod
    @postgres_wrapper
    def create_emotion(cursor, phone, value, title='', description='') -> Emotion:
        cursor.execute(f"""
                SELECT pk_id FROM users WHERE phone like '{phone}'
                """)
        user_id = cursor.fetchall()[0][0]
        cursor.execute(f"""
        INSERT INTO emotions as e
        VALUES (DEFAULT, {value}, '{description}', {user_id}, '{title}', '{dt.datetime.now()}')
        RETURNING e.pk_id, e.value, e.description, e.user_id, e.title, e.ts""")
        e_args = cursor.fetchall()[0]
        return Emotion(*e_args)

    @staticmethod
    @postgres_wrapper
    def get_all_emotions(cursor) -> List[Emotion]:
        cursor.execute(f"""
        SELECT * FROM emotions
        """)
        res = cursor.fetchall()
        return [Emotion(*e_args) for e_args in res]

    @staticmethod
    @postgres_wrapper
    def get_last_emotion_value(cursor, user_id: int) -> int:
        cursor.execute(f"""
        SELECT e.value
        FROM emotions as e
        WHERE e.user_id = {user_id}
        ORDER BY e.ts DESC
        LIMIT 1
        """)
        res = cursor.fetchall()
        if res:
            return res[0][0]
        else:
            return 0
