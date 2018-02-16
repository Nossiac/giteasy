import sys
import uuid
import datetime
import platform
import sqlite3

from peewee import *
from playhouse.shortcuts import model_to_dict, dict_to_model


db = SqliteDatabase('giteasy.db')

class BaseModel(Model):
	class Meta:
		database = db

	@classmethod
	def random(cls):
		if isinstance(db, SqliteDatabase):
			random_query = cls.select().order_by(fn.random())
		elif isinstance(db, MySQLDatabase):
			random_query = cls.select().order_by(fn.Rand())
		return random_query.get()

	def __iter__(self):
		for k in vars(self.__class__).keys():
			if isinstance(getattr(self.__class__,k), Field):
				t = getattr(self.__class__,k)
				v = getattr(self, k)
				if isinstance(t, ForeignKeyField):
					continue
				if isinstance(t, DateTimeField):
					yield (k, str(v))
				else:
					yield (k, v)

	def asdict(self):
		return model_to_dict(self)



class User(BaseModel):
	uid = CharField(default=uuid.uuid4, primary_key=True)
	email = CharField(default="")
	username = CharField(default="", unique=True)
	nickname = CharField(default="")
	password = CharField(default="")
	ctime = DateTimeField(default=datetime.datetime.now)
	intro = CharField(default="")
	role = SmallIntegerField(default=0)
	locked = BooleanField(default=False)
	banned = BooleanField(default=False)
	class Meta:
		table_name = "user"

	def admin(self):
		return self.role >= 90

class Repo(BaseModel):
	rid = CharField(default=uuid.uuid4, primary_key=True)
	reponame = CharField(unique=True)
	intro = CharField(default="")
	public = BooleanField(default=False)
	ctime = DateTimeField(default=datetime.datetime.now)
	owner = ForeignKeyField(User, column_name="user_id", backref="repos")

	class Meta:
		table_name = "repo"

class RepoCollaborator(BaseModel):
	# cid = PrimaryKeyField()
	repo_id = ForeignKeyField(Repo, backref="collaborators")
	user_id = ForeignKeyField(User)
	class Meta:
		table_name = "repo_collaborator"
		primary_key = False


class RepoHook(BaseModel):
	hid = PrimaryKeyField()
	repo_id = ForeignKeyField(Repo, backref="hooks")
	url = CharField()
	method = CharField(default="GET")
	credential = CharField(default="")
	disabled = BooleanField(default=False)
	# by_tag = BooleanField()
	# by_push = BooleanField()
	class Meta:
		table_name = "repo_hook"
		primary_key = False


if not db.table_exists("user"):
	try:
		db.create_tables([User, Repo, RepoHook, RepoCollaborator])
	except Exception as e:
		raise Exception

