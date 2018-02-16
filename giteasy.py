# -*- coding: utf-8 -*-

import os
import io
import time
import datetime
import re
import sys
import random
import struct
import shlex
import select
import subprocess
import sqlite3
import hashlib
import shutil
import uuid
import concurrent

import requests
import markdown
import pygit2

import tornado.httpserver
import tornado.web
import tornado.ioloop
import tornado.options
import tornado.escape

# for safer markdown
import bleach
from bleach_whitelist import markdown_tags, markdown_attrs

# import database.database
from modules.Database import User, Repo, RepoHook, RepoCollaborator
from modules.Base import *
from modules.User import *
from modules.Repo import *
from modules.Lib import *
from modules.Git import *

tornado.options.define("port", default=8088, help="http port", type=int)
tornado.options.define("repo", default="repo", help="repo root path", type=str)
tornado.options.define("perf", default=True, help="High performance instead of full feature", type=bool)
tornado.options.define("daemon", default=0, help="run as a daemon", type=int)



def owner(func):
	def _decorator(username, reponame):
		def _wrapper(self, *args, **kwargs):
			user = self.current_user
			if not user:
				return self.redirect("/!login?next="+self.request.uri)
			else:
				if user.admin():
					return func(self, *args, **kwargs)
				else:
					return self.info("未授权!")

		user = User.get_or_none(User.username == username)
		repo = Repo.get_or_none(Repo.reponame == reponame)

		if not user or not repo or repo.owner.uid != user.uid:
			return self.info("未授权!") 
		return _wrapper
	return _decorator

class Paginator(tornado.web.UIModule):
	def render(self, paginator):
		return self.render_string(
			"uimodule/paginator.htm", paginator = paginator)


class RepoMenu(tornado.web.UIModule):
	def render(self, repo, logined = None):
		return self.render_string(
			"uimodule/repomenu.htm", repo = repo, logined = logined)



if __name__ == "__main__":
	tornado.options.parse_command_line()

	if tornado.options.options.daemon:
		daemonize(".giteasy.log")

	if not os.path.exists(REPO_ROOT):
		os.makedirs(REPO_ROOT)

	app = tornado.web.Application(
		handlers=[
			(r'/', UserHomeHandler),
			(r'/!welcome', WelcomeHandler),
			(r'/!init', UserAddHandler),
			(r'/!useradd', UserAddHandler),
			(r'/!login', LoginHandler),
			(r'/!logout', LogoutHandler),
			(r'/!repoadd', RepoAddHandler),
			(r'/!repoimport', RepoImportHandler),
			(r'/!check/(\w+)', RemoteCheckHandler),
			(r'/!users', UserListHandler),
			(r'/([\w\.]+)', UserHomeHandler),
			(r'/([\w\.]+)/!edit', UserEditHandler),
			(r'/([\w\.]+)/!info', UserInfoHandler),
			(r'/([\w\.]+)/([\w\.-]+)/info/refs', GitReqInfoHandler),
			(r'/([\w\.]+)/([\w\.-]+)/git-receive-pack', GitRecvPackHandler),
			(r'/([\w\.]+)/([\w\.-]+)/git-upload-pack', GitUploadPackHandler),
			(r'/([\w\.]+)/([\w\.-]+)/commit/(\w+)', RepoCommitHandler),
			(r'/([\w\.]+)/([\w\.-]+)/history/([^/]+)/(.*)', RepoHistoryHandler),
			(r'/([\w\.]+)/([\w\.-]+)/history/([^/]+)', RepoHistoryHandler),
			(r'/([\w\.]+)/([\w\.-]+)/history/*', RepoHistoryHandler),
			(r'/([\w\.]+)/([\w\.-]+)/blob/([^/]+)/(.*)', RepoBlobHandler),
			(r'/([\w\.]+)/([\w\.-]+)/edit/basic', RepoEditHandler),
			(r'/([\w\.]+)/([\w\.-]+)/edit/hooks', RepoHooksHandler),
			(r'/([\w\.]+)/([\w\.-]+)/delete', RepoDeleteHandler),
			(r'/([\w\.]+)/([\w\.-]+)/tree/([^/]+)', RepoTreeHandler),
			(r'/([\w\.]+)/([\w\.-]+)/tree/([^/]+)/(.*)', RepoTreeHandler),
			(r'/([\w\.]+)/([\w\.-]+)', RepoTreeHandler),

			(r'.*', Error404Handler),
		],
		debug = True,
		template_path = os.path.join(os.path.dirname(__file__), "templates"),
		static_path = os.path.join(os.path.dirname(__file__), "static"),
		login_url = "/login",
		cookie_secret = cookie_secret,
		ui_modules = {"Paginator":Paginator, "RepoMenu":RepoMenu},
	)
	http_server = tornado.httpserver.HTTPServer(app, decompress_request=True)
	http_server.listen(tornado.options.options.port)
	tornado.ioloop.IOLoop.instance().start()
