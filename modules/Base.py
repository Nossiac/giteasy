import os

import markdown
import tornado.web

from modules.Database import User, Repo


class BaseHandler(tornado.web.RequestHandler):
	def prepare(self):
		if self.request.uri != "/!init" and User.select().count() == 0:
			return self.redirect("/!init")
		return super().prepare()

	def get_current_user(self):
		username = self.get_secure_cookie("username")
		try:
			return User.get(User.username == username)
		except User.DoesNotExist as e:
			return None

	def set_current_user(self, user):
		self.set_secure_cookie("username", user.username)

	def clear_current_user(self):
		self.clear_cookie("username")

	def admin(self):
		return self.current_user and self.current_user.role == 100

	def render(self, template_name, **kwargs):
		return super().render(template_name,
			logined=self.current_user,
			admin=self.admin(),
			**kwargs)

	def info(self,
		info="Something is wrong ...",
		title="",
		button="OK",
		link="javascript:history.go(-1)"):
		return self.render("info.htm",
			title=title,
			info=info,
			button=button,
			link=link)

	def user_repo_access(self, username, reponame):
		user = User.get_or_none(User.username == username)
		repo = Repo.get_or_none(Repo.reponame == reponame)

		if not user:
			return None, None, "user not available"

		if not repo:
			return None, None, "repo not available"

		if not repo.public:
			if self.current_user != user:
				return None, None, "not authorized"
			if self.current_user.uid != repo.owner.uid:
				return None, None, "not authorized"

		return user, repo, None



class WelcomeHandler(BaseHandler):

	def get(self):

		if os.path.exists("WELCOME.md"):
			filename = "WELCOME.md"
		elif os.path.exists("README.md"):
			filename = "README.md"
		else:
			return self.render("welcome.htm", content="")

		with open(filename, "rb") as fp:
			welcome = fp.read().decode("utf-8", errors="ignore")

		return self.render("welcome.htm",
			content=markdown.markdown(welcome)) # we trust welcome.md



class RemoteCheckHandler(tornado.web.RequestHandler):
	def get(self, action):
		if action == "edituser":
			username = self.get_argument("username", None)
			uid = self.get_argument("uid", None)
			user = User.get_or_none(User.uid == uid) or self.current_user
			if not user:
				return self.finish("false")
			elif user.username == username and user.uid != uid:
				return self.finish("false")
			return self.finish("true")
		elif action == "newuser":
			username = self.get_argument("username", None)
			email = self.get_argument("email", None)
			user = User.get_or_none(User.username == username) or self.current_user
			if user:
				return self.finish("false")
			return self.finish("true")
		elif action == "newrepo": # true means OK
			reponame = self.get_argument("reponame", None)
			username = self.get_argument("username", None)
			user = User.get_or_none(User.username == username) or self.current_user
			if not user:
				return self.finish("false")
			for repo in user.repos:
				if repo.reponame == reponame:
					return self.finish("false")
			return self.finish("true")
		elif action == "editrepo": # true means OK
			rid = self.get_argument("rid", None)
			reponame = self.get_argument("reponame", None)
			username = self.get_argument("username", None)
			user = User.get_or_none(User.username == username)
			if not user:
				return self.finish("false")
			for repo in user.repos:
				if repo.reponame == reponame:
					return self.finish("true" if repo.rid == rid else "false")
			return self.finish("true")
		else:
			return self.finish("false")


class Error404Handler(BaseHandler):
	def get(self):
		self.info("Oops, page not found ...", link="/")


class PageInfo():
	def __init__(self, url, total, page, unit=10):
		assert page >= 1
		self.unit = unit
		self.url = url
		self.page_now = page
		self.page_total = (total+unit-1)//unit
		self.item_now = (page-1)*unit
		self.item_total = total
		self.page_left = page - 4 if page > 4 else 1
		self.page_right = page + 4 if self.page_total - page > 4 else self.page_total

