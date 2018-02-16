import os
import re
import uuid
import hashlib

import pygit2
import tornado.web

from modules.Base import BaseHandler, PageInfo
from modules.Database import User, Repo
from modules.Lib import safe_markdown, admin
from modules.Config import *


class UserInfoHandler(BaseHandler):
	def get(self, username=None):

		if not username:
			user = self.current_user
			if not user:
				return self.redirect("/")
		else:
			try:
				user = User.get(User.username == username)
			except User.DoesNotExist as e:
				return self.info("User Not Found!")

		user.intro = safe_markdown(user.intro)
		return self.render("userinfo.htm", user = user)


class UserEditHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self, username=None):
		if username:
			if username != self.current_user.username and not self.current_user.admin():
				return self.info("not authorized")
			user = User.get(User.username == username)
		else:
			user = self.current_user

		# user = DATABASE.getAdministrator()
		return self.render("useredit.htm", user = user, errors=[])

	@tornado.web.authenticated
	def post(self, username = None):
		username = self.get_argument("username").strip()
		nickname = self.get_argument("nickname").strip()
		password = self.get_argument("password").strip()
		password2 = self.get_argument("password2").strip()
		email = self.get_argument("email").strip()
		usertype = self.get_argument("usertype", "administrator").strip()
		intro = self.get_argument("intro").strip()
		uid = self.get_argument("uid").strip()
		errors = []

		# Check user input
		if len(username) < 2 or len(username) > 32:
			errors.append("Username length should be between 2-32 characters.")
		if not re.match(r"[_\w]+", username):
			errors.append("Username should consist of numbers, letters and underscore.")
		if password and password != password2:
			errors.append("Password mismatch.")
		if email and not re.match(r"[\.\w]+@[\.\w]+\w", email):
			errors.append("Invalid Email address.")


		user = User.get_or_none(User.uid == uid)
		if not user:
			errors.append("Wrong username.")

		if errors:
			return self.render("useredit.htm", user=user, errors=errors)

		if user.username != username:
			try:
				os.rename(os.path.join(REPO_ROOT, user.username),
					os.path.join(REPO_ROOT, username))
			except OSError as e:
				return self.info("failed to rename the repo. " + str(e))

		# OK, everything is fine.
		user.username = username
		user.nickname = nickname
		user.email = email
		user.intro = intro
		if password:
			user.password = hashlib.md5(password.encode("utf-8")).hexdigest()

		user.save()
		self.set_current_user(user)
		self.redirect("/{}/!info".format(username))

class UserAddHandler(BaseHandler):
	def get(self):

		if User.select().count() == 0:
			return self.add_first_user()
		else:
			return self.add_user()

	def post(self):

		username = self.get_argument("username").strip()
		nickname = self.get_argument("nickname", username).strip()
		password = self.get_argument("password").strip()
		password2 = self.get_argument("password2").strip()
		email = self.get_argument("email").strip()
		usertype = self.get_argument("usertype", "administrator").strip()
		intro = self.get_argument("intro").strip()

		errors = []

		# Check user input
		if len(username) < 2 or len(username) > 32:
			errors.append("Username length should be between 2-32 characters.")
		if not re.match(r"[_\w]+", username) or len(username) < 2:
			errors.append("Username should consist of numbers, letters and underscore.")
		if not password:
			errors.append("Password empty.")
		elif password != password2:
			errors.append("Password mismatch.")
		if email and not re.match(r"[\.\w]+@[\.\w]+\w", email):
			errors.append("Invalid Email address.")

		if errors:
			return self.render("useredit.htm", errors=errors)

		password = hashlib.md5(password.encode("utf-8")).hexdigest()


		user = User()
		user.uid = uuid.uuid4()
		user.username = username
		user.nickname = nickname
		user.password = password
		user.intro = intro
		user.email = email
		user.locked = True
		if User.select().count() == 0:
			user.role = 99
		else:
			user.role = 10
		user.save(force_insert=True)

		self.redirect("/")

	def add_first_user(self):
		return self.render("useradd.htm", info=["The first user will be the administrator!"])

	@tornado.web.authenticated
	def add_user(self):
		return self.render("useradd.htm", info=[])




class UserListHandler(BaseHandler):
	@admin
	def get(self):
		users = User.select()
		return self.render("userlist.htm", users = users)

class UserHomeHandler(BaseHandler):
	def scan(self, user):
		# add new repos into database
		userpath = os.path.join(REPO_ROOT, user.username)
		if not os.path.isdir(userpath):
			return
		reponames = os.listdir(userpath)
		for reponame in reponames:
			repo = Repo.get_or_none(Repo.reponame == reponame)
			repopath = os.path.join(userpath, reponame)
			if repo: continue
			try:
				pygit2.Repository(repopath)
				repo = Repo()
				repo.rid = uuid.uuid4()
				repo.user_id = user.uid
				repo.reponame = reponame
				repo.intro = "This is an auto import repo."
				repo.public = False
				repo.save(force_insert=True)

			except OSError as e:
				return self.info("failed to rename the repo. " + str(e))
			except Exception as e:
				print(e)
				return self.info("Invalid repository.")
			finally:
				pass


	def get(self, username = None):
		user = None
		if username:
			try:
				user = User.get(User.username == username)
			except User.DoesNotExist as e:
				return self.info("User does not exist!")
		else:
			user = self.current_user
			if user: self.scan(user)

		if not user:
			return self.redirect("/!welcome")


		page = int(self.get_argument("p", 1))
		total = user.repos.count()
		paginator = PageInfo(url = "/?p=", total = total, page = page)

		if user != self.current_user:
			repos = Repo.select().where((Repo.public == True) & (Repo.user_id == user.uid)).paginate(paginator.page_now, paginator.unit).order_by(-Repo.ctime)
		else:
			repos = user.repos.paginate(paginator.page_now, paginator.unit).order_by(-Repo.ctime)

		for repo in repos:
			try:
				repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, repo.reponame))

				if tornado.options.options.perf:
					repo.total_commit = -1
				elif repo.git.is_empty:
					repo.total_commit = 0
				else:
					cmd = GitCommand("git rev-list")
					cmd.addParam("--count")
					cmd.addParam("--all")
					cmd.setDir(os.path.join(REPO_ROOT, user.username, repo.reponame))
					result = cmd.run(self.request.body)
					repo.total_commit = int(result.decode("utf-8"))

			except pygit2.GitError as e:
				print(e)
				repo.git = None
			except GitCommandException as e:
				print(repo.reponame, e)
				repo.total_commit = "unknown"
			except UnicodeDecodeError as e:
				print(e)
				repo.total_commit = "unknown"
			except Exception as e:
				repo.total_commit = "unknown"
				print(repo.reponame, e)
		self.render("userhome.htm", user=user, repos=repos, paginator=paginator)


class LoginHandler(BaseHandler):
	def get(self):
		if self.current_user:
			return self.info("已经登录为："+self.current_user)
		else:
			return self.render("login.htm", next=self.get_argument("next", "/"), errors=[])

	def post(self):
		username = self.get_argument("username", "").strip()
		password = self.get_argument("password", "").strip()
		redirect = self.get_argument("next", "/").strip()

		errors= []
		if not username:
			errors.append("Username empty.")
		if not password:
			errors.append("Password empty.")

		user = None
		try:
			user = User.get(User.username == username)
			if not user.password == hashlib.md5(password.encode("utf-8")).hexdigest():
				errors.append("Wrong password.")
		except User.DoesNotExist as e:
			errors.append("Wrong username.")

		if errors:
			return self.render("login.htm", next=self.get_argument("next", "/"), errors=errors)

		# OK, everything is fine.
		self.set_current_user(user)
		return self.redirect(redirect)


class LogoutHandler(BaseHandler):
	def get(self):
		self.clear_current_user()
		return self.redirect("/")
	def post(self):
		self.clear_current_user()
		return self.redirect("/")


