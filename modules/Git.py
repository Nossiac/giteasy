import os
import io
import re
import datetime
import time
import hashlib
import subprocess

import tornado.web
import pygit2
import base64

from modules.Config import *
from modules.Base import BaseHandler
from modules.Database import User, Repo


def pkt_line(line = ""):
	tmp = "{0:04x}{1}".format(len(line)+4, line)
	return tmp


def git_authenticated(func):
	def _wrapper(self, *args, **kwargs):
		m = re.match(r'/([\w\.]+)/([\w\.-]+)/.*', self.request.uri)
		username = m.group(1)
		reponame = m.group(2)
		user = User.get_or_none(User.username == username)
		repo = Repo.get_or_none(Repo.reponame == reponame)

		if not user or not repo:
			self.set_status(404)
			return self.finish()

		if repo.public:
			return func(self, *args, **kwargs)

		tmp = self.request.headers.get("Authorization", None)
		if not tmp:
			self.set_status(401)
			self.set_header("WWW-Authenticate", 'Basic realm="/{}/{}"'.format(username, reponame))
			return self.finish("Authorization header not present!")

		tmp = re.match(r"Basic\s+(.+)", tmp)
		if not tmp:
			self.set_status(401)
			self.set_header("WWW-Authenticate", 'Basic realm="/{}/{}"'.format(username, reponame))
			return self.finish("Authorization secret not present!")

		tmp = tmp.group(1).encode("utf-8")
		tmp = base64.b64decode(tmp)
		visitor_username, visitor_password = tmp.decode("utf-8").split(":", 1)
		visitor = User.get_or_none(User.username == visitor_username)
		if visitor and visitor.uid == repo.owner.uid and visitor.password == hashlib.md5(visitor_password.encode("utf-8")).hexdigest():
			return func(self, *args, **kwargs)

		self.set_status(401)
		self.set_header("WWW-Authenticate", 'Basic realm="{}"'.format(reponame))
		return self.finish()

	return _wrapper



class GitBaseHandler(tornado.web.RequestHandler):
	def handle_request(self, user, repo):
		raise Exception("Not implimented!")

	@git_authenticated
	def authenticate_first(self, user, repo):
		return self.handle_request(user, repo)


	def get_user_repo(self, username, reponame):
		user = User.get_or_none(User.username == username)
		repo = Repo.get_or_none(Repo.reponame == reponame)

		if not user or not repo:
			self.set_status(404)
			self.finish()
			return False, False
		return user, repo

class GitReqInfoHandler(GitBaseHandler):
	def get(self, username, reponame):
		user, repo = self.get_user_repo(username, reponame)
		if not user or not repo: return

		if not repo.public:
			return self.authenticate_first(user, repo)
		else:
			return self.handle_request(user, repo)

	def handle_request(self, user, repo):
		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, repo.reponame))
		except Exception as e:
			print(e)
			self.set_status(500)
			return self.finish()

		service = self.get_argument("service", None)
		if not service:
			self.set_status(400)
			return self.write("We do not support dumb client!")

		self.set_header("Content-Type", "application/x-{}-advertisement".format(service))
		self.set_header("Cache-Control", "no-cache")
		self.set_header('Cache-Control', 'no-cache, max-age=0, must-revalidate')

		try:
			cmd = GitCommand(service)
			cmd.addParam("--advertise-refs")
			cmd.addParam("--stateless-rpc")
			cmd.addParam(os.path.join(REPO_ROOT, user.username, repo.reponame))
			result = cmd.run(self.request.body)
		except GitCommandException as e:
			print(e)
			self.set_status(500)
			self.write("Failed to serve the request, exception happened.")
			return self.finish()

		self.write(pkt_line("# service={}\n".format(service)))
		self.write("0000")
		self.write(result)
		self.finish()

class GitRecvPackHandler(GitBaseHandler):
	def post(self, username, reponame):
		user, repo = self.get_user_repo(username, reponame)
		if not user or not repo: return

		if not repo.public:
			return self.authenticate_first(user, repo)
		else:
			return self.handle_request(user, repo)

	def handle_request(self, user, repo):

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, repo.reponame))
		except Exception as e:
			print(e)
			self.set_status(500)
			return self.finish()


		self.set_header("Content-Type", 'application/x-git-receive-pack-result')
		self.set_header('Pragma', 'no-cache')
		self.set_header('Cache-Control', 'no-cache, max-age=0, must-revalidate')

		try:
			cmd = GitCommand("git-receive-pack")
			cmd.addParam("--stateless-rpc")
			cmd.addParam(os.path.join(REPO_ROOT, user.username, repo.reponame))
			result = cmd.run(self.request.body)
		except GitCommandException as e:
			print(e)
			self.set_status(500)
			self.write("Failed to serve the request, exception happened.")
			return self.finish()

		self.write(result)
		self.finish()

class GitUploadPackHandler(GitBaseHandler):
	def post(self, username, reponame):
		user, repo = self.get_user_repo(username, reponame)
		if not user or not repo: return

		if not repo.public:
			return self.authenticate_first(user, repo)
		else:
			return self.handle_request(user, repo)

	def handle_request(self, user, repo):

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, repo.reponame))
		except Exception as e:
			print(e)
			self.set_status(500)
			return self.finish()

		self.set_header("Content-Type", 'application/x-git-upload-pack-result')
		self.set_header('Pragma', 'no-cache')
		self.set_header('Cache-Control', 'no-cache, max-age=0, must-revalidate')

		try:
			cmd = GitCommand("git-upload-pack")
			cmd.addParam("--stateless-rpc")
			cmd.addParam(os.path.join(REPO_ROOT, user.username, repo.reponame))
			result = cmd.run(self.request.body)
		except GitCommandException as e:
			print(e)
			self.set_status(500)
			self.write("Failed to serve the request, exception happened.")
			return self.finish()
		self.write(result)
		self.finish()





class GitCommandException(Exception):
	pass

class GitCommand():
	def __init__(self, command, *, cwd=None):
		self.command = command
		self.params = []
		self.envars = []
		self.cwd = cwd

	def __repr__(self):
		command = "{envars} {command} {params}".format(
			envars = " ".join(self.envars),
			command = os.path.join(GIT_PATH, self.command),
			params = " ".join((str(param) for param in self.params)))
		return "cwd: {}\ncmd: {}\n".format(self.cwd or ".", command)

	def setDir(self, cwd):
		self.cwd = cwd

	def addParam(self, param):
		self.params.append(param)

	def addEnv(self, envar):
		self.envars.append(envar)

	def run(self, input=None):
		command = "{envars} {command} {params}".format(
			envars = " ".join(self.envars),
			command = os.path.join(GIT_PATH, self.command),
			params = " ".join((str(param) for param in self.params)))
		try:
			start = time.time()
			p = subprocess.Popen(command.split(),
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				close_fds=True,
				cwd = self.cwd)
			out,err = p.communicate(input)
			end = time.time()
			# print("time ", end-start, self)
			return out or err or "internal error"
		except Exception as e:
			raise GitCommandException(str(e))


class EmptyObject():
	pass

class GitCommit():
	def __init__(self):
		self.hex = ""
		self.message = ""
		self.commit_time = 0
		self.author = EmptyObject()
		self.author.name = ""
		self.author.email = ""

class GitLog():
	def __init__(self, repopath, *, ref=None, item="", n=10, reverse=False):
		self.repopath = repopath
		self.ref = ref
		self.item = item
		self.n = n
		cmd = GitCommand("git log")
		cmd.setDir(repopath)
		if reverse:
			cmd.addParam("--reverse")
		if self.n:
			cmd.addParam("-n {}".format(self.n))
		if self.ref:
			cmd.addParam(self.ref)
		if self.item:
			cmd.addParam("-- {}".format(self.item.lstrip("/")))

		cmdret = cmd.run()
		self.log = io.StringIO(cmdret.decode("utf-8"))
		self.buffer = ""

	def __iter__(self):
		return self

	def __next__(self):
		while True:
			line = self.buffer or self.log.readline()
			self.buffer = None

			if not line:
				raise StopIteration()

			m = re.match(r"commit\s+([a-f0-9]{40,})", line)
			if not m:
				continue

			commit = GitCommit()
			commit.hex = m.group(1)

			while True:
				line = self.log.readline()
				assert(line)
				commit_author = re.match(r"Author:\s+([^<]+?)\s<(.+?)>", line)
				if commit_author:
					commit.author.name = commit_author.group(1)
					commit.author.email = commit_author.group(2)
					break

			while True:
				line = self.log.readline()
				assert(line)
				commit_date = re.match(r"Date:\s+(.+)", line)
				if commit_date:
					commit.date = commit_date.group(1)
					commit.commit_time = datetime.datetime.strptime(commit_date.group(1), "%a %b %d %H:%M:%S %Y %z").timestamp()
					break
			# commit message
			line = self.log.readline() # skip empty line
			assert(line.strip() == "")

			commit.message = ""
			while True:
				line = self.log.readline()
				if not line:
					break
				if re.match(r"commit\s+([a-f0-9]{40,})", line):
					self.buffer = line
					break

				commit.message = commit.message + line[4:]

			return commit


