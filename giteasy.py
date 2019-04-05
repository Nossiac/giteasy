# -*- coding: utf-8 -*-

import os
import io
import time
import datetime
import re
import sys

import tornado.httpserver
import tornado.web
import tornado.ioloop
import tornado.options
import tornado.escape

from modules.UIModules import *
from modules.Base import *
from modules.User import *
from modules.Repo import *
from modules.Lib import *
from modules.Git import *

tornado.options.define("port", default=8088, help="http port", type=int)
tornado.options.define("repo", default="repo", help="repo root path", type=str)
tornado.options.define("perf", default=True, help="High performance instead of full feature", type=bool)
tornado.options.define("daemon", default=0, help="run as a daemon", type=int)


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
