import os
import uuid
import concurrent
import shutil

import pygit2
import tornado.web

from modules.Base import BaseHandler
from modules.Database import User, Repo
from modules.Config import *
from modules.Git import *
from modules.Lib import safe_markdown, admin


class RepoImportHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", None)
		if action == "progress":
			self.get_progress()
		else:
			self.render("repoimport.htm")

	def get_progress(self):
		pass

	@tornado.web.authenticated
	def post(self):

		user = self.current_user
		assert user

		userpath = os.path.join(REPO_ROOT, user.username)
		os.makedirs(userpath, exist_ok=True)
		assert os.path.exists(userpath)

		repourl = self.get_argument("repo.url")
		reponame = self.get_argument("repo.reponame", "")
		private = self.get_argument("repo.private", False)
		intro = self.get_argument("repo.intro", "")

		if not reponame:
			reponame = repourl.split("/")[-1]
			if reponame.endswith(".git"):
				reponame = reponame[:-4]

		if os.path.exists(os.path.join(userpath, reponame)):
			return self.info("reponame already exists!")


		def import_repo(remote_path, local_path):
			try:
				repo = pygit2.clone_repository(remote_path, local_path, bare=True)
				return repo
			except Exception as e:
				print(e)
				return str(e)

		repo = Repo()
		repo.rid = uuid.uuid4()
		repo.user_id = user.uid
		repo.reponame = reponame
		repo.intro = intro or "Cloned from "+repourl
		repo.public = (not private)
		repo.save(force_insert=True)

		task = concurrent.futures.ThreadPoolExecutor(1)
		future = task.submit(import_repo, repourl, os.path.join(userpath, reponame))
		ASYNC_TASK[str(repo.rid)] = future

		self.redirect("/{}/{}".format(user.username, repo.reponame))


class RepoDeleteHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self, username, reponame):
		user = User.get_or_none(User.username == username)
		if not user:
			return self.info("user not exists")

		repo = Repo.get_or_none(Repo.reponame == reponame)
		if not repo:
			return self.info("repo not exists")

		if username != self.current_user.username:
			return self.info("not authorized")

		repopath = os.path.join(REPO_ROOT, user.username, repo.reponame)


		try:
			Repo.delete().where(Repo.rid == repo.rid).execute()
		except Exception as e:
			return self.info("failed to delete repo from database!"+str(e))

		try:
			if os.path.exists(repopath):
				shutil.rmtree(repopath, ignore_errors=False, onerror=None)
		except OSError as e:
			return self.info("failed to delete repo from filesystem!"+str(e))

		return self.redirect("/")

class RepoEditHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self, username, reponame):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		self.render("repoedit.htm", repo = repo)

	@tornado.web.authenticated
	def post(self, username, reponame):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		newreponame = self.get_argument("repo.reponame", None)
		intro = self.get_argument("repo.intro", "")
		private = self.get_argument("repo.private", False)

		if not newreponame:
			return self.info("reponame cannot be empty")

		if Repo.get_or_none((Repo.reponame == newreponame) &(Repo.rid != repo.rid)):
			return self.info("reponame already exists")

		try:
			os.rename(os.path.join(REPO_ROOT, user.username, repo.reponame),
				os.path.join(REPO_ROOT, user.username, newreponame))
		except OSError as e:
			return self.info("failed to rename the repo. " + str(e))

		repo.reponame = newreponame
		repo.intro = intro
		repo.public = (not bool(private))
		repo.save()

		return self.redirect("/{}/{}".format(user.username, repo.reponame))


class RepoHooksHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self, username, reponame):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		if repo.owner.uid != self.current_user.uid:
			return self.info("not authorized")

		hook_id = self.get_argument("hid", None)
		action = self.get_argument("action", None)

		if hook_id:
			hook = RepoHook.get_or_none(RepoHook.hid == int(hook_id))
			if not hook:
				return self.info("invalid hook id")
			if action == "disable":
				hook.disabled = True
				hook.save()
				return self.redirect("/{}/{}/edit/hooks".format(user.username, repo.reponame))
			elif action == "enable":
				hook.disabled = False
				hook.save()
				return self.redirect("/{}/{}/edit/hooks".format(user.username, repo.reponame))
			elif action == "delete":
				RepoHook.delete().where(RepoHook.hid == hook_id).execute()
				return self.redirect("/{}/{}/edit/hooks".format(user.username, repo.reponame))
			else:
				pass
		else:
			hook = RepoHook()

		self.render("repohook.htm", repo = repo, current = hook)

	@tornado.web.authenticated
	def post(self, username, reponame):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		if repo.owner.uid != self.current_user.uid:
			return self.info("not authorized")

		url = self.get_argument("hook.url")
		credential = self.get_argument("hook.credential", "")
		method = self.get_argument("hook.method", "GET")

		hook_id = self.get_argument("hid", None)
		if hook_id:
			hook = RepoHook.get_or_none(RepoHook.hid == hook_id)
		else:
			hook = RepoHook()

		hook.url = url
		hook.credential = credential
		hook.post = (method == "GET")
		hook.repo_id = repo.rid

		hook.save()

		self.redirect("/{}/{}/edit/hooks".format(user.username, repo.reponame))


class RepoAddHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("repoadd.htm")

	@tornado.web.authenticated
	def post(self):
		user = self.current_user
		reponame = self.get_argument("repo.reponame").strip()
		private = self.get_argument("repo.private", False)
		intro = self.get_argument("repo.intro", "")
		repopath = os.path.join(REPO_ROOT, user.username, reponame)
		if os.path.exists(repopath):
			return self.write("Name already taken.")

		try:
			cmd = GitCommand("git")
			cmd.addParam("init")
			cmd.addParam("--bare")
			cmd.addParam(repopath)
			cmd.run()
		except GitCommandException as e:
			print(e)
			shutil.rmtree(repopath, ignore_errors=True)
			return self.info("Failed to create repo, exception happened!")

		repo = Repo()
		repo.rid = uuid.uuid4()
		repo.user_id = user.uid
		repo.reponame = reponame
		repo.intro = intro
		repo.public = (not private)
		ret = repo.save(force_insert=True)

		self.redirect("/{}/{}".format(repo.owner.username, repo.reponame))




class RepoBlobHandler(BaseHandler):
	def get(self, username, reponame, ref, path):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, reponame))
		except Exception as e:
			print(e)
			return self.info("Invalid repository.")

		path = "/"+path.strip("/") if path else ""
		if not ref: ref = repo.git.head.shorthand

		for a in repo.git.listall_references():
			if ref == a.split("/")[-1]:
				ref = a
				break

		repo.url = os.path.join("http://", self.request.host, username, reponame)
		repo.path = path
		repo.ref = ref
		repo.ref_short = ref.split("/")[-1]

		target_node = repo.git.revparse_single(ref)
		if hasattr(target_node, "tree"):
			target_node = target_node.tree
		elif isinstance(target_node, pygit2.Tag):
			target_node = target_node.get_object().tree
		else:
			return self.info("Failed to get tree of type:", target_node)


		if path:
			for p in path.split("/"):
				if not p: continue
				target_node = target_node[p]
				if target_node.type == "tree":
					target_node = repo.git.get(target_node.id)

		repo.filename = target_node.name
		repo.items = []
		blob = repo.git.get(target_node.id)
		try:
			repo.filedata = blob.data.decode("utf-8")
			if repo.filename.endswith(".md"):
				repo.filedata = safe_markdown(repo.filedata)
			else:
				repo.filedata = tornado.escape.xhtml_escape(repo.filedata)
		except UnicodeDecodeError as e:
			repo.filedata = "binary data"

		self.render("repotree.htm", repo=repo, lastcommit=None)


class RepoHistoryHandler(BaseHandler):
	def get(self, username, reponame, ref = None, path = None):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, reponame))
		except Exception as e:
			print(e)
			return self.info("Invalid repository.")

		path = "/"+path.strip("/") if path else ""
		if not ref: ref = repo.git.head.shorthand

		for a in repo.git.listall_references():
			if ref == a.split("/")[-1]:
				ref = a
				break

		repo.url = os.path.join("http://", self.request.host, username, reponame)
		repo.path = path
		repo.ref = ref
		repo.ref_short = ref.split("/")[-1]

		history = list(GitLog(os.path.join(REPO_ROOT, user.username, repo.reponame),
			ref = repo.ref_short, item = path.lstrip("/")))

		self.render("history.htm", repo = repo, history = history)



class RepoTreeHandler(BaseHandler):
	def get(self, username, reponame, ref = None, path = None):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		if str(repo.rid) in ASYNC_TASK:
			if ASYNC_TASK[str(repo.rid)].done():
				result = ASYNC_TASK[str(repo.rid)].result()
				if not isinstance(result, pygit2.Repository):
					print("import failure", result)
				del ASYNC_TASK[str(repo.rid)]
			else:
				return self.info("repo is importing")

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, repo.reponame))
		except Exception as e:
			print(e)
			return self.info("Invalid repository.")

		if repo.git.is_empty:
			return self.render("repoempty.htm", repo = repo, host=self.request.host)

		path = "/"+path.strip("/") if path else ""
		if not ref: ref = repo.git.head.shorthand

		for a in repo.git.listall_references():
			if ref == a.split("/")[-1]:
				ref = a
				break

		repo.url = os.path.join("http://", self.request.host, username, reponame)
		repo.path = path
		repo.ref = ref
		repo.ref_short = ref.split("/")[-1]

		target_tree = repo.git.revparse_single(ref)
		if hasattr(target_tree, "tree"):
			target_tree = target_tree.tree
		elif isinstance(target_tree, pygit2.Tag):
			target_tree = target_tree.get_object().tree
		else:
			return self.info("Failed to get tree of type:", target_tree)

		if path:
			for p in path.split("/"):
				if not p: continue
				target_tree = repo.git.get(target_tree[p].oid)


		lastcommit = next(GitLog(os.path.join(REPO_ROOT, user.username, repo.reponame),
			ref=repo.ref_short, item=path, n=1), None)

		repo.items = []
		repo.filename = None
		repo.filedata = None

		if target_tree:
			for node in repo.git.get(target_tree.oid):
				x = repo.git.get(node.id)

				if tornado.options.options.perf:
					commit = None
				else:
					commit = next(GitLog(os.path.join(REPO_ROOT, user.username, repo.reponame),
						ref=repo.ref_short, item=os.path.join(path, node.name), n=1))

				repo.items.append({
					"name": node.name,
					"type": str(node.type),
					"lastcommit": commit,
				})

				if node.name.upper() == "README.MD":
					repo.filename = node.name
					blob = repo.git.get(node.id)
					repo.filedata = safe_markdown(blob.data.decode("utf-8"))

		self.render("repotree.htm", repo=repo, lastcommit=lastcommit)



class RepoCommitHandler(BaseHandler):
	def get(self, username, reponame, oid):
		user, repo, error = self.user_repo_access(username, reponame)
		if error:
			return self.info(error)

		try:
			repo.git = pygit2.Repository(os.path.join(REPO_ROOT, user.username, reponame))
		except Exception as e:
			print(e)
			return self.info("Invalid repository.")

		if repo.git.is_empty:
			return self.render("repoempty.htm", repo = repo, host=self.request.host)

		repo.url = os.path.join("http://", self.request.host, username, reponame)
		repo.path = ""
		repo.ref = ""
		repo.ref_short = ""

		self.render("commit.htm", repo = repo, commit = repo.git.get(oid))
